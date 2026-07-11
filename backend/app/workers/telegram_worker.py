from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.services.telegram_api import TelegramBotApi
from app.services.telegram_command_agent import handle_command_update
from app.services.telegram_ingestion import get_message_from_update, ingest_telegram_update

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("telegram-worker")


def main() -> None:
    settings = get_settings()
    init_db()
    api = TelegramBotApi(settings.telegram_bot_token)
    api.delete_webhook()
    offset: int | None = None
    logger.info("Telegram worker started with allowed_updates=%s", settings.telegram_allowed_updates)

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
        except Exception:
            logger.exception("Telegram polling failed")
            time.sleep(5)


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

    with SessionLocal() as session:
        mention = ingest_telegram_update(session, update, chat_description=chat_description)
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
