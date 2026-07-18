from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

from sqlalchemy import or_, text

from app.config import get_settings
from app.db import SessionLocal, engine, init_db
from app.models import TelegramBotConnection, TelegramSource
from app.services.telegram_api import TelegramBotApi, TelegramBotApiError
from app.services.telegram_connector import (
    ConnectorEncryptionError,
    decrypt_bot_token,
    ingest_connector_update,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("telegram-connector-worker")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def advisory_key(connection_id: uuid.UUID) -> int:
    return int.from_bytes(connection_id.bytes[:8], byteorder="big", signed=True)


@contextmanager
def connection_poll_lock(connection_id: uuid.UUID) -> Iterator[bool]:
    if engine.dialect.name != "postgresql":
        yield True
        return

    lock_connection = engine.connect()
    lock_key = advisory_key(connection_id)
    acquired = bool(
        lock_connection.execute(
            text("SELECT pg_try_advisory_lock(:lock_key)"),
            {"lock_key": lock_key},
        ).scalar()
    )
    try:
        yield acquired
    finally:
        if acquired:
            lock_connection.execute(
                text("SELECT pg_advisory_unlock(:lock_key)"),
                {"lock_key": lock_key},
            )
        lock_connection.close()


def load_due_connection_ids() -> list[uuid.UUID]:
    now = utcnow()
    with SessionLocal() as session:
        return [
            row.id
            for row in (
                session.query(TelegramBotConnection.id)
                .filter(
                    TelegramBotConnection.active.is_(True),
                    TelegramBotConnection.mode == "polling",
                    TelegramBotConnection.token_ciphertext.is_not(None),
                    or_(
                        TelegramBotConnection.retry_after_at.is_(None),
                        TelegramBotConnection.retry_after_at <= now,
                    ),
                )
                .order_by(TelegramBotConnection.created_at.asc())
                .all()
            )
        ]


def update_connection_status(
    connection_id: uuid.UUID,
    *,
    status: str,
    detail: str,
    retry_after_seconds: int | None = None,
    active: bool | None = None,
) -> None:
    with SessionLocal() as session:
        connection = session.get(TelegramBotConnection, connection_id)
        if connection is None:
            return
        connection.status = status
        connection.status_detail = detail
        connection.retry_after_at = (
            utcnow() + timedelta(seconds=retry_after_seconds)
            if retry_after_seconds is not None
            else None
        )
        if active is not None:
            connection.active = active
            if not active:
                (
                    session.query(TelegramSource)
                    .filter(
                        TelegramSource.bot_connection_id == connection_id,
                        TelegramSource.source_role == "bot_inbox",
                    )
                    .update({TelegramSource.active: False}, synchronize_session=False)
                )
        if status == "active":
            (
                session.query(TelegramSource)
                .filter(
                    TelegramSource.bot_connection_id == connection_id,
                    TelegramSource.source_role == "bot_inbox",
                )
                .update(
                    {
                        TelegramSource.active: True,
                        TelegramSource.bot_access_status: "ready",
                    },
                    synchronize_session=False,
                )
            )
        elif status in {"invalid", "encryption_error"}:
            (
                session.query(TelegramSource)
                .filter(TelegramSource.bot_connection_id == connection_id)
                .update({TelegramSource.bot_access_status: "denied"}, synchronize_session=False)
            )
        session.commit()


def handle_poll_error(connection_id: uuid.UUID, exc: TelegramBotApiError) -> None:
    settings = get_settings()
    if exc.status_code == 401:
        update_connection_status(
            connection_id,
            status="invalid",
            detail="Telegram bot token rad etildi; connection suspend qilindi",
            active=False,
        )
        logger.warning("Telegram connector suspended connection=%s status=401", connection_id)
        return
    if exc.status_code == 409:
        update_connection_status(
            connection_id,
            status="conflict",
            detail="Boshqa consumer yoki webhook Telegram update oqimini ishlatyapti",
            retry_after_seconds=settings.telegram_poll_conflict_backoff_seconds,
        )
        logger.warning("Telegram connector conflict connection=%s status=409", connection_id)
        return
    if exc.status_code == 429:
        retry_after = max(1, exc.retry_after_seconds or 60)
        update_connection_status(
            connection_id,
            status="rate_limited",
            detail="Telegram rate limit; worker belgilangan vaqtdan keyin qayta urinadi",
            retry_after_seconds=retry_after,
        )
        logger.warning("Telegram connector rate limited connection=%s retry_after=%ss", connection_id, retry_after)
        return

    update_connection_status(
        connection_id,
        status="error",
        detail="Telegram polling vaqtincha ishlamadi",
        retry_after_seconds=settings.telegram_connector_error_backoff_seconds,
    )
    logger.warning("Telegram connector poll error connection=%s status=%s", connection_id, exc.status_code)


def poll_connection(connection_id: uuid.UUID) -> None:
    with connection_poll_lock(connection_id) as acquired:
        if not acquired:
            return

        with SessionLocal() as session:
            connection = session.get(TelegramBotConnection, connection_id)
            if (
                connection is None
                or not connection.active
                or connection.mode != "polling"
                or not connection.token_ciphertext
                or (connection.retry_after_at and connection.retry_after_at > utcnow())
            ):
                return
            try:
                token = decrypt_bot_token(connection.token_ciphertext)
            except ConnectorEncryptionError:
                update_connection_status(
                    connection_id,
                    status="encryption_error",
                    detail="Connector tokenini decrypt qilib bo'lmadi; connection suspend qilindi",
                    active=False,
                )
                logger.error("Telegram connector encryption error connection=%s", connection_id)
                return
            offset = connection.last_update_id + 1 if connection.last_update_id is not None else None

        api = TelegramBotApi(token)
        try:
            updates = api.get_updates(
                offset=offset,
                timeout=0,
                allowed_updates=get_settings().telegram_allowed_updates,
            )
        except TelegramBotApiError as exc:
            handle_poll_error(connection_id, exc)
            return

        for update in sorted(updates, key=lambda item: int(item.get("update_id") or -1)):
            update_id = update.get("update_id")
            if update_id is None:
                continue
            with SessionLocal() as session:
                connection = session.get(TelegramBotConnection, connection_id)
                if connection is None or not connection.active or connection.mode != "polling":
                    return
                if connection.last_update_id is not None and int(update_id) <= connection.last_update_id:
                    continue
                try:
                    ingest_connector_update(session, update, connection)
                    connection.last_update_id = int(update_id)
                    connection.status = "active"
                    connection.status_detail = "Polling faol"
                    connection.retry_after_at = None
                    (
                        session.query(TelegramSource)
                        .filter(
                            TelegramSource.bot_connection_id == connection_id,
                            TelegramSource.source_role == "bot_inbox",
                        )
                        .update(
                            {TelegramSource.bot_access_status: "ready"},
                            synchronize_session=False,
                        )
                    )
                    session.commit()
                except Exception:
                    session.rollback()
                    update_connection_status(
                        connection_id,
                        status="error",
                        detail="Telegram update xavfsiz qayta ishlanmadi; cursor siljitilmadi",
                        retry_after_seconds=get_settings().telegram_connector_error_backoff_seconds,
                    )
                    logger.exception("Telegram connector ingestion failed connection=%s", connection_id)
                    return

        if not updates:
            update_connection_status(
                connection_id,
                status="active",
                detail="Polling faol",
            )


def run_once() -> None:
    for connection_id in load_due_connection_ids():
        try:
            poll_connection(connection_id)
        except Exception:
            logger.exception("Telegram connector cycle failed connection=%s", connection_id)


def main() -> None:
    settings = get_settings()
    init_db()
    logger.info("Telegram connector worker started interval=%ss", settings.telegram_connector_poll_interval_seconds)
    while True:
        run_once()
        time.sleep(settings.telegram_connector_poll_interval_seconds)


if __name__ == "__main__":
    main()
