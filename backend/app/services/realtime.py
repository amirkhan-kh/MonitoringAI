from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, AsyncIterator
from uuid import UUID

import psycopg
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings

REALTIME_CHANNEL = "monitoring_realtime"
logger = logging.getLogger("realtime")


def publish_realtime_event(
    session: Session,
    event_type: str,
    payload: dict[str, Any],
    *,
    commit: bool = True,
) -> None:
    """Queue a realtime event on the session.

    Postgres delivers NOTIFY at COMMIT, so callers that are mid-transaction should
    pass ``commit=False`` and let their own commit publish the batch — committing
    here would break their atomicity by making partial work durable.
    """
    message = json.dumps({"type": event_type, "payload": payload}, ensure_ascii=False, default=json_default)
    try:
        session.execute(text("select pg_notify(:channel, :payload)"), {"channel": REALTIME_CHANNEL, "payload": message})
        if commit:
            session.commit()
    except Exception:
        if commit:
            session.rollback()
        logger.debug("Could not publish realtime event type=%s", event_type, exc_info=True)


async def realtime_event_stream(request: Any) -> AsyncIterator[str]:
    conninfo = psycopg_conninfo(get_settings().database_url)
    async with await psycopg.AsyncConnection.connect(conninfo, autocommit=True) as connection:
        await connection.execute(f"LISTEN {REALTIME_CHANNEL}")
        yield sse("connected", {"ok": True})

        while True:
            if await request.is_disconnected():
                break

            had_notification = False
            async for notify in connection.notifies(timeout=25, stop_after=1):
                had_notification = True
                yield notification_to_sse(notify.payload)

            if not had_notification:
                yield sse("ping", {"ok": True})


def notification_to_sse(payload: str) -> str:
    try:
        message = json.loads(payload)
    except json.JSONDecodeError:
        return sse("message", {"raw": payload})
    return sse(str(message.get("type") or "message"), message.get("payload") or {})


def sse(event: str, payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False, default=json_default)
    return f"event: {event}\ndata: {data}\n\n"


def json_default(value: Any) -> str:
    if isinstance(value, (datetime, date, UUID)):
        return str(value)
    return str(value)


def psycopg_conninfo(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)
