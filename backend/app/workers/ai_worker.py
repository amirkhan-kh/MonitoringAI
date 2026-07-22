from __future__ import annotations

import concurrent.futures
import logging
import time

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.models import (
    Analysis,
    Brand,
    FacebookAnalysis,
    FacebookMention,
    FacebookSource,
    InstagramAnalysis,
    InstagramMention,
    InstagramSource,
    Mention,
    YouTubeAnalysis,
    YouTubeMention,
)
from app.services.alerts import record_alert
from app.services.gemini_analysis import (
    ProviderRetryableError,
    analyze_facebook_mention,
    analyze_instagram_mention,
    analyze_mention,
    analyze_youtube_mention,
    create_gemini_client,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ai-worker")
# The SDK logs every HTTP request (incl. throttled 429 retries) at INFO — far too noisy
# under dynamic-shared-quota backoff. Keep our own analysis logs, quiet the transport.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google_genai.models").setLevel(logging.WARNING)
logging.getLogger("google_genai._api_client").setLevel(logging.WARNING)


def _short(exc: Exception, limit: int = 200) -> str:
    message = " ".join(str(exc).split())
    return message[:limit] + ("…" if len(message) > limit else "")


def main() -> None:
    settings = get_settings()
    init_db()
    logger.info(
        "AI worker started gate=%s gate_model=%s analysis_model=%s cycle=%ss max/cycle=%s concurrency=%s vertex=%s",
        settings.gemini_relevance_gate,
        settings.gemini_gate_model,
        settings.gemini_analysis_model,
        settings.ai_cycle_seconds,
        settings.ai_max_per_cycle,
        settings.ai_concurrency,
        settings.gemini_use_vertex,
    )

    client = None
    while True:
        try:
            if client is None:
                # Lazy + retried: a missing project / bad credentials no longer
                # crashes the process, it just retries on the next cycle.
                client = create_gemini_client(settings)
            total = run_cycle(settings, client)
            logger.info("Cycle complete: processed=%s; next pass in %ss", total, settings.ai_cycle_seconds)
        except ProviderRetryableError as exc:
            reason = "config (billing/permission/credentials)" if exc.config_error else "transient"
            logger.warning("AI provider unavailable this cycle (%s): %s", reason, _short(exc))
        except Exception:
            logger.exception("AI worker cycle failed")
            client = None  # rebuild the client in case it went bad
        # Batched, not continuous: sleep between passes to cap token burn.
        time.sleep(settings.ai_cycle_seconds)


def run_cycle(settings, client) -> int:
    """Analyze up to ``ai_max_per_cycle`` pending mentions this pass, then return.

    The cap keeps a large backlog from turning the 5-minute cycle back into a
    continuous grind; a backlog simply drains a chunk per cycle. Steady-state
    traffic (a few new mentions per cycle) clears in one pass.
    """
    total = 0
    cap = max(1, settings.ai_max_per_cycle)
    while total < cap:
        processed, retry_exc = process_next_batch(settings, client)
        if retry_exc is not None:
            if total == 0:
                raise retry_exc  # whole first batch failed → surface to main for logging
            logger.warning("Provider throttled mid-cycle; ending pass early at %s processed", total)
            break
        if processed == 0:
            break
        total += processed
    return total


def process_next_batch(settings, client) -> tuple[int, ProviderRetryableError | None]:
    """Fetch a batch of unanalyzed mentions and analyze them concurrently.

    Returns ``(processed_count, retry_exc)``. ``retry_exc`` is set when one or
    more mentions hit a retryable provider error so the caller backs off; the
    mentions that succeeded are already committed and the failed ones are left
    unpersisted to be retried on a later batch. Analysis is network-bound, so a
    thread pool drains a backlog ~``ai_concurrency``x faster than a serial loop.
    """
    conc = max(1, settings.ai_concurrency)
    with SessionLocal() as session:
        tg_ids = [
            row.id
            for row in session.query(Mention.id)
            .outerjoin(Analysis, Analysis.mention_id == Mention.id)
            .filter(Analysis.id.is_(None))
            .filter(Mention.brand_id.is_not(None))
            .order_by(Mention.created_at.asc())
            .limit(conc)
            .all()
        ]
        yt_ids = [
            row.id
            for row in session.query(YouTubeMention.id)
            .outerjoin(YouTubeAnalysis, YouTubeAnalysis.youtube_mention_id == YouTubeMention.id)
            .filter(YouTubeAnalysis.id.is_(None))
            .filter(YouTubeMention.brand_id.is_not(None))
            .order_by(YouTubeMention.created_at.asc())
            .limit(conc)
            .all()
        ]
        ig_ids = [
            row.id
            for row in session.query(InstagramMention.id)
            .outerjoin(InstagramAnalysis, InstagramAnalysis.instagram_mention_id == InstagramMention.id)
            .filter(InstagramAnalysis.id.is_(None))
            .filter(InstagramMention.brand_id.is_not(None))
            .order_by(InstagramMention.created_at.asc())
            .limit(conc)
            .all()
        ]
        fb_ids = [
            row.id
            for row in session.query(FacebookMention.id)
            .outerjoin(FacebookAnalysis, FacebookAnalysis.facebook_mention_id == FacebookMention.id)
            .filter(FacebookAnalysis.id.is_(None))
            .filter(FacebookMention.brand_id.is_not(None))
            .order_by(FacebookMention.created_at.asc())
            .limit(conc)
            .all()
        ]
    tasks = (
        [("telegram", mid) for mid in tg_ids]
        + [("youtube", mid) for mid in yt_ids]
        + [("instagram", mid) for mid in ig_ids]
        + [("facebook", mid) for mid in fb_ids]
    )
    if not tasks:
        return 0, None

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(conc, len(tasks))) as pool:
        results = list(pool.map(lambda task: _process_one(settings, client, task[0], task[1]), tasks))
    retry_errs = [r for r in results if isinstance(r, ProviderRetryableError)]
    ok = len(results) - len(retry_errs)

    # Only back off when the WHOLE batch failed transiently (provider truly down /
    # exhausted). A partial failure — e.g. a per-minute 429 on some calls — just means
    # those mentions retry on the next batch; backing off would needlessly stall the
    # ones that are succeeding. A config error (billing/permission) always backs off.
    retry_exc: ProviderRetryableError | None = None
    config_errs = [r for r in retry_errs if r.config_error]
    if config_errs:
        retry_exc = config_errs[0]
    elif ok == 0 and retry_errs:
        retry_exc = retry_errs[0]
    elif retry_errs:
        # Partial throttle (some 429s, some succeeded): Gemini 2.5 uses dynamic shared
        # quota, which gives better net throughput when you pace instead of hammering
        # the shared pool. Short, proportional pause before the next batch.
        time.sleep(min(5.0, 0.5 * len(retry_errs)))
    return len(tasks), retry_exc


