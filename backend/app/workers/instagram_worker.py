"""Instagram poller — catch-up ingestion of comments on the connected account's own
media. Webhooks give true real-time; this poller guarantees coverage even before the
Meta webhook is fully approved/live, and backfills anything a webhook missed. All
writes are idempotent (keyed on comment id), so poller + webhook never double-count.
"""

from __future__ import annotations

import logging
import time

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.models import InstagramSource
from app.services.instagram_api import InstagramApiError
from app.services.instagram_sync import sync_instagram_source

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("instagram-worker")


def main() -> None:
    settings = get_settings()
    init_db()
    logger.info("Instagram worker started interval=%ss", settings.instagram_poll_interval_seconds)

    while True:
        try:
            if not settings.instagram_enabled:
                time.sleep(settings.instagram_poll_interval_seconds)
                continue
            with SessionLocal() as session:
                source_ids = [
                    row.id
                    for row in session.query(InstagramSource.id)
                    .filter(InstagramSource.active.is_(True))
                    .order_by(InstagramSource.created_at.asc())
                    .all()
                ]
            for source_id in source_ids:
                _poll_source(settings, source_id)
        except Exception:
            logger.exception("Instagram worker loop failed")
        time.sleep(settings.instagram_poll_interval_seconds)


def _is_auth_error(exc: InstagramApiError) -> bool:
    if exc.status_code in (401, 190):
        return True
    msg = str(exc).lower()
    return exc.status_code == 400 and any(k in msg for k in ("oauth", "token", "session", "code\": 190", "code':190"))


def _poll_source(settings, source_id) -> None:
    with SessionLocal() as session:
        source = session.get(InstagramSource, source_id)
        if source is None or not source.active or not source.collect_comments:
            return
        # Don't hammer a token we already know is bad — the dashboard will show it red
        # and the operator swaps it. It resumes automatically once re-validated to active.
        if source.token_status == "invalid":
            return
        try:
            stats = sync_instagram_source(session, settings, source)
        except InstagramApiError as exc:
            if _is_auth_error(exc):
                source.token_status = "invalid"
                source.status_detail = str(exc)[:400]
                session.commit()
                logger.warning("IG token invalid source=%s — marked invalid: %s", source.ig_user_id, exc)
            else:
                logger.warning("IG media fetch failed source=%s: %s", source.ig_user_id, exc)
            return
        if stats.created_ids or stats.records_updated:
            logger.info(
                "Instagram synced source=%s media=%s posts=%s comments=%s updated=%s",
                source.username or source.ig_user_id,
                stats.media_seen,
                stats.posts_created,
                stats.comments_created,
                stats.records_updated,
            )


if __name__ == "__main__":
    main()
