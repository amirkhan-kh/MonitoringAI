from __future__ import annotations

import json
import logging
import os
from typing import Any

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import (
    Analysis,
    Brand,
    FacebookAnalysis,
    FacebookMention,
    InstagramAnalysis,
    InstagramMention,
    Mention,
    YouTubeAnalysis,
    YouTubeMention,
)
from app.services.realtime import publish_realtime_event
from app.services.matching import collect_ignored_terms, normalize_text

logger = logging.getLogger("gemini-analysis")


class ProviderRetryableError(Exception):
    """The model provider returned a transient/config error.

    The mention is intentionally NOT persisted as a permanent error so it gets
    re-analyzed once the provider recovers (rate limit lifted, billing enabled,
    credentials fixed). ``config_error`` marks issues that need operator action
    (billing/permission/credentials) so the worker can back off harder instead of
    hammering the API every few seconds.
    """

    def __init__(self, original: Exception, *, config_error: bool = False) -> None:
        super().__init__(str(original))
        self.original = original
        self.config_error = config_error


ANALYSIS_SYSTEM_INSTRUCTION = """
Siz brend reputatsiyasini monitoring qiluvchi tajribali tahlilchi AI'siz.
Javobni faqat berilgan JSON sxema bo'yicha qaytaring. Markdown yoki qo'shimcha matn ishlatmang.
Sentiment score -1.0 dan 1.0 gacha: -1 juda salbiy, 0 neytral, 1 juda ijobiy.
Risk score 0.0 dan 1.0 gacha: 1 juda xavfli reputatsion inqiroz signali.
Spam score 0.0 dan 1.0 gacha.
Mavzular qisqa va biznesga foydali bo'lsin.
Uzbek, Russian, English va aralash (kirill/lotin) matnlarni to'g'ri tushuning; kinoya va yashirin salbiylikni ilg'ang.

MUHIM — engagement signallarini tahlilga qo'shing (faqat post matni emas):
- Telegram: reaksiyalar (like/emoji), discussion commentlari, views va forwards. Ko'p ko'rilgan yoki ko'p tarqalgan salbiy post riskni oshiradi. Salbiy kommentlar ko'p bo'lsa sentiment/risk shunga mos og'irlashadi.
- YouTube: like_count, comment_count, reply_count, view_count. Ko'p layk = ijobiy signal; salbiy izohli va ko'p ko'rilgan video riskni oshiradi. (YouTube Data API dislike sonini bermaydi — uni taxmin qilmang.)
- Engagement yuqori bo'lsa ishonch (va risk/sentiment kuchi) ortadi; engagement past yoki yo'q bo'lsa ehtiyotkor baho bering.

Agar faqat post matni bo'lsa, xulosani faqat mavjud kontentga tayangan holda bering va yo'q ma'lumotni to'qib chiqarmang.
Har doim to'liq JSON qaytaring: barcha maydonlar to'ldirilsin.
"""

# BLOCK_ONLY_HIGH: monitoring oqimida shikoyat, tanqid, salbiy va inqiroz matnlari qonuniy —
# ular tahlil qilinishi kerak. Qattiqroq filtr ularni bloklab, bo'sh javob qaytarardi va
# aynan eng muhim (salbiy) mention'lar tahlilsiz qolardi.
SAFETY_SETTINGS = [
    types.SafetySetting(category=category, threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH)
    for category in (
        types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
    )
]

# Server-tomon majburlanadigan JSON sxema — model faqat shu shaklda javob bera oladi.
# Bu markdown/erkin matn bilan buzilishni yo'qotadi va enum qiymatlarni kafolatlaydi
# (parse xatolari va noto'g'ri toifalar keskin kamayadi → aniqlik oshadi).
ANALYSIS_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "language": {"type": "STRING", "enum": ["uz", "ru", "en", "mixed", "unknown"]},
        "sentiment": {"type": "STRING", "enum": ["positive", "negative", "neutral", "mixed"]},
        "sentiment_score": {"type": "NUMBER"},
        "topics": {"type": "ARRAY", "items": {"type": "STRING"}},
        "risk_level": {"type": "STRING", "enum": ["low", "medium", "high", "critical"]},
        "risk_score": {"type": "NUMBER"},
        "spam_score": {"type": "NUMBER"},
        "summary": {"type": "STRING"},
        "suggested_action": {"type": "STRING"},
    },
    "required": [
        "language", "sentiment", "sentiment_score", "topics",
        "risk_level", "risk_score", "spam_score", "summary", "suggested_action",
    ],
}

