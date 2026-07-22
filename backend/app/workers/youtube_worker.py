from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.main import sync_youtube_source
from app.models import YouTubeSource
from app.schemas import YouTubeSourceSyncRequest
from app.services.youtube_api import YouTubeApi, seconds_until_quota_reset


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("youtube-worker")

# keyword/hashtag sources are the only ones that hit search.list, which costs 100
# units per call against a 10k/day default quota.
SEARCH_SOURCE_KINDS = {"keyword", "hashtag"}


def is_due(source: YouTubeSource, *, now: datetime, min_interval_seconds: int) -> bool:
    """Whether an expensive search-backed source has waited out its own interval."""
    if source.source_kind not in SEARCH_SOURCE_KINDS:
        return True
    if source.last_checked_at is None:
        return True
    last_checked_at = source.last_checked_at
    if last_checked_at.tzinfo is None:
        last_checked_at = last_checked_at.replace(tzinfo=timezone.utc)
    return now - last_checked_at >= timedelta(seconds=min_interval_seconds)


def main() -> None:
    settings = get_settings()
    init_db()
    logger.info(
        "YouTube worker started interval=%ss search_interval=%ss",
        settings.youtube_poll_interval_seconds,
        settings.youtube_search_min_interval_seconds,
    )

    while True:
        cycle_sleep_seconds = settings.youtube_poll_interval_seconds
        try:
            if not settings.youtube_api_key:
                logger.info("YOUTUBE_API_KEY is not configured; YouTube sync paused")
                time.sleep(settings.youtube_poll_interval_seconds)
                continue

            with SessionLocal() as session:
                # Least-recently-synced first, so a cycle cut short by a rate limit
                # resumes with the sources it skipped instead of always replaying
                # the same oldest rows and starving the tail of the list.
                source_ids = [
                    row.id
                    for row in session.query(YouTubeSource.id)
                    .filter(YouTubeSource.active.is_(True))
                    .filter(YouTubeSource.deleted_at.is_(None))
                    .order_by(
                        YouTubeSource.last_checked_at.asc().nullsfirst(),
                        YouTubeSource.created_at.asc(),
                    )
                    .all()
                ]

            # One pooled HTTP client for the whole cycle instead of a fresh
            # TCP+TLS handshake per request.
            with YouTubeApi(settings.youtube_api_key) as api:
                # A short session per source keeps a connection/transaction from being
                # held open across every source's network round-trips for the cycle.
                for source_id in source_ids:
                    with SessionLocal() as session:
                        source = session.get(YouTubeSource, source_id)
                        if source is None or not source.active or source.deleted_at is not None:
                            continue
                        if not is_due(
                            source,
                            now=datetime.now(timezone.utc),
                            min_interval_seconds=settings.youtube_search_min_interval_seconds,
                        ):
                            continue
                        source_ref = source.source_ref
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
                                source_ref,
                                result.videos_seen,
                                result.comments_seen,
                                result.imported,
                            )
                            continue

                        logger.warning("YouTube source sync failed source=%s error=%s", source_ref, result.error)
                        if result.quota_exceeded:
                            # The daily allowance is spent. Retrying hourly just
                            # collects 403s until the midnight-Pacific reset.
                            cycle_sleep_seconds = seconds_until_quota_reset()
                            logger.error(
                                "YouTube daily quota exhausted; pausing all syncs for %ss (until quota reset)",
                                cycle_sleep_seconds,
                            )
                            break
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
                        # A single source failing (deleted channel, comments
                        # disabled, transient error) must not skip the rest.
        except Exception:
            logger.exception("YouTube worker loop failed")

        time.sleep(cycle_sleep_seconds)


if __name__ == "__main__":
    main()
