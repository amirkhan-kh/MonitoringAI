from __future__ import annotations

import asyncio
import csv
import json
import re
import uuid
from collections import Counter
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.brand_taxonomy import build_brand_taxonomy
from app.db import SessionLocal, get_session, init_db
from app.localization import (
    localize_source_categories,
    localize_strings,
    localize_taxonomy,
    request_language,
)
from app.models import (
    AlertEvent,
    Analysis,
    Brand,
    FacebookAnalysis,
    FacebookMention,
    FacebookSource,
    InstagramAnalysis,
    InstagramMention,
    InstagramSource,
    Mention,
    TelegramSource,
    YouTubeAnalysis,
    YouTubeMention,
    YouTubeSource,
)
from app.schemas import (
    AlertEventOut,
    BrandCreate,
    BrandOut,
    BrandProfileSuggestRequest,
    BrandProfileSuggestion,
    BrandUpdate,
    DashboardSummary,
    LoginRequest,
    TokenResponse,
    FacebookAnalysisOut,
    FacebookManualIngest,
    FacebookManualIngestResult,
    FacebookMentionOut,
    FacebookSourceCreate,
    FacebookSourceOut,
    FacebookSourceUpdate,
    FacebookStatus,
    FacebookSummary,
    InstagramAnalysisOut,
    InstagramManualIngest,
    InstagramManualIngestResult,
    InstagramMentionOut,
    InstagramSourceCreate,
    InstagramSourceOut,
    InstagramSourceUpdate,
    InstagramStatus,
    InstagramSummary,
    InstagramSyncResult,
    InlineAnalysisOut,
    MentionDetailOut,
    MentionOut,
    SourceDeleteResult,
    TelegramBotStatus,
    TelegramSourceBackfillRequest,
    TelegramSourceBackfillResult,
    TelegramSourceAccessCheck,
    TelegramSourceAccessStatus,
    TelegramSourceCategory,
    TelegramSourceCreate,
    TelegramSourceImport,
    TelegramSourceImportResult,
    TelegramSourceOut,
    TelegramSourceRefreshResult,
    TelegramSourceResolve,
    TelegramSourceUpdate,
    TelegramSessionStatus,
    YouTubeMentionOut,
    YouTubeSourceCategory,
    YouTubeSourceImport,
    YouTubeSourceImportResult,
    YouTubeSourceOut,
    YouTubeSourceSyncRequest,
    YouTubeSourceSyncResult,
    YouTubeSourceUpdate,
    YouTubeStatus,
    YouTubeSummary,
)
from app.services.alerts import record_alert
from app.services.auth import create_token, verify_credentials, verify_token
from app.services.facebook_api import (
    FacebookApi,
    FacebookApiError,
    detect_page,
    verify_signature as fb_verify_signature,
)
from app.services.facebook_ingestion import ingest_facebook_comment
from app.services.gemini_analysis import (
    ProviderRetryableError,
    analyze_facebook_mention,
    analyze_instagram_mention,
    create_gemini_client,
    suggest_brand_profile,
)
from app.services.instagram_api import InstagramApi, InstagramApiError, detect_account, verify_signature
from app.services.instagram_ingestion import ingest_instagram_comment
from app.services.instagram_sync import sync_instagram_source
from app.services.matching import BrandMatch, collect_matched_terms, invalidate_brand_cache, match_brand, normalize_text
from app.services.source_deletion import SourceNotFoundError, delete_monitored_source
from app.services.telegram_api import TelegramBotApi
from app.services.realtime import publish_realtime_event, realtime_event_stream
from app.services.youtube_api import (
    YouTubeApi,
    comment_url,
    parse_rfc3339,
    parse_youtube_ref,
    video_url,
)
from app.workers.telegram_backfill import backfill_source

from telethon import TelegramClient

import logging


logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telethon.network.mtprotosender").setLevel(logging.WARNING)

SOURCE_CATEGORIES = [
    {
        "key": "owned",
        "label": "Rasmiy kanallar",
        "default_monitoring_mode": "all_messages",
        "description": "Clientning rasmiy kanal, group va linked discussion manbalari.",
    },
    {
        "key": "bot",
        "label": "Botlar",
        "default_monitoring_mode": "all_messages",
        "description": "Client botlari, monitoring botlari va bot orqali keladigan suhbatlar.",
    },
    {
        "key": "competitor",
        "label": "Raqobatchilar",
        "default_monitoring_mode": "all_messages",
        "description": "Raqobatchi kompaniya, brend yoki loyiha kanallari.",
    },
    {
        "key": "news",
        "label": "Yangiliklar",
        "default_monitoring_mode": "brand_matches_only",
        "description": "Media va yangilik kanallari.",
    },
    {
        "key": "industry",
        "label": "Yo'nalish",
        "default_monitoring_mode": "brand_matches_only",
        "description": "Soha, bozor va mavzu bo'yicha kanallar.",
    },
    {
        "key": "influencer",
        "label": "Influencerlar",
        "default_monitoring_mode": "brand_matches_only",
        "description": "Bloger, ekspert va shaxsiy media manbalari.",
    },
    {
        "key": "community",
        "label": "Chatlar",
        "default_monitoring_mode": "brand_matches_only",
        "description": "Public chat, forum va community guruhlar.",
    },
    {
        "key": "useful",
        "label": "Foydali",
        "default_monitoring_mode": "brand_matches_only",
        "description": "Benchmark, hamkorlik yoki trend kuzatuvi uchun manbalar.",
    },
    {
        "key": "risk",
        "label": "Risk watch",
        "default_monitoring_mode": "all_messages",
        "description": "Shikoyat, krizis, salbiy signal yoki reputatsiya xavfi yuqori manbalar.",
    },
    {
        "key": "unknown",
        "label": "Tasniflanmagan",
        "default_monitoring_mode": "brand_matches_only",
        "description": "Hali tartibga solinmagan source.",
    },
]

YOUTUBE_SOURCE_CATEGORIES = [
    {
        "key": "owned",
        "label": "Rasmiy kanallar",
        "default_monitoring_mode": "all_messages",
        "description": "Clientning rasmiy YouTube kanali, Shorts va video comment oqimi.",
    },
    {
        "key": "competitor",
        "label": "Raqobatchilar",
        "default_monitoring_mode": "all_messages",
        "description": "Raqobatchi channel, video va content signallari.",
    },
    {
        "key": "keyword",
        "label": "Keyword watch",
        "default_monitoring_mode": "brand_matches_only",
        "description": "Brand nomi, mahsulot, muammo yoki bozor so'zlari bo'yicha YouTube search.",
    },
    {
        "key": "hashtag",
        "label": "Hashtaglar",
        "default_monitoring_mode": "brand_matches_only",
        "description": "Hashtag yoki kampaniya taglari ostidagi video va commentlar.",
    },
    {
        "key": "influencer",
        "label": "Creatorlar",
        "default_monitoring_mode": "brand_matches_only",
        "description": "Bloger, sharhlovchi va creator kanallari.",
    },
    {
        "key": "campaign",
        "label": "Kampaniyalar",
        "default_monitoring_mode": "brand_matches_only",
        "description": "Reklama, launch, promo va event kampaniyalari.",
    },
    {
        "key": "risk",
        "label": "Risk watch",
        "default_monitoring_mode": "all_messages",
        "description": "Salbiy signal, shikoyat, crisis va brand safety kuzatuvi.",
    },
    {
        "key": "unknown",
        "label": "Tasniflanmagan",
        "default_monitoring_mode": "brand_matches_only",
        "description": "Hali tartibga solinmagan YouTube source.",
    },
]

BRAND_TAXONOMY = {
    "categories": [
        {
            "key": "retail_fashion",
            "label": "Kiyim va retail",
            "children": ["sport kiyimlari", "kundalik kiyim", "poyabzal", "aksessuar", "online do'kon"],
            "keywords": ["sifat", "razmer", "yetkazib berish", "narx", "original", "chegirma"],
            "risk_keywords": ["aldadi", "soxta", "kechikdi", "qaytarish", "defekt", "mos kelmadi"],
        },
        {
            "key": "food_hospitality",
            "label": "Ovqatlanish va servis",
            "children": ["restoran", "kafe", "delivery", "fast food", "mehmonxona"],
            "keywords": ["ta'm", "xizmat", "tezlik", "bron", "yetkazish", "tozalik"],
            "risk_keywords": ["sovuq", "kechikdi", "zaharlanish", "qo'pol", "bekor qilindi", "iflos"],
        },
        {
            "key": "software_saas",
            "label": "Software va SaaS",
            "children": ["AI mahsulot", "CRM", "dashboard", "mobile app", "API", "automation"],
            "keywords": ["demo", "integratsiya", "tezlik", "xato", "support", "narx"],
            "risk_keywords": ["ishlamayapti", "bug", "login", "to'lov", "ma'lumot yo'qoldi", "sekin"],
        },
        {
            "key": "education",
            "label": "Ta'lim",
            "children": ["kurs", "online ta'lim", "til markazi", "universitet", "mentorlik"],
            "keywords": ["dars", "mentor", "sertifikat", "natija", "narx", "jadval"],
            "risk_keywords": ["va'da", "pul qaytarish", "sifatsiz", "bekor", "aldadi", "natija yo'q"],
        },
        {
            "key": "health_beauty",
            "label": "Sog'liq va beauty",
            "children": ["klinika", "kosmetologiya", "fitness", "dorixona", "salon"],
            "keywords": ["navbat", "mutaxassis", "natija", "xavfsizlik", "narx", "qabul"],
            "risk_keywords": ["asorat", "allergiya", "shikoyat", "litsenziya", "qimmat", "natija bermadi"],
        },
        {
            "key": "finance_fintech",
            "label": "Moliya va fintech",
            "children": ["bank", "to'lov", "kredit", "investitsiya", "sug'urta"],
            "keywords": ["komissiya", "limit", "karta", "to'lov", "ilova", "xavfsizlik"],
            "risk_keywords": ["bloklandi", "pul yechildi", "fraud", "kechikdi", "support javob bermadi"],
        },
        {
            "key": "ecommerce_marketplace",
            "label": "E-commerce va marketplace",
            "children": ["marketplace", "shopping app", "seller", "logistika", "ombor"],
            "keywords": ["buyurtma", "yetkazish", "qaytarish", "ombor", "seller", "aksiya"],
            "risk_keywords": ["kelmadi", "noto'g'ri tovar", "refund", "support", "cancel", "kechikdi"],
        },
        {
            "key": "media_creator",
            "label": "Media va creator",
            "children": ["blog", "news", "podcast", "YouTube kanal", "influencer"],
            "keywords": ["kontent", "obuna", "ko'rish", "komment", "hamkorlik", "reklama"],
            "risk_keywords": ["fake news", "plagiat", "tanqid", "cancel", "shikoyat", "toxicity"],
        },
    ],
    "goals": [
        {"key": "own_profile", "label": "O'z profilimdagi post/commentlarni kuzatish"},
        {"key": "competitor_watch", "label": "Raqobatchilarni kuzatish"},
        {"key": "global_brand_watch", "label": "Internet bo'ylab brand zikrlarini topish"},
        {"key": "crisis_alerts", "label": "Salbiy signal va crisis alert"},
        {"key": "campaign_tracking", "label": "Kampaniya/hashtag natijasini kuzatish"},
        {"key": "customer_support", "label": "Support va javob berish uchun mention ajratish"},
    ],
    "source_playbooks": {
        "telegram": [
            "Kanal yoki guruh linkini kiriting.",
            "Monitoring botni kanal/guruhga admin qiling.",
            "Discussion group bo'lsa bot u yerda ham a'zo/admin bo'lishi kerak.",
            "Backfill tugmasi bilan eski post/commentlarni tortib oling.",
        ],
        "youtube": [
            "Kanal, video, hashtag yoki keyword kiriting.",
            "YouTube API key sozlangan bo'lsa sync comment/video oqimini tortadi.",
            "Raqobatchi kanal uchun token kerak emas, public Data API yetarli.",
            "Dislike soni public API orqali berilmaydi, shuning uchun taxmin qilinmaydi.",
        ],
        "instagram": [
            "O'z profilingiz uchun Instagram Business/Creator + Facebook Page kerak.",
            "Development rejimda faqat tester/owned oqim ko'rinishi mumkin.",
            "Real public comment/@mention uchun App Review va kerakli permissionlar talab qilinadi.",
            "Token yoki webhook ulanmasa, qo'lda demo ingest orqali AI tahlilni tekshirish mumkin.",
        ],
        "facebook": [
            "Facebook Page token yoki Page access kerak.",
            "Own Page comment/reply oqimi poller/webhook orqali keladi.",
            "Business portfolio cheklovi bo'lsa avval Meta account/page holatini tuzatish kerak.",
            "Raqobatchi Page uchun public postlarni cheklangan darajada kuzatish mumkin, admin token talab qilinmaydigan joylar kam.",
        ],
    },
}

BRAND_TAXONOMY = build_brand_taxonomy(BRAND_TAXONOMY)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


# Routes reachable without a token: health check, the login endpoint itself, the API
# docs, and the Instagram webhook (Meta calls it unauthenticated — it has its own
# signature/verify-token checks).
AUTH_PUBLIC_PATHS = {"/health", "/auth/login", "/docs", "/redoc", "/openapi.json"}
AUTH_PUBLIC_PREFIXES = ("/instagram/webhook",)


async def require_auth(request: Request) -> None:
    settings = get_settings()
    if not settings.auth_enabled:
        return
    path = request.url.path
    if request.method == "OPTIONS" or path in AUTH_PUBLIC_PATHS or path.startswith(AUTH_PUBLIC_PREFIXES):
        return
    # EventSource (SSE) can't set an Authorization header, so /events takes the token
    # as a query param instead.
    if path == "/events":
        token = request.query_params.get("access_token")
    else:
        header = request.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else None
    if verify_token(settings, token) is None:
        raise HTTPException(status_code=401, detail="Avtorizatsiya talab qilinadi. Qaytadan kiring.")


app = FastAPI(title="MonitoringAI", version="0.1.0", lifespan=lifespan, dependencies=[Depends(require_auth)])
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/auth/login", response_model=TokenResponse)
def auth_login(payload: LoginRequest) -> TokenResponse:
    settings = get_settings()
    if not verify_credentials(settings, payload.username, payload.password):
        raise HTTPException(status_code=401, detail="Login yoki parol noto'g'ri")
    token, expires_at = create_token(settings, payload.username)
    return TokenResponse(access_token=token, username=payload.username, expires_at=expires_at)


@app.get("/auth/me")
def auth_me(request: Request) -> dict[str, object]:
    settings = get_settings()
    header = request.headers.get("Authorization", "")
    token = header[7:] if header.startswith("Bearer ") else None
    username = verify_token(settings, token)
    return {"username": username, "auth_enabled": settings.auth_enabled}

DbSession = Annotated[Session, Depends(get_session)]
LOCAL_TZ = timezone(timedelta(hours=5))


def today_local_date() -> date:
    return datetime.now(LOCAL_TZ).date()


def start_of_day_utc(value: date | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=LOCAL_TZ)
        return value.astimezone(timezone.utc)
    return datetime.combine(value, time.min, tzinfo=LOCAL_TZ).astimezone(timezone.utc)


def monitor_start_or_today(value: date | datetime | None) -> datetime:
    return start_of_day_utc(value or today_local_date()) or datetime.now(timezone.utc)


def parse_date_field(value: str | None) -> date | None:
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return date.fromisoformat(cleaned)


def normalize_chat_ref(value: int | str) -> int | str:
    if isinstance(value, int):
        return value
    ref = value.strip()
    ref = re.sub(r"^https?://", "", ref)
    ref = ref.removeprefix("t.me/")
    ref = ref.removeprefix("telegram.me/")
    ref = ref.split("?", 1)[0].strip("/")
    if "/" in ref:
        ref = ref.split("/", 1)[0]
    if re.fullmatch(r"-?\d+", ref):
        return int(ref)
    return ref if ref.startswith("@") else f"@{ref}"


