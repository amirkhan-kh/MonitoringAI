"""Facebook poller — catch-up ingestion of comments on the connected Page's posts.

Webhooks give true real-time; this poller guarantees coverage even before the Meta
webhook is live and backfills anything a webhook missed. All writes are idempotent
(keyed on comment id), so poller + webhook never double-count. Mirrors
instagram_worker.py.
"""

from __future__ import annotations

import logging
import time

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.models import FacebookSource
from app.services.facebook_api import FacebookApi, FacebookApiError
from app.services.facebook_ingestion import ingest_facebook_comment

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("facebook-worker")


def main() -> None:
    settings = get_settings()
    init_db()
    logger.info("Facebook worker started interval=%ss", settings.facebook_poll_interval_seconds)

    while True:
        try:
            if not settings.facebook_enabled:
                time.sleep(settings.facebook_poll_interval_seconds)
                continue
            with SessionLocal() as session:
                source_ids = [
                    row.id
                    for row in session.query(FacebookSource.id)
                    .filter(FacebookSource.active.is_(True))
                    .order_by(FacebookSource.created_at.asc())
                    .all()
                ]
            for source_id in source_ids:
                _poll_source(settings, source_id)
        except Exception:
            logger.exception("Facebook worker loop failed")
        time.sleep(settings.facebook_poll_interval_seconds)


def _is_auth_error(exc: FacebookApiError) -> bool:
    if exc.status_code in (401, 190):
        return True
    msg = str(exc).lower()
    return exc.status_code == 400 and any(k in msg for k in ("oauth", "token", "session", "code\": 190", "code':190"))


def _poll_source(settings, source_id) -> None:
    with SessionLocal() as session:
        source = session.get(FacebookSource, source_id)
        if source is None or not source.active or not source.collect_comments:
            return
        if source.token_status == "invalid":
            return
        token = source.access_token or settings.fb_access_token
        if not token:
            return
        api = FacebookApi(token, graph_version=settings.fb_graph_version, api_base=source.api_base or "graph.facebook.com")
        try:
            posts = api.get_recent_posts(source.page_id, limit=settings.facebook_posts_per_poll)
        except FacebookApiError as exc:
            if _is_auth_error(exc):
                source.token_status = "invalid"
                source.status_detail = str(exc)[:400]
                session.commit()
                logger.warning("FB token invalid source=%s — marked invalid: %s", source.page_id, exc)
            else:
                logger.warning("FB posts fetch failed source=%s: %s", source.page_id, exc)
            return

        imported = 0
        for post in posts:
            post_id = str(post.get("id") or "")
            if not post_id:
                continue
            try:
                comments = api.get_post_comments(post_id, limit=settings.facebook_comments_per_post)
            except FacebookApiError as exc:
                logger.warning("FB comments fetch failed post=%s: %s", post_id, exc)
                continue
            for comment in comments:
                enriched = {**comment, "post_id": post_id}
                if ingest_facebook_comment(session, source, enriched, item_type="comment") is not None:
                    imported += 1
                # Replies come nested under ``comments``; flatten them so they're analyzed too.
                for reply in (comment.get("comments", {}) or {}).get("data", []) or []:
                    enriched_reply = {**reply, "post_id": post_id, "parent_id": comment.get("id")}
                    if ingest_facebook_comment(session, source, enriched_reply, item_type="reply") is not None:
                        imported += 1
        if imported:
            logger.info("Facebook synced source=%s posts=%s imported=%s", source.page_name or source.page_id, len(posts), imported)


if __name__ == "__main__":
    main()
