from __future__ import annotations

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from telethon import TelegramClient

from app.config import get_settings
from app.models import Brand, TelegramSource
from app.services.realtime import publish_realtime_event
from app.services.telegram_api import TelegramBotApi
from app.services.telegram_ingestion import ensure_telegram_source_owner
from app.workers.telegram_backfill import backfill_source


CATEGORY_DEFAULT_MODES = {
    "owned": "all_messages",
    "bot": "all_messages",
    "competitor": "all_messages",
    "news": "brand_matches_only",
    "industry": "brand_matches_only",
    "influencer": "brand_matches_only",
    "community": "brand_matches_only",
    "useful": "brand_matches_only",
    "risk": "all_messages",
    "unknown": "brand_matches_only",
}

VALID_CATEGORIES = set(CATEGORY_DEFAULT_MODES)
VALID_MODES = {"all_messages", "brand_matches_only"}
LOCAL_TZ = timezone(timedelta(hours=5))
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
logger = logging.getLogger(__name__)


@dataclass
class AccessStatus:
    ok: bool
    chat_id_or_username: int | str
    bot_username: str | None = None
    chat_id: int | None = None
    chat_username: str | None = None
    chat_title: str | None = None
    chat_type: str | None = None
    bot_status: str | None = None
    can_read_posts: bool = False
    can_read_comments: bool = False
    linked_discussion_chat_id: int | None = None
    linked_discussion_bot_status: str | None = None
    issues: list[str] | None = None


def handle_command_update(api: TelegramBotApi, session: Session, update: dict[str, Any]) -> bool:
    message = update.get("message") or update.get("edited_message")
    if not message:
        return False

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    chat_type = chat.get("type")
    text = (message.get("text") or "").strip()
    if not chat_id or not text:
        return False

    command = parse_command(text)
    if not command:
        return False

    # Agent commands are intentionally private-chat only, so normal group traffic
    # cannot accidentally edit the monitoring catalog.
    if chat_type != "private":
        if command.name in {"add", "remove", "delete", "pause", "resume", "backfill", "check", "sources", "status", "help", "start"}:
            api.send_message(chat_id, "Agent komandalarini botga private chatda yuboring.")
            return True
        return False

    sender_id = (message.get("from") or {}).get("id")
    allowed_user_ids = set(get_settings().telegram_command_allowed_user_ids)
    if sender_id not in allowed_user_ids:
        logger.warning("Rejected Telegram agent command name=%s sender_id=%s", command.name, sender_id)
        api.send_message(chat_id, "Bu agent komandalarini ishlatishga ruxsatingiz yo'q.")
        return True

    try:
        response = execute_command(api, session, command)
    except Exception as exc:
        session.rollback()
        response = f"Xatolik: {exc}"

    api.send_message(chat_id, response)
    return True


@dataclass
class Command:
    name: str
    args: list[str]


def parse_command(text: str) -> Command | None:
    cleaned = text.strip()
    if not cleaned:
        return None

    if cleaned.startswith("/"):
        parts = cleaned.split()
        name = parts[0].split("@", 1)[0].lstrip("/").lower()
        return Command(name=name, args=parts[1:])

    if looks_like_source_ref(cleaned):
        return Command(name="add", args=[cleaned])

    return None


def looks_like_source_ref(value: str) -> bool:
    value = value.strip()
    return bool(
        value.startswith("@")
        or value.startswith("https://t.me/")
        or value.startswith("http://t.me/")
        or value.startswith("t.me/")
        or re.fullmatch(r"-?\d{5,}", value)
    )


