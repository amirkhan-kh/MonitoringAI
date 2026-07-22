"""Reputation-risk alerts — detect, queue, deliver, and work off in the staff group.

Design for "always correct":
  1. Detection is decoupled from delivery. When a risky mention is analyzed we
     persist a **pending** AlertEvent with everything needed to render the message.
     This never fails the analysis and never loses an alert (even if the Telegram
     chat isn't configured yet or the bot is down).
  2. A separate dispatcher (alert_worker) delivers pending/failed alerts with retry
     and rate-limiting, then marks them sent/abandoned.
  3. Idempotent: one alert per (platform, mention) via a payload dedup key.
  4. Every delivered card carries inline buttons, so the staff group closes the loop:
     who reviewed the AI verdict, and who actually replied to the customer. That state
     lives in DB columns (see AlertEvent.work_status), not in the message text — the
     message is only a rendering of it, and can be re-rendered at any time.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AlertEvent
from app.services.realtime import publish_realtime_event
from app.services.telegram_api import TelegramBotApi

ALERT_MAX_ATTEMPTS = 6

PLATFORM_LABELS = {"telegram": "Telegram", "youtube": "YouTube", "instagram": "Instagram", "facebook": "Facebook"}
RISK_EMOJI = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
RISK_ORDER = ("critical", "high", "medium", "low")

# Uzbekistan time — the staff group reads timestamps, so render them locally.
LOCAL_TZ = timezone(timedelta(hours=5))

WORK_STATUS_OPEN = "open"
WORK_STATUS_CHECKED = "checked"
WORK_STATUS_ANSWERED = "answered"
OPEN_WORK_STATUSES = (WORK_STATUS_OPEN, WORK_STATUS_CHECKED)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def local_time_text(value: datetime | None) -> str:
    value = _as_utc(value)
    return value.astimezone(LOCAL_TZ).strftime("%H:%M") if value else "-"


def duration_text(delta: timedelta | None) -> str:
    """Human duration in Uzbek, coarse enough to stay stable between refreshes."""
    if delta is None:
        return "-"
    minutes = max(0, int(delta.total_seconds() // 60))
    if minutes < 60:
        return f"{minutes} daq"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours} soat {minutes} daq" if minutes else f"{hours} soat"
    days, hours = divmod(hours, 24)
    return f"{days} kun {hours} soat" if hours else f"{days} kun"


def should_alert(settings: Settings, analysis) -> bool:
    """A mention is alert-worthy when the model flags real reputation risk."""
    risk_level = (getattr(analysis, "risk_level", None) or "").lower()
    sentiment = (getattr(analysis, "sentiment", None) or "").lower()
    risk_score = getattr(analysis, "risk_score", None) or 0.0
    sentiment_score = getattr(analysis, "sentiment_score", None)
    sentiment_score = sentiment_score if sentiment_score is not None else 0.0
    return (
        risk_level in {"high", "critical"}
        or risk_score >= settings.alert_negative_risk_threshold
        or (sentiment == "negative" and sentiment_score <= settings.alert_negative_sentiment_threshold)
    )


def record_alert(
    session: Session,
    settings: Settings,
    *,
    platform: str,
    brand_id,
    mention_id,
    brand_name: str | None,
    source: str | None,
    author: str | None,
    text: str | None,
    permalink: str | None,
    analysis,
) -> AlertEvent | None:
    """Queue a pending alert if the analysis is risky and one doesn't already exist.

    Never raises — alerting must not break the analysis pipeline.
    """
    try:
        if not should_alert(settings, analysis):
            return None
        dedup_key = f"{platform}:{mention_id}"
        exists = (
            session.query(AlertEvent.id)
            .filter(AlertEvent.payload["dedup_key"].astext == dedup_key)
            .first()
        )
        if exists:
            return None
        payload = {
            "dedup_key": dedup_key,
            "platform": platform,
            "brand_name": brand_name,
            "source": source,
            "author": author,
            "text": (text or "").strip()[:500],
            "sentiment": analysis.sentiment,
            "sentiment_score": analysis.sentiment_score,
            "risk_level": analysis.risk_level,
            "risk_score": analysis.risk_score,
            "summary": analysis.summary,
            "suggested_action": analysis.suggested_action,
            "permalink": permalink,
            "attempts": 0,
        }
        event = AlertEvent(
            brand_id=brand_id,
            # mention_id FK only exists for telegram mentions; others live in payload.
            mention_id=mention_id if platform == "telegram" else None,
            event_type="reputation_risk",
            status="pending",
            delivery_channel="telegram",
            delivery_target=settings.alert_telegram_chat_id or None,
            payload=payload,
        )
        session.add(event)
        session.flush()
        # The dashboard inbox listens for this, so a new signal shows up there the moment
        # it is detected — before the Telegram card is even delivered.
        publish_realtime_event(
            session,
            "alert_event",
            {
                "id": event.id,
                "brand_id": event.brand_id,
                "work_status": event.work_status,
                "status": event.status,
                "payload": payload,
                "created_at": event.created_at,
            },
            commit=False,
        )
        session.commit()
        session.refresh(event)
        return event
    except Exception:
        session.rollback()
        return None


def build_alert_text(payload: dict, event: AlertEvent | None = None) -> str:
    risk = (payload.get("risk_level") or "").lower()
    emoji = RISK_EMOJI.get(risk, "⚠️")
    platform = PLATFORM_LABELS.get(payload.get("platform"), payload.get("platform") or "?")
    lines = [f"{emoji} Reputatsion xavf signali — {platform}"]
    if payload.get("brand_name"):
        lines.append(f"Brend: {payload['brand_name']}")
    if payload.get("source"):
        lines.append(f"Manba: {payload['source']}")
    if payload.get("author"):
        lines.append(f"Muallif: {payload['author']}")
    lines.append(f"Risk: {payload.get('risk_level')} ({payload.get('risk_score')})")
    lines.append(f"Sentiment: {payload.get('sentiment')} ({payload.get('sentiment_score')})")
    if payload.get("text"):
        lines.append(f"\nMatn: {payload['text']}")
    if payload.get("summary"):
        lines.append(f"Xulosa: {payload['summary']}")
    if payload.get("suggested_action"):
        lines.append(f"Tavsiya: {payload['suggested_action']}")
    if payload.get("permalink"):
        lines.append(f"Link: {payload['permalink']}")
    if event is not None:
        lines.append("")
        lines.extend(build_status_lines(event))
    return "\n".join(lines)


def build_status_lines(event: AlertEvent) -> list[str]:
    """The workflow footer: always says whether a human has closed this signal."""
    work_status = event.work_status or WORK_STATUS_OPEN
    lines: list[str] = []
    if work_status == WORK_STATUS_ANSWERED:
        answered_at = _as_utc(event.answered_at)
        started_at = _as_utc(event.sent_at) or _as_utc(event.created_at)
        took = duration_text(answered_at - started_at) if answered_at and started_at else "-"
        lines.append("📌 Holat: ✅ Javob berildi")
        lines.append(f"👤 Javob bergan: {event.answered_by or '-'} · {local_time_text(event.answered_at)} ({took})")
        if event.checked_by:
            lines.append(f"🔎 Tekshirgan: {event.checked_by} · {local_time_text(event.checked_at)}")
    elif work_status == WORK_STATUS_CHECKED:
        lines.append(f"📌 Holat: 👀 Tekshirildi — {event.checked_by or '-'} · {local_time_text(event.checked_at)}")
        lines.append("⏳ Mijozga hali javob berilmagan")
    else:
        lines.append("📌 Holat: 🆕 Tekshirilmadi — javob kutilmoqda")
    return lines


def build_alert_keyboard(event: AlertEvent) -> dict:
    """Inline buttons under the card.

    Two workflow buttons (the AI verdict was reviewed / the customer was answered) plus a
    direct deep link to the comment, so answering is one tap away from the alert.
    """
    work_status = event.work_status or WORK_STATUS_OPEN
    event_id = str(event.id)
    if work_status == WORK_STATUS_ANSWERED:
        rows = [[{"text": "↩️ Qayta ochish", "callback_data": f"alert:reopen:{event_id}"}]]
    else:
        checked = work_status == WORK_STATUS_CHECKED
        check_label = f"☑️ Tekshirildi · {_short_name(event.checked_by)}" if checked else "🔍 Tekshirildi"
        rows = [
            [
                {"text": check_label, "callback_data": f"alert:check:{event_id}"},
                {"text": "💬 Javob berdim", "callback_data": f"alert:answer:{event_id}"},
            ]
        ]
    permalink = (event.payload or {}).get("permalink")
    if permalink:
        rows.append([{"text": "🔗 Kommentga o'tish", "url": permalink}])
    return {"inline_keyboard": rows}


def _short_name(name: str | None, limit: int = 14) -> str:
    name = (name or "").strip()
    if not name:
        return "-"
    return name if len(name) <= limit else name[: limit - 1] + "…"


def deliver_one(session: Session, settings: Settings, event: AlertEvent) -> None:
    """Try to send one alert; update its status + attempt count. Never raises."""
    payload = dict(event.payload or {})
    attempts = int(payload.get("attempts", 0))
    try:
        response = TelegramBotApi(settings.telegram_bot_token).send_message(
            settings.alert_telegram_chat_id,
            build_alert_text(payload, event),
            reply_markup=build_alert_keyboard(event),
        )
        sent_message = response.get("result") or {}
        event.status = "sent"
        event.sent_at = _utcnow()
        event.error = None
        event.delivery_target = settings.alert_telegram_chat_id
        # Remember where the card landed so button presses can edit it in place.
        event.telegram_chat_id = str((sent_message.get("chat") or {}).get("id") or settings.alert_telegram_chat_id)
        message_id = sent_message.get("message_id")
        event.telegram_message_id = int(message_id) if message_id else None
    except Exception as exc:  # noqa: BLE001 - record + retry, never crash the loop
        attempts += 1
        event.error = str(exc)[:500]
        event.status = "abandoned" if attempts >= ALERT_MAX_ATTEMPTS else "failed"
    # Reassign payload so SQLAlchemy detects the JSONB change.
    payload["attempts"] = attempts
    event.payload = payload
    session.commit()


def dispatch_pending_alerts(session: Session, settings: Settings, limit: int = 20) -> int:
    """Deliver queued alerts. No-op (leaves them pending) until a chat id is set."""
    if not settings.alert_telegram_chat_id or not settings.telegram_bot_token:
        return 0
    events = (
        session.query(AlertEvent)
        .filter(AlertEvent.delivery_channel == "telegram")
        .filter(AlertEvent.status.in_(["pending", "failed"]))
        .order_by(AlertEvent.created_at.asc())
        .limit(limit)
        .all()
    )
    sent = 0
    for event in events:
        deliver_one(session, settings, event)
        if event.status == "sent":
            sent += 1
    return sent


def due_reminder_alerts(session: Session, settings: Settings, limit: int = 10) -> list[AlertEvent]:
    """Delivered signals nobody has answered within the SLA, oldest first.

    Escalation is capped (``alert_reminder_max``) so a signal that is genuinely stuck
    cannot turn the staff group into a notification treadmill.
    """
    if settings.alert_sla_minutes <= 0:
        return []
    now = _utcnow()
    first_due = now - timedelta(minutes=settings.alert_sla_minutes)
    repeat_due = now - timedelta(minutes=settings.alert_reminder_repeat_minutes)
    return (
        session.query(AlertEvent)
        .filter(AlertEvent.status == "sent")
        .filter(AlertEvent.work_status.in_(OPEN_WORK_STATUSES))
        .filter(AlertEvent.telegram_message_id.is_not(None))
        .filter(AlertEvent.reminder_count < settings.alert_reminder_max)
        .filter(AlertEvent.sent_at < first_due)
        .filter((AlertEvent.reminded_at.is_(None)) | (AlertEvent.reminded_at < repeat_due))
        .order_by(AlertEvent.sent_at.asc())
        .limit(limit)
        .all()
    )


def send_sla_reminders(session: Session, settings: Settings, api: TelegramBotApi | None = None) -> int:
    """Nudge the staff group about signals still waiting for a reply. Never raises."""
    if not settings.alert_telegram_chat_id or not settings.telegram_bot_token:
        return 0
    events = due_reminder_alerts(session, settings)
    if not events:
        return 0
    api = api or TelegramBotApi(settings.telegram_bot_token)
    sent = 0
    now = _utcnow()
    for event in events:
        waited = duration_text(now - (_as_utc(event.sent_at) or now))
        payload = event.payload or {}
        who = "Tekshirilgan, lekin javob berilmagan" if event.work_status == WORK_STATUS_CHECKED else "Hali hech kim ko'rmadi"
        text = (
            f"⏰ {waited} javobsiz turibdi — {who}.\n"
            f"Manba: {payload.get('source') or '-'}\n"
            "Kim oladi? Javob bergach «💬 Javob berdim» tugmasini bosing."
        )
        try:
            api.send_message(
                event.telegram_chat_id or settings.alert_telegram_chat_id,
                text,
                reply_to_message_id=event.telegram_message_id,
                reply_markup=build_alert_keyboard(event),
            )
        except Exception:  # noqa: BLE001 - a failed nudge must not stall the loop
            continue
        event.reminded_at = now
        event.reminder_count = int(event.reminder_count or 0) + 1
        sent += 1
    session.commit()
    return sent