# Stage-1 relevance gate. A cheap flash-lite yes/no filter: does this text actually
# concern the brand (name / alias / product / monitored keyword), or is it unrelated
# noise (general sport, politics, ads, other brands)? Only relevant mentions go on to
# the expensive Stage-2 deep analysis — this is the main token saver on high-volume,
# all-messages sources where most comments have nothing to do with the brand.
GATE_SYSTEM_INSTRUCTION = """Sen brend monitoringi uchun tezkor RELEVANTLIK filtrisan.
Berilgan matn (post yoki komment) shu brendga aloqadormi yoki yo'qmi — faqat shuni hal qil.
Aloqador (true) = brend nomi, aliaslari, mahsulot/xizmatlari yoki kuzatiladigan kalit
so'zlaridan biri matnda tilga olingan, YOKI matn mazmunan aynan shu brend haqida.
Aloqador emas (false) = brend umuman eslatilmagan; umumiy mavzu (sport, siyosat, boshqa
brend, reklama, shaxsiy suhbat, ma'nosiz matn).
Chuqur tahlil QILMA — bu shunchaki ha/yo'q filtri. Faqat JSON qaytar."""

GATE_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "brand_relevant": {"type": "BOOLEAN"},
        "matched_terms": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["brand_relevant"],
}

PROFILE_SUGGESTION_SYSTEM_INSTRUCTION = """
Siz senior brand strategist va social listening arxitektorisiz.
Berilgan brand nomi, ierarxik yo'nalish, faoliyat turi, biznes modeli, auditoriya va hududdan kelib chiqib
monitoring profilini juda aniq va amaliy to'ldiring. Natija grammatik to'g'ri va faqat JSON bo'lsin.
Aliaslarda real yozilish/transliteratsiya variantlari bo'lsin. Keywordlar brand, mahsulot, kampaniya, muammo va
xarid niyatini qamrasin. Risk va ijobiy signallar aynan tanlangan sohaga mos bo'lsin. Ignore-termlar brandga
aloqasiz shovqin va omonimlarni chetlatishga xizmat qilsin. Mavjud faktlarni saqlang, lekin placeholder yoki
to'qib chiqarilgan fakt, URL, sertifikat va kompaniya nomlarini yozmang. Raqobatchi nomi ishonchli bo'lmasa,
aniq profil/toifa tavsifini bering. Har bir ro'yxat takrorlarsiz va monitoring uchun foydali bo'lsin.
"""

PROFILE_LANGUAGE_INSTRUCTIONS = {
    "uz": "Barcha tavsif, auditoriya, izoh va umumiy keywordlarni tabiiy, grammatik to'g'ri o'zbek tilida yozing.",
    "ru": "Все описания, аудитории, примечания и общие ключевые слова пишите на естественном, грамматически правильном русском языке.",
    "en": "Write every description, audience, note, and generic keyword in natural, grammatically correct English.",
}

PROFILE_SUGGESTION_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "description": {"type": "STRING"},
        "audience": {"type": "STRING"},
        "aliases": {"type": "ARRAY", "items": {"type": "STRING"}},
        "keywords": {"type": "ARRAY", "items": {"type": "STRING"}},
        "products": {"type": "ARRAY", "items": {"type": "STRING"}},
        "competitors": {"type": "ARRAY", "items": {"type": "STRING"}},
        "risk_keywords": {"type": "ARRAY", "items": {"type": "STRING"}},
        "positive_keywords": {"type": "ARRAY", "items": {"type": "STRING"}},
        "ignore_terms": {"type": "ARRAY", "items": {"type": "STRING"}},
        "monitor_notes": {"type": "STRING"},
    },
    "required": [
        "description", "audience", "aliases", "keywords", "products", "competitors",
        "risk_keywords", "positive_keywords", "ignore_terms", "monitor_notes",
    ],
}


def create_gemini_client(settings: Settings) -> genai.Client:
    if settings.gemini_use_vertex:
        if not settings.google_cloud_project:
            raise RuntimeError("GOOGLE_CLOUD_PROJECT is required when GEMINI_USE_VERTEX=true")
        # pydantic loads .env into Settings only; google-auth resolves ADC from the
        # process environment, so bridge the credentials path across explicitly
        # (harmless under docker where env_file already exports it).
        if settings.google_application_credentials:
            os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", settings.google_application_credentials)
        return genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )
    # Gemini Developer API (AI Studio) — authenticates with a plain API key,
    # no service account / billing project required.
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is required when GEMINI_USE_VERTEX=false")
    return genai.Client(api_key=settings.gemini_api_key)


