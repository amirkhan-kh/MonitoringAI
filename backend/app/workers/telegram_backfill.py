from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from telethon import TelegramClient, utils
from telethon.errors import RPCError
from telethon.tl.custom.message import Message

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.models import TelegramSource
from app.services.telegram_ingestion import ingest_telethon_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("telegram-backfill")


async def main() -> None:
    settings = get_settings()
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        raise RuntimeError("TELEGRAM_API_ID and TELEGRAM_API_HASH are required for backfill")

    init_db()
    client = TelegramClient(settings.telegram_session_name, settings.telegram_api_id, settings.telegram_api_hash)
    await client.start()
    logger.info("Telethon backfill started")

    with SessionLocal() as session:
        sources = session.query(TelegramSource).filter(TelegramSource.active.is_(True)).all()
        source_refs = [
            (source.username or source.chat_id, source.monitor_from)
            for source in sources
            if source.username or source.chat_id
        ]

    for source_ref, from_date in source_refs:
        if source_ref is None:
            continue
        try:
            await backfill_source(
                client,
                source_ref,
                settings.telegram_backfill_limit,
                settings.telegram_backfill_comments_per_post,
                from_date=from_date,
            )
        except Exception:
            logger.exception("Backfill failed for source=%s", source_ref)

    await client.disconnect()


async def backfill_source(
    client: TelegramClient,
    source_ref: str | int,
    limit: int | None,
    comments_per_post: int,
    *,
    from_date: datetime | None = None,
) -> dict[str, int]:
    return await import_source_messages(
        client,
        source_ref,
        limit=limit,
        comments_per_post=comments_per_post,
        min_message_id=None,
        mark_backfilled=True,
        from_date=from_date,
    )


async def sync_source_since(
    client: TelegramClient,
    source_ref: str | int,
    *,
    min_message_id: int | None,
    limit: int,
    comments_per_post: int,
) -> dict[str, int]:
    return await import_source_messages(
        client,
        source_ref,
        limit=limit,
        comments_per_post=comments_per_post,
        min_message_id=min_message_id,
        mark_backfilled=False,
        from_date=None,
    )


async def import_source_messages(
    client: TelegramClient,
    source_ref: str | int,
    *,
    limit: int | None,
    comments_per_post: int,
    min_message_id: int | None,
    mark_backfilled: bool,
    from_date: datetime | None,
) -> dict[str, int]:
    entity = await client.get_entity(source_ref)
    chat = await entity_to_chat_dict(entity)
    normalized_from_date = normalize_datetime(from_date)
    iter_kwargs: dict[str, Any] = {}
    if limit is not None:
        iter_kwargs["limit"] = limit
    if min_message_id:
        iter_kwargs["min_id"] = min_message_id

    logger.info(
        "Importing Telegram source=%s limit=%s min_id=%s from_date=%s",
        source_ref,
        limit,
        min_message_id,
        normalized_from_date,
    )
    posts_seen = 0
    comments_seen = 0
    messages: list[Message] = []

    async for message in client.iter_messages(entity, **iter_kwargs):
        if not isinstance(message, Message):
            continue
        if normalized_from_date and normalize_datetime(message.date) and normalize_datetime(message.date) < normalized_from_date:
            break
        messages.append(message)

    for message in sorted(messages, key=lambda item: item.id or 0):
        posts_seen += 1
        message_payload = telethon_message_to_dict(message)
        source_type = source_type_for_telethon_message(chat, message)
        with SessionLocal() as session:
            ingest_telethon_message(session, chat=chat, message=message_payload, source_type=source_type)

        if comments_per_post > 0 and source_type == "channel_post":
            comments_seen += await backfill_comments(client, entity, chat, message, comments_per_post)

    if mark_backfilled:
        with SessionLocal() as session:
            source = session.query(TelegramSource).filter(TelegramSource.chat_id == chat.get("id")).one_or_none()
            if source:
                source.last_backfilled_at = datetime.now(timezone.utc)
                session.commit()

    return {"posts_seen": posts_seen, "comments_seen": comments_seen}


def normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def source_type_for_telethon_message(chat: dict[str, Any], message: Message) -> str:
    if chat.get("type") == "channel":
        return "channel_post"
    if getattr(message, "reply_to", None):
        return "comment"
    return "group_message"


async def backfill_comments(client: TelegramClient, entity: Any, chat: dict[str, Any], post: Message, limit: int) -> int:
    comments_seen = 0
    try:
        async for comment in client.iter_messages(entity, reply_to=post.id, limit=limit):
            if not isinstance(comment, Message):
                continue
            comments_seen += 1
            payload = telethon_message_to_dict(comment)
            payload["discussion_message_id"] = post.id
            payload["reply_to_message_id"] = getattr(comment.reply_to, "reply_to_msg_id", None) if comment.reply_to else post.id
            if getattr(comment, "chat", None):
                payload["discussion_chat"] = await entity_to_chat_dict(comment.chat)
            with SessionLocal() as session:
                ingest_telethon_message(session, chat=chat, message=payload, source_type="comment")
    except (RPCError, ValueError):
        logger.debug("No comments or inaccessible discussion for post=%s", post.id, exc_info=True)
    return comments_seen


async def entity_to_chat_dict(entity: Any) -> dict[str, Any]:
    if getattr(entity, "broadcast", False):
        chat_type = "channel"
    elif getattr(entity, "megagroup", False):
        chat_type = "supergroup"
    elif entity.__class__.__name__ == "Chat":
        chat_type = "group"
    elif entity.__class__.__name__ == "User":
        chat_type = "private"
    else:
        chat_type = "unknown"

    return {
        "id": utils.get_peer_id(entity),
        "username": getattr(entity, "username", None),
        "title": getattr(entity, "title", None) or getattr(entity, "first_name", None),
        "type": chat_type,
    }


def telethon_message_to_dict(message: Message) -> dict[str, Any]:
    author = None
    if message.sender:
        first_name = getattr(message.sender, "first_name", None)
        last_name = getattr(message.sender, "last_name", None)
        author = {
            "id": getattr(message.sender, "id", None),
            "username": getattr(message.sender, "username", None),
            "name": " ".join(part for part in [first_name, last_name] if part) or getattr(message.sender, "title", None),
        }
    return {
        "message_id": message.id,
        "text": message.raw_text or None,
        "caption": None,
        "date": message.date,
        "edit_date": message.edit_date,
        "reply_to_message_id": getattr(message.reply_to, "reply_to_msg_id", None) if message.reply_to else None,
        "author": author,
        "media_type": type(message.media).__name__ if message.media else None,
        "permalink": None,
        "views": getattr(message, "views", None),
        "forwards": getattr(message, "forwards", None),
        "replies": replies_to_dict(getattr(message, "replies", None)),
        "reactions": reactions_to_dict(getattr(message, "reactions", None)),
        "post_author": getattr(message, "post_author", None),
        "grouped_id": getattr(message, "grouped_id", None),
    }


def replies_to_dict(replies: Any) -> dict[str, Any] | None:
    if not replies:
        return None
    return {
        "count": getattr(replies, "replies", None),
        "comments": getattr(replies, "comments", None),
        "channel_id": getattr(replies, "channel_id", None),
        "max_id": getattr(replies, "max_id", None),
        "read_max_id": getattr(replies, "read_max_id", None),
    }


def reactions_to_dict(reactions: Any) -> dict[str, Any] | None:
    if not reactions:
        return None

    results = []
    for item in getattr(reactions, "results", None) or []:
        results.append(
            {
                "reaction": reaction_value(getattr(item, "reaction", None)),
                "count": getattr(item, "count", None),
                "chosen_order": getattr(item, "chosen_order", None),
            }
        )

    return {
        "results": results,
        "min": getattr(reactions, "min", None),
        "can_see_list": getattr(reactions, "can_see_list", None),
        "reactions_as_tags": getattr(reactions, "reactions_as_tags", None),
    }


def reaction_value(reaction: Any) -> str | None:
    if reaction is None:
        return None
    if getattr(reaction, "emoticon", None):
        return reaction.emoticon
    if getattr(reaction, "document_id", None):
        return str(reaction.document_id)
    return reaction.__class__.__name__


if __name__ == "__main__":
    asyncio.run(main())
