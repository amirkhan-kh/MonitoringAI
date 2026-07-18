from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_
from telethon import TelegramClient, events
from telethon.errors import RPCError

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.models import TelegramSource
from app.services.telegram_ingestion import ingest_telethon_message
from app.workers.telegram_backfill import (
    backfill_comments,
    entity_to_chat_dict,
    source_type_for_telethon_message,
    sync_source_since,
    telethon_message_to_dict,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("telethon.network.mtprotosender").setLevel(logging.WARNING)
logger = logging.getLogger("telegram-live-sync")
FAILED_REF_BACKOFF_SECONDS = 900
failed_refs: dict[str, float] = {}


@dataclass(frozen=True)
class SourceSyncSpec:
    source_id: uuid.UUID
    ref: str | int
    title: str
    last_seen_message_id: int | None
    collect_comments: bool


async def main() -> None:
    settings = get_settings()
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        raise RuntimeError("TELEGRAM_API_ID and TELEGRAM_API_HASH are required for Telethon live sync")

    init_db()
    session_name = settings.telegram_live_sync_session_name or settings.telegram_session_name

    client = TelegramClient(
        session_name,
        settings.telegram_api_id,
        settings.telegram_api_hash,
        connection_retries=5,
        retry_delay=2,
        auto_reconnect=True,
    )
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError(
                f"Telethon live-sync session is not authorized. Run scripts/telegram_login.py {session_name} first; "
                "never copy a .session file between workers or machines."
            )

        register_event_handlers(client)
        logger.info("Telethon live sync started interval=%ss", settings.telegram_live_sync_interval_seconds)
        catchup_task = asyncio.create_task(catchup_loop(client))
        try:
            await client.run_until_disconnected()
        finally:
            catchup_task.cancel()
            await asyncio.gather(catchup_task, return_exceptions=True)
    finally:
        await client.disconnect()


def register_event_handlers(client: TelegramClient) -> None:
    async def handle_message(event: events.NewMessage.Event | events.MessageEdited.Event) -> None:
        try:
            await ingest_event_message(client, event)
        except Exception:
            logger.exception("Telethon realtime event ingestion failed")

    client.add_event_handler(handle_message, events.NewMessage(incoming=True))
    client.add_event_handler(handle_message, events.MessageEdited(incoming=True))


async def ingest_event_message(client: TelegramClient, event: events.NewMessage.Event | events.MessageEdited.Event) -> None:
    message = event.message
    if not message:
        return

    entity = await event.get_chat()
    if entity is None:
        return

    chat = await entity_to_chat_dict(entity)
    source_type = source_type_for_telethon_message(chat, message)
    payload = telethon_message_to_dict(message)
    with SessionLocal() as session:
        source_specs = [
            (source.id, source.collect_comments)
            for source in active_sources_for_chat(session, chat)
        ]
    for source_id, collect_comments in source_specs:
        with SessionLocal() as session:
            source = session.get(TelegramSource, source_id)
            if source is None or not source.active:
                continue
            ingest_telethon_message(
                session,
                chat=chat,
                message=payload,
                source_type=source_type,
                source_override=source,
            )
        set_telethon_access_status(source_id, "ready")

        if source_type == "channel_post" and collect_comments:
            comments_per_post = get_settings().telegram_live_sync_comments_per_post
            if comments_per_post:
                await backfill_comments(
                    client,
                    entity,
                    chat,
                    message,
                    comments_per_post,
                    parent_source_id=source_id,
                )


async def catchup_loop(client: TelegramClient) -> None:
    while True:
        await sync_once(client)
        await asyncio.sleep(get_settings().telegram_live_sync_interval_seconds)


async def sync_once(client: TelegramClient) -> None:
    settings = get_settings()
    specs = load_source_specs()
    if not specs:
        logger.info("No active Telegram sources for live sync")
        return

    for spec in specs:
        failed_until = failed_refs.get(str(spec.source_id), 0)
        if failed_until > time.monotonic():
            continue

        limit = settings.telegram_live_sync_batch_limit if spec.last_seen_message_id else settings.telegram_live_sync_initial_limit
        comments_per_post = settings.telegram_live_sync_comments_per_post if spec.collect_comments else 0
        try:
            counts = await sync_source_since(
                client,
                spec.ref,
                min_message_id=spec.last_seen_message_id,
                limit=limit,
                comments_per_post=comments_per_post,
                source_id=spec.source_id,
            )
            if counts.get("posts_seen") or counts.get("comments_seen"):
                logger.info(
                    "Synced source=%s posts=%s comments=%s",
                    spec.title,
                    counts.get("posts_seen", 0),
                    counts.get("comments_seen", 0),
                )
            set_telethon_access_status(spec.source_id, "ready")
            failed_refs.pop(str(spec.source_id), None)
        except (ValueError, RPCError, ConnectionError, OSError, asyncio.TimeoutError) as exc:
            failed_refs[str(spec.source_id)] = time.monotonic() + FAILED_REF_BACKOFF_SECONDS
            if isinstance(exc, (ValueError, RPCError)):
                set_telethon_access_status(spec.source_id, "denied")
            logger.warning("Telethon source unavailable for %s ref=%s: %s", spec.title, spec.ref, exc)
        except Exception:
            logger.exception("Telethon live sync failed for source=%s ref=%s", spec.title, spec.ref)


def active_source_for_chat(session: Any, chat: dict[str, Any]) -> TelegramSource | None:
    sources = active_sources_for_chat(session, chat)
    return sources[0] if sources else None


def set_telethon_access_status(source_id: uuid.UUID, status: str) -> None:
    with SessionLocal() as session:
        source = session.get(TelegramSource, source_id)
        if source is None or not source.connector_managed:
            return
        source.telethon_access_status = status
        source.access_checked_at = datetime.now(timezone.utc)
        session.commit()


def active_sources_for_chat(session: Any, chat: dict[str, Any]) -> list[TelegramSource]:
    chat_id = chat.get("id")
    username = chat.get("username")
    filters = []
    if chat_id is not None:
        filters.append(TelegramSource.chat_id == chat_id)
    if username:
        filters.append(TelegramSource.username == username)
    if not filters:
        return None
    return list(
        session.query(TelegramSource)
        .filter(TelegramSource.active.is_(True))
        .filter(TelegramSource.source_role != "bot_inbox")
        .filter(or_(*filters))
        .order_by(TelegramSource.created_at.asc())
        .all()
    )


def load_source_specs() -> list[SourceSyncSpec]:
    with SessionLocal() as session:
        sources = (
            session.query(TelegramSource)
            .filter(TelegramSource.active.is_(True))
            .filter(or_(TelegramSource.collect_posts.is_(True), TelegramSource.collect_comments.is_(True)))
            .filter(TelegramSource.source_category != "bot")
            .filter(TelegramSource.source_kind != "private")
            .order_by(TelegramSource.created_at.asc())
            .all()
        )
        specs: list[SourceSyncSpec] = []
        for source in sources:
            ref: str | int | None = source.username or source.chat_id
            if ref is None:
                continue
            specs.append(
                SourceSyncSpec(
                    source_id=source.id,
                    ref=ref,
                    title=source.title or source.username or str(source.chat_id),
                    last_seen_message_id=source.last_seen_message_id,
                    collect_comments=source.collect_comments,
                )
            )
        return specs


async def run_forever() -> None:
    """Supervise the live-sync client so a transient disconnect self-heals.

    Telethon raises a transport ``ConnectionError`` once it exhausts its built-in
    reconnect budget; without this loop that error would exit the process and the
    worker would stay down until manually restarted.
    """
    backoff = 5
    while True:
        try:
            await main()
            backoff = 5  # a clean disconnect resets the backoff
        except (ConnectionError, OSError, asyncio.TimeoutError) as exc:
            logger.warning("Live sync connection lost; reconnecting in %ss: %s", backoff, exc)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 300)
        except Exception:
            logger.exception("Live sync crashed; restarting in %ss", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 300)


if __name__ == "__main__":
    asyncio.run(run_forever())