def suggest_brand_profile(settings: Settings, client: genai.Client, context: dict[str, Any]) -> dict[str, Any]:
    language = str(context.get("language") or "uz").lower()
    if language not in PROFILE_LANGUAGE_INSTRUCTIONS:
        language = "uz"
    context = {**context, "language": language, "output_language": language}
    prompt = json.dumps(context, ensure_ascii=False)
    language_instruction = PROFILE_LANGUAGE_INSTRUCTIONS[language]
    response = client.models.generate_content(
        model=settings.gemini_analysis_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=f"{PROFILE_SUGGESTION_SYSTEM_INSTRUCTION}\n{language_instruction}\nBrand nomi, proper noun va alias/transliteratsiyalarni buzib tarjima qilmang.",
            response_mime_type="application/json",
            response_schema=PROFILE_SUGGESTION_SCHEMA,
            temperature=0.25,
            safety_settings=SAFETY_SETTINGS,
            thinking_config=types.ThinkingConfig(
                thinking_budget=settings.gemini_profile_thinking_budget,
                include_thoughts=False,
            ),
        ),
    )
    payload = parse_json_response(_text_or_raise(response))
    payload["model_name"] = settings.gemini_analysis_model
    return payload


def _text_or_raise(response: Any) -> str:
    """Return response text, or raise when a safety filter blocked it (no text at all).

    Raising keeps a blocked/empty reply visible and retryable instead of silently
    persisting an empty analysis. With BLOCK_ONLY_HIGH this is rare, but a blocked
    reply is exactly the kind of high-signal (harsh) mention we must not drop.
    """
    text = (getattr(response, "text", None) or "").strip()
    if text:
        return text
    candidates = getattr(response, "candidates", None) or []
    finish_reason = getattr(candidates[0], "finish_reason", None) if candidates else None
    block_reason = getattr(getattr(response, "prompt_feedback", None), "block_reason", None)
    raise ProviderEmptyResponseError(
        f"model returned no text (finish_reason={finish_reason}, block_reason={block_reason})"
    )


class ProviderEmptyResponseError(Exception):
    """The model returned an empty/blocked response (no usable text)."""


def _generate_payload(client: genai.Client, model: str, prompt: str, *, deep: bool) -> dict[str, Any]:
    """One structured generate_content call against ``model``.

    ``deep=False`` (primary/flash): thinking disabled — fast, cheap, deterministic,
    and guaranteed non-empty structured output for the high-volume path.
    ``deep=True`` (pro): default thinking left on for richer reasoning on hard cases.
    """
    config = types.GenerateContentConfig(
        system_instruction=ANALYSIS_SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=ANALYSIS_RESPONSE_SCHEMA,
        temperature=0.2,
        safety_settings=SAFETY_SETTINGS,
        thinking_config=None if deep else types.ThinkingConfig(thinking_budget=0),
    )
    response = client.models.generate_content(model=model, contents=prompt, config=config)
    return parse_json_response(_text_or_raise(response))


def _should_escalate(settings: Settings, payload: dict[str, Any]) -> bool:
    """High-risk mentions get a second, deeper (Pro) pass for accuracy."""
    if not settings.gemini_escalate_high_risk:
        return False
    risk_level = (payload.get("risk_level") or "").strip().lower()
    if risk_level in {"high", "critical"}:
        return True
    score = to_float(payload.get("risk_score"))
    return score is not None and score >= settings.gemini_escalation_risk_threshold


def _is_content_block(exc: Exception) -> bool:
    """Only a blocked/empty content reply is worth an immediate Pro retry — Pro may
    accept content the primary refused.

    Rate-limit (429) is deliberately NOT here: on Vertex it is a per-minute RPM blip
    that clears in seconds, so cascading every rate-limited mention to the slow,
    expensive Pro model would waste money on low-risk noise. 429 is instead treated as
    transient (see ``classify_provider_error``) so the worker backs off briefly and
    retries the SAME cheap model, keeping coverage without the cost blowup."""
    return isinstance(exc, ProviderEmptyResponseError)