def _brand_name(session, brand_id) -> str | None:
    if not brand_id:
        return None
    brand = session.get(Brand, brand_id)
    return brand.name if brand else None


def _instagram_source_name(session, mention: InstagramMention) -> str | None:
    source = session.get(InstagramSource, mention.source_id) if mention.source_id else None
    if source:
        return source.account_name or (f"@{source.username}" if source.username else source.ig_user_id)
    return mention.author_username


def _facebook_source_name(session, mention: FacebookMention) -> str | None:
    source = session.get(FacebookSource, mention.source_id) if mention.source_id else None
    if source:
        return source.page_name or source.username or source.page_id
    return mention.post_id


def _process_one(settings, client, kind: str, mention_id) -> ProviderRetryableError | None:
    """Analyze one mention in its own DB session (safe to run across threads).

    Returns a ``ProviderRetryableError`` to signal the batch should back off,
    otherwise ``None``. Unexpected per-mention errors are logged and swallowed so
    one bad mention never sinks the whole batch.
    """
    try:
        with SessionLocal() as session:
            if kind == "telegram":
                mention = session.get(Mention, mention_id)
                if mention is None:
                    return None
                analysis = analyze_mention(session, settings, client, mention)
                if not analysis.error:
                    record_alert(
                        session, settings, platform="telegram", brand_id=mention.brand_id,
                        mention_id=mention.id, brand_name=_brand_name(session, mention.brand_id),
                        source=mention.chat_title or mention.chat_username or str(mention.chat_id),
                        author=mention.author_username or mention.author_name,
                        text=mention.text or mention.caption, permalink=mention.permalink, analysis=analysis,
                    )
            elif kind == "instagram":
                mention = session.get(InstagramMention, mention_id)
                if mention is None:
                    return None
                analysis = analyze_instagram_mention(session, settings, client, mention)
                if not analysis.error:
                    record_alert(
                        session, settings, platform="instagram", brand_id=mention.brand_id,
                        mention_id=mention.id, brand_name=_brand_name(session, mention.brand_id),
                        source=_instagram_source_name(session, mention), author=mention.author_username,
                        text=mention.text, permalink=mention.permalink, analysis=analysis,
                    )
            elif kind == "facebook":
                mention = session.get(FacebookMention, mention_id)
                if mention is None:
                    return None
                analysis = analyze_facebook_mention(session, settings, client, mention)
                if not analysis.error:
                    record_alert(
                        session, settings, platform="facebook", brand_id=mention.brand_id,
                        mention_id=mention.id, brand_name=_brand_name(session, mention.brand_id),
                        # The staff group groups open signals by source name, so a raw
                        # post id would make the Facebook rows unreadable there.
                        source=_facebook_source_name(session, mention), author=mention.author_name,
                        text=mention.text, permalink=mention.permalink, analysis=analysis,
                    )
            else:
                mention = session.get(YouTubeMention, mention_id)
                if mention is None:
                    return None
                analysis = analyze_youtube_mention(session, settings, client, mention)
                if not analysis.error:
                    record_alert(
                        session, settings, platform="youtube", brand_id=mention.brand_id,
                        mention_id=mention.id, brand_name=_brand_name(session, mention.brand_id),
                        source=mention.channel_title, author=mention.author_name,
                        text=mention.text or mention.title, permalink=mention.permalink, analysis=analysis,
                    )
            logger.info(
                "Analyzed %s mention=%s model=%s sentiment=%s risk=%s error=%s",
                kind,
                mention_id,
                analysis.model_name,
                analysis.sentiment,
                analysis.risk_score,
                bool(analysis.error),
            )
        return None
    except ProviderRetryableError as exc:
        return exc
    except Exception:
        logger.exception("AI analyze failed kind=%s mention=%s", kind, mention_id)
        return None


if __name__ == "__main__":
    main()
