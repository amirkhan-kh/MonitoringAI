from __future__ import annotations

import json
from typing import Any

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Analysis, Brand, Mention, YouTubeAnalysis, YouTubeMention
from app.services.realtime import publish_realtime_event


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
Siz social media monitoring uchun tahlilchi AI'siz.
Javobni faqat JSON qilib qaytaring. Markdown ishlatmang.
Sentiment score -1.0 dan 1.0 gacha: -1 juda salbiy, 0 neytral, 1 juda ijobiy.
Risk score 0.0 dan 1.0 gacha: 1 juda xavfli reputatsion inqiroz signali.
Spam score 0.0 dan 1.0 gacha.
Mavzular qisqa va biznesga foydali bo'lsin.
Uzbek, Russian, English va aralash matnlarni tushuning.
Agar discussion commentlari, reaksiyalar yoki views/forwards ma'lumotlari bo'lsa, ularni post matni bilan birga baholang.
Agar faqat post matni bo'lsa, xulosani faqat post mazmuniga tayangan holda bering va yo'q kontekstni taxmin qilmang.
"""


def create_gemini_client(settings: Settings) -> genai.Client:
    if settings.gemini_use_vertex:
        if not settings.google_cloud_project:
            raise RuntimeError("GOOGLE_CLOUD_PROJECT is required when GEMINI_USE_VERTEX=true")
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


def analyze_mention(session: Session, settings: Settings, client: genai.Client, mention: Mention) -> Analysis:
    brand = session.get(Brand, mention.brand_id) if mention.brand_id else None
    prompt = build_prompt(mention, brand)
    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=ANALYSIS_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        payload = parse_json_response(response.text or "{}")
        analysis = Analysis(
            mention_id=mention.id,
            model_provider="vertex-gemini" if settings.gemini_use_vertex else "gemini",
            model_name=settings.gemini_model,
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
            model_provider="vertex-gemini" if settings.gemini_use_vertex else "gemini",
            model_name=settings.gemini_model,
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
    prompt = build_youtube_prompt(mention, brand)
    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=ANALYSIS_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        payload = parse_json_response(response.text or "{}")
        analysis = YouTubeAnalysis(
            youtube_mention_id=mention.id,
            model_provider="vertex-gemini" if settings.gemini_use_vertex else "gemini",
            model_name=settings.gemini_model,
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
            model_provider="vertex-gemini" if settings.gemini_use_vertex else "gemini",
            model_name=settings.gemini_model,
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


def build_prompt(mention: Mention, brand: Brand | None) -> str:
    text = mention.text or mention.caption or mention.normalized_text
    raw_message = (mention.raw or {}).get("message") or {}
    brand_profile: dict[str, Any] = {}
    if brand:
        brand_profile = {
            "name": brand.name,
            "description": brand.description,
            "industry": brand.industry,
            "aliases": brand.aliases,
            "keywords": brand.keywords,
            "competitors": brand.competitors,
            "monitor_notes": brand.monitor_notes,
        }
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
    brand_profile: dict[str, Any] = {}
    if brand:
        brand_profile = {
            "name": brand.name,
            "description": brand.description,
            "industry": brand.industry,
            "aliases": brand.aliases,
            "keywords": brand.keywords,
            "competitors": brand.competitors,
            "monitor_notes": brand.monitor_notes,
        }
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

# Genuinely transient errors: short backoff and retry.
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
)


def classify_provider_error(exc: Exception) -> tuple[bool, bool]:
    """Return (retryable, is_config_error) for a provider exception.

    retryable=True means "don't persist as a permanent error, retry later".
    is_config_error=True means the operator must act (billing/permission/creds),
    so the caller should back off harder.
    """
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
