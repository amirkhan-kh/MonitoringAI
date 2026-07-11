from __future__ import annotations

import logging
import time

from sqlalchemy.orm import joinedload

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.models import Analysis, Mention, YouTubeAnalysis, YouTubeMention
from app.services.alerts import maybe_send_alert
from app.services.gemini_analysis import (
    ProviderRetryableError,
    analyze_mention,
    analyze_youtube_mention,
    create_gemini_client,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ai-worker")

MAX_PROVIDER_BACKOFF_SECONDS = 300


def _short(exc: Exception, limit: int = 200) -> str:
    message = " ".join(str(exc).split())
    return message[:limit] + ("…" if len(message) > limit else "")


def main() -> None:
    settings = get_settings()
    init_db()
    logger.info("AI worker started model=%s vertex=%s", settings.gemini_model, settings.gemini_use_vertex)

    client = None
    provider_backoff = 0
    while True:
        try:
            if client is None:
                # Lazy + retried: a missing project / bad credentials no longer
                # crashes the process, it just retries until the operator fixes it.
                client = create_gemini_client(settings)
            processed = process_next_batch(settings, client)
            provider_backoff = 0
            if processed == 0:
                time.sleep(settings.gemini_poll_interval_seconds)
        except ProviderRetryableError as exc:
            if exc.config_error:
                # Operator action needed (billing/permission): retry rarely.
                floor, cap = 30, MAX_PROVIDER_BACKOFF_SECONDS
                reason = "needs operator action (billing/permission/credentials)"
            else:
                # Transient (503 high-demand / 429): clears fast, so retry often
                # to keep draining the backlog instead of idling for minutes.
                floor, cap = 5, 45
                reason = "transient"
            provider_backoff = min(max(provider_backoff * 2, floor), cap)
            logger.warning(
                "AI provider unavailable (%s); backing off %ss: %s",
                reason,
                provider_backoff,
                _short(exc),
            )
            time.sleep(provider_backoff)
        except Exception:
            logger.exception("AI worker loop failed")
            client = None  # rebuild the client in case it went bad
            time.sleep(10)


def process_next_batch(settings, client, limit: int = 10) -> int:
    with SessionLocal() as session:
        telegram_limit = max(1, limit // 2)
        youtube_limit = max(1, limit - telegram_limit)
        mentions = (
            session.query(Mention)
            .outerjoin(Analysis, Analysis.mention_id == Mention.id)
            .filter(Analysis.id.is_(None))
            .filter(Mention.brand_id.is_not(None))
            .options(joinedload(Mention.analysis))
            .order_by(Mention.created_at.asc())
            .limit(telegram_limit)
            .all()
        )
        if len(mentions) < telegram_limit:
            youtube_limit += telegram_limit - len(mentions)
        youtube_mentions = (
            session.query(YouTubeMention)
            .outerjoin(YouTubeAnalysis, YouTubeAnalysis.youtube_mention_id == YouTubeMention.id)
            .filter(YouTubeAnalysis.id.is_(None))
            .filter(YouTubeMention.brand_id.is_not(None))
            .order_by(YouTubeMention.created_at.asc())
            .limit(youtube_limit)
            .all()
        )
        if len(youtube_mentions) < youtube_limit and len(mentions) == telegram_limit:
            extra_limit = min(limit - len(mentions) - len(youtube_mentions), youtube_limit - len(youtube_mentions))
            if extra_limit > 0:
                mentions.extend(
                    session.query(Mention)
                    .outerjoin(Analysis, Analysis.mention_id == Mention.id)
                    .filter(Analysis.id.is_(None))
                    .filter(Mention.brand_id.is_not(None))
                    .order_by(Mention.created_at.asc())
                    .offset(len(mentions))
                    .limit(extra_limit)
                    .all()
                )
        for mention in mentions:
            analysis = analyze_mention(session, settings, client, mention)
            logger.info(
                "Analyzed telegram mention=%s sentiment=%s risk=%s error=%s",
                mention.id,
                analysis.sentiment,
                analysis.risk_score,
                bool(analysis.error),
            )
            if not analysis.error:
                maybe_send_alert(session, settings, mention, analysis)
        for mention in youtube_mentions:
            analysis = analyze_youtube_mention(session, settings, client, mention)
            logger.info(
                "Analyzed youtube mention=%s sentiment=%s risk=%s error=%s",
                mention.id,
                analysis.sentiment,
                analysis.risk_score,
                bool(analysis.error),
            )
        return len(mentions) + len(youtube_mentions)


if __name__ == "__main__":
    main()
