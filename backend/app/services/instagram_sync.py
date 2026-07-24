from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import InstagramMention, InstagramSource
from app.services.instagram_api import InstagramApi, InstagramApiError
from app.services.instagram_ingestion import ingest_instagram_comment, ingest_instagram_media

log = logging.getLogger("instagram-sync")


@dataclass
class InstagramSyncStats:
    source_id: UUID
    media_seen: int = 0
    posts_created: int = 0
    comments_created: int = 0
    records_updated: int = 0
    # Media that report a non-zero comments_count but whose comment TEXT we could
    # not read — the Meta Advanced Access / App Review gate (or a permission error).
    comments_blocked_media: int = 0
    created_ids: list[UUID] = field(default_factory=list)

    def as_response(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "media_seen": self.media_seen,
            "posts_created": self.posts_created,
            "comments_created": self.comments_created,
            "records_updated": self.records_updated,
            "analysis_queued": len(self.created_ids),
        }


def _snapshot(item: InstagramMention | None) -> tuple[Any, ...] | None:
    if item is None:
        return None
    return (
        item.text,
        item.permalink,
        item.media_url,
        item.like_count,
        item.comment_count,
        item.reply_count,
        item.raw,
    )


def _ingest_and_count(
    session: Session,
    source: InstagramSource,
    payload: dict[str, Any],
    *,
    item_type: str,
    stats: InstagramSyncStats,
) -> None:
    external_id = str(payload.get("id") or "")
    existing = (
        session.query(InstagramMention)
        .filter(InstagramMention.external_id == external_id)
        .one_or_none()
        if external_id
        else None
    )
    before = _snapshot(existing)
    created = (
        ingest_instagram_media(session, source, payload)
        if item_type == "post"
        else ingest_instagram_comment(session, source, payload, item_type=item_type)
    )
    if created is not None:
        stats.created_ids.append(created.id)
        if item_type == "post":
            stats.posts_created += 1
        else:
            stats.comments_created += 1
        return
    if existing is not None and _snapshot(existing) != before:
        stats.records_updated += 1


def sync_instagram_source(
    session: Session,
    settings: Settings,
    source: InstagramSource,
    *,
    media_limit: int | None = None,
) -> InstagramSyncStats:
    if not source.active:
        raise InstagramApiError("Instagram akkaunt faol emas")
    token = source.access_token or settings.ig_access_token
    if not token:
        raise InstagramApiError("Instagram access token sozlanmagan")

    api = InstagramApi(
        token,
        graph_version=settings.ig_graph_version,
        api_base=source.api_base or "graph.facebook.com",
    )
    stats = InstagramSyncStats(source_id=source.id)
    media_items = api.get_recent_media(
        source.ig_user_id,
        limit=media_limit or settings.instagram_media_per_poll,
    )
    stats.media_seen = len(media_items)

    for media in media_items:
        media_id = str(media.get("id") or "")
        if not media_id:
            continue
        _ingest_and_count(session, source, media, item_type="post", stats=stats)
        if not source.collect_comments:
            continue
        # Skip the per-media /comments call when Meta already reports zero comments on
        # this post. The engagement counts above come from the single /media page, so
        # metrics for every post stay fresh cheaply; only posts that actually have
        # comments cost an extra call. Keeps the API volume bounded even with a large
        # instagram_media_per_poll window.
        if int(media.get("comments_count") or 0) == 0:
            continue
        try:
            comments = api.get_media_comments(media_id, limit=settings.instagram_comments_per_media)
        except InstagramApiError as exc:
            # A token-level failure must still bubble up so the caller can mark the
            # source invalid; but a comment-scope/permission error on one media
            # (common in Development mode before App Review) must NOT abort the whole
            # sync — the posts and engagement metrics above are already committed.
            if exc.status_code == 401 or exc.error_code == 190:
                raise
            stats.comments_blocked_media += 1
            log.warning(
                "IG comment read failed media=%s source=%s: %s",
                media_id,
                source.username or source.ig_user_id,
                exc,
            )
            continue
        # Meta reports an aggregate comments_count on the media object but returns no
        # comment text: this is the Advanced Access / App Review gate, not an empty
        # thread. Surface it so the "N comments / 0 imported" banner is diagnosable.
        if not comments and int(media.get("comments_count") or 0) > 0:
            stats.comments_blocked_media += 1
            log.info(
                "IG media=%s reports %s comment(s) but text is unreadable "
                "(Advanced Access for instagram_manage_comments / App Review required)",
                media_id,
                media.get("comments_count"),
            )
        for comment in comments:
            enriched = {
                **comment,
                "media": {
                    "id": media_id,
                    "media_type": media.get("media_type"),
                    "permalink": media.get("permalink"),
                    "media_url": media.get("media_url"),
                },
            }
            _ingest_and_count(session, source, enriched, item_type="comment", stats=stats)
            for reply in (comment.get("replies", {}) or {}).get("data", []) or []:
                enriched_reply = {
                    **reply,
                    "parent_id": comment.get("id"),
                    "media": enriched["media"],
                }
                _ingest_and_count(session, source, enriched_reply, item_type="comment", stats=stats)

    source.token_status = "active"
    source.status_detail = f"@{source.username or source.ig_user_id}: oxirgi sync muvaffaqiyatli"
    source.last_checked_at = datetime.now(timezone.utc)
    session.commit()
    return stats