def execute_command(api: TelegramBotApi, session: Session, command: Command) -> str:
    if command.name in {"start", "help"}:
        return help_text()
    if command.name == "status":
        return status_text(api, session)
    if command.name == "sources":
        return sources_text(session)
    if command.name == "check":
        ref = require_ref(command)
        access, _ = build_access_status(api, ref)
        return access_text(access)
    if command.name == "add":
        return add_source(api, session, command.args)
    if command.name in {"remove", "delete"}:
        ref = require_ref(command)
        return set_source_active(session, ref, active=False)
    if command.name == "pause":
        ref = require_ref(command)
        return set_source_active(session, ref, active=False)
    if command.name == "resume":
        ref = require_ref(command)
        return set_source_active(session, ref, active=True)
    if command.name == "backfill":
        ref = require_ref(command)
        limit, from_date = parse_backfill_args(command.args[1:] if len(command.args) > 1 else [])
        return backfill_ref(session, ref, limit=limit, comments_per_post=50, from_date=from_date)

    return f"Noma'lum komanda: /{command.name}\n\n{help_text()}"


def help_text() -> str:
    return (
        "MonitoringAI agent komandalar:\n"
        "/add @channel [category] [mode] [YYYY-MM-DD] - source qo'shish va import qilish\n"
        "/check @channel - bot access tekshirish\n"
        "/sources - active source ro'yxati\n"
        "/backfill @channel [limit] [YYYY-MM-DD] - eski postlarni import qilish\n"
        "/pause @channel - monitoringni to'xtatish\n"
        "/resume @channel - monitoringni yoqish\n"
        "/remove @channel - source'ni active=false qilish\n"
        "/status - bot, Telethon va source status\n\n"
        "Xodimlar guruhida (bot admin bo'lishi kerak):\n"
        "/id - guruh chat id (ALERT_TELEGRAM_CHAT_ID uchun)\n"
        "/ochiq - javob kutayotgan signallar ro'yxati\n"
        "/statistika - bugungi javoblar va xodimlar kesimi\n"
        "/xodimlar - kim nechta signalga javob bergani (jadval)\n"
        "/til uz|ru|en - guruh bot tilini o'zgartirish\n"
        "/jamlanma - pin qilingan hisoblagichni yangilash\n\n"
        "Category: owned, competitor, news, community, risk, bot, industry.\n"
        "Mode: all_messages yoki brand_matches_only.\n"
        "Sana berilmasa bugundan kuzatadi. Masalan: /add @channel owned all_messages 2026-07-01\n"
        "Linkni commandisiz yuborsangiz ham /add sifatida qabul qilinadi."
    )


def require_ref(command: Command) -> str:
    if not command.args:
        raise ValueError("Source ref kerak. Masalan: /add @channel")
    return command.args[0]


def parse_int_arg(args: list[str], *, default: int, minimum: int, maximum: int) -> int:
    if not args:
        return default
    try:
        value = int(args[0])
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def today_local_date() -> date:
    return datetime.now(LOCAL_TZ).date()


def start_of_day_utc(value: date | datetime | None) -> datetime:
    if value is None:
        value = today_local_date()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=LOCAL_TZ)
        return value.astimezone(timezone.utc)
    return datetime.combine(value, time.min, tzinfo=LOCAL_TZ).astimezone(timezone.utc)


def format_monitor_date(value: datetime | None) -> str:
    if value is None:
        return "-"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(LOCAL_TZ).date().isoformat()


def parse_date_token(value: str) -> date | None:
    if not DATE_RE.fullmatch(value.strip()):
        return None
    return date.fromisoformat(value.strip())


def parse_backfill_args(args: list[str]) -> tuple[int | None, datetime | None]:
    limit: int | None = None
    from_date: datetime | None = None
    for token in args:
        parsed_date = parse_date_token(token)
        if parsed_date:
            from_date = start_of_day_utc(parsed_date)
            continue
        if limit is None:
            try:
                limit = max(1, min(10000, int(token)))
            except ValueError:
                continue
    return limit, from_date


