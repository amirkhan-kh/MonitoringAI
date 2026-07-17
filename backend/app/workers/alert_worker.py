"""Alert dispatcher — delivers queued reputation-risk alerts to Telegram reliably.

Detection (in ai_worker) only queues pending AlertEvents; this worker is the single
place that talks to Telegram, so delivery has retry + rate-limiting and survives a
missing chat id / bot outage without losing alerts. Idempotent and safe to restart.
"""

from __future__ import annotations

import logging
import time

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.services.alerts import dispatch_pending_alerts

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("alert-worker")
logging.getLogger("httpx").setLevel(logging.WARNING)


def main() -> None:
    settings = get_settings()
    init_db()
    logger.info(
        "Alert worker started interval=%ss chat=%s",
        settings.alert_poll_interval_seconds,
        "set" if settings.alert_telegram_chat_id else "NOT SET (alerts will queue as pending)",
    )
    warned_no_chat = False
    while True:
        try:
            settings = get_settings()
            if not settings.alert_telegram_chat_id:
                if not warned_no_chat:
                    logger.info("ALERT_TELEGRAM_CHAT_ID not set — queuing alerts, not delivering yet")
                    warned_no_chat = True
            else:
                warned_no_chat = False
                with SessionLocal() as session:
                    sent = dispatch_pending_alerts(session, settings)
                    if sent:
                        logger.info("Delivered %s alert(s) to Telegram", sent)
        except Exception:
            logger.exception("Alert dispatch loop failed")
        time.sleep(settings.alert_poll_interval_seconds)


if __name__ == "__main__":
    main()