def analyze_payload(settings: Settings, client: genai.Client, prompt: str) -> tuple[dict[str, Any], str, str]:
    """Run the tiered model strategy for one prompt.

    Returns ``(payload, model_used, tier)`` where tier is one of
    ``primary`` | ``fallback`` (flash quota/limit exhausted) | ``escalated`` (high-risk deep pass).
    Raises on failures the caller should classify/retry so no mention is silently dropped.
    """
    primary = settings.gemini_model
    deep = settings.gemini_escalation_model
    has_distinct_deep = bool(deep) and deep != primary

    try:
        payload = _generate_payload(client, primary, prompt, deep=False)
    except Exception as exc:
        # A blocked/empty reply -> fall back to Pro (it may accept what the primary
        # refused) so the mention is still analyzed. Rate limits are NOT handled here
        # (see _is_content_block): they propagate as transient and retry on the cheap model.
        if has_distinct_deep and settings.gemini_quota_fallback and _is_content_block(exc):
            payload = _generate_payload(client, deep, prompt, deep=True)
            payload["_analysis_tier"] = "fallback"
            return payload, deep, "fallback"
        raise

    if has_distinct_deep and _should_escalate(settings, payload):
        try:
            deep_payload = _generate_payload(client, deep, prompt, deep=True)
            deep_payload["_analysis_tier"] = "escalated"
            deep_payload["_primary_risk_score"] = payload.get("risk_score")
            return deep_payload, deep, "escalated"
        except Exception:
            # Deep pass failed transiently — keep the solid Flash result rather than
            # losing the analysis entirely. The risk signal is already captured.
            logger.warning("escalation pass failed; keeping primary result", exc_info=True)
    return payload, primary, "primary"


def _provider(settings: Settings) -> str:
    return "vertex-gemini" if settings.gemini_use_vertex else "gemini"


def build_brand_profile(brand: Brand | None) -> dict[str, Any]:
    if not brand:
        return {}
    return {
        "name": brand.name,
        "description": brand.description,
        "industry": brand.industry,
        "primary_category": brand.primary_category,
        "category_path": brand.category_path,
        "website": brand.website,
        "language": brand.language,
        "aliases": brand.aliases,
        "keywords": brand.keywords,
        "products": brand.products,
        "competitors": brand.competitors,
        "ignore_terms": brand.ignore_terms,
        "audience": brand.audience,
        "region": brand.region,
        "monitoring_goals": brand.monitoring_goals,
        "risk_keywords": brand.risk_keywords,
        "positive_keywords": brand.positive_keywords,
        "monitor_notes": brand.monitor_notes,
        "profile_config": brand.profile_config,
    }