def username_from_ref(value: int | str) -> str | None:
    normalized = normalize_chat_ref(value)
    if isinstance(normalized, int):
        return None
    username = normalized.lstrip("@")
    return username or None


def upsert_telegram_source_from_chat(
    session: Session,
    *,
    chat_info: dict,
    brand_id: uuid.UUID | None,
    source_category: str,
    monitoring_mode: str,
    competitor_name: str | None,
    notes: str | None,
    collect_posts: bool,
    collect_comments: bool,
    monitor_from: datetime | None = None,
) -> TelegramSource:
    source = session.query(TelegramSource).filter(TelegramSource.chat_id == chat_info["id"]).one_or_none()
    if not source and chat_info.get("username"):
        source = session.query(TelegramSource).filter(TelegramSource.username == chat_info["username"]).one_or_none()
    if not source:
        source = TelegramSource(chat_id=chat_info["id"])
        session.add(source)

    source.brand_id = brand_id
    source.source_kind = chat_info.get("type") or "unknown"
    source.source_category = source_category
    source.monitoring_mode = monitoring_mode
    source.competitor_name = competitor_name
    source.chat_id = chat_info.get("id")
    source.username = chat_info.get("username")
    source.title = chat_info.get("title") or chat_info.get("first_name")
    source.description = chat_info.get("description")
    source.linked_discussion_chat_id = chat_info.get("linked_chat_id")
    source.notes = notes
    source.collect_posts = collect_posts
    source.collect_comments = collect_comments
    source.monitor_from = monitor_from or source.monitor_from or datetime.now(timezone.utc)
    source.active = True
    return source


def upsert_related_telegram_source(
    api: TelegramBotApi,
    session: Session,
    *,
    parent_chat_info: dict,
    parent_source: TelegramSource,
    brand_id: uuid.UUID | None,
    source_category: str,
    monitoring_mode: str,
    collect_comments: bool,
    monitor_from: datetime | None = None,
) -> TelegramSource | None:
    linked_chat_id = parent_chat_info.get("linked_chat_id")
    if not linked_chat_id:
        return None
    try:
        linked_chat_info = api.get_chat(int(linked_chat_id))
    except Exception:
        return None
    if not linked_chat_info:
        return None

    title = parent_source.title or parent_chat_info.get("title") or parent_chat_info.get("username") or "channel"
    parent_type = parent_chat_info.get("type")
    linked_type = linked_chat_info.get("type")
    if parent_type == "channel":
        notes = f"Linked discussion group for {title}. Commentlar shu source orqali olinadi."
        linked_collect_posts = False
        linked_collect_comments = collect_comments
    elif parent_type in {"group", "supergroup"} and linked_type == "channel":
        notes = f"Linked channel for {title}. Postlar shu source orqali olinadi."
        linked_collect_posts = True
        linked_collect_comments = collect_comments
    else:
        notes = f"Linked Telegram source for {title}."
        linked_collect_posts = True
        linked_collect_comments = collect_comments

    return upsert_telegram_source_from_chat(
        session,
        chat_info=linked_chat_info,
        brand_id=brand_id,
        source_category=source_category,
        monitoring_mode=monitoring_mode,
        competitor_name=parent_source.competitor_name,
        notes=notes,
        collect_posts=linked_collect_posts,
        collect_comments=linked_collect_comments,
        monitor_from=monitor_from or parent_source.monitor_from,
    )


def upsert_catalog_source(
    session: Session,
    *,
    ref: int | str,
    brand_id: uuid.UUID | None,
    source_category: str,
    monitoring_mode: str,
    competitor_name: str | None,
    notes: str | None,
    collect_posts: bool,
    collect_comments: bool,
    monitor_from: datetime | None = None,
) -> TelegramSource:
    chat_id = normalize_chat_ref(ref)
    username = username_from_ref(ref)
    source = None
    if isinstance(chat_id, int):
        source = session.query(TelegramSource).filter(TelegramSource.chat_id == chat_id).one_or_none()
    if source is None and username:
        source = session.query(TelegramSource).filter(TelegramSource.username == username).one_or_none()
    if source is None:
        source = TelegramSource(chat_id=chat_id if isinstance(chat_id, int) else None, username=username)
        session.add(source)

    source.brand_id = brand_id
    source.source_kind = source.source_kind or "unknown"
    source.source_category = source_category
    source.monitoring_mode = monitoring_mode
    source.competitor_name = competitor_name
    source.notes = notes
    source.collect_posts = collect_posts
    source.collect_comments = collect_comments
    source.monitor_from = monitor_from or source.monitor_from or datetime.now(timezone.utc)
    source.active = True
    return source


def parse_import_rows(raw_text: str, default_category: str, default_mode: str) -> list[dict[str, str | None]]:
    rows: list[dict[str, str | None]] = []
    for line in raw_text.splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        fields = next(csv.reader([cleaned]))
        fields = [field.strip() for field in fields]
        ref = fields[0] if fields else ""
        if not ref:
            continue
        rows.append(
            {
                "ref": ref,
                "source_category": fields[1] if len(fields) > 1 and fields[1] else default_category,
                "monitoring_mode": fields[2] if len(fields) > 2 and fields[2] else default_mode,
                "competitor_name": fields[3] if len(fields) > 3 and fields[3] else None,
                "notes": fields[4] if len(fields) > 4 and fields[4] else None,
                "monitor_from": fields[5] if len(fields) > 5 and fields[5] else None,
            }
        )
    return rows


def parse_youtube_import_rows(raw_text: str, default_category: str, default_mode: str) -> list[dict[str, str | None]]:
    rows: list[dict[str, str | None]] = []
    for line in raw_text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        fields = next(csv.reader([cleaned]))
        fields = [field.strip() for field in fields]
        ref = fields[0] if fields else ""
        if not ref:
            continue
        rows.append(
            {
                "ref": ref,
                "source_category": fields[1] if len(fields) > 1 and fields[1] else default_category,
                "monitoring_mode": fields[2] if len(fields) > 2 and fields[2] else default_mode,
                "competitor_name": fields[3] if len(fields) > 3 and fields[3] else None,
                "notes": fields[4] if len(fields) > 4 and fields[4] else None,
                "monitor_from": fields[5] if len(fields) > 5 and fields[5] else None,
                "hashtags": fields[6] if len(fields) > 6 and fields[6] else None,
            }
        )
    return rows


def normalize_hashtag(value: str) -> str | None:
    cleaned = value.strip().strip(",;")
    if not cleaned:
        return None
    cleaned = cleaned.replace("＃", "#")
    if cleaned.startswith("#"):
        tag = "#" + re.sub(r"\s+", "", cleaned.lstrip("#"))
    else:
        tag = "#" + re.sub(r"\s+", "", cleaned)
    return tag.lower() if len(tag) > 1 else None


def parse_hashtags(value: str | list[str] | None) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = re.split(r"[\s,;]+", value)
    tags: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        tag = normalize_hashtag(str(item))
        if tag and tag not in seen:
            seen.add(tag)
            tags.append(tag)
    return tags