def parse_add_args(args: list[str]) -> tuple[str, str, str, str | None, datetime]:
    if not args:
        raise ValueError("Source ref kerak. Masalan: /add @channel owned all_messages")

    ref = args[0]
    category = "owned"
    category_set = False
    mode: str | None = None
    monitor_date: date | None = None
    notes_parts: list[str] = []

    for token in args[1:]:
        lowered = token.lower()
        parsed_date = parse_date_token(token)
        if parsed_date and monitor_date is None:
            monitor_date = parsed_date
        elif lowered in VALID_CATEGORIES and not category_set:
            category = lowered
            category_set = True
        elif lowered in VALID_MODES and mode is None:
            mode = lowered
        else:
            notes_parts.append(token)

    resolved_mode = mode or CATEGORY_DEFAULT_MODES[category]
    notes = " ".join(notes_parts).strip() or None
    return ref, category, resolved_mode, notes, start_of_day_utc(monitor_date)


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


def add_source(api: TelegramBotApi, session: Session, args: list[str]) -> str:
    ref, category, mode, notes, monitor_from = parse_add_args(args)
    normalized_ref = normalize_chat_ref(ref)
    access, chat_info = build_access_status(api, normalized_ref)

    try:
        if chat_info:
            source = upsert_telegram_source_from_chat(
                session,
                chat_info=chat_info,
                brand_id=default_brand_id(session),
                source_category=category,
                monitoring_mode=mode,
                competitor_name=None,
                notes=notes,
                collect_posts=True,
                collect_comments=True,
                monitor_from=monitor_from,
            )
            linked_source = upsert_related_telegram_source(
                api,
                session,
                parent_chat_info=chat_info,
                parent_source=source,
                brand_id=source.brand_id,
                source_category=category,
                monitoring_mode=mode,
                collect_comments=True,
                monitor_from=source.monitor_from,
            )
            import_status = "resolved"
        else:
            source = upsert_catalog_source(
                session,
                ref=normalized_ref,
                brand_id=default_brand_id(session),
                source_category=category,
                monitoring_mode=mode,
                competitor_name=None,
                notes=notes,
                collect_posts=True,
                collect_comments=True,
                monitor_from=monitor_from,
            )
            linked_source = None
            import_status = "cataloged"

        session.commit()
        session.refresh(source)
        if linked_source:
            session.refresh(linked_source)
            publish_source_event(session, linked_source)
        publish_source_event(session, source)
    except IntegrityError as exc:
        session.rollback()
        raise ValueError(str(exc.orig)) from exc

    backfill_message = ""
    if source.username or source.chat_id:
        backfill_message = "\n" + backfill_source_text(source, limit=None, comments_per_post=50)

    return (
        f"Source qo'shildi: {source_title(source)}\n"
        f"Status: {import_status}\n"
        f"Papka: {source.source_category}\n"
        f"Mode: {source.monitoring_mode}\n"
        f"Kuzatuv boshlanishi: {format_monitor_date(source.monitor_from)}\n"
        f"Import usuli: {'Bot API + Telethon' if access.ok else 'Telethon user-session'}\n"
        f"Live sync: active source ro'yxatiga qo'shildi\n"
        f"Bot access: {'OK' if access.ok else 'muammo'}\n"
        f"Postlar: {yes_no(access.can_read_posts)}\n"
        f"Commentlar: {yes_no(access.can_read_comments)}"
        f"{format_issues(access.issues or [])}"
        f"{backfill_message}"
    )


def default_brand_id(session: Session) -> uuid.UUID | None:
    brand = session.query(Brand).filter(Brand.active.is_(True)).order_by(Brand.created_at.desc()).first()
    return brand.id if brand else None


