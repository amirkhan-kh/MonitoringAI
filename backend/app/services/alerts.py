from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AlertEvent, Analysis, Mention
from app.services.telegram_api import TelegramBotApi


def maybe_send_alert(session: Session, settings: Settings, mention: Mention, analysis: Analysis) -> AlertEvent | None:
    if not should_alert(settings, analysis):
        return None

    payload = {
        "mention_id": str(mention.id),
        "brand_id": str(mention.brand_id) if mention.brand_id else None,
        "sentiment": analysis.sentiment,
        "sentiment_score": analysis.sentiment_score,
        "risk_level": analysis.risk_level,
        "risk_score": analysis.risk_score,
        "summary": analysis.summary,
        "permalink": mention.permalink,
    }
    event = AlertEvent(
        brand_id=mention.brand_id,
        mention_id=mention.id,
        event_type="negative_risk",
        delivery_channel="telegram" if settings.alert_telegram_chat_id else None,
        delivery_target=settings.alert_telegram_chat_id or None,
        payload=payload,
    )
    session.add(event)
    session.commit()
    session.refresh(event)

    if settings.alert_telegram_chat_id:
        try:
            TelegramBotApi(settings.telegram_bot_token).send_message(
                settings.alert_telegram_chat_id,
                build_alert_text(mention, analysis),
            )
            event.status = "sent"
            event.sent_at = datetime.now(timezone.utc)
        except Exception as exc:
            event.status = "failed"
            event.error = str(exc)
        session.commit()
        session.refresh(event)
    return event


def should_alert(settings: Settings, analysis: Analysis) -> bool:
    risk_score = analysis.risk_score or 0.0
    sentiment_score = analysis.sentiment_score if analysis.sentiment_score is not None else 0.0
    risk_level = (analysis.risk_level or "").lower()
    sentiment = (analysis.sentiment or "").lower()
    return (
        risk_level in {"high", "critical"}
        or risk_score >= settings.alert_negative_risk_threshold
        or (sentiment == "negative" and sentiment_score <= settings.alert_negative_sentiment_threshold)
    )


def build_alert_text(mention: Mention, analysis: Analysis) -> str:
    lines = [
        "Reputatsion xavf signali",
        f"Manba: Telegram / {mention.chat_title or mention.chat_username or mention.chat_id}",
        f"Sentiment: {analysis.sentiment} ({analysis.sentiment_score})",
        f"Risk: {analysis.risk_level} ({analysis.risk_score})",
    ]
    if analysis.summary:
        lines.append(f"Xulosa: {analysis.summary}")
    if analysis.suggested_action:
        lines.append(f"Tavsiya: {analysis.suggested_action}")
    if mention.permalink:
        lines.append(f"Link: {mention.permalink}")
    return "\n".join(lines)