def _gate_relevant(settings: Settings, client: genai.Client, brand: Brand | None, text: str) -> tuple[bool, list[str]]:
    """Stage-1 cheap flash-lite check: is this text about the brand? Returns
    (relevant, matched_terms). Raises on provider errors so the caller can retry."""
    profile = build_brand_profile(brand)
    prompt = json.dumps({"brand": profile, "text": (text or "")[:2000]}, ensure_ascii=False)
    response = client.models.generate_content(
        model=settings.gemini_gate_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=GATE_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=GATE_RESPONSE_SCHEMA,
            temperature=0.0,
            safety_settings=SAFETY_SETTINGS,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    payload = parse_json_response(_text_or_raise(response))
    return bool(payload.get("brand_relevant")), payload.get("matched_terms") or []


SCREENED_OUT_PAYLOAD = {
    "brand_relevant": False,
    "screened": True,
    "risk_level": "low",
    "risk_score": 0.0,
    "summary": "Brendga aloqador kalit so'z topilmadi — chuqur tahlil qilinmadi (gate).",
}


def screen_and_analyze(
    settings: Settings, client: genai.Client, brand: Brand | None, mention: Any, text: str, prompt: str
) -> tuple[dict[str, Any], str, str]:
    """Gate-then-analyze. Returns ``(payload, model_used, tier)``.

    tier: ``screened`` (Stage-1 said not brand-relevant → no deep analysis, tokens
    saved) | ``analyzed`` (relevant → Stage-2 deep model) | else the ``analyze_payload``
    tiers when the gate is disabled.
    """
    ignored_terms = collect_ignored_terms(brand, normalize_text(text)) if brand else []
    if ignored_terms:
        return {
            **SCREENED_OUT_PAYLOAD,
            "summary": "Brand profilidagi ignore-term topildi — chuqur tahlil qilinmadi.",
            "matched_terms": [],
            "ignored_terms": ignored_terms,
            "screening_reason": "ignore_term",
            "_analysis_tier": "screened",
        }, settings.gemini_gate_model, "screened"

    if not settings.gemini_relevance_gate:
        return analyze_payload(settings, client, prompt)

    # Mentions already matched to a brand keyword at ingestion are relevant by
    # definition — skip the gate call entirely (extra token saving).
    matched_at_ingestion = [t for t in (getattr(mention, "brand_match_terms", None) or []) if t]
    if matched_at_ingestion:
        relevant, matched = True, matched_at_ingestion
        screening_reason = "deterministic_term_match"
    elif not (text or "").strip():
        # No text to match a keyword against -> not deep-analyzed.
        return {
            **SCREENED_OUT_PAYLOAD,
            "matched_terms": [],
            "screening_reason": "empty_text",
            "_analysis_tier": "screened",
        }, settings.gemini_gate_model, "screened"
    else:
        relevant, matched = _gate_relevant(settings, client, brand, text)
        screening_reason = "ai_relevance_gate"

    if not relevant:
        return {
            **SCREENED_OUT_PAYLOAD,
            "matched_terms": matched,
            "screening_reason": screening_reason,
            "_analysis_tier": "screened",
        }, settings.gemini_gate_model, "screened"

    # Stage 2: relevant -> deep analysis with the Pro model.
    payload = _generate_payload(client, settings.gemini_analysis_model, prompt, deep=True)
    payload["brand_relevant"] = True
    payload["matched_terms"] = matched
    payload["screening_reason"] = screening_reason
    payload["_analysis_tier"] = "deep"
    return payload, settings.gemini_analysis_model, "analyzed"


def analyze_mention(session: Session, settings: Settings, client: genai.Client, mention: Mention) -> Analysis:
    brand = session.get(Brand, mention.brand_id) if mention.brand_id else None
    text = mention.text or mention.caption or mention.normalized_text or ""
    prompt = build_prompt(mention, brand)
    try:
        payload, model_used, tier = screen_and_analyze(settings, client, brand, mention, text, prompt)
        analysis = Analysis(
            mention_id=mention.id,
            model_provider=_provider(settings),
            model_name=model_used,
            language=payload.get("language"),
            sentiment=payload.get("sentiment"),
            sentiment_score=to_float(payload.get("sentiment_score")),
            topics=payload.get("topics") or [],
            risk_level=payload.get("risk_level"),
            risk_score=to_float(payload.get("risk_score")),
            spam_score=to_float(payload.get("spam_score")),
            summary=payload.get("summary"),
            suggested_action=payload.get("suggested_action"),
            raw=payload,
        )
    except Exception as exc:
        retry, config_error = classify_provider_error(exc)
        if retry:
            session.rollback()
            raise ProviderRetryableError(exc, config_error=config_error) from exc
        analysis = Analysis(
            mention_id=mention.id,
            model_provider=_provider(settings),
            model_name=settings.gemini_gate_model,
            error=str(exc),
        )
    session.add(analysis)
    session.commit()
    session.refresh(analysis)
    publish_realtime_event(
        session,
        "analysis_updated",
        {
            "id": analysis.id,
            "mention_id": analysis.mention_id,
            "brand_id": mention.brand_id,
            "risk_level": analysis.risk_level,
            "sentiment": analysis.sentiment,
            "created_at": analysis.created_at,
        },
    )
    return analysis


def analyze_youtube_mention(
    session: Session,
    settings: Settings,
    client: genai.Client,
    mention: YouTubeMention,
) -> YouTubeAnalysis:
    brand = session.get(Brand, mention.brand_id) if mention.brand_id else None
    text = mention.text or mention.title or mention.normalized_text or ""
    prompt = build_youtube_prompt(mention, brand)
    try:
        payload, model_used, tier = screen_and_analyze(settings, client, brand, mention, text, prompt)
        analysis = YouTubeAnalysis(
            youtube_mention_id=mention.id,
            model_provider=_provider(settings),
            model_name=model_used,
            language=payload.get("language"),
            sentiment=payload.get("sentiment"),
            sentiment_score=to_float(payload.get("sentiment_score")),
            topics=payload.get("topics") or [],
            risk_level=payload.get("risk_level"),
            risk_score=to_float(payload.get("risk_score")),
            spam_score=to_float(payload.get("spam_score")),
            summary=payload.get("summary"),
            suggested_action=payload.get("suggested_action"),
            raw=payload,
        )
    except Exception as exc:
        retry, config_error = classify_provider_error(exc)
        if retry:
            session.rollback()
            raise ProviderRetryableError(exc, config_error=config_error) from exc
        analysis = YouTubeAnalysis(
            youtube_mention_id=mention.id,
            model_provider=_provider(settings),
            model_name=settings.gemini_gate_model,
            error=str(exc),
        )
    session.add(analysis)
    session.commit()
    session.refresh(analysis)
    publish_realtime_event(
        session,
        "analysis_updated",
        {
            "id": analysis.id,
            "youtube_mention_id": analysis.youtube_mention_id,
            "brand_id": mention.brand_id,
            "platform": "youtube",
            "risk_level": analysis.risk_level,
            "sentiment": analysis.sentiment,
            "created_at": analysis.created_at,
        },
    )
    return analysis


def analyze_instagram_mention(
    session: Session,
    settings: Settings,
    client: genai.Client,
    mention: InstagramMention,
) -> InstagramAnalysis:
    brand = session.get(Brand, mention.brand_id) if mention.brand_id else None
    text = mention.text or mention.normalized_text or ""
    prompt = build_instagram_prompt(mention, brand)
    try:
        payload, model_used, tier = screen_and_analyze(settings, client, brand, mention, text, prompt)
        analysis = InstagramAnalysis(
            instagram_mention_id=mention.id,
            model_provider=_provider(settings),
            model_name=model_used,
            language=payload.get("language"),
            sentiment=payload.get("sentiment"),
            sentiment_score=to_float(payload.get("sentiment_score")),
            topics=payload.get("topics") or [],
            risk_level=payload.get("risk_level"),
            risk_score=to_float(payload.get("risk_score")),
            spam_score=to_float(payload.get("spam_score")),
            summary=payload.get("summary"),
            suggested_action=payload.get("suggested_action"),
            raw=payload,
        )
    except Exception as exc:
        retry, config_error = classify_provider_error(exc)
        if retry:
            session.rollback()
            raise ProviderRetryableError(exc, config_error=config_error) from exc
        analysis = InstagramAnalysis(
            instagram_mention_id=mention.id,
            model_provider=_provider(settings),
            model_name=settings.gemini_gate_model,
            error=str(exc),
        )
    session.add(analysis)
    session.commit()
    session.refresh(analysis)
    publish_realtime_event(
        session,
        "analysis_updated",
        {
            "id": analysis.id,
            "instagram_mention_id": analysis.instagram_mention_id,
            "brand_id": mention.brand_id,
            "platform": "instagram",
            "risk_level": analysis.risk_level,
            "sentiment": analysis.sentiment,
            "created_at": analysis.created_at,
        },
    )
    return analysis


def build_instagram_prompt(mention: InstagramMention, brand: Brand | None) -> str:
    text = mention.text or mention.normalized_text
    brand_profile = build_brand_profile(brand)
    data = {
        "task": "instagram_mention_analysis",
        "brand_profile": brand_profile,
        "source": {
            "platform": "instagram",
            "item_type": mention.item_type,
            "author_username": mention.author_username,
            "media_id": mention.media_id,
            "media_type": mention.media_type,
            "permalink": mention.permalink,
        },
        "engagement_context": {
            "like_count": mention.like_count,
            "comment_count": mention.comment_count,
            "reply_count": mention.reply_count,
            "is_direct_mention": mention.item_type == "mention",
        },
        "brand_match_terms": mention.brand_match_terms,
        "mention_text": text,
        "required_json_schema": {
            "language": "uz|ru|en|mixed|unknown",
            "sentiment": "positive|negative|neutral|mixed",
            "sentiment_score": "float -1..1",
            "topics": ["short topic names"],
            "risk_level": "low|medium|high|critical",
            "risk_score": "float 0..1",
            "spam_score": "float 0..1",
            "summary": "1-2 sentences in Uzbek",
            "suggested_action": "what the brand should do next in Uzbek",
        },
    }
    return json.dumps(data, ensure_ascii=False)


def analyze_facebook_mention(
    session: Session,
    settings: Settings,
    client: genai.Client,
    mention: FacebookMention,
) -> FacebookAnalysis:
    brand = session.get(Brand, mention.brand_id) if mention.brand_id else None
    text = mention.text or mention.normalized_text or ""
    prompt = build_facebook_prompt(mention, brand)
    try:
        payload, model_used, tier = screen_and_analyze(settings, client, brand, mention, text, prompt)
        analysis = FacebookAnalysis(
            facebook_mention_id=mention.id,
            model_provider=_provider(settings),
            model_name=model_used,
            language=payload.get("language"),
            sentiment=payload.get("sentiment"),
            sentiment_score=to_float(payload.get("sentiment_score")),
            topics=payload.get("topics") or [],
            risk_level=payload.get("risk_level"),
            risk_score=to_float(payload.get("risk_score")),
            spam_score=to_float(payload.get("spam_score")),
            summary=payload.get("summary"),
            suggested_action=payload.get("suggested_action"),
            raw=payload,
        )
    except Exception as exc:
        retry, config_error = classify_provider_error(exc)
        if retry:
            session.rollback()
            raise ProviderRetryableError(exc, config_error=config_error) from exc
        analysis = FacebookAnalysis(
            facebook_mention_id=mention.id,
            model_provider=_provider(settings),
            model_name=settings.gemini_gate_model,
            error=str(exc),
        )
    session.add(analysis)
    session.commit()
    session.refresh(analysis)
    publish_realtime_event(
        session,
        "analysis_updated",
        {
            "id": analysis.id,
            "facebook_mention_id": analysis.facebook_mention_id,
            "brand_id": mention.brand_id,
            "platform": "facebook",
            "risk_level": analysis.risk_level,
            "sentiment": analysis.sentiment,
            "created_at": analysis.created_at,
        },
    )
    return analysis


def build_facebook_prompt(mention: FacebookMention, brand: Brand | None) -> str:
    text = mention.text or mention.normalized_text
    brand_profile = build_brand_profile(brand)
    data = {
        "task": "facebook_comment_analysis",
        "brand_profile": brand_profile,
        "source": {
            "platform": "facebook",
            "item_type": mention.item_type,
            "author_name": mention.author_name,
            "post_id": mention.post_id,
            "permalink": mention.permalink,
        },
        "engagement_context": {
            "like_count": mention.like_count,
            "reply_count": mention.reply_count,
            "is_reply": mention.item_type == "reply",
        },
        "brand_match_terms": mention.brand_match_terms,
        "mention_text": text,
        "required_json_schema": {
            "language": "uz|ru|en|mixed|unknown",
            "sentiment": "positive|negative|neutral|mixed",
            "sentiment_score": "float -1..1",
            "topics": ["short topic names"],
            "risk_level": "low|medium|high|critical",
            "risk_score": "float 0..1",
            "spam_score": "float 0..1",
            "summary": "1-2 sentences in Uzbek",
            "suggested_action": "what the brand should do next in Uzbek",
        },
    }
    return json.dumps(data, ensure_ascii=False)


def build_prompt(mention: Mention, brand: Brand | None) -> str:
    text = mention.text or mention.caption or mention.normalized_text
    raw_message = (mention.raw or {}).get("message") or {}
    brand_profile = build_brand_profile(brand)
    data = {
        "task": "telegram_mention_analysis",
        "brand_profile": brand_profile,
        "source": {
            "platform": mention.platform,
            "source_type": mention.source_type,
            "chat_title": mention.chat_title,
            "chat_description": mention.chat_description,
            "author_username": mention.author_username,
            "permalink": mention.permalink,
        },
        "engagement_context": build_engagement_context(raw_message),
        "mention_text": text,
        "required_json_schema": {
            "language": "uz|ru|en|mixed|unknown",
            "sentiment": "positive|negative|neutral|mixed",
            "sentiment_score": "float -1..1",
            "topics": ["short topic names"],
            "risk_level": "low|medium|high|critical",
            "risk_score": "float 0..1",
            "spam_score": "float 0..1",
            "summary": "1-2 sentences in Uzbek",
            "suggested_action": "what the brand should do next in Uzbek",
        },
    }
    return json.dumps(data, ensure_ascii=False)


def build_youtube_prompt(mention: YouTubeMention, brand: Brand | None) -> str:
    text = mention.text or mention.title or mention.normalized_text
    brand_profile = build_brand_profile(brand)
    data = {
        "task": "youtube_mention_analysis",
        "brand_profile": brand_profile,
        "source": {
            "platform": "youtube",
            "item_type": mention.item_type,
            "channel_title": mention.channel_title,
            "author_name": mention.author_name,
            "video_id": mention.video_id,
            "permalink": mention.permalink,
        },
        "engagement_context": {
            "like_count": mention.like_count,
            "reply_count": mention.reply_count,
            "view_count": mention.view_count,
            "comment_count": mention.comment_count,
            "public_dislike_count": None,
            "public_dislike_note": "YouTube public Data API dislike sonini bermaydi.",
        },
        "brand_match_terms": mention.brand_match_terms,
        "mention_text": text,
        "required_json_schema": {
            "language": "uz|ru|en|mixed|unknown",
            "sentiment": "positive|negative|neutral|mixed",
            "sentiment_score": "float -1..1",
            "topics": ["short topic names"],
            "risk_level": "low|medium|high|critical",
            "risk_score": "float 0..1",
            "spam_score": "float 0..1",
            "summary": "1-2 sentences in Uzbek",
            "suggested_action": "what the brand should do next in Uzbek",
        },
    }
    return json.dumps(data, ensure_ascii=False)


def build_engagement_context(raw_message: dict[str, Any]) -> dict[str, Any]:
    return {
        "views": raw_message.get("views"),
        "forwards": raw_message.get("forwards"),
        "reply_count": (raw_message.get("replies") or {}).get("count") if raw_message.get("replies") else None,
        "comments_enabled": (raw_message.get("replies") or {}).get("comments") if raw_message.get("replies") else None,
        "reactions": (raw_message.get("reactions") or {}).get("results") if raw_message.get("reactions") else [],
    }


def parse_json_response(value: str) -> dict[str, Any]:
    cleaned = value.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    return json.loads(cleaned)


# Operator-action errors: retrying every few seconds is pointless and just burns
# quota + floods logs. Still retryable (not persisted) so mentions get analyzed
# once the operator fixes the project, but the worker backs off hard.
CONFIG_ERROR_MARKERS = (
    "billing",
    "billing_disabled",
    "permission_denied",
    "permission",
    "forbidden",
    "unauthenticated",
    "api key",
    "api_key",
    "api not enabled",
    "has not been used",
    "is disabled",
    "consumer",
)

# Genuinely transient errors: short backoff and retry. Network / DNS failures are
# included deliberately — a container that briefly can't resolve the Vertex host must
# NOT persist a permanent error row (that would silently freeze the mention as
# "analyzed" forever and drop it from AI coverage).
TRANSIENT_ERROR_MARKERS = (
    "429",
    "500",
    "502",
    "503",
    "504",
    "quota",
    "resource_exhausted",
    "rate limit",
    "deadline",
    "timeout",
    "temporarily unavailable",
    "unavailable",
    "overloaded",
    "connection",
    # DNS / socket / transport failures (resolve blips, resets, dropped responses)
    "name or service not known",
    "temporary failure in name resolution",
    "name resolution",
    "nodename nor servname",
    "getaddrinfo",
    "network is unreachable",
    "connection reset",
    "server disconnected",
    "disconnected without",
    "eof occurred",
    "errno -2",
    "errno -3",
)


def classify_provider_error(exc: Exception) -> tuple[bool, bool]:
    """Return (retryable, is_config_error) for a provider exception.

    retryable=True means "don't persist as a permanent error, retry later".
    is_config_error=True means the operator must act (billing/permission/creds),
    so the caller should back off harder.
    """
    # A blocked/empty content reply is deterministic — retrying yields the same block.
    # Persist it (counted, not stuck) so the worker moves on instead of looping.
    if isinstance(exc, ProviderEmptyResponseError):
        return False, False

    # Prefer the structured HTTP status when the SDK exposes one (google-genai
    # ClientError/ServerError set ``.code``): far more reliable than string matching.
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        if code in {401, 403}:
            return True, True  # billing / permission / credentials — retry rarely
        if code in {408, 429, 500, 502, 503, 504}:
            return True, False  # transient — retry soon
        return False, False  # 400/404 etc. — persist; retrying won't help

    message = str(exc).lower()
    # Transient takes precedence: a 429 RESOURCE_EXHAUSTED body literally says
    # "check your plan and billing details", but it is a rate/quota limit that
    # clears on its own — it must NOT be treated as an operator/config error.
    if any(marker in message for marker in TRANSIENT_ERROR_MARKERS):
        return True, False
    config_error = any(marker in message for marker in CONFIG_ERROR_MARKERS) or "403" in message
    return config_error, config_error


def should_retry_provider_error(exc: Exception) -> bool:
    return classify_provider_error(exc)[0]


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
