from __future__ import annotations

import logging
import time

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.main import sync_youtube_source
from app.models import YouTubeSource
from app.schemas import YouTubeSourceSyncRequest
from app.services.youtube_api import YouTubeApi


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("youtube-worker")


def main() -> None:
    settings = get_settings()
    init_db()
    logger.info("YouTube worker started interval=%ss", settings.youtube_poll_interval_seconds)

    while True:
        cycle_sleep_seconds = settings.youtube_poll_interval_seconds
        try:
            if not settings.youtube_api_key:
                logger.info("YOUTUBE_API_KEY is not configured; YouTube sync paused")
                time.sleep(settings.youtube_poll_interval_seconds)
                continue

            api = YouTubeApi(settings.youtube_api_key)
            with SessionLocal() as session:
                source_ids = [
                    row.id
                    for row in session.query(YouTubeSource.id)
                    .filter(YouTubeSource.active.is_(True))
                    .order_by(YouTubeSource.created_at.asc())
                    .all()
                ]

            # A short session per source keeps a connection/transaction from being
            # held open across every source's network round-trips for the cycle.
            for source_id in source_ids:
                with SessionLocal() as session:
                    source = session.get(YouTubeSource, source_id)
                    if source is None or not source.active:
                        continue
                    result = sync_youtube_source(
                        session,
                        source,
                        api,
                        YouTubeSourceSyncRequest(
                            max_pages=settings.youtube_sync_max_pages,
                            comments_per_video=settings.youtube_comments_per_video,
                        ),
                    )
                    if result.ok:
                        logger.info(
                            "Synced YouTube source=%s videos=%s comments=%s imported=%s",
                            source.source_ref,
                            result.videos_seen,
                            result.comments_seen,
                            result.imported,
                        )
                    else:
                        logger.warning("YouTube source sync failed source=%s error=%s", source.source_ref, result.error)
                        if result.rate_limited:
                            cycle_sleep_seconds = max(
                                settings.youtube_rate_limit_backoff_seconds,
                                result.retry_after_seconds or 0,
                            )
                            logger.warning(
                                "YouTube API rate limited; pausing all source syncs for %ss",
                                cycle_sleep_seconds,
                            )
                            break
        except Exception:
            logger.exception("YouTube worker loop failed")

        time.sleep(cycle_sleep_seconds)


if __name__ == "__main__":
    main()