def upsert_telegram_source_from_chat(
    session: Session,
    *,
    chat_info: dict[str, Any],
    brand_id: uuid.UUID | None,
    source_category: str,
    monitoring_mode: str,
    competitor_name: str | None,
    notes: str | None,
    collect_posts: bool,
    collect_comments: bool,
    monitor_from: datetime | None = None,
) -> TelegramSource:
    source = (
        session.query(TelegramSource)
        .filter(TelegramSource.brand_id == brand_id, TelegramSource.chat_id == chat_info["id"])
        .one_or_none()
    )
    if not source and chat_info.get("username"):
        source = (
            session.query(TelegramSource)
            .filter(TelegramSource.brand_id == brand_id, TelegramSource.username == chat_info["username"])
            .one_or_none()
        )
    if not source:
        source = TelegramSource(chat_id=chat_info["id"])
        session.add(source)
    else:
        ensure_telegram_source_owner(source, brand_id)

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
    # Re-adding a source that was removed with its mentions kept revives the same row, so
    # last_seen_message_id survives: catch-up imports only the gap and the AI worker only
    # analyses what still has no verdict.
    source.deleted_at = None
    return source


def upsert_related_telegram_source(
    api: TelegramBotApi,
    session: Session,
    *,
    parent_chat_info: dict[str, Any],
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
    source = find_source(session, ref, brand_id=brand_id)
    if source is None:
        source = TelegramSource(chat_id=chat_id if isinstance(chat_id, int) else None, username=username)
        session.add(source)
    else:
        ensure_telegram_source_owner(source, brand_id)

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
    # Re-adding a source that was removed with its mentions kept revives the same row, so
    # last_seen_message_id survives: catch-up imports only the gap and the AI worker only
    # analyses what still has no verdict.
    source.deleted_at = None
    return source


def build_access_status(api: TelegramBotApi, chat_id_or_username: int | str) -> tuple[AccessStatus, dict[str, Any] | None]:
    issues: list[str] = []
    bot = api.get_me()
    bot_id = int(bot["id"]) if bot and bot.get("id") else None
    bot_username = bot.get("username") if bot else None
    chat_ref = normalize_chat_ref(chat_id_or_username)
    if bot_id is None:
        return AccessStatus(ok=False, chat_id_or_username=chat_id_or_username, issues=["bot_token_invalid_or_getme_failed"]), None

    try:
        chat_info = api.get_chat(chat_ref)
    except Exception:
        return (
            AccessStatus(
                ok=False,
                chat_id_or_username=chat_id_or_username,
                bot_username=bot_username,
                issues=["chat_not_found_or_bot_has_no_access"],
            ),
            None,
        )

    if not chat_info:
        return (
            AccessStatus(
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
        AccessStatus(
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


def find_source(
    session: Session,
    ref: int | str,
    *,
    brand_id: uuid.UUID | None,
) -> TelegramSource | None:
    normalized = normalize_chat_ref(ref)
    username = username_from_ref(ref)
    filters = []
    if isinstance(normalized, int):
        filters.append(TelegramSource.chat_id == normalized)
    if username:
        filters.append(TelegramSource.username == username)
    if not filters:
        return None
    return (
        session.query(TelegramSource)
        .filter(TelegramSource.brand_id == brand_id, or_(*filters))
        .one_or_none()
    )


def set_source_active(session: Session, ref: str, *, active: bool) -> str:
    source = find_source(session, ref, brand_id=default_brand_id(session))
    if not source:
        return "Source topilmadi."
    source.active = active
    session.commit()
    publish_source_event(session, source)
    return f"{source_title(source)}: {'active' if active else 'paused'}"


def sources_text(session: Session) -> str:
    sources = session.query(TelegramSource).filter(TelegramSource.active.is_(True)).order_by(TelegramSource.created_at.desc()).limit(20).all()
    total = session.query(TelegramSource).filter(TelegramSource.active.is_(True)).count()
    if not sources:
        return "Active source yo'q. /add @channel bilan qo'shing."

    lines = [f"Active sources: {total}"]
    for source in sources:
        lines.append(f"- {source_ref(source)} · {source.source_category} · {source_title(source)}")
    if total > len(sources):
        lines.append(f"... yana {total - len(sources)} ta")
    return "\n".join(lines)


def status_text(api: TelegramBotApi, session: Session) -> str:
    settings = get_settings()
    bot = api.get_me() or {}
    active_count = session.query(TelegramSource).filter(TelegramSource.active.is_(True)).count()
    all_count = session.query(TelegramSource).count()
    telethon = telethon_status_text(settings.telegram_session_name, settings.telegram_api_id, settings.telegram_api_hash)
    return (
        "MonitoringAI status\n"
        f"Bot: @{bot.get('username') or '-'}\n"
        f"Group privacy: {'disabled' if bot.get('can_read_all_group_messages') else 'not disabled'}\n"
        f"Sources: {active_count} active / {all_count} total\n"
        f"Telethon: {telethon}\n"
        "Live sync: telegram-live-sync service active bo'lsa adminsiz public/member source'larni import qiladi"
    )


def telethon_status_text(session_name: str, api_id: int | None, api_hash: str) -> str:
    if not api_id or not api_hash:
        return "not configured"

    async def check() -> str:
        client = TelegramClient(session_name, api_id, api_hash)
        await client.connect()
        try:
            if not await client.is_user_authorized():
                return "not authorized"
            me = await client.get_me()
            return f"authorized @{getattr(me, 'username', None) or getattr(me, 'id', None)}"
        finally:
            await client.disconnect()

    try:
        return asyncio.run(check())
    except Exception as exc:
        return f"error: {exc}"


def backfill_ref(session: Session, ref: str, *, limit: int | None, comments_per_post: int, from_date: datetime | None = None) -> str:
    source = find_source(session, ref, brand_id=default_brand_id(session))
    if not source:
        return "Source topilmadi. Avval /add bilan qo'shing."
    return backfill_source_text(source, limit=limit, comments_per_post=comments_per_post, from_date=from_date)


def backfill_source_text(
    source: TelegramSource,
    *,
    limit: int | None,
    comments_per_post: int,
    from_date: datetime | None = None,
) -> str:
    source_ref_value = source.username or source.chat_id
    if source_ref_value is None:
        return "Backfill: source ref yo'q."

    settings = get_settings()
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        return "Backfill: TELEGRAM_API_ID/API_HASH yo'q."

    async def run() -> dict[str, int]:
        client = TelegramClient(settings.telegram_session_name, settings.telegram_api_id, settings.telegram_api_hash)
        await client.connect()
        try:
            if not await client.is_user_authorized():
                raise RuntimeError("Telethon session authorized emas.")
            return await backfill_source(
                client,
                source_ref_value,
                limit,
                comments_per_post,
                from_date=from_date or source.monitor_from or source.created_at,
                source_id=source.id,
            )
        finally:
            await client.disconnect()

    try:
        counts = asyncio.run(run())
    except Exception as exc:
        return f"Backfill: xatolik - {exc}"

    return f"Backfill: {counts.get('posts_seen', 0)} post, {counts.get('comments_seen', 0)} comment import qilindi."


def access_text(access: AccessStatus) -> str:
    return (
        f"Access check: {access.chat_title or access.chat_username or access.chat_id_or_username}\n"
        f"Bot: {access.bot_status or '-'}\n"
        f"Postlar: {yes_no(access.can_read_posts)}\n"
        f"Commentlar: {yes_no(access.can_read_comments)}"
        f"{format_issues(access.issues or [])}"
    )


def format_issues(issues: list[str]) -> str:
    if not issues:
        return ""
    return "\nMuammolar: " + ", ".join(issues)


def yes_no(value: bool) -> str:
    return "ha" if value else "yo'q"


def source_title(source: TelegramSource) -> str:
    return source.title or source.competitor_name or source_ref(source)


def source_ref(source: TelegramSource) -> str:
    if source.username:
        return f"@{source.username}"
    if source.chat_id:
        return str(source.chat_id)
    return "unresolved"


def publish_source_event(session: Session, source: TelegramSource) -> None:
    publish_realtime_event(
        session,
        "telegram_source",
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
