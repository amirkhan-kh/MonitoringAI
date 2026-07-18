from __future__ import annotations

import fcntl
import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import or_

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.models import TelegramSource
from app.services.telegram_api import TelegramBotApi, TelegramPollingConflictError
from app.services.telegram_command_agent import handle_command_update
from app.services.telegram_ingestion import get_message_from_update, ingest_telegram_update

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("telegram-worker")


def main() -> None:
    settings = get_settings()
    init_db()
    api = TelegramBotApi(settings.telegram_bot_token)
    with exclusive_polling_lock(settings.telegram_poll_lock_file):
        while not polling_transport_available(api):
            time.sleep(settings.telegram_poll_conflict_backoff_seconds)
        poll_updates(api)


def polling_transport_available(api: TelegramBotApi) -> bool:
    try:
        webhook = api.get_webhook_info() or {}
    except Exception:
        logger.exception("Telegram webhook status check failed; polling will not start")
        return False
    if str(webhook.get("url") or "").strip():
        logger.critical(
            "Telegram bot has an active webhook; polling will not start and the webhook will not be deleted"
        )
        return False
    return True


def poll_updates(api: TelegramBotApi) -> None:
    settings = get_settings()
    offset: int | None = None
    logger.info(
        "Telegram worker started with allowed_updates=%s command_allowlist_size=%s",
        settings.telegram_allowed_updates,
        len(settings.telegram_command_allowed_user_ids),
    )

    while True:
        try:
            updates = api.get_updates(
                offset=offset,
                timeout=settings.telegram_poll_timeout_seconds,
                allowed_updates=settings.telegram_allowed_updates,
            )
            for update in updates:
                offset = max(offset or 0, int(update["update_id"]) + 1)
                handle_update(api, update)
        except httpx.TimeoutException as exc:
            logger.warning("Telegram polling timeout: %s", exc)
            time.sleep(1)
        except TelegramPollingConflictError as exc:
            logger.critical(
                "Telegram getUpdates conflict: another poller is using this bot token; retrying in %ss (%s)",
                settings.telegram_poll_conflict_backoff_seconds,
                exc,
            )
            time.sleep(settings.telegram_poll_conflict_backoff_seconds)
        except Exception:
            logger.exception("Telegram polling failed")
            time.sleep(5)


@contextmanager
def exclusive_polling_lock(lock_file: str):
    path = Path(lock_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"Another Telegram polling worker owns {path}") from exc
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def handle_update(api: TelegramBotApi, update: dict[str, Any]) -> None:
    with SessionLocal() as session:
        if handle_command_update(api, session, update):
            return

    extracted = get_message_from_update(update)
    chat_description = None
    if extracted:
        _, message = extracted
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is not None:
            try:
                chat_info = api.get_chat(chat_id)
                chat_description = (chat_info or {}).get("description")
            except Exception:
                logger.debug("Could not fetch getChat for chat_id=%s", chat_id, exc_info=True)

    source_ids = []
    matching_source_exists = False
    if extracted:
        _, message = extracted
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        username = chat.get("username")
        filters = []
        if chat_id is not None:
            filters.append(TelegramSource.chat_id == chat_id)
        if username:
            filters.append(TelegramSource.username == username)
        if filters:
            with SessionLocal() as session:
                matching_source_exists = (
                    session.query(TelegramSource.id)
                    .filter(or_(*filters))
                    .first()
                    is not None
                )
                source_ids = [
                    row.id
                    for row in (
                        session.query(TelegramSource.id)
                        .filter(
                            TelegramSource.active.is_(True),
                            TelegramSource.bot_connection_id.is_(None),
                            or_(*filters),
                        )
                        .order_by(TelegramSource.created_at.asc())
                        .all()
                    )
                ]

    if source_ids:
        for source_id in source_ids:
            with SessionLocal() as session:
                source = session.get(TelegramSource, source_id)
                if source is None or not source.active:
                    continue
                mention = ingest_telegram_update(
                    session,
                    update,
                    chat_description=chat_description,
                    source_override=source,
                )
                log_stored_mention(mention)
        return

    if matching_source_exists:
        return

    with SessionLocal() as session:
        mention = ingest_telegram_update(session, update, chat_description=chat_description)
        log_stored_mention(mention)


def log_stored_mention(mention: Any | None) -> None:
    if mention:
        logger.info(
            "Stored telegram %s chat=%s message=%s brand=%s",
            mention.source_type,
            mention.chat_id,
            mention.message_id,
            mention.brand_id,
        )


if __name__ == "__main__":
    main()
