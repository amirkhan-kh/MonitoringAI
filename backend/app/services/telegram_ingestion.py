from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Mention, TelegramSource
from app.services.matching import BrandMatch, collect_matched_terms, match_brand, normalize_text
from app.services.realtime import publish_realtime_event


class TelegramSourceOwnershipError(ValueError):
    pass


def ensure_telegram_source_owner(source: TelegramSource, brand_id: object | None) -> None:
    if source.brand_id is None or source.brand_id == brand_id:
        return
    raise TelegramSourceOwnershipError(
        "Telegram source boshqa brandga biriktirilgan; ownership avtomatik ko'chirilmaydi"
    )


def parse_telegram_datetime(value: int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc)


def json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    return value


def get_message_from_update(update: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    for key, source_type in (
        ("channel_post", "channel_post"),
        ("edited_channel_post", "channel_post"),
        ("message", "message"),
        ("edited_message", "message"),
    ):
        message = update.get(key)
        if message:
            return source_type, message
    return None


def source_type_for_message(default_type: str, message: dict[str, Any]) -> str:
    if default_type == "channel_post":
        return "channel_post"
    chat_type = (message.get("chat") or {}).get("type")
    if chat_type in {"group", "supergroup"} and message.get("reply_to_message"):
        return "comment"
    if chat_type in {"group", "supergroup"}:
        return "group_message"
    return "message"


def upsert_telegram_source(
    session: Session,
    chat: dict[str, Any],
    chat_description: str | None = None,
    brand_id: object | None = None,
) -> TelegramSource:
    chat_id = chat.get("id")
    username = chat.get("username")
    source = None
    if chat_id is not None:
        source = (
            session.query(TelegramSource)
            .filter(TelegramSource.brand_id == brand_id, TelegramSource.chat_id == chat_id)
            .one_or_none()
        )
    if source is None and username:
        source = (
            session.query(TelegramSource)
            .filter(TelegramSource.brand_id == brand_id, TelegramSource.username == username)
            .one_or_none()
        )
    if source is None:
        source = TelegramSource(
            brand_id=brand_id,
            chat_id=chat_id,
            username=username,
            source_kind=chat.get("type") or "unknown",
        )
        session.add(source)
    source.chat_id = chat_id
    source.username = username
    source.title = chat.get("title") or chat.get("first_name") or source.title
    source.description = chat_description if chat_description is not None else source.description
    source.source_kind = chat.get("type") or source.source_kind
    return source


def upsert_linked_discussion_source(
    session: Session,
    *,
    parent_chat: dict[str, Any],
    discussion_chat: dict[str, Any],
    parent_source: TelegramSource | None = None,
) -> TelegramSource:
    parent_source = parent_source or source_for_chat(session, parent_chat, brand_id=None)
    source = upsert_telegram_source(
        session,
        discussion_chat,
        brand_id=parent_source.brand_id if parent_source else None,
    )
    if parent_source is None or parent_source is source:
        return source

    ensure_telegram_source_owner(source, parent_source.brand_id)
    parent_source.linked_discussion_chat_id = discussion_chat.get("id")
    source.brand_id = parent_source.brand_id
    source.bot_connection_id = getattr(parent_source, "bot_connection_id", None)
    source.parent_source_id = getattr(parent_source, "id", None)
    source.source_role = "discussion"
    source.source_category = parent_source.source_category
    source.monitoring_mode = parent_source.monitoring_mode
    source.competitor_name = parent_source.competitor_name
    source.collect_posts = False
    source.collect_comments = parent_source.collect_comments
    source.monitor_from = parent_source.monitor_from
    source.active = parent_source.active
    return source


def source_for_chat(
    session: Session,
    chat: dict[str, Any],
    *,
    brand_id: object | None,
) -> TelegramSource | None:
    chat_id = chat.get("id")
    username = chat.get("username")
    source = None
    if chat_id is not None:
        source = (
            session.query(TelegramSource)
            .filter(TelegramSource.brand_id == brand_id, TelegramSource.chat_id == chat_id)
            .one_or_none()
        )
    if source is None and username:
        source = (
            session.query(TelegramSource)
            .filter(TelegramSource.brand_id == brand_id, TelegramSource.username == username)
            .one_or_none()
        )
    return source


def match_brand_for_source(session: Session, source: TelegramSource | None, normalized_text: str) -> BrandMatch:
    if source and source.brand_id and source.brand:
        terms = collect_matched_terms(source.brand, normalized_text)
        if source.monitoring_mode == "brand_matches_only":
            return BrandMatch(source.brand, terms) if terms else BrandMatch(None, [])
        return BrandMatch(source.brand, terms)
    return match_brand(session, normalized_text)


def ingest_telegram_update(
    session: Session,
    update: dict[str, Any],
    chat_description: str | None = None,
    source_override: TelegramSource | None = None,
) -> Mention | None:
    extracted = get_message_from_update(update)
    if not extracted:
        return None

    default_source_type, message = extracted
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    message_id = message.get("message_id")
    if chat_id is None or message_id is None:
        return None

    source = source_override or upsert_telegram_source(session, chat, chat_description=chat_description)
    session.flush()
    resolved_source_type = source_type_for_message(default_source_type, message)
    if should_skip_source_message(source, resolved_source_type):
        session.rollback()
        return None

    text = message.get("text")
    caption = message.get("caption")
    normalized_text = normalize_text(" ".join(part for part in [text, caption] if part))
    brand_match = match_brand_for_source(session, source, normalized_text)
    reply_to = message.get("reply_to_message") or {}
    author = message.get("from") or message.get("sender_chat") or {}

    mention = Mention(
        brand_id=brand_match.brand.id if brand_match.brand else None,
        source_id=source.id if source else None,
        platform="telegram",
        source_type=resolved_source_type,
        chat_id=chat_id,
        chat_username=chat.get("username"),
        chat_title=chat.get("title") or chat.get("first_name"),
        chat_description=source.description if source else chat_description,
        message_id=message_id,
        reply_to_message_id=reply_to.get("message_id"),
        discussion_message_id=reply_to.get("message_id"),
        author_id=author.get("id"),
        author_username=author.get("username"),
        author_name=display_name(author),
        text=text,
        caption=caption,
        normalized_text=normalized_text,
        media_type=detect_media_type(message),
        permalink=build_permalink(chat, message_id),
        brand_match_terms=brand_match.terms,
        raw=json_safe(update),
        message_date=parse_telegram_datetime(message.get("date")),
        edit_date=parse_telegram_datetime(message.get("edit_date")),
    )
    session.add(mention)

    if source.last_seen_message_id is None or message_id > source.last_seen_message_id:
        source.last_seen_message_id = message_id

    try:
        session.commit()
        session.refresh(mention)
        publish_mention_event(session, mention)
        return mention
    except IntegrityError:
        session.rollback()
        existing = (
            session.query(Mention)
            .filter(
                Mention.brand_id == mention.brand_id,
                Mention.source_id == mention.source_id,
                Mention.platform == "telegram",
                Mention.chat_id == chat_id,
                Mention.message_id == message_id,
            )
            .one_or_none()
        )
        return existing


def ingest_telethon_message(
    session: Session,
    *,
    chat: dict[str, Any],
    message: dict[str, Any],
    source_type: str,
    chat_description: str | None = None,
    parent_chat: dict[str, Any] | None = None,
    source_override: TelegramSource | None = None,
    parent_source_override: TelegramSource | None = None,
) -> Mention | None:
    update = {"telethon": True, "message": message, "chat": chat}
    chat_id = chat.get("id")
    message_id = message.get("message_id")
    if chat_id is None or message_id is None:
        return None

    if source_override is not None:
        source = source_override
    elif source_type == "comment" and parent_chat:
        source = upsert_linked_discussion_source(
            session,
            parent_chat=parent_chat,
            discussion_chat=chat,
            parent_source=parent_source_override,
        )
    else:
        source = upsert_telegram_source(session, chat, chat_description=chat_description)
    session.flush()
    if should_skip_source_message(source, source_type):
        session.rollback()
        return None

    text = message.get("text")
    caption = message.get("caption")
    normalized_text = normalize_text(" ".join(part for part in [text, caption] if part))
    brand_match = match_brand_for_source(session, source, normalized_text)
    author = message.get("author") or {}

    mention = Mention(
        brand_id=brand_match.brand.id if brand_match.brand else None,
        source_id=source.id,
        platform="telegram",
        source_type=source_type,
        chat_id=chat_id,
        chat_username=chat.get("username"),
        chat_title=chat.get("title"),
        chat_description=source.description if source else chat_description,
        message_id=message_id,
        reply_to_message_id=message.get("reply_to_message_id"),
        discussion_message_id=message.get("discussion_message_id"),
        author_id=author.get("id"),
        author_username=author.get("username"),
        author_name=author.get("name"),
        text=text,
        caption=caption,
        normalized_text=normalized_text,
        media_type=message.get("media_type"),
        permalink=message.get("permalink") or build_permalink(chat, message_id),
        brand_match_terms=brand_match.terms,
        raw=json_safe(update),
        message_date=message.get("date"),
        edit_date=message.get("edit_date"),
    )
    session.add(mention)
    if source.last_seen_message_id is None or message_id > source.last_seen_message_id:
        source.last_seen_message_id = message_id

    try:
        session.commit()
        session.refresh(mention)
        publish_mention_event(session, mention)
        return mention
    except IntegrityError:
        session.rollback()
        return (
            session.query(Mention)
            .filter(
                Mention.brand_id == mention.brand_id,
                Mention.source_id == mention.source_id,
                Mention.platform == "telegram",
                Mention.chat_id == chat_id,
                Mention.message_id == message_id,
            )
            .one_or_none()
        )


def display_name(author: dict[str, Any]) -> str | None:
    if not author:
        return None
    parts = [author.get("first_name"), author.get("last_name")]
    name = " ".join(part for part in parts if part).strip()
    return name or author.get("title") or author.get("username")


def should_skip_source_message(source: TelegramSource | None, source_type: str) -> bool:
    if not source or not source.active:
        return True
    if source_type == "comment":
        return not source.collect_comments
    if getattr(source, "source_role", None) == "discussion" and source_type == "group_message":
        return not source.collect_comments
    return not source.collect_posts


def detect_media_type(message: dict[str, Any]) -> str | None:
    for key in ("photo", "video", "audio", "voice", "document", "animation", "sticker", "poll"):
        if key in message:
            return key
    return None


def build_permalink(chat: dict[str, Any], message_id: int) -> str | None:
    username = chat.get("username")
    if username:
        return f"https://t.me/{username}/{message_id}"
    chat_id = chat.get("id")
    if isinstance(chat_id, int) and str(chat_id).startswith("-100"):
        internal_id = str(abs(chat_id))[3:]
        return f"https://t.me/c/{internal_id}/{message_id}"
    return None


def publish_mention_event(session: Session, mention: Mention) -> None:
    publish_realtime_event(
        session,
        "telegram_mention",
        {
            "id": mention.id,
            "brand_id": mention.brand_id,
            "source_id": mention.source_id,
            "source_type": mention.source_type,
            "chat_id": mention.chat_id,
            "chat_username": mention.chat_username,
            "message_id": mention.message_id,
            "message_date": mention.message_date,
            "created_at": mention.created_at,
        },
    )
