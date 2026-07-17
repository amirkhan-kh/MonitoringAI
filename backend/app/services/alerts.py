"""Reputation-risk alerts — detect, queue, and reliably deliver.

Design for "always correct":
  1. Detection is decoupled from delivery. When a risky mention is analyzed we
     persist a **pending** AlertEvent with everything needed to render the message.
     This never fails the analysis and never loses an alert (even if the Telegram
     chat isn't configured yet or the bot is down).
  2. A separate dispatcher (alert_worker) delivers pending/failed alerts with retry
     and rate-limiting, then marks them sent/abandoned.
  3. Idempotent: one alert per (platform, mention) via a payload dedup key.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AlertEvent
from app.services.telegram_api import TelegramBotApi

ALERT_MAX_ATTEMPTS = 6

PLATFORM_LABELS = {"telegram": "Telegram", "youtube": "YouTube", "instagram": "Instagram", "facebook": "Facebook"}
RISK_EMOJI = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
        session.commit()
        session.refresh(event)
        return event
    except Exception:
        session.rollback()
        return None


def build_alert_text(payload: dict) -> str:
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
    return "\n".join(lines)


def deliver_one(session: Session, settings: Settings, event: AlertEvent) -> None:
    """Try to send one alert; update its status + attempt count. Never raises."""
    payload = dict(event.payload or {})
    attempts = int(payload.get("attempts", 0))
    try:
        TelegramBotApi(settings.telegram_bot_token).send_message(
            settings.alert_telegram_chat_id, build_alert_text(payload)
        )
        event.status = "sent"
        event.sent_at = _utcnow()
        event.error = None
        event.delivery_target = settings.alert_telegram_chat_id
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