def merge_hashtags(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            tag = normalize_hashtag(item)
            if tag and tag not in seen:
                seen.add(tag)
                merged.append(tag)
    return merged


def normalize_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def upsert_youtube_source(
    session: Session,
    *,
    ref: str,
    brand_id: uuid.UUID | None,
    source_category: str,
    monitoring_mode: str,
    nickname: str | None,
    competitor_name: str | None,
    hashtags: list[str],
    notes: str | None,
    collect_videos: bool,
    collect_comments: bool,
    collect_transcripts: bool,
    monitor_from: datetime,
    api: YouTubeApi | None = None,
) -> YouTubeSource:
    parsed = parse_youtube_ref(ref)
    source = session.query(YouTubeSource).filter(YouTubeSource.source_ref == parsed.ref).one_or_none()
    if source is None:
        source = YouTubeSource(source_ref=parsed.ref)
        session.add(source)

    source.brand_id = brand_id
    source.source_ref = parsed.ref
    source.source_kind = parsed.kind
    source.source_category = source_category
    source.monitoring_mode = monitoring_mode
    source.nickname = nickname
    source.competitor_name = competitor_name
    source.hashtags = merge_hashtags(hashtags, [parsed.query] if parsed.kind == "hashtag" and parsed.query else [])
    source.notes = notes
    source.collect_videos = collect_videos
    source.collect_comments = collect_comments
    source.collect_transcripts = collect_transcripts
    source.monitor_from = monitor_from
    source.active = True
    source.video_id = parsed.video_id
    source.channel_id = parsed.channel_id
    source.channel_handle = parsed.channel_handle
    source.query = parsed.query
    source.title = nickname or parsed.query or parsed.channel_handle or parsed.video_id or parsed.ref

    if api and api.configured:
        enrich_youtube_source(source, api)

    return source


def enrich_youtube_source(source: YouTubeSource, api: YouTubeApi) -> None:
    if source.source_kind == "channel":
        item = api.channel_by_id(source.channel_id) if source.channel_id else api.channel_by_handle(source.channel_handle or source.source_ref)
        if item:
            snippet = item.get("snippet") or {}
            content_details = item.get("contentDetails") or {}
            related_playlists = content_details.get("relatedPlaylists") or {}
            source.channel_id = item.get("id") or source.channel_id
            source.channel_title = snippet.get("title") or source.channel_title
            source.title = snippet.get("title") or source.title
            source.description = snippet.get("description") or source.description
            source.uploads_playlist_id = related_playlists.get("uploads") or source.uploads_playlist_id
    elif source.source_kind == "video" and source.video_id:
        item = api.video_by_id(source.video_id)
        if item:
            snippet = item.get("snippet") or {}
            source.title = snippet.get("title") or source.title
            source.description = snippet.get("description") or source.description
            source.channel_id = snippet.get("channelId") or source.channel_id
            source.channel_title = snippet.get("channelTitle") or source.channel_title


def match_brand_for_youtube_source(session: Session, source: YouTubeSource, normalized_text: str) -> BrandMatch:
    source_terms = collect_youtube_source_terms(source, normalized_text)
    if source.brand_id:
        brand = session.get(Brand, source.brand_id)
        if brand:
            terms = collect_matched_terms(brand, normalized_text)
            if source.monitoring_mode == "brand_matches_only":
                return BrandMatch(brand, unique_terms([*terms, *source_terms])) if terms or source_terms else BrandMatch(None, [])
            return BrandMatch(brand, unique_terms([*terms, *source_terms]))
    brand_match = match_brand(session, normalized_text)
    if brand_match.brand:
        return BrandMatch(brand_match.brand, unique_terms([*brand_match.terms, *source_terms]))
    return BrandMatch(None, source_terms)


def collect_youtube_source_terms(source: YouTubeSource, normalized_text: str) -> list[str]:
    candidates: list[str] = []
    candidates.extend(source.hashtags or [])
    if source.query:
        candidates.append(source.query)
    if source.nickname:
        candidates.append(source.nickname)
    matched: list[str] = []
    for candidate in candidates:
        normalized_candidate = normalize_text(candidate)
        if normalized_candidate and normalized_candidate in normalized_text:
            matched.append(candidate)
            continue
        if candidate.startswith("#"):
            without_hash = normalize_text(candidate.lstrip("#"))
            if without_hash and without_hash in normalized_text:
                matched.append(candidate)
    return unique_terms(matched)


def unique_terms(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.lower()
        if key and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def ingest_youtube_video(session: Session, source: YouTubeSource, item: dict) -> YouTubeMention | None:
    video_id = youtube_video_id_from_item(item)
    if not video_id:
        return None
    snippet = item.get("snippet") or {}
    statistics = item.get("statistics") or {}
    text = "\n".join(part for part in [snippet.get("title"), snippet.get("description")] if part)
    normalized = normalize_text(text)
    brand_match = match_brand_for_youtube_source(session, source, normalized)
    if source.monitoring_mode == "brand_matches_only" and not brand_match.brand:
        return None

    external_id = f"youtube:video:{video_id}"
    mention = session.query(YouTubeMention).filter(YouTubeMention.external_id == external_id).one_or_none()
    if mention is None:
        mention = YouTubeMention(external_id=external_id, item_type="video")
        session.add(mention)

    mention.source_id = source.id
    mention.brand_id = brand_match.brand.id if brand_match.brand else source.brand_id
    mention.video_id = video_id
    mention.channel_id = snippet.get("channelId") or source.channel_id
    mention.channel_title = snippet.get("channelTitle") or source.channel_title
    mention.title = snippet.get("title")
    mention.text = snippet.get("description")
    mention.normalized_text = normalized
    mention.permalink = video_url(video_id)
    thumbnails = snippet.get("thumbnails") or {}
    mention.thumbnail_url = (thumbnails.get("medium") or thumbnails.get("default") or {}).get("url")
    mention.view_count = int_or_none(statistics.get("viewCount"))
    mention.like_count = int_or_none(statistics.get("likeCount"))
    mention.comment_count = int_or_none(statistics.get("commentCount"))
    mention.brand_match_terms = brand_match.terms
    mention.raw = item
    mention.published_at = parse_rfc3339(snippet.get("publishedAt"))
    return mention


def ingest_youtube_comment(
    session: Session,
    source: YouTubeSource,
    *,
    comment_id: str,
    video_id: str | None,
    snippet: dict,
    raw: dict,
    item_type: str = "comment",
) -> YouTubeMention | None:
    text = snippet.get("textDisplay") or snippet.get("textOriginal") or ""
    normalized = normalize_text(text)
    brand_match = match_brand_for_youtube_source(session, source, normalized)
    if source.monitoring_mode == "brand_matches_only" and not brand_match.brand:
        return None

    external_id = f"youtube:comment:{comment_id}"
    mention = session.query(YouTubeMention).filter(YouTubeMention.external_id == external_id).one_or_none()
    if mention is None:
        mention = YouTubeMention(external_id=external_id, item_type=item_type)
        session.add(mention)

    author_channel = snippet.get("authorChannelId") or {}
    mention.source_id = source.id
    mention.brand_id = brand_match.brand.id if brand_match.brand else source.brand_id
    mention.item_type = item_type
    mention.video_id = video_id
    mention.channel_id = source.channel_id
    mention.channel_title = source.channel_title
    mention.author_channel_id = author_channel.get("value") if isinstance(author_channel, dict) else None
    mention.author_name = snippet.get("authorDisplayName")
    mention.text = text
    mention.normalized_text = normalized
    mention.permalink = comment_url(video_id, comment_id)
    mention.like_count = int_or_none(snippet.get("likeCount"))
    mention.brand_match_terms = brand_match.terms
    mention.raw = raw
    mention.published_at = parse_rfc3339(snippet.get("publishedAt"))
    return mention


def ingest_youtube_comment_thread(session: Session, source: YouTubeSource, item: dict, from_date: datetime | None) -> int:
    count = 0
    snippet = item.get("snippet") or {}
    top_level = (snippet.get("topLevelComment") or {})
    top_snippet = top_level.get("snippet") or {}
    published_at = parse_rfc3339(top_snippet.get("publishedAt"))
    if from_date and published_at and published_at < from_date:
        return 0
    if top_level.get("id") and ingest_youtube_comment(
        session,
        source,
        comment_id=top_level["id"],
        video_id=snippet.get("videoId"),
        snippet=top_snippet,
        raw=item,
        item_type="comment",
    ):
        count += 1

    for reply in ((item.get("replies") or {}).get("comments") or []):
        reply_snippet = reply.get("snippet") or {}
        reply_published_at = parse_rfc3339(reply_snippet.get("publishedAt"))
        if from_date and reply_published_at and reply_published_at < from_date:
            continue
        if reply.get("id") and ingest_youtube_comment(
            session,
            source,
            comment_id=reply["id"],
            video_id=reply_snippet.get("videoId") or snippet.get("videoId"),
            snippet=reply_snippet,
            raw=reply,
            item_type="comment_reply",
        ):
            count += 1
    return count


def int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def publish_youtube_source_event(session: Session, source: YouTubeSource) -> None:
    publish_realtime_event(
        session,
        "youtube_source",
        {
            "id": source.id,
            "brand_id": source.brand_id,
            "source_category": source.source_category,
            "source_kind": source.source_kind,
            "title": source.title,
            "source_ref": source.source_ref,
            "uploads_playlist_id": source.uploads_playlist_id,
            "active": source.active,
        },
    )


def publish_youtube_mention_event(session: Session, mention: YouTubeMention) -> None:
    publish_realtime_event(
        session,
        "youtube_mention",
        {
            "id": mention.id,
            "brand_id": mention.brand_id,
            "source_id": mention.source_id,
            "item_type": mention.item_type,
            "video_id": mention.video_id,
            "published_at": mention.published_at,
        },
    )


def sync_youtube_source(session: Session, source: YouTubeSource, api: YouTubeApi, payload: YouTubeSourceSyncRequest) -> YouTubeSourceSyncResult:
    if not api.configured:
        return YouTubeSourceSyncResult(source_id=source.id, ok=False, error="YOUTUBE_API_KEY sozlanmagan")

    try:
        enrich_youtube_source(source, api)
        session.flush()
        from_date = normalize_aware(source.monitor_from or source.created_at)
        imported = 0
        videos_seen = 0
        comments_seen = 0
        video_ids: list[str] = []

        if source.collect_videos:
            video_items = fetch_youtube_video_items(api, source, from_date=from_date, max_pages=payload.max_pages)
            for item in video_items:
                video_id = youtube_video_id_from_item(item)
                if not video_id:
                    continue
                videos_seen += 1
                video_ids.append(video_id)
                detail = api.video_by_id(video_id) or item
                mention = ingest_youtube_video(session, source, detail)
                if mention:
                    imported += 1
                    session.flush()
                    publish_youtube_mention_event(session, mention)

        if source.collect_comments:
            if source.source_kind == "channel" and source.channel_id:
                comments_seen += fetch_and_ingest_channel_comments(
                    session,
                    api,
                    source,
                    from_date=from_date,
                    max_pages=payload.max_pages,
                    max_results=payload.comments_per_video,
                )
            comment_video_ids = [] if source.source_kind == "channel" else [source.video_id, *video_ids]
            for video_id in list(dict.fromkeys(comment_video_ids)):
                if not video_id:
                    continue
                comments_seen += fetch_and_ingest_video_comments(
                    session,
                    api,
                    source,
                    video_id=video_id,
                    from_date=from_date,
                    max_pages=payload.max_pages,
                    max_results=payload.comments_per_video,
                )

        source.last_checked_at = datetime.now(timezone.utc)
        session.commit()
        return YouTubeSourceSyncResult(
            source_id=source.id,
            ok=True,
            videos_seen=videos_seen,
            comments_seen=comments_seen,
            imported=imported + comments_seen,
        )
    except Exception as exc:
        session.rollback()
        return YouTubeSourceSyncResult(source_id=source.id, ok=False, error=str(exc))


def fetch_youtube_video_items(
    api: YouTubeApi,
    source: YouTubeSource,
    *,
    from_date: datetime | None,
    max_pages: int,
) -> list[dict]:
    if source.source_kind == "video" and source.video_id:
        item = api.video_by_id(source.video_id)
        return [item] if item else []

    if source.source_kind == "channel":
        if not source.uploads_playlist_id:
            return []
        return fetch_youtube_upload_playlist_items(
            api,
            source.uploads_playlist_id,
            from_date=from_date,
            max_pages=max_pages,
        )

    items: list[dict] = []
    page_token = None
    for _ in range(max_pages):
        payload = api.search_videos(
            query=source.query if source.source_kind in {"keyword", "hashtag"} else None,
            channel_id=source.channel_id if source.source_kind == "channel" else None,
            published_after=from_date,
            page_token=page_token,
        )
        items.extend(payload.get("items") or [])
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    return items


def fetch_youtube_upload_playlist_items(
    api: YouTubeApi,
    uploads_playlist_id: str,
    *,
    from_date: datetime | None,
    max_pages: int,
) -> list[dict]:
    items: list[dict] = []
    page_token = None
    for _ in range(max_pages):
        payload = api.playlist_items(uploads_playlist_id, page_token=page_token)
        should_stop = False
        for item in payload.get("items") or []:
            snippet = item.get("snippet") or {}
            published_at = parse_rfc3339(snippet.get("publishedAt"))
            if from_date and published_at and published_at < from_date:
                should_stop = True
                break
            items.append(item)
        if should_stop:
            break
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    return items


def youtube_video_id_from_item(item: dict) -> str | None:
    item_id = item.get("id")
    if isinstance(item_id, dict):
        return item_id.get("videoId")
    snippet = item.get("snippet") or {}
    resource_id = snippet.get("resourceId") or {}
    if isinstance(resource_id, dict) and resource_id.get("videoId"):
        return resource_id.get("videoId")
    content_details = item.get("contentDetails") or {}
    if content_details.get("videoId"):
        return content_details.get("videoId")
    return item_id if isinstance(item_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{11}", item_id) else None


def fetch_and_ingest_video_comments(
    session: Session,
    api: YouTubeApi,
    source: YouTubeSource,
    *,
    video_id: str,
    from_date: datetime | None,
    max_pages: int,
    max_results: int,
) -> int:
    comments_seen = 0
    page_token = None
    for _ in range(max_pages):
        try:
            payload = api.video_comments(video_id, page_token=page_token, max_results=max_results)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {403, 404}:
                break
            raise
        for item in payload.get("items") or []:
            comments_seen += ingest_youtube_comment_thread(session, source, item, from_date)
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    return comments_seen


def fetch_and_ingest_channel_comments(
    session: Session,
    api: YouTubeApi,
    source: YouTubeSource,
    *,
    from_date: datetime | None,
    max_pages: int,
    max_results: int,
) -> int:
    if not source.channel_id:
        return 0
    comments_seen = 0
    page_token = None
    for _ in range(max_pages):
        try:
            payload = api.channel_comments(source.channel_id, page_token=page_token, max_results=max_results)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {403, 404}:
                break
            raise
        for item in payload.get("items") or []:
            comments_seen += ingest_youtube_comment_thread(session, source, item, from_date)
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    return comments_seen


def membership_status(api: TelegramBotApi, chat_id: int, bot_id: int, issues: list[str]) -> str | None:
    try:
        member = api.get_chat_member(chat_id, bot_id)
    except Exception:
        issues.append("bot_not_member_or_no_access")
        return None
    return member.get("status") if member else None


def is_member_status(status: str | None) -> bool:
    return status in {"creator", "administrator", "member"}


def is_admin_status(status: str | None) -> bool:
    return status in {"creator", "administrator"}


def mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    if len(phone) <= 4:
        return "****"
    return f"{phone[:3]}***{phone[-2:]}"


def build_access_status(api: TelegramBotApi, chat_id_or_username: int | str) -> tuple[TelegramSourceAccessStatus, dict | None]:
    issues: list[str] = []
    bot = api.get_me()
    bot_id = int(bot["id"]) if bot and bot.get("id") else None
    bot_username = bot.get("username") if bot else None
    chat_ref = normalize_chat_ref(chat_id_or_username)
    if bot_id is None:
        return (
            TelegramSourceAccessStatus(
                ok=False,
                chat_id_or_username=chat_id_or_username,
                issues=["bot_token_invalid_or_getme_failed"],
            ),
            None,
        )

    try:
        chat_info = api.get_chat(chat_ref)
    except Exception:
        return (
            TelegramSourceAccessStatus(
                ok=False,
                chat_id_or_username=chat_id_or_username,
                bot_username=bot_username,
                issues=["chat_not_found_or_bot_has_no_access"],
            ),
            None,
        )

    if not chat_info:
        return (
            TelegramSourceAccessStatus(
                ok=False,
                chat_id_or_username=chat_id_or_username,
                bot_username=bot_username,
                issues=["chat_not_found_or_bot_has_no_access"],
            ),
            None,
        )

    chat_id = int(chat_info["id"])
    chat_type = chat_info.get("type")
    bot_status = membership_status(api, chat_id, bot_id, issues)
    linked_chat_id = chat_info.get("linked_chat_id")
    linked_status = None
    if linked_chat_id:
        linked_status = membership_status(api, int(linked_chat_id), bot_id, issues)

    can_read_posts = False
    can_read_comments = False
    if chat_type == "channel":
        can_read_posts = is_admin_status(bot_status)
        can_read_comments = bool(linked_chat_id and is_member_status(linked_status) and bot.get("can_read_all_group_messages"))
        if not can_read_posts:
            issues.append("channel_admin_required")
        if not linked_chat_id:
            issues.append("linked_discussion_not_found")
        elif not can_read_comments:
            issues.append("discussion_group_access_required")
    elif chat_type in {"group", "supergroup"}:
        can_read_posts = is_member_status(bot_status) and bool(bot.get("can_read_all_group_messages"))
        can_read_comments = can_read_posts
        if not can_read_posts:
            issues.append("group_access_or_privacy_required")
    elif chat_type == "private":
        can_read_posts = True
        can_read_comments = False
    else:
        issues.append("unsupported_chat_type")

    return (
        TelegramSourceAccessStatus(
            ok=can_read_posts or can_read_comments,
            chat_id_or_username=chat_id_or_username,
            bot_username=bot_username,
            chat_id=chat_id,
            chat_username=chat_info.get("username"),
            chat_title=chat_info.get("title") or chat_info.get("first_name"),
            chat_type=chat_type,
            bot_status=bot_status,
            can_read_posts=can_read_posts,
            can_read_comments=can_read_comments,
            linked_discussion_chat_id=linked_chat_id,
            linked_discussion_bot_status=linked_status,
            issues=sorted(set(issues)),
        ),
        chat_info,
    )


def publish_source_event(session: Session, source: TelegramSource, event_type: str = "telegram_source") -> None:
    publish_realtime_event(
        session,
        event_type,
        {
            "id": source.id,
            "brand_id": source.brand_id,
            "source_category": source.source_category,
            "source_kind": source.source_kind,
            "username": source.username,
            "chat_id": source.chat_id,
            "title": source.title,
            "active": source.active,
            "monitor_from": source.monitor_from,
            "last_seen_message_id": source.last_seen_message_id,
        },
    )


def delete_source_and_notify(platform: str, source_id: uuid.UUID, session: Session) -> dict[str, Any]:
    try:
        result = delete_monitored_source(session, platform, source_id)
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    publish_realtime_event(
        session,
        f"{platform}_source",
        {
            "id": source_id,
            "deleted": True,
            "mentions_deleted": result["mentions_deleted"],
            "analyses_deleted": result["analyses_deleted"],
        },
    )
    return result


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/events")
async def realtime_events(request: Request) -> StreamingResponse:
    return StreamingResponse(
        realtime_event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/telegram/bot/status", response_model=TelegramBotStatus)
def telegram_bot_status() -> TelegramBotStatus:
    settings = get_settings()
    try:
        bot = TelegramBotApi(settings.telegram_bot_token).get_me()
    except Exception as exc:
        return TelegramBotStatus(ok=False, error=str(exc))
    return TelegramBotStatus(ok=True, **(bot or {}))


@app.get("/telegram/source-categories", response_model=list[TelegramSourceCategory])
def telegram_source_categories(request: Request) -> list[dict[str, str]]:
    return localize_source_categories(SOURCE_CATEGORIES, request_language(request))


@app.get("/telegram/backfill/session-status", response_model=TelegramSessionStatus)
async def telegram_backfill_session_status() -> TelegramSessionStatus:
    settings = get_settings()
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        return TelegramSessionStatus(configured=False, authorized=False, error="TELEGRAM_API_ID and TELEGRAM_API_HASH are required")

    client = TelegramClient(settings.telegram_session_name, settings.telegram_api_id, settings.telegram_api_hash)
    await client.connect()
    try:
        authorized = await client.is_user_authorized()
        if not authorized:
            return TelegramSessionStatus(configured=True, authorized=False, session_name=settings.telegram_session_name)
        me = await client.get_me()
        return TelegramSessionStatus(
            configured=True,
            authorized=True,
            session_name=settings.telegram_session_name,
            user_id=getattr(me, "id", None),
            username=getattr(me, "username", None),
            phone=mask_phone(getattr(me, "phone", None)),
        )
    except Exception as exc:
        return TelegramSessionStatus(configured=True, authorized=False, session_name=settings.telegram_session_name, error=str(exc))
    finally:
        await client.disconnect()


@app.post("/brands", response_model=BrandOut)
def create_brand(payload: BrandCreate, session: DbSession) -> Brand:
    brand = Brand(**payload.model_dump())
    session.add(brand)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Bu nomdagi brand allaqachon mavjud") from exc
    session.refresh(brand)
    invalidate_brand_cache()
    return brand


@app.get("/brands/taxonomy")
def brand_taxonomy(request: Request) -> dict[str, Any]:
    return localize_taxonomy(BRAND_TAXONOMY, request_language(request))


@app.get("/brand-taxonomy")
def brand_taxonomy_stable(request: Request) -> dict[str, Any]:
    return localize_taxonomy(BRAND_TAXONOMY, request_language(request))


@app.post("/brands/profile-suggestions", response_model=BrandProfileSuggestion)
def brand_profile_suggestions(payload: BrandProfileSuggestRequest, request: Request) -> dict[str, Any]:
    settings = get_settings()
    language = request_language(request)
    try:
        client = create_gemini_client(settings)
        context = payload.model_dump()
        context["language"] = language
        return suggest_brand_profile(settings, client, context)
    except Exception as exc:
        prefix = {
            "uz": "AI profil tavsiyasi hozir olinmadi",
            "ru": "Сейчас не удалось получить рекомендации ИИ для профиля",
            "en": "AI profile suggestions are currently unavailable",
        }[language]
        raise HTTPException(status_code=503, detail=f"{prefix}: {exc}") from exc


@app.get("/brands", response_model=list[BrandOut])
def list_brands(session: DbSession) -> list[Brand]:
    return session.query(Brand).order_by(Brand.created_at.desc()).all()


@app.get("/brands/{brand_id}", response_model=BrandOut)
def get_brand(brand_id: uuid.UUID, session: DbSession) -> Brand:
    brand = session.get(Brand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand


@app.patch("/brands/{brand_id}", response_model=BrandOut)
def update_brand(brand_id: uuid.UUID, payload: BrandUpdate, session: DbSession) -> Brand:
    brand = session.get(Brand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(brand, field, value)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Bu nomdagi brand allaqachon mavjud") from exc
    session.refresh(brand)
    invalidate_brand_cache()
    return brand


@app.post("/telegram/sources", response_model=TelegramSourceOut)
def create_telegram_source(payload: TelegramSourceCreate, session: DbSession) -> TelegramSource:
    data = payload.model_dump()
    if data.get("username"):
        data["username"] = str(data["username"]).lstrip("@")
    data["monitor_from"] = monitor_start_or_today(data.get("monitor_from"))
    source = TelegramSource(**data)
    session.add(source)
    session.commit()
    session.refresh(source)
    publish_source_event(session, source, "telegram_source")
    return source


@app.post("/telegram/sources/resolve", response_model=TelegramSourceOut)
def resolve_telegram_source(payload: TelegramSourceResolve, session: DbSession) -> TelegramSource:
    settings = get_settings()
    api = TelegramBotApi(settings.telegram_bot_token)
    chat_ref = normalize_chat_ref(payload.chat_id_or_username)
    chat_info = api.get_chat(chat_ref)
    if not chat_info:
        raise HTTPException(status_code=404, detail="Telegram chat not found or bot has no access")

    source = upsert_telegram_source_from_chat(
        session,
        chat_info=chat_info,
        brand_id=payload.brand_id,
        source_category=payload.source_category,
        monitoring_mode=payload.monitoring_mode,
        competitor_name=payload.competitor_name,
        notes=payload.notes,
        collect_posts=payload.collect_posts,
        collect_comments=payload.collect_comments,
        monitor_from=monitor_start_or_today(payload.monitor_from),
    )
    upsert_related_telegram_source(
        api,
        session,
        parent_chat_info=chat_info,
        parent_source=source,
        brand_id=payload.brand_id,
        source_category=payload.source_category,
        monitoring_mode=payload.monitoring_mode,
        collect_comments=payload.collect_comments,
        monitor_from=source.monitor_from,
    )
    session.commit()
    session.refresh(source)
    publish_source_event(session, source, "telegram_source")
    return source


@app.post("/telegram/sources/access-check", response_model=TelegramSourceAccessStatus)
def check_telegram_source_access(payload: TelegramSourceAccessCheck) -> TelegramSourceAccessStatus:
    settings = get_settings()
    api = TelegramBotApi(settings.telegram_bot_token)
    status, _ = build_access_status(api, payload.chat_id_or_username)
    return status


@app.post("/telegram/sources/import", response_model=list[TelegramSourceImportResult])
def import_telegram_sources(payload: TelegramSourceImport, session: DbSession) -> list[TelegramSourceImportResult]:
    settings = get_settings()
    api = TelegramBotApi(settings.telegram_bot_token)
    results: list[TelegramSourceImportResult] = []

    for row in parse_import_rows(payload.raw_text, payload.default_source_category, payload.default_monitoring_mode):
        ref = str(row["ref"] or "")
        source_category = str(row["source_category"] or payload.default_source_category)
        monitoring_mode = str(row["monitoring_mode"] or payload.default_monitoring_mode)
        competitor_name = row["competitor_name"]
        notes = row["notes"]
        try:
            monitor_from = monitor_start_or_today(parse_date_field(row["monitor_from"]) or payload.default_monitor_from)
            try:
                chat_info = api.get_chat(normalize_chat_ref(ref))
            except Exception:
                chat_info = None

            if chat_info:
                source = upsert_telegram_source_from_chat(
                    session,
                    chat_info=chat_info,
                    brand_id=payload.brand_id,
                    source_category=source_category,
                    monitoring_mode=monitoring_mode,
                    competitor_name=str(competitor_name) if competitor_name else None,
                    notes=str(notes) if notes else None,
                    collect_posts=payload.collect_posts,
                    collect_comments=payload.collect_comments,
                    monitor_from=monitor_from,
                )
                upsert_related_telegram_source(
                    api,
                    session,
                    parent_chat_info=chat_info,
                    parent_source=source,
                    brand_id=payload.brand_id,
                    source_category=source_category,
                    monitoring_mode=monitoring_mode,
                    collect_comments=payload.collect_comments,
                    monitor_from=source.monitor_from,
                )
                status = "resolved"
            else:
                source = upsert_catalog_source(
                    session,
                    ref=ref,
                    brand_id=payload.brand_id,
                    source_category=source_category,
                    monitoring_mode=monitoring_mode,
                    competitor_name=str(competitor_name) if competitor_name else None,
                    notes=str(notes) if notes else None,
                    collect_posts=payload.collect_posts,
                    collect_comments=payload.collect_comments,
                    monitor_from=monitor_from,
                )
                status = "cataloged"
            session.commit()
            session.refresh(source)
            publish_source_event(session, source, "telegram_source")
            results.append(TelegramSourceImportResult(ref=ref, status=status, source=source))
        except IntegrityError as exc:
            session.rollback()
            results.append(TelegramSourceImportResult(ref=ref, status="error", error=str(exc.orig)))
        except Exception as exc:
            session.rollback()
            results.append(TelegramSourceImportResult(ref=ref, status="error", error=str(exc)))

    return results


@app.get("/telegram/sources", response_model=list[TelegramSourceOut])
def list_telegram_sources(session: DbSession) -> list[TelegramSource]:
    return session.query(TelegramSource).order_by(TelegramSource.created_at.desc()).all()


@app.patch("/telegram/sources/{source_id}", response_model=TelegramSourceOut)
def update_telegram_source(source_id: uuid.UUID, payload: TelegramSourceUpdate, session: DbSession) -> TelegramSource:
    source = session.get(TelegramSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Telegram source not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "monitor_from":
            value = monitor_start_or_today(value)
        if field == "hashtags":
            value = parse_hashtags(value)
        setattr(source, field, value)
    session.commit()
    session.refresh(source)
    publish_source_event(session, source, "telegram_source")
    return source


@app.delete("/telegram/sources/{source_id}", response_model=SourceDeleteResult)
def delete_telegram_source(source_id: uuid.UUID, session: DbSession) -> dict[str, Any]:
    return delete_source_and_notify("telegram", source_id, session)


@app.post("/telegram/sources/{source_id}/refresh", response_model=TelegramSourceRefreshResult)
def refresh_telegram_source(source_id: uuid.UUID, session: DbSession) -> TelegramSourceRefreshResult:
    source = session.get(TelegramSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Telegram source not found")

    source_ref: int | str | None = source.chat_id or (f"@{source.username}" if source.username else None)
    if source_ref is None:
        raise HTTPException(status_code=400, detail="Source has no chat_id or username")

    settings = get_settings()
    api = TelegramBotApi(settings.telegram_bot_token)
    access, chat_info = build_access_status(api, source_ref)
    linked_source = None

    if chat_info:
        source.source_kind = chat_info.get("type") or source.source_kind
        source.chat_id = chat_info.get("id")
        source.username = chat_info.get("username")
        source.title = chat_info.get("title") or chat_info.get("first_name") or source.title
        source.description = chat_info.get("description")
        source.linked_discussion_chat_id = chat_info.get("linked_chat_id")
        linked_source = upsert_related_telegram_source(
            api,
            session,
            parent_chat_info=chat_info,
            parent_source=source,
            brand_id=source.brand_id,
            source_category=source.source_category,
            monitoring_mode=source.monitoring_mode,
            collect_comments=source.collect_comments,
            monitor_from=source.monitor_from,
        )

    session.commit()
    session.refresh(source)
    if linked_source:
        session.refresh(linked_source)
        publish_source_event(session, linked_source, "telegram_source")
    publish_source_event(session, source, "telegram_source")
    return TelegramSourceRefreshResult(source=source, access=access, linked_source=linked_source)


@app.post("/telegram/sources/{source_id}/backfill", response_model=TelegramSourceBackfillResult)
def backfill_telegram_source(
    source_id: uuid.UUID,
    payload: TelegramSourceBackfillRequest,
    session: DbSession,
) -> TelegramSourceBackfillResult:
    source = session.get(TelegramSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Telegram source not found")

    source_ref: int | str | None = source.username or source.chat_id
    if source_ref is None:
        raise HTTPException(status_code=400, detail="Source has no chat_id or username")

    settings = get_settings()
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        return TelegramSourceBackfillResult(
            source_id=source.id,
            source_ref=source_ref,
            ok=False,
            error="TELEGRAM_API_ID and TELEGRAM_API_HASH are required for backfill",
        )

    async def run_backfill() -> dict[str, int]:
        client = TelegramClient(settings.telegram_session_name, settings.telegram_api_id, settings.telegram_api_hash)
        await client.connect()
        try:
            if not await client.is_user_authorized():
                raise RuntimeError("Telethon session is not authorized. Run backend/scripts/telegram_login.py first.")
            from_date = start_of_day_utc(payload.from_date) or source.monitor_from or source.created_at
            return await backfill_source(
                client,
                source_ref,
                payload.limit,
                payload.comments_per_post,
                from_date=from_date,
            )
        finally:
            await client.disconnect()

    try:
        counts = asyncio.run(run_backfill())
    except Exception as exc:
        return TelegramSourceBackfillResult(source_id=source.id, source_ref=source_ref, ok=False, error=str(exc))

    session.refresh(source)
    return TelegramSourceBackfillResult(
        source_id=source.id,
        source_ref=source_ref,
        posts_seen=counts.get("posts_seen", 0),
        comments_seen=counts.get("comments_seen", 0),
        ok=True,
    )


@app.get("/youtube/status", response_model=YouTubeStatus)
def youtube_status(request: Request) -> YouTubeStatus:
    settings = get_settings()
    configured = bool(settings.youtube_api_key)
    return YouTubeStatus(
        configured=configured,
        api_key_present=configured,
        comments_supported=True,
        videos_supported=True,
        transcripts_supported=False,
        notes=localize_strings(
            [
                "YouTube Data API commentThreads orqali public video commentlarini olish mumkin.",
                "Transcript/audio AI keyingi bosqichda alohida pipeline bo'ladi.",
            ],
            request_language(request),
        ),
    )


@app.get("/youtube/source-categories", response_model=list[YouTubeSourceCategory])
def youtube_source_categories(request: Request) -> list[dict[str, str]]:
    return localize_source_categories(YOUTUBE_SOURCE_CATEGORIES, request_language(request))


@app.get("/youtube/sources", response_model=list[YouTubeSourceOut])
def list_youtube_sources(session: DbSession) -> list[YouTubeSource]:
    return session.query(YouTubeSource).order_by(YouTubeSource.created_at.desc()).all()


@app.post("/youtube/sources/import", response_model=list[YouTubeSourceImportResult])
def import_youtube_sources(payload: YouTubeSourceImport, session: DbSession) -> list[YouTubeSourceImportResult]:
    settings = get_settings()
    api = YouTubeApi(settings.youtube_api_key)
    results: list[YouTubeSourceImportResult] = []

    for row in parse_youtube_import_rows(payload.raw_text, payload.default_source_category, payload.default_monitoring_mode):
        ref = str(row["ref"] or "")
        try:
            row_hashtags = parse_hashtags(row["hashtags"])
            source = upsert_youtube_source(
                session,
                ref=ref,
                brand_id=payload.brand_id,
                source_category=str(row["source_category"] or payload.default_source_category),
                monitoring_mode=str(row["monitoring_mode"] or payload.default_monitoring_mode),
                nickname=str(row["competitor_name"]) if row["competitor_name"] else None,
                competitor_name=str(row["competitor_name"]) if row["competitor_name"] else None,
                hashtags=merge_hashtags(row_hashtags or payload.default_hashtags),
                notes=str(row["notes"]) if row["notes"] else None,
                collect_videos=payload.collect_videos,
                collect_comments=payload.collect_comments,
                collect_transcripts=payload.collect_transcripts,
                monitor_from=monitor_start_or_today(parse_date_field(row["monitor_from"]) or payload.default_monitor_from),
                api=api,
            )
            session.commit()
            session.refresh(source)
            publish_youtube_source_event(session, source)
            results.append(YouTubeSourceImportResult(ref=ref, status="resolved" if api.configured else "cataloged", source=source))
        except IntegrityError as exc:
            session.rollback()
            results.append(YouTubeSourceImportResult(ref=ref, status="error", error=str(exc.orig)))
        except Exception as exc:
            session.rollback()
            results.append(YouTubeSourceImportResult(ref=ref, status="error", error=str(exc)))

    return results


@app.patch("/youtube/sources/{source_id}", response_model=YouTubeSourceOut)
def update_youtube_source(source_id: uuid.UUID, payload: YouTubeSourceUpdate, session: DbSession) -> YouTubeSource:
    source = session.get(YouTubeSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="YouTube source not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "monitor_from":
            value = monitor_start_or_today(value)
        setattr(source, field, value)
    session.commit()
    session.refresh(source)
    publish_youtube_source_event(session, source)
    return source


@app.delete("/youtube/sources/{source_id}", response_model=SourceDeleteResult)
def delete_youtube_source(source_id: uuid.UUID, session: DbSession) -> dict[str, Any]:
    return delete_source_and_notify("youtube", source_id, session)


@app.post("/youtube/sources/{source_id}/sync", response_model=YouTubeSourceSyncResult)
def sync_youtube_source_endpoint(
    source_id: uuid.UUID,
    payload: YouTubeSourceSyncRequest,
    session: DbSession,
) -> YouTubeSourceSyncResult:
    source = session.get(YouTubeSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="YouTube source not found")
    api = YouTubeApi(get_settings().youtube_api_key)
    return sync_youtube_source(session, source, api, payload)


@app.get("/youtube/mentions", response_model=list[YouTubeMentionOut])
def list_youtube_mentions(
    session: DbSession,
    brand_id: uuid.UUID | None = None,
    item_type: str | None = None,
    limit: int | None = Query(default=100, ge=1, le=10000),
) -> list[YouTubeMentionOut]:
    latest_time = func.coalesce(YouTubeMention.published_at, YouTubeMention.created_at)
    query = session.query(YouTubeMention).order_by(latest_time.desc(), YouTubeMention.created_at.desc())
    if brand_id:
        query = query.filter(YouTubeMention.brand_id == brand_id)
    if item_type:
        query = query.filter(YouTubeMention.item_type == item_type)
    if limit:
        query = query.limit(limit)
    rows = query.all()
    if not rows:
        return []
    analyses = {
        a.youtube_mention_id: a
        for a in session.query(YouTubeAnalysis).filter(
            YouTubeAnalysis.youtube_mention_id.in_([row.id for row in rows])
        )
    }
    out: list[YouTubeMentionOut] = []
    for mention in rows:
        item = YouTubeMentionOut.model_validate(mention)
        analysis = analyses.get(mention.id)
        if analysis is not None:
            item.analysis = InlineAnalysisOut.model_validate(analysis)
        out.append(item)
    return out


@app.get("/youtube/summary", response_model=YouTubeSummary)
def youtube_summary(session: DbSession, brand_id: uuid.UUID | None = None) -> YouTubeSummary:
    source_query = session.query(YouTubeSource)
    mention_query = session.query(YouTubeMention)
    analysis_query = (
        session.query(YouTubeAnalysis)
        .join(YouTubeMention, YouTubeAnalysis.youtube_mention_id == YouTubeMention.id)
        .filter(YouTubeAnalysis.error.is_(None))
    )
    if brand_id:
        source_query = source_query.filter(YouTubeSource.brand_id == brand_id)
        mention_query = mention_query.filter(YouTubeMention.brand_id == brand_id)
        analysis_query = analysis_query.filter(YouTubeMention.brand_id == brand_id)

    mentions_total = mention_query.count()
    analyzed_total = analysis_query.count()
    analysis_denominator = max(mentions_total, analyzed_total)

    return YouTubeSummary(
        sources_total=source_query.count(),
        mentions_total=mentions_total,
        comments_total=mention_query.filter(YouTubeMention.item_type.in_(["comment", "comment_reply"])).count(),
        videos_total=mention_query.filter(YouTubeMention.item_type == "video").count(),
        analyzed_total=analyzed_total,
        analysis_coverage=round(analyzed_total / analysis_denominator, 3) if analysis_denominator else 0,
        high_risk=analysis_query.filter(YouTubeAnalysis.risk_level.in_(["high", "critical"])).count(),
        latest_mentions=mention_query.order_by(
            func.coalesce(YouTubeMention.published_at, YouTubeMention.created_at).desc(),
            YouTubeMention.created_at.desc(),
        ).limit(10).all(),
    )


def bounded_days(days: int) -> int:
    return max(1, min(180, days))


def mention_time(value: datetime | None, fallback: datetime) -> datetime:
    return normalize_aware(value) or normalize_aware(fallback) or datetime.now(timezone.utc)


def dashboard_timezone(tz_name: str | None = None) -> tuple[timezone | ZoneInfo, str]:
    if tz_name:
        try:
            return ZoneInfo(tz_name), tz_name
        except ZoneInfoNotFoundError:
            pass
    return LOCAL_TZ, "Asia/Tashkent"


def utc_offset_label(tz: timezone | ZoneInfo, at_time: datetime) -> str:
    offset = at_time.astimezone(tz).utcoffset() or timedelta()
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    hours, minutes = divmod(total_minutes, 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


def normalize_interval(days: int, interval: str | None) -> str:
    if interval in {"hour", "day", "week", "month"}:
        return interval
    if days <= 1:
        return "hour"
    if days >= 90:
        return "week"
    return "day"


def trend_bucket_start(value: datetime, interval: str, tz: timezone) -> datetime:
    local_value = value.astimezone(tz)
    if interval == "hour":
        return local_value.replace(minute=0, second=0, microsecond=0)
    if interval == "week":
        day_start = local_value.replace(hour=0, minute=0, second=0, microsecond=0)
        return day_start - timedelta(days=day_start.weekday())
    if interval == "month":
        return local_value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return local_value.replace(hour=0, minute=0, second=0, microsecond=0)


def next_bucket_start(value: datetime, interval: str) -> datetime:
    if interval == "hour":
        return value + timedelta(hours=1)
    if interval == "week":
        return value + timedelta(days=7)
    if interval == "month":
        year = value.year + (1 if value.month == 12 else 0)
        month = 1 if value.month == 12 else value.month + 1
        return value.replace(year=year, month=month, day=1)
    return value + timedelta(days=1)


def trend_bucket_label(value: datetime, interval: str) -> str:
    if interval == "hour":
        return value.strftime("%H:00")
    if interval == "week":
        end_value = value + timedelta(days=6)
        return f"{value.strftime('%d.%m')}-{end_value.strftime('%d.%m')}"
    if interval == "month":
        return value.strftime("%m.%Y")
    return value.strftime("%d.%m")


def empty_trend_row(bucket_start: datetime, interval: str) -> dict[str, Any]:
    bucket_end = next_bucket_start(bucket_start, interval)
    return {
        "bucket": bucket_start.isoformat(),
        "label": trend_bucket_label(bucket_start, interval),
        "start_at": bucket_start,
        "end_at": bucket_end,
        "telegram": 0,
        "youtube": 0,
        "instagram": 0,
        "facebook": 0,
        "total": 0,
        "comments": 0,
        "engagement": 0,
        "telegram_reactions": 0,
        "telegram_views": 0,
        "youtube_likes": 0,
        "youtube_views": 0,
        "youtube_video_comments": 0,
        "instagram_likes": 0,
        "instagram_replies": 0,
        "facebook_likes": 0,
        "facebook_replies": 0,
        "high_risk": 0,
    }


def telegram_raw_message(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    if raw.get("telethon") and isinstance(raw.get("message"), dict):
        return raw["message"]
    for key in ("message", "edited_message", "channel_post", "edited_channel_post"):
        message = raw.get(key)
        if isinstance(message, dict):
            return message
    return {}


def telegram_views(mention: Mention) -> int:
    message = telegram_raw_message(mention.raw)
    return int_or_none(message.get("views")) or 0


def telegram_reactions(mention: Mention) -> int:
    message = telegram_raw_message(mention.raw)
    reactions = message.get("reactions")
    if not isinstance(reactions, dict):
        return 0
    total = 0
    for item in reactions.get("results") or []:
        if isinstance(item, dict):
            total += int_or_none(item.get("count")) or 0
    return total


def scaled_next_7d(total: int, days: int) -> int:
    return round((total / max(1, days)) * 7)


def successful_analysis_rows(rows: list[Any]) -> list[Any]:
    return [row for row in rows if not row.error]


def ai_metric_payload(
    platform_totals: dict[str, int],
    platform_analyses: dict[str, list[Any]],
    active_sources: int,
) -> dict[str, Any]:
    all_rows = [row for rows in platform_analyses.values() for row in rows]
    successful_by_platform = {
        platform: successful_analysis_rows(rows)
        for platform, rows in platform_analyses.items()
    }
    successful_rows = [row for rows in successful_by_platform.values() for row in rows]
    total_mentions = sum(platform_totals.values())
    processed_total = len(all_rows)
    successful_total = len(successful_rows)
    failed_total = sum(1 for row in all_rows if row.error)
    error_rate = failed_total / processed_total if processed_total else 0

    platform_metrics: dict[str, dict[str, Any]] = {}
    for platform, mention_total in platform_totals.items():
        processed = len(platform_analyses.get(platform, []))
        successful = len(successful_by_platform.get(platform, []))
        platform_metrics[platform] = {
            "mentions": mention_total,
            "processed": processed,
            "analyzed": successful,
            "failed": processed - successful,
            "coverage": round(successful / mention_total, 3) if mention_total else 0,
            "processed_coverage": round(processed / mention_total, 3) if mention_total else 0,
        }

    coverage_values = [
        metric["coverage"]
        for platform, metric in platform_metrics.items()
        if platform_totals.get(platform, 0) > 0
    ]
    if len(coverage_values) > 1 and max(coverage_values) > 0:
        platform_balance = min(coverage_values) / max(coverage_values)
    elif coverage_values:
        platform_balance = 1
    else:
        platform_balance = 0

    total_coverage = successful_total / total_mentions if total_mentions else 0
    processed_coverage = processed_total / total_mentions if total_mentions else 0
    sample_confidence = min(1, successful_total / 120)
    source_confidence = min(1, active_sources / 8)
    reliability = 0
    if total_mentions:
        reliability = min(
            0.96,
            max(
                0,
                (total_coverage * 0.55)
                + (sample_confidence * 0.18)
                + (platform_balance * 0.12)
                + (source_confidence * 0.10)
                + ((1 - error_rate) * 0.05 if processed_total else 0),
            ),
        )

    sentiment_scores = [row.sentiment_score for row in successful_rows if row.sentiment_score is not None]
    risk_scores = [row.risk_score for row in successful_rows if row.risk_score is not None]

    return {
        "rows": all_rows,
        "successful_rows": successful_rows,
        "processed_total": processed_total,
        "successful_total": successful_total,
        "failed_total": failed_total,
        "total_coverage": total_coverage,
        "processed_coverage": processed_coverage,
        "error_rate": error_rate,
        "platform_balance": platform_balance,
        "platforms": platform_metrics,
        "reliability": reliability,
        "avg_sentiment_score": sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0,
        "avg_risk_score": sum(risk_scores) / len(risk_scores) if risk_scores else 0,
    }


def forecast_payload(
    current_total: int,
    previous_total: int,
    analysis_coverage: float,
    active_sources: int,
    days: int,
    totals: dict[str, int],
) -> dict[str, Any]:
    daily_average = current_total / max(1, days)
    next_7d = round(daily_average * 7)
    if previous_total:
        change_percent = round(((current_total - previous_total) / previous_total) * 100, 1)
    else:
        change_percent = 100.0 if current_total else 0.0
    if change_percent > 8:
        direction = "o'sish"
    elif change_percent < -8:
        direction = "pasayish"
    else:
        direction = "barqaror"
    confidence = min(0.92, 0.32 + min(0.38, analysis_coverage * 0.38) + min(0.22, active_sources * 0.025))
    return {
        "next_7d_mentions": next_7d,
        "next_7d_comments": scaled_next_7d(totals.get("comments", 0), days),
        "next_7d_youtube_likes": scaled_next_7d(totals.get("youtube_likes", 0), days),
        "next_7d_youtube_views": scaled_next_7d(totals.get("youtube_views", 0), days),
        "next_7d_telegram_reactions": scaled_next_7d(totals.get("telegram_reactions", 0), days),
        "next_7d_instagram_likes": scaled_next_7d(totals.get("instagram_likes", 0), days),
        "next_7d_facebook_likes": scaled_next_7d(totals.get("facebook_likes", 0), days),
        "next_7d_dislikes": None,
        "daily_average": round(daily_average, 1),
        "previous_period_mentions": previous_total,
        "change_percent": change_percent,
        "direction": direction,
        "confidence": round(confidence, 2),
        "method": "AI sentiment/risk qamrovi + oxirgi davr trendi + oldingi davr solishtiruvi. Dislike public API orqali mavjud emas.",
    }


@app.get("/dashboard/analytics")
def dashboard_analytics(
    session: DbSession,
    brand_id: uuid.UUID | None = None,
    days: int = Query(default=30, ge=1, le=180),
    interval: str | None = Query(default=None, pattern="^(hour|day|week|month)$"),
    client_timezone: str | None = Query(default=None, alias="timezone", max_length=80),
) -> dict[str, Any]:
    days = bounded_days(days)
    interval = normalize_interval(days, interval)
    tz, tz_name = dashboard_timezone(client_timezone)
    end_local = datetime.now(tz)
    start_local = end_local - timedelta(days=days)
    end_at = end_local.astimezone(timezone.utc)
    start_at = start_local.astimezone(timezone.utc)
    previous_start = start_at - (end_at - start_at)

    telegram_query = session.query(Mention).filter(func.coalesce(Mention.message_date, Mention.created_at) >= start_at)
    youtube_query = session.query(YouTubeMention).filter(func.coalesce(YouTubeMention.published_at, YouTubeMention.created_at) >= start_at)
    instagram_query = session.query(InstagramMention).filter(func.coalesce(InstagramMention.published_at, InstagramMention.created_at) >= start_at)
    facebook_query = session.query(FacebookMention).filter(func.coalesce(FacebookMention.published_at, FacebookMention.created_at) >= start_at)
    previous_telegram_query = session.query(Mention).filter(
        func.coalesce(Mention.message_date, Mention.created_at) >= previous_start,
        func.coalesce(Mention.message_date, Mention.created_at) < start_at,
    )
    previous_youtube_query = session.query(YouTubeMention).filter(
        func.coalesce(YouTubeMention.published_at, YouTubeMention.created_at) >= previous_start,
        func.coalesce(YouTubeMention.published_at, YouTubeMention.created_at) < start_at,
    )
    previous_instagram_query = session.query(InstagramMention).filter(
        func.coalesce(InstagramMention.published_at, InstagramMention.created_at) >= previous_start,
        func.coalesce(InstagramMention.published_at, InstagramMention.created_at) < start_at,
    )
    previous_facebook_query = session.query(FacebookMention).filter(
        func.coalesce(FacebookMention.published_at, FacebookMention.created_at) >= previous_start,
        func.coalesce(FacebookMention.published_at, FacebookMention.created_at) < start_at,
    )
    telegram_sources_query = session.query(TelegramSource)
    youtube_sources_query = session.query(YouTubeSource)
    instagram_sources_query = session.query(InstagramSource)
    facebook_sources_query = session.query(FacebookSource)
    analysis_query = session.query(Analysis).join(Mention).filter(func.coalesce(Mention.message_date, Mention.created_at) >= start_at)
    youtube_analysis_query = (
        session.query(YouTubeAnalysis)
        .join(YouTubeMention, YouTubeAnalysis.youtube_mention_id == YouTubeMention.id)
        .filter(func.coalesce(YouTubeMention.published_at, YouTubeMention.created_at) >= start_at)
    )
    instagram_analysis_query = (
        session.query(InstagramAnalysis)
        .join(InstagramMention, InstagramAnalysis.instagram_mention_id == InstagramMention.id)
        .filter(func.coalesce(InstagramMention.published_at, InstagramMention.created_at) >= start_at)
    )
    facebook_analysis_query = (
        session.query(FacebookAnalysis)
        .join(FacebookMention, FacebookAnalysis.facebook_mention_id == FacebookMention.id)
        .filter(func.coalesce(FacebookMention.published_at, FacebookMention.created_at) >= start_at)
    )

    if brand_id:
        telegram_query = telegram_query.filter(Mention.brand_id == brand_id)
        youtube_query = youtube_query.filter(YouTubeMention.brand_id == brand_id)
        instagram_query = instagram_query.filter(InstagramMention.brand_id == brand_id)
        facebook_query = facebook_query.filter(FacebookMention.brand_id == brand_id)
        previous_telegram_query = previous_telegram_query.filter(Mention.brand_id == brand_id)
        previous_youtube_query = previous_youtube_query.filter(YouTubeMention.brand_id == brand_id)
        previous_instagram_query = previous_instagram_query.filter(InstagramMention.brand_id == brand_id)
        previous_facebook_query = previous_facebook_query.filter(FacebookMention.brand_id == brand_id)
        telegram_sources_query = telegram_sources_query.filter(TelegramSource.brand_id == brand_id)
        youtube_sources_query = youtube_sources_query.filter(YouTubeSource.brand_id == brand_id)
        instagram_sources_query = instagram_sources_query.filter(InstagramSource.brand_id == brand_id)
        facebook_sources_query = facebook_sources_query.filter(FacebookSource.brand_id == brand_id)
        analysis_query = analysis_query.filter(Mention.brand_id == brand_id)
        youtube_analysis_query = youtube_analysis_query.filter(YouTubeMention.brand_id == brand_id)
        instagram_analysis_query = instagram_analysis_query.filter(InstagramMention.brand_id == brand_id)
        facebook_analysis_query = facebook_analysis_query.filter(FacebookMention.brand_id == brand_id)

    telegram_event_time = func.coalesce(Mention.message_date, Mention.created_at).label("event_time")
    youtube_event_time = func.coalesce(YouTubeMention.published_at, YouTubeMention.created_at).label("event_time")
    instagram_event_time = func.coalesce(InstagramMention.published_at, InstagramMention.created_at).label("event_time")
    facebook_event_time = func.coalesce(FacebookMention.published_at, FacebookMention.created_at).label("event_time")

    telegram_mentions = telegram_query.with_entities(
        telegram_event_time,
        Mention.source_type.label("source_type"),
        Mention.raw.label("raw"),
    ).all()
    youtube_mentions = youtube_query.with_entities(
        youtube_event_time,
        YouTubeMention.item_type.label("item_type"),
        YouTubeMention.like_count.label("like_count"),
        YouTubeMention.view_count.label("view_count"),
        YouTubeMention.comment_count.label("comment_count"),
    ).all()
    instagram_mentions = instagram_query.with_entities(
        instagram_event_time,
        InstagramMention.item_type.label("item_type"),
        InstagramMention.like_count.label("like_count"),
        InstagramMention.reply_count.label("reply_count"),
    ).all()
    facebook_mentions = facebook_query.with_entities(
        facebook_event_time,
        FacebookMention.item_type.label("item_type"),
        FacebookMention.like_count.label("like_count"),
        FacebookMention.reply_count.label("reply_count"),
    ).all()
    analyses = analysis_query.with_entities(
        Analysis.error.label("error"),
        Analysis.sentiment.label("sentiment"),
        Analysis.sentiment_score.label("sentiment_score"),
        Analysis.risk_level.label("risk_level"),
        Analysis.risk_score.label("risk_score"),
        telegram_event_time,
    ).all()
    youtube_analyses = youtube_analysis_query.with_entities(
        YouTubeAnalysis.error.label("error"),
        YouTubeAnalysis.sentiment.label("sentiment"),
        YouTubeAnalysis.sentiment_score.label("sentiment_score"),
        YouTubeAnalysis.risk_level.label("risk_level"),
        YouTubeAnalysis.risk_score.label("risk_score"),
        youtube_event_time,
    ).all()
    instagram_analyses = instagram_analysis_query.with_entities(
        InstagramAnalysis.error.label("error"),
        InstagramAnalysis.sentiment.label("sentiment"),
        InstagramAnalysis.sentiment_score.label("sentiment_score"),
        InstagramAnalysis.risk_level.label("risk_level"),
        InstagramAnalysis.risk_score.label("risk_score"),
        instagram_event_time,
    ).all()
    facebook_analyses = facebook_analysis_query.with_entities(
        FacebookAnalysis.error.label("error"),
        FacebookAnalysis.sentiment.label("sentiment"),
        FacebookAnalysis.sentiment_score.label("sentiment_score"),
        FacebookAnalysis.risk_level.label("risk_level"),
        FacebookAnalysis.risk_score.label("risk_score"),
        facebook_event_time,
    ).all()
    telegram_sources = telegram_sources_query.all()
    youtube_sources = youtube_sources_query.all()
    instagram_sources = instagram_sources_query.all()
    facebook_sources = facebook_sources_query.all()
    selected_brand = session.get(Brand, brand_id) if brand_id else None

    trend_map: dict[str, dict[str, Any]] = {}
    bucket = trend_bucket_start(start_at, interval, tz)
    end_bucket = trend_bucket_start(end_at, interval, tz)
    while bucket <= end_bucket:
        trend_map[bucket.isoformat()] = empty_trend_row(bucket, interval)
        bucket = next_bucket_start(bucket, interval)

    telegram_comment_count = 0
    telegram_post_count = 0
    telegram_view_count = 0
    telegram_reaction_count = 0
    for mention in telegram_mentions:
        event_time = mention_time(mention.event_time, mention.event_time)
        bucket_start = trend_bucket_start(event_time, interval, tz)
        key = bucket_start.isoformat()
        row = trend_map.setdefault(key, empty_trend_row(bucket_start, interval))
        row["telegram"] += 1
        row["total"] += 1
        if mention.source_type in {"comment", "group_message", "message"}:
            telegram_comment_count += 1
            row["comments"] += 1
        if mention.source_type == "channel_post":
            telegram_post_count += 1
        views = telegram_views(mention)
        reactions = telegram_reactions(mention)
        telegram_view_count += views
        telegram_reaction_count += reactions
        row["engagement"] += reactions
        row["telegram_reactions"] += reactions
        row["telegram_views"] += views

    youtube_comment_mentions = 0
    youtube_video_count = 0
    youtube_like_count = 0
    youtube_view_count = 0
    youtube_video_comment_count = 0
    for mention in youtube_mentions:
        event_time = mention_time(mention.event_time, mention.event_time)
        bucket_start = trend_bucket_start(event_time, interval, tz)
        key = bucket_start.isoformat()
        row = trend_map.setdefault(key, empty_trend_row(bucket_start, interval))
        row["youtube"] += 1
        row["total"] += 1
        likes = mention.like_count or 0
        youtube_like_count += likes
        row["engagement"] += likes
        row["youtube_likes"] += likes
        if mention.item_type == "video":
            youtube_video_count += 1
            views = mention.view_count or 0
            video_comments = mention.comment_count or 0
            youtube_view_count += views
            youtube_video_comment_count += video_comments
            row["youtube_views"] += views
            row["youtube_video_comments"] += video_comments
        if mention.item_type in {"comment", "comment_reply"}:
            youtube_comment_mentions += 1
            row["comments"] += 1

    instagram_comment_count = 0
    instagram_direct_mention_count = 0
    instagram_caption_count = 0
    instagram_like_count = 0
    instagram_reply_count = 0
    for mention in instagram_mentions:
        event_time = mention_time(mention.event_time, mention.event_time)
        bucket_start = trend_bucket_start(event_time, interval, tz)
        key = bucket_start.isoformat()
        row = trend_map.setdefault(key, empty_trend_row(bucket_start, interval))
        row["instagram"] += 1
        row["total"] += 1
        likes = mention.like_count or 0
        replies = mention.reply_count or 0
        instagram_like_count += likes
        instagram_reply_count += replies
        row["engagement"] += likes + replies
        row["instagram_likes"] += likes
        row["instagram_replies"] += replies
        if mention.item_type == "comment":
            instagram_comment_count += 1
            row["comments"] += 1
        elif mention.item_type == "mention":
            instagram_direct_mention_count += 1
        elif mention.item_type == "caption":
            instagram_caption_count += 1

    facebook_comment_count = 0
    facebook_reply_count = 0
    facebook_post_count = 0
    facebook_direct_mention_count = 0
    facebook_like_count = 0
    facebook_reply_engagement = 0
    for mention in facebook_mentions:
        event_time = mention_time(mention.event_time, mention.event_time)
        bucket_start = trend_bucket_start(event_time, interval, tz)
        key = bucket_start.isoformat()
        row = trend_map.setdefault(key, empty_trend_row(bucket_start, interval))
        row["facebook"] += 1
        row["total"] += 1
        likes = mention.like_count or 0
        replies = mention.reply_count or 0
        facebook_like_count += likes
        facebook_reply_engagement += replies
        row["engagement"] += likes + replies
        row["facebook_likes"] += likes
        row["facebook_replies"] += replies
        if mention.item_type == "comment":
            facebook_comment_count += 1
            row["comments"] += 1
        elif mention.item_type == "reply":
            facebook_reply_count += 1
            row["comments"] += 1
        elif mention.item_type == "post":
            facebook_post_count += 1
        elif mention.item_type == "mention":
            facebook_direct_mention_count += 1

    all_sources = [*telegram_sources, *youtube_sources, *instagram_sources, *facebook_sources]
    active_sources = sum(1 for source in all_sources if source.active)
    ai_metrics = ai_metric_payload(
        {
            "telegram": len(telegram_mentions),
            "youtube": len(youtube_mentions),
            "instagram": len(instagram_mentions),
            "facebook": len(facebook_mentions),
        },
        {
            "telegram": analyses,
            "youtube": youtube_analyses,
            "instagram": instagram_analyses,
            "facebook": facebook_analyses,
        },
        active_sources,
    )
    successful_ai_rows = ai_metrics["successful_rows"]
    sentiment_counts = Counter(analysis.sentiment or "unknown" for analysis in successful_ai_rows)
    risk_counts = Counter(analysis.risk_level or "unknown" for analysis in successful_ai_rows)
    for analysis in successful_ai_rows:
        if analysis.risk_level in {"high", "critical"}:
            bucket_start = trend_bucket_start(mention_time(analysis.event_time, analysis.event_time), interval, tz)
            key = bucket_start.isoformat()
            if key in trend_map:
                trend_map[key]["high_risk"] += 1

    trend_rows = sorted(trend_map.values(), key=lambda row: row["start_at"])
    current_total = len(telegram_mentions) + len(youtube_mentions) + len(instagram_mentions) + len(facebook_mentions)
    previous_total = previous_telegram_query.count() + previous_youtube_query.count() + previous_instagram_query.count() + previous_facebook_query.count()
    analyzed_total = ai_metrics["successful_total"]
    total_ai_coverage = ai_metrics["total_coverage"]

    return {
        "filter": {
            "brand_id": str(brand_id) if brand_id else None,
            "brand_name": selected_brand.name if selected_brand else "Barcha brandlar",
            "is_brand_filtered": bool(brand_id),
            "scope": "Tanlangan brand/client bo'yicha" if brand_id else "Barcha brandlar umumiy oqimi",
        },
        "period": {
            "days": days,
            "interval": interval,
            "timezone": tz_name,
            "utc_offset": utc_offset_label(tz, end_at),
            "start_at": start_at,
            "end_at": end_at,
        },
        "sources": {
            "total": len(all_sources),
            "active": active_sources,
            "telegram": len(telegram_sources),
            "youtube": len(youtube_sources),
            "instagram": len(instagram_sources),
            "facebook": len(facebook_sources),
            "official_total": sum(1 for source in all_sources if source.source_category == "owned"),
            "official_telegram": sum(1 for source in telegram_sources if source.source_category == "owned"),
            "official_youtube": sum(1 for source in youtube_sources if source.source_category == "owned"),
            "official_instagram": sum(1 for source in instagram_sources if source.source_category == "owned"),
            "official_facebook": sum(1 for source in facebook_sources if source.source_category == "owned"),
            "invalid_meta_tokens": sum(
                1
                for source in [*instagram_sources, *facebook_sources]
                if source.active and source.token_status == "invalid"
            ),
        },
        "mentions": {
            "total": current_total,
            "telegram": len(telegram_mentions),
            "youtube": len(youtube_mentions),
            "instagram": len(instagram_mentions),
            "facebook": len(facebook_mentions),
            "telegram_posts": telegram_post_count,
            "telegram_comments": telegram_comment_count,
            "youtube_videos": youtube_video_count,
            "youtube_comments": youtube_comment_mentions,
            "instagram_comments": instagram_comment_count,
            "instagram_direct_mentions": instagram_direct_mention_count,
            "instagram_captions": instagram_caption_count,
            "facebook_comments": facebook_comment_count,
            "facebook_replies": facebook_reply_count,
            "facebook_posts": facebook_post_count,
            "facebook_direct_mentions": facebook_direct_mention_count,
            "analyzed": analyzed_total,
            "analysis_coverage": round(total_ai_coverage, 3),
            "processed_analysis_coverage": round(ai_metrics["processed_coverage"], 3),
            "telegram_analysis_coverage": ai_metrics["platforms"]["telegram"]["coverage"],
            "youtube_analysis_coverage": ai_metrics["platforms"]["youtube"]["coverage"],
            "instagram_analysis_coverage": ai_metrics["platforms"]["instagram"]["coverage"],
            "facebook_analysis_coverage": ai_metrics["platforms"]["facebook"]["coverage"],
            "ai_failed": ai_metrics["failed_total"],
        },
        "ai": {
            "model": get_settings().gemini_model,
            "provider": "vertex-gemini" if get_settings().gemini_use_vertex else "gemini",
            "analyzed_mentions": analyzed_total,
            "processed_mentions": ai_metrics["processed_total"],
            "failed_mentions": ai_metrics["failed_total"],
            "total_coverage": round(total_ai_coverage, 3),
            "processed_coverage": round(ai_metrics["processed_coverage"], 3),
            "telegram_coverage": ai_metrics["platforms"]["telegram"]["coverage"],
            "youtube_coverage": ai_metrics["platforms"]["youtube"]["coverage"],
            "instagram_coverage": ai_metrics["platforms"]["instagram"]["coverage"],
            "facebook_coverage": ai_metrics["platforms"]["facebook"]["coverage"],
            "platforms": ai_metrics["platforms"],
            "platform_balance": round(ai_metrics["platform_balance"], 3),
            "error_rate": round(ai_metrics["error_rate"], 3),
            "reliability": round(ai_metrics["reliability"], 2),
            "avg_sentiment_score": round(ai_metrics["avg_sentiment_score"], 3),
            "avg_risk_score": round(ai_metrics["avg_risk_score"], 3),
            "note": "Ijobiy/salbiy fikrlar Telegram, YouTube, Instagram va Facebook bo'yicha AI muvaffaqiyatli tahlil qilgan mentionlar asosida hisoblanadi.",
        },
        "engagement": {
            "telegram_views": telegram_view_count,
            "telegram_reactions": telegram_reaction_count,
            "youtube_views": youtube_view_count,
            "youtube_likes": youtube_like_count,
            "youtube_comment_count": youtube_video_comment_count,
            "instagram_likes": instagram_like_count,
            "instagram_replies": instagram_reply_count,
            "facebook_likes": facebook_like_count,
            "facebook_replies": facebook_reply_engagement,
            "youtube_dislikes": None,
            "youtube_dislikes_note": "YouTube public Data API dislike sonini bermaydi.",
        },
        "sentiment": dict(sentiment_counts),
        "risk": dict(risk_counts),
        "trend": trend_rows,
        "forecast": forecast_payload(
            current_total,
            previous_total,
            total_ai_coverage,
            active_sources,
            days,
            {
                "comments": telegram_comment_count + youtube_comment_mentions + instagram_comment_count + facebook_comment_count + facebook_reply_count,
                "youtube_likes": youtube_like_count,
                "youtube_views": youtube_view_count,
                "telegram_reactions": telegram_reaction_count,
                "instagram_likes": instagram_like_count,
                "facebook_likes": facebook_like_count,
            },
        ),
    }


@app.get("/mentions", response_model=list[MentionOut])
def list_mentions(
    session: DbSession,
    brand_id: uuid.UUID | None = None,
    source_type: str | None = None,
    limit: int | None = Query(default=100, ge=1, le=10000),
) -> list[MentionOut]:
    latest_time = func.coalesce(Mention.message_date, Mention.created_at)
    query = session.query(Mention).order_by(latest_time.desc(), Mention.created_at.desc())
    if brand_id:
        query = query.filter(Mention.brand_id == brand_id)
    if source_type:
        query = query.filter(Mention.source_type == source_type)
    if limit:
        query = query.limit(limit)
    rows = query.all()
    if not rows:
        return []
    analyses = {
        a.mention_id: a
        for a in session.query(Analysis).filter(Analysis.mention_id.in_([row.id for row in rows]))
    }
    out: list[MentionOut] = []
    for mention in rows:
        item = MentionOut.model_validate(mention)
        analysis = analyses.get(mention.id)
        if analysis is not None:
            item.analysis = InlineAnalysisOut.model_validate(analysis)
        out.append(item)
    return out


@app.get("/mentions/{mention_id}", response_model=MentionDetailOut)
def get_mention(mention_id: uuid.UUID, session: DbSession) -> Mention:
    mention = session.query(Mention).options(joinedload(Mention.analysis)).filter(Mention.id == mention_id).one_or_none()
    if not mention:
        raise HTTPException(status_code=404, detail="Mention not found")
    return mention


@app.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(session: DbSession, brand_id: uuid.UUID | None = None) -> DashboardSummary:
    mention_query = session.query(Mention)
    analysis_query = session.query(Analysis).join(Mention)
    if brand_id:
        mention_query = mention_query.filter(Mention.brand_id == brand_id)
        analysis_query = analysis_query.filter(Mention.brand_id == brand_id)

    mentions_total = mention_query.count()
    analyzed_total = analysis_query.count()
    sentiment_key = func.coalesce(Analysis.sentiment, "unknown")
    risk_key = func.coalesce(Analysis.risk_level, "unknown")
    sentiment_counts = dict(
        analysis_query.with_entities(sentiment_key, func.count(Analysis.id)).group_by(sentiment_key).all()
    )
    risk_counts = dict(
        analysis_query.with_entities(risk_key, func.count(Analysis.id)).group_by(risk_key).all()
    )
    latest_mentions = mention_query.order_by(
        func.coalesce(Mention.message_date, Mention.created_at).desc(),
        Mention.created_at.desc(),
    ).limit(10).all()

    return DashboardSummary(
        mentions_total=mentions_total,
        analyzed_total=analyzed_total,
        sentiment_counts=dict(sentiment_counts),
        risk_counts=dict(risk_counts),
        top_topics={},
        latest_mentions=latest_mentions,
    )


@app.get("/dashboard/timeseries")
def dashboard_timeseries(
    session: DbSession,
    brand_id: uuid.UUID | None = None,
    interval: str = Query(default="hour", pattern="^(hour|day)$"),
) -> list[dict[str, object]]:
    bucket = func.date_trunc(interval, Mention.message_date)
    query = session.query(bucket.label("bucket"), func.count(Mention.id).label("count")).filter(Mention.message_date.is_not(None))
    if brand_id:
        query = query.filter(Mention.brand_id == brand_id)
    rows = query.group_by(bucket).order_by(bucket.asc()).all()
    return [{"bucket": row.bucket, "count": row.count} for row in rows]


@app.get("/alerts/events", response_model=list[AlertEventOut])
def list_alert_events(session: DbSession, limit: int = Query(default=100, le=500)) -> list[AlertEvent]:
    return session.query(AlertEvent).order_by(AlertEvent.created_at.desc()).limit(limit).all()


# ============================ Instagram ============================
# Real-time comments/@mentions arrive as Meta webhooks (the "webhook alternative"
# like Bitrix24): Meta POSTs a minimal event, we fetch the full object via the
# Graph API using the connected account's token, then ingest + AI-analyze it.

INSTAGRAM_SOURCE_CATEGORIES = [
    {"key": "owned", "label": "Rasmiy akkaunt", "description": "Brendning o'z Instagram Business akkaunti."},
    {"key": "competitor", "label": "Raqobatchi", "description": "Raqobatchi akkaunt (mention/hashtag orqali)."},
    {"key": "influencer", "label": "Influencer", "description": "Bloger/ekspert akkauntlari."},
    {"key": "hashtag", "label": "Hashtag", "description": "Kuzatiladigan hashtag oqimi."},
    {"key": "unknown", "label": "Aniqlanmagan", "description": "Toifasiz."},
]


def _instagram_api_for(source: InstagramSource) -> InstagramApi:
    settings = get_settings()
    token = source.access_token or settings.ig_access_token
    if not token:
        raise HTTPException(status_code=400, detail="Instagram source has no access token")
    return InstagramApi(
        token,
        graph_version=settings.ig_graph_version,
        api_base=source.api_base or "graph.facebook.com",
    )


@app.get("/instagram/status", response_model=InstagramStatus)
def instagram_status(request: Request, session: DbSession) -> InstagramStatus:
    settings = get_settings()
    connected = session.query(InstagramSource).filter(InstagramSource.active.is_(True)).count()
    # Behind nginx the public API lives under /api (nginx strips it before proxying) and
    # the raw scheme is http — honor X-Forwarded-Proto so the operator sees the exact
    # public https URL Meta must call. Direct (dev) hits the backend at the root.
    fwd_scheme = request.headers.get("x-forwarded-proto")
    host = request.headers.get("x-forwarded-host") or request.url.netloc
    if fwd_scheme:
        callback = f"{fwd_scheme}://{host}/api/instagram/webhook"
    else:
        callback = f"{request.url.scheme}://{host}/instagram/webhook"
    return InstagramStatus(
        configured=bool(settings.ig_app_id and settings.ig_app_secret),
        enabled=settings.instagram_enabled,
        graph_version=settings.ig_graph_version,
        webhook_callback_url=callback,
        verify_token_set=bool(settings.ig_verify_token),
        connected_accounts=connected,
    )


@app.get("/instagram/source-categories")
def instagram_source_categories(request: Request) -> list[dict[str, str]]:
    return localize_source_categories(INSTAGRAM_SOURCE_CATEGORIES, request_language(request))


@app.get("/instagram/sources", response_model=list[InstagramSourceOut])
def list_instagram_sources(session: DbSession) -> list[InstagramSource]:
    return session.query(InstagramSource).order_by(InstagramSource.created_at.asc()).all()


@app.post("/instagram/sources", response_model=InstagramSourceOut)
def connect_instagram_source(payload: InstagramSourceCreate, session: DbSession) -> InstagramSource:
    settings = get_settings()
    # Auto-detect the account straight from the pasted token (works for page tokens,
    # user tokens, and Instagram-login tokens) — this both validates the token and
    # finds the ig_user_id/username, so the client only has to paste one token.
    try:
        detected = detect_account(payload.access_token, graph_version=settings.ig_graph_version)
    except InstagramApiError as exc:
        raise HTTPException(status_code=400, detail=f"Token ishlamadi — {exc}")
    ig_user_id = payload.ig_user_id or detected["ig_user_id"]
    existing = session.query(InstagramSource).filter(InstagramSource.ig_user_id == ig_user_id).one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Bu Instagram akkaunt allaqachon ulangan")
    provided_username = (payload.username or "").strip().lstrip("@") or None
    source = InstagramSource(
        brand_id=payload.brand_id,
        ig_user_id=ig_user_id,
        username=provided_username or detected.get("username"),
        account_name=payload.account_name or detected.get("username"),
        page_id=payload.page_id or detected.get("page_id"),
        # Prefer the detected token (a long-lived Page token when we resolved one).
        access_token=detected.get("access_token") or payload.access_token,
        api_base=detected["api_base"],
        token_status="active",
        status_detail=f"@{detected.get('username')} ({detected['api_base']})",
        last_checked_at=datetime.now(timezone.utc),
        source_category=payload.source_category,
        monitoring_mode=payload.monitoring_mode,
        collect_comments=payload.collect_comments,
        collect_mentions=payload.collect_mentions,
        hashtags=payload.hashtags,
        notes=payload.notes,
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


@app.post("/instagram/sources/{source_id}/validate", response_model=InstagramSourceOut)
def validate_instagram_source(source_id: uuid.UUID, session: DbSession) -> InstagramSource:
    """Re-check a source's token and refresh its status — used by the dashboard's
    'tekshirish' button and after a token swap."""
    source = session.get(InstagramSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Instagram source topilmadi")
    settings = get_settings()
    try:
        detected = detect_account(source.access_token or "", graph_version=settings.ig_graph_version)
        source.token_status = "active"
        source.api_base = detected["api_base"]
        source.username = detected.get("username") or source.username
        source.status_detail = f"@{detected.get('username')} ({detected['api_base']})"
    except InstagramApiError as exc:
        source.token_status = "invalid"
        source.status_detail = str(exc)[:400]
    source.last_checked_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(source)
    return source


@app.post("/instagram/sources/{source_id}/sync", response_model=InstagramSyncResult)
def sync_instagram_source_now(
    source_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: DbSession,
) -> InstagramSyncResult:
    """Fetch owned media, aggregate engagement, comments and replies immediately."""
    source = session.get(InstagramSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Instagram source topilmadi")
    try:
        settings = get_settings()
        stats = sync_instagram_source(
            session,
            settings,
            source,
            media_limit=settings.instagram_manual_sync_media_limit,
        )
    except InstagramApiError as exc:
        source.status_detail = str(exc)[:400]
        source.last_checked_at = datetime.now(timezone.utc)
        session.commit()
        raise HTTPException(status_code=400, detail=f"Instagram sync ishlamadi — {exc}")
    background_tasks.add_task(_analyze_instagram_mentions_now, stats.created_ids)
    return InstagramSyncResult(**stats.as_response())


@app.patch("/instagram/sources/{source_id}", response_model=InstagramSourceOut)
def update_instagram_source(source_id: uuid.UUID, payload: InstagramSourceUpdate, session: DbSession) -> InstagramSource:
    source = session.get(InstagramSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Instagram source topilmadi")
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(source, field, value)
    # A new token -> re-detect + re-validate so a client can swap accounts by just
    # pasting a fresh token.
    if updates.get("access_token"):
        try:
            detected = detect_account(source.access_token, graph_version=get_settings().ig_graph_version)
            source.access_token = detected.get("access_token") or source.access_token
            source.api_base = detected["api_base"]
            source.ig_user_id = detected["ig_user_id"]
            source.username = detected.get("username") or source.username
            source.token_status = "active"
            source.status_detail = f"@{detected.get('username')} ({detected['api_base']})"
        except InstagramApiError as exc:
            source.token_status = "invalid"
            source.status_detail = str(exc)[:400]
        source.last_checked_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(source)
    return source


@app.delete("/instagram/sources/{source_id}", response_model=SourceDeleteResult)
def delete_instagram_source(source_id: uuid.UUID, session: DbSession) -> dict[str, Any]:
    return delete_source_and_notify("instagram", source_id, session)


@app.get("/instagram/mentions", response_model=list[InstagramMentionOut])
def list_instagram_mentions(
    session: DbSession, brand_id: uuid.UUID | None = None, limit: int = Query(default=100, le=500)
) -> list[InstagramMentionOut]:
    query = session.query(InstagramMention)
    if brand_id:
        query = query.filter(InstagramMention.brand_id == brand_id)
    rows = query.order_by(InstagramMention.created_at.desc()).limit(limit).all()
    if not rows:
        return []
    # Attach each mention's AI verdict so the feed can show sentiment/risk/summary
    # inline (one extra query instead of N).
    analyses = {
        a.instagram_mention_id: a
        for a in session.query(InstagramAnalysis).filter(
            InstagramAnalysis.instagram_mention_id.in_([r.id for r in rows])
        )
    }
    out: list[InstagramMentionOut] = []
    for mention in rows:
        item = InstagramMentionOut.model_validate(mention)
        analysis = analyses.get(mention.id)
        if analysis is not None:
            item.analysis = InstagramAnalysisOut.model_validate(analysis)
        out.append(item)
    return out


@app.post("/instagram/mentions/manual", response_model=InstagramManualIngestResult)
def instagram_manual_ingest(
    payload: InstagramManualIngest, background_tasks: BackgroundTasks, session: DbSession
) -> InstagramManualIngestResult:
    """Meta'siz demo/qo'lda ingest: brendga tegishli kommentlarni to'g'ridan-to'g'ri
    AI quvuriga yuboradi. Token/webhook shart emas — Instagram real-time ulanmagan
    holatda ham to'liq sentiment/risk/summary tahlilini ko'rsatish uchun."""
    brand = session.get(Brand, payload.brand_id)
    if brand is None:
        raise HTTPException(status_code=404, detail="Brand topilmadi")

    items: list[dict[str, Any]] = []
    for comment in payload.comments or []:
        if (comment.text or "").strip():
            items.append(
                {"text": comment.text.strip(), "author_username": comment.author_username, "item_type": comment.item_type}
            )
    for line in (payload.raw_text or "").splitlines():
        if line.strip():
            items.append({"text": line.strip(), "author_username": None, "item_type": "comment"})
    if not items:
        raise HTTPException(status_code=400, detail="Kamida bitta komment matni kerak")

    now = datetime.now(timezone.utc)
    created_ids: list[uuid.UUID] = []
    for item in items:
        text = item["text"]
        item_type = item["item_type"] if item["item_type"] in ("comment", "mention", "caption") else "comment"
        mention = InstagramMention(
            source_id=None,
            brand_id=brand.id,
            external_id=f"manual:{uuid.uuid4()}",
            item_type=item_type,
            author_username=item.get("author_username") or "demo_user",
            text=text,
            normalized_text=normalize_text(text),
            permalink=payload.permalink,
            # A non-empty match term makes screen_and_analyze skip the cheap relevance
            # gate and run full Pro sentiment/risk — these were hand-picked for the brand.
            brand_match_terms=[brand.name] if brand.name else ["manual"],
            raw={"manual": True, "media_caption": payload.media_caption},
            published_at=now,
        )
        session.add(mention)
        session.commit()
        session.refresh(mention)
        created_ids.append(mention.id)
        publish_realtime_event(
            session,
            "instagram_mention",
            {
                "id": str(mention.id),
                "brand_id": str(brand.id),
                "platform": "instagram",
                "item_type": mention.item_type,
                "author_username": mention.author_username,
                "created_at": mention.created_at.isoformat() if isinstance(mention.created_at, datetime) else None,
            },
        )

    # Analyze immediately in the background so the demo shows AI verdicts within
    # seconds instead of waiting for the 5-minute ai-worker cycle. Any failure just
    # leaves the mention pending for the worker to pick up — nothing is lost.
    background_tasks.add_task(_analyze_instagram_mentions_now, created_ids)
    return InstagramManualIngestResult(created=len(created_ids), mention_ids=created_ids)


def _analyze_instagram_mentions_now(mention_ids: list[uuid.UUID]) -> None:
    if not mention_ids:
        return
    settings = get_settings()
    log = logging.getLogger("instagram-manual")
    try:
        client = create_gemini_client(settings)
    except Exception:
        log.warning("Gemini client unavailable; ai-worker will analyze the demo comments on its next cycle")
        return
    for mention_id in mention_ids:
        try:
            with SessionLocal() as session:
                mention = session.get(InstagramMention, mention_id)
                if mention is None:
                    continue
                already = (
                    session.query(InstagramAnalysis)
                    .filter(InstagramAnalysis.instagram_mention_id == mention_id)
                    .first()
                )
                if already is not None:
                    continue  # ai-worker raced us — leave it
                analysis = analyze_instagram_mention(session, settings, client, mention)
                if not analysis.error:
                    brand = session.get(Brand, mention.brand_id) if mention.brand_id else None
                    record_alert(
                        session,
                        settings,
                        platform="instagram",
                        brand_id=mention.brand_id,
                        mention_id=mention.id,
                        brand_name=brand.name if brand else None,
                        source=mention.author_username,
                        author=mention.author_username,
                        text=mention.text,
                        permalink=mention.permalink,
                        analysis=analysis,
                    )
        except ProviderRetryableError as exc:
            log.warning(
                "Gemini temporarily unavailable; stopping immediate Instagram analysis and leaving the backlog for ai-worker: %s",
                exc,
            )
            break
        except Exception:
            log.exception("manual analyze failed mention=%s", mention_id)


@app.get("/instagram/summary", response_model=InstagramSummary)
def instagram_summary(session: DbSession, brand_id: uuid.UUID | None = None) -> InstagramSummary:
    source_q = session.query(InstagramSource)
    mention_q = session.query(InstagramMention)
    if brand_id:
        source_q = source_q.filter(InstagramSource.brand_id == brand_id)
        mention_q = mention_q.filter(InstagramMention.brand_id == brand_id)
    mentions_total = mention_q.count()
    posts_total = mention_q.filter(InstagramMention.item_type.in_(["post", "caption"])).count()
    comments_total = mention_q.filter(InstagramMention.item_type == "comment").count()
    direct_total = mention_q.filter(InstagramMention.item_type == "mention").count()
    likes_total = mention_q.with_entities(func.coalesce(func.sum(InstagramMention.like_count), 0)).scalar() or 0
    post_comments_total = (
        mention_q.filter(InstagramMention.item_type.in_(["post", "caption"]))
        .with_entities(func.coalesce(func.sum(InstagramMention.comment_count), 0))
        .scalar()
        or 0
    )
    analyzed_total = (
        session.query(InstagramAnalysis)
        .join(InstagramMention, InstagramMention.id == InstagramAnalysis.instagram_mention_id)
        .filter(InstagramAnalysis.error.is_(None))
    )
    high_risk = analyzed_total.filter(InstagramAnalysis.risk_level.in_(["high", "critical"]))
    if brand_id:
        analyzed_total = analyzed_total.filter(InstagramMention.brand_id == brand_id)
        high_risk = high_risk.filter(InstagramMention.brand_id == brand_id)
    latest = mention_q.order_by(InstagramMention.created_at.desc()).limit(20).all()
    return InstagramSummary(
        sources_total=source_q.count(),
        mentions_total=mentions_total,
        posts_total=posts_total,
        comments_total=comments_total,
        mentions_direct_total=direct_total,
        likes_total=int(likes_total),
        post_comments_total=int(post_comments_total),
        analyzed_total=analyzed_total.count(),
        high_risk=high_risk.count(),
        latest_mentions=latest,
    )


@app.get("/instagram/webhook")
def instagram_webhook_verify(request: Request) -> PlainTextResponse:
    """Meta calls this once to verify the callback URL (hub.challenge echo)."""
    settings = get_settings()
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    if mode == "subscribe" and token and token == settings.ig_verify_token:
        return PlainTextResponse(challenge or "")
    raise HTTPException(status_code=403, detail="Verify token mismatch")


@app.post("/instagram/webhook")
async def instagram_webhook_receive(request: Request) -> dict[str, object]:
    """Receive Meta webhook events for the connected Instagram accounts."""
    settings = get_settings()
    raw = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    # Signature is enforced only when an app secret is configured (dev-friendly).
    if settings.ig_app_secret and not verify_signature(settings.ig_app_secret, raw, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")
    try:
        body = json.loads(raw.decode() or "{}")
    except json.JSONDecodeError:
        return {"ok": True, "processed": 0}
    processed = _process_instagram_webhook(body)
    return {"ok": True, "processed": processed}


def _process_instagram_webhook(body: dict[str, object]) -> int:
    if body.get("object") != "instagram":
        return 0
    processed = 0
    for entry in body.get("entry", []) or []:
        ig_user_id = str(entry.get("id") or "")
        with SessionLocal() as session:
            source = (
                session.query(InstagramSource)
                .filter(InstagramSource.ig_user_id == ig_user_id, InstagramSource.active.is_(True))
                .one_or_none()
            )
            if source is None:
                continue
            if not source.webhook_subscribed:
                source.webhook_subscribed = True
                session.commit()
            for change in entry.get("changes", []) or []:
                field = change.get("field")
                value = change.get("value") or {}
                item_type = "mention" if field == "mentions" else "comment"
                comment = _resolve_instagram_object(source, field, value)
                if not comment:
                    continue
                try:
                    if ingest_instagram_comment(session, source, comment, item_type=item_type) is not None:
                        processed += 1
                except Exception:
                    logging.getLogger("instagram-webhook").exception("ingest failed id=%s", comment.get("id"))
    return processed


def _resolve_instagram_object(source: InstagramSource, field: str | None, value: dict) -> dict | None:
    """Webhook values are minimal; fetch the full comment via Graph API when needed."""
    if value.get("text"):
        return value  # comment payloads often already carry the text
    comment_id = value.get("id") or value.get("comment_id")
    if not comment_id:
        return None
    try:
        api = _instagram_api_for(source)
        if field == "mentions":
            data = api.get_mentioned_comment(source.ig_user_id, str(comment_id))
            mc = data.get("mentioned_comment") or {}
            if value.get("media_id") and "media" not in mc:
                mc["media_id"] = value.get("media_id")
            return mc or None
        return api.get_comment(str(comment_id))
    except (InstagramApiError, HTTPException):
        # Fall back to the minimal payload so the mention is still recorded.
        return {"id": comment_id, "text": value.get("text"), "media_id": value.get("media_id")}


# ============================ Facebook Pages ============================
# Same Meta Graph API + webhook model as Instagram, keyed on the Facebook Page id.
# Comments on the Page's posts arrive as ``feed`` webhook events; the Graph API fetches
# the full object and backfills recent post comments.

FACEBOOK_SOURCE_CATEGORIES = [
    {"key": "owned", "label": "Rasmiy sahifa", "description": "Brendning o'z Facebook Page'i."},
    {"key": "competitor", "label": "Raqobatchi", "description": "Raqobatchi sahifa."},
    {"key": "influencer", "label": "Influencer", "description": "Bloger/ekspert sahifalari."},
    {"key": "unknown", "label": "Aniqlanmagan", "description": "Toifasiz."},
]


def _facebook_api_for(source: FacebookSource) -> FacebookApi:
    settings = get_settings()
    token = source.access_token or settings.fb_access_token
    if not token:
        raise HTTPException(status_code=400, detail="Facebook source has no access token")
    return FacebookApi(
        token,
        graph_version=settings.fb_graph_version,
        api_base=source.api_base or "graph.facebook.com",
    )


@app.get("/facebook/status", response_model=FacebookStatus)
def facebook_status(request: Request, session: DbSession) -> FacebookStatus:
    settings = get_settings()
    connected = session.query(FacebookSource).filter(FacebookSource.active.is_(True)).count()
    fwd_scheme = request.headers.get("x-forwarded-proto")
    host = request.headers.get("x-forwarded-host") or request.url.netloc
    if fwd_scheme:
        callback = f"{fwd_scheme}://{host}/api/facebook/webhook"
    else:
        callback = f"{request.url.scheme}://{host}/facebook/webhook"
    return FacebookStatus(
        configured=bool(settings.fb_app_id and settings.fb_app_secret),
        enabled=settings.facebook_enabled,
        graph_version=settings.fb_graph_version,
        webhook_callback_url=callback,
        verify_token_set=bool(settings.fb_verify_token),
        connected_pages=connected,
    )


@app.get("/facebook/source-categories")
def facebook_source_categories(request: Request) -> list[dict[str, str]]:
    return localize_source_categories(FACEBOOK_SOURCE_CATEGORIES, request_language(request))


@app.get("/facebook/sources", response_model=list[FacebookSourceOut])
def list_facebook_sources(session: DbSession) -> list[FacebookSource]:
    return session.query(FacebookSource).order_by(FacebookSource.created_at.asc()).all()


@app.post("/facebook/sources", response_model=FacebookSourceOut)
def connect_facebook_source(payload: FacebookSourceCreate, session: DbSession) -> FacebookSource:
    settings = get_settings()
    try:
        detected = detect_page(payload.access_token, graph_version=settings.fb_graph_version)
    except FacebookApiError as exc:
        raise HTTPException(status_code=400, detail=f"Token ishlamadi — {exc}")
    page_id = payload.page_id or detected["page_id"]
    existing = session.query(FacebookSource).filter(FacebookSource.page_id == page_id).one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Bu Facebook Page allaqachon ulangan")
    source = FacebookSource(
        brand_id=payload.brand_id,
        page_id=page_id,
        page_name=payload.page_name or detected.get("page_name"),
        username=payload.username or detected.get("username"),
        access_token=detected.get("access_token") or payload.access_token,
        api_base=detected["api_base"],
        token_status="active",
        status_detail=f"{detected.get('page_name')} ({detected['api_base']})",
        last_checked_at=datetime.now(timezone.utc),
        source_category=payload.source_category,
        monitoring_mode=payload.monitoring_mode,
        collect_comments=payload.collect_comments,
        collect_mentions=payload.collect_mentions,
        hashtags=payload.hashtags,
        notes=payload.notes,
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


@app.post("/facebook/sources/{source_id}/validate", response_model=FacebookSourceOut)
def validate_facebook_source(source_id: uuid.UUID, session: DbSession) -> FacebookSource:
    source = session.get(FacebookSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Facebook source topilmadi")
    settings = get_settings()
    try:
        detected = detect_page(source.access_token or "", graph_version=settings.fb_graph_version)
        source.token_status = "active"
        source.api_base = detected["api_base"]
        source.page_name = detected.get("page_name") or source.page_name
        source.status_detail = f"{detected.get('page_name')} ({detected['api_base']})"
    except FacebookApiError as exc:
        source.token_status = "invalid"
        source.status_detail = str(exc)[:400]
    source.last_checked_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(source)
    return source


@app.patch("/facebook/sources/{source_id}", response_model=FacebookSourceOut)
def update_facebook_source(source_id: uuid.UUID, payload: FacebookSourceUpdate, session: DbSession) -> FacebookSource:
    source = session.get(FacebookSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Facebook source topilmadi")
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(source, field, value)
    if updates.get("access_token"):
        try:
            detected = detect_page(source.access_token, graph_version=get_settings().fb_graph_version)
            source.access_token = detected.get("access_token") or source.access_token
            source.api_base = detected["api_base"]
            source.page_id = detected["page_id"]
            source.page_name = detected.get("page_name") or source.page_name
            source.token_status = "active"
            source.status_detail = f"{detected.get('page_name')} ({detected['api_base']})"
        except FacebookApiError as exc:
            source.token_status = "invalid"
            source.status_detail = str(exc)[:400]
        source.last_checked_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(source)
    return source


@app.delete("/facebook/sources/{source_id}", response_model=SourceDeleteResult)
def delete_facebook_source(source_id: uuid.UUID, session: DbSession) -> dict[str, Any]:
    return delete_source_and_notify("facebook", source_id, session)


@app.get("/facebook/mentions", response_model=list[FacebookMentionOut])
def list_facebook_mentions(
    session: DbSession, brand_id: uuid.UUID | None = None, limit: int = Query(default=100, le=500)
) -> list[FacebookMentionOut]:
    query = session.query(FacebookMention)
    if brand_id:
        query = query.filter(FacebookMention.brand_id == brand_id)
    rows = query.order_by(FacebookMention.created_at.desc()).limit(limit).all()
    if not rows:
        return []
    analyses = {
        a.facebook_mention_id: a
        for a in session.query(FacebookAnalysis).filter(
            FacebookAnalysis.facebook_mention_id.in_([r.id for r in rows])
        )
    }
    out: list[FacebookMentionOut] = []
    for mention in rows:
        item = FacebookMentionOut.model_validate(mention)
        analysis = analyses.get(mention.id)
        if analysis is not None:
            item.analysis = FacebookAnalysisOut.model_validate(analysis)
        out.append(item)
    return out


@app.get("/facebook/summary", response_model=FacebookSummary)
def facebook_summary(session: DbSession, brand_id: uuid.UUID | None = None) -> FacebookSummary:
    source_q = session.query(FacebookSource)
    mention_q = session.query(FacebookMention)
    if brand_id:
        source_q = source_q.filter(FacebookSource.brand_id == brand_id)
        mention_q = mention_q.filter(FacebookMention.brand_id == brand_id)
    mentions_total = mention_q.count()
    comments_total = mention_q.filter(FacebookMention.item_type.in_(["comment", "reply"])).count()
    analyzed_total = (
        session.query(FacebookAnalysis)
        .join(FacebookMention, FacebookMention.id == FacebookAnalysis.facebook_mention_id)
        .filter(FacebookAnalysis.error.is_(None))
    )
    high_risk = analyzed_total.filter(FacebookAnalysis.risk_level.in_(["high", "critical"]))
    if brand_id:
        analyzed_total = analyzed_total.filter(FacebookMention.brand_id == brand_id)
        high_risk = high_risk.filter(FacebookMention.brand_id == brand_id)
    latest = mention_q.order_by(FacebookMention.created_at.desc()).limit(20).all()
    return FacebookSummary(
        sources_total=source_q.count(),
        mentions_total=mentions_total,
        comments_total=comments_total,
        analyzed_total=analyzed_total.count(),
        high_risk=high_risk.count(),
        latest_mentions=latest,
    )


@app.post("/facebook/mentions/manual", response_model=FacebookManualIngestResult)
def facebook_manual_ingest(
    payload: FacebookManualIngest, background_tasks: BackgroundTasks, session: DbSession
) -> FacebookManualIngestResult:
    """Meta'siz demo/qo'lda ingest for Facebook — same idea as the Instagram one."""
    brand = session.get(Brand, payload.brand_id)
    if brand is None:
        raise HTTPException(status_code=404, detail="Brand topilmadi")

    items: list[dict[str, Any]] = []
    for comment in payload.comments or []:
        if (comment.text or "").strip():
            items.append(
                {"text": comment.text.strip(), "author_name": comment.author_name, "item_type": comment.item_type}
            )
    for line in (payload.raw_text or "").splitlines():
        if line.strip():
            items.append({"text": line.strip(), "author_name": None, "item_type": "comment"})
    if not items:
        raise HTTPException(status_code=400, detail="Kamida bitta komment matni kerak")

    now = datetime.now(timezone.utc)
    created_ids: list[uuid.UUID] = []
    for item in items:
        text = item["text"]
        item_type = item["item_type"] if item["item_type"] in ("comment", "reply", "post", "mention") else "comment"
        mention = FacebookMention(
            source_id=None,
            brand_id=brand.id,
            external_id=f"manual:{uuid.uuid4()}",
            item_type=item_type,
            author_name=item.get("author_name") or "demo_user",
            text=text,
            normalized_text=normalize_text(text),
            permalink=payload.permalink,
            brand_match_terms=[brand.name] if brand.name else ["manual"],
            raw={"manual": True},
            published_at=now,
        )
        session.add(mention)
        session.commit()
        session.refresh(mention)
        created_ids.append(mention.id)
        publish_realtime_event(
            session,
            "facebook_mention",
            {
                "id": str(mention.id),
                "brand_id": str(brand.id),
                "platform": "facebook",
                "item_type": mention.item_type,
                "author_name": mention.author_name,
                "created_at": mention.created_at.isoformat() if isinstance(mention.created_at, datetime) else None,
            },
        )
    background_tasks.add_task(_analyze_facebook_mentions_now, created_ids)
    return FacebookManualIngestResult(created=len(created_ids), mention_ids=created_ids)


def _analyze_facebook_mentions_now(mention_ids: list[uuid.UUID]) -> None:
    if not mention_ids:
        return
    settings = get_settings()
    log = logging.getLogger("facebook-manual")
    try:
        client = create_gemini_client(settings)
    except Exception:
        log.warning("Gemini client unavailable; ai-worker will analyze the demo comments on its next cycle")
        return
    for mention_id in mention_ids:
        try:
            with SessionLocal() as session:
                mention = session.get(FacebookMention, mention_id)
                if mention is None:
                    continue
                already = (
                    session.query(FacebookAnalysis)
                    .filter(FacebookAnalysis.facebook_mention_id == mention_id)
                    .first()
                )
                if already is not None:
                    continue
                analysis = analyze_facebook_mention(session, settings, client, mention)
                if not analysis.error:
                    brand = session.get(Brand, mention.brand_id) if mention.brand_id else None
                    record_alert(
                        session,
                        settings,
                        platform="facebook",
                        brand_id=mention.brand_id,
                        mention_id=mention.id,
                        brand_name=brand.name if brand else None,
                        source=mention.post_id,
                        author=mention.author_name,
                        text=mention.text,
                        permalink=mention.permalink,
                        analysis=analysis,
                    )
        except Exception:
            log.exception("manual analyze failed mention=%s", mention_id)


@app.get("/facebook/webhook")
def facebook_webhook_verify(request: Request) -> PlainTextResponse:
    """Meta calls this once to verify the callback URL (hub.challenge echo)."""
    settings = get_settings()
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    if mode == "subscribe" and token and token == settings.fb_verify_token:
        return PlainTextResponse(challenge or "")
    raise HTTPException(status_code=403, detail="Verify token mismatch")


@app.post("/facebook/webhook")
async def facebook_webhook_receive(request: Request) -> dict[str, object]:
    settings = get_settings()
    raw = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    if settings.fb_app_secret and not fb_verify_signature(settings.fb_app_secret, raw, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")
    try:
        body = json.loads(raw.decode() or "{}")
    except json.JSONDecodeError:
        return {"ok": True, "processed": 0}
    processed = _process_facebook_webhook(body)
    return {"ok": True, "processed": processed}


def _process_facebook_webhook(body: dict[str, object]) -> int:
    if body.get("object") != "page":
        return 0
    processed = 0
    for entry in body.get("entry", []) or []:
        page_id = str(entry.get("id") or "")
        with SessionLocal() as session:
            source = (
                session.query(FacebookSource)
                .filter(FacebookSource.page_id == page_id, FacebookSource.active.is_(True))
                .one_or_none()
            )
            if source is None:
                continue
            for change in entry.get("changes", []) or []:
                if change.get("field") != "feed":
                    continue
                value = change.get("value") or {}
                if value.get("item") != "comment" or value.get("verb") not in ("add", "edited", "edit"):
                    continue
                comment = _resolve_facebook_object(source, value)
                if not comment:
                    continue
                try:
                    if ingest_facebook_comment(session, source, comment, item_type="comment") is not None:
                        processed += 1
                except Exception:
                    logging.getLogger("facebook-webhook").exception("ingest failed id=%s", comment.get("id"))
    return processed


def _resolve_facebook_object(source: FacebookSource, value: dict) -> dict | None:
    """Feed webhook values usually carry the message already; fetch the full comment
    via the Graph API when they don't."""
    comment_id = value.get("comment_id") or value.get("id")
    if not comment_id:
        return None
    if value.get("message"):
        created = value.get("created_time")
        if isinstance(created, (int, float)):
            created = datetime.fromtimestamp(created, tz=timezone.utc).isoformat()
        return {
            "id": comment_id,
            "message": value.get("message"),
            "from": value.get("from") or {},
            "post_id": value.get("post_id"),
            "parent_id": value.get("parent_id"),
            "created_time": created,
        }
    try:
        api = _facebook_api_for(source)
        return api.get_comment(str(comment_id))
    except (FacebookApiError, HTTPException):
        return {"id": comment_id, "message": value.get("message"), "post_id": value.get("post_id")}
