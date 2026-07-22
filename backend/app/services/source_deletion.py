from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    AlertEvent,
    Analysis,
    FacebookAnalysis,
    FacebookMention,
    FacebookSource,
    InstagramAnalysis,
    InstagramMention,
    InstagramSource,
    Mention,
    TelegramSource,
    YouTubeAnalysis,
    YouTubeMention,
    YouTubeSource,
)


SOURCE_DELETE_CONFIG: dict[str, tuple[Any, Any, Any, Any]] = {
    "telegram": (TelegramSource, Mention, Analysis, Analysis.mention_id),
    "youtube": (YouTubeSource, YouTubeMention, YouTubeAnalysis, YouTubeAnalysis.youtube_mention_id),
    "instagram": (InstagramSource, InstagramMention, InstagramAnalysis, InstagramAnalysis.instagram_mention_id),
    "facebook": (FacebookSource, FacebookMention, FacebookAnalysis, FacebookAnalysis.facebook_mention_id),
}


class SourceNotFoundError(LookupError):
    pass


def _source_ids(session: Session, platform: str, source: Any) -> list[uuid.UUID]:
    source_ids = [source.id]
    if platform == "telegram" and source.linked_discussion_chat_id:
        linked_query = session.query(TelegramSource.id).filter(
            TelegramSource.chat_id == source.linked_discussion_chat_id,
        )
        if source.brand_id:
            linked_query = linked_query.filter(TelegramSource.brand_id == source.brand_id)
        source_ids.extend(row[0] for row in linked_query.all())
    return list(dict.fromkeys(source_ids))


def delete_monitored_source(
    session: Session,
    platform: str,
    source_id: uuid.UUID,
    *,
    purge_mentions: bool = True,
) -> dict[str, Any]:
    """Remove a monitored source, optionally keeping the mentions it already collected.

    ``purge_mentions=True`` wipes the source and everything derived from it, which is
    what you want when the source was added by mistake or its data is no longer wanted
    on disk.

    ``purge_mentions=False`` keeps every mention, analysis and alert and only soft-deletes
    the source row (``deleted_at`` set, ``active`` cleared). The row must survive because
    a mention's uniqueness key includes ``source_id``: dropping it would make a later
    re-add re-ingest the same messages under a fresh id and pay for a second AI analysis.
    Reviving this row instead keeps ingestion deduplicating against what is already stored,
    so only messages missed while the source was gone get analysed.
    """
    if platform not in SOURCE_DELETE_CONFIG:
        raise ValueError(f"Unsupported platform: {platform}")

    source_model, mention_model, analysis_model, analysis_mention_column = SOURCE_DELETE_CONFIG[platform]
    source = session.get(source_model, source_id)
    if source is None:
        raise SourceNotFoundError(f"{platform} source topilmadi")
    session.flush()

    source_ids = _source_ids(session, platform, source)

    if not purge_mentions:
        mentions_retained = (
            session.query(mention_model.id).filter(mention_model.source_id.in_(source_ids)).count()
        )
        now = datetime.now(timezone.utc)
        sources_deleted = (
            session.query(source_model)
            .filter(source_model.id.in_(source_ids))
            .update({"deleted_at": now, "active": False}, synchronize_session=False)
        )
        session.commit()
        return {
            "ok": True,
            "platform": platform,
            "source_id": source_id,
            "sources_deleted": sources_deleted,
            "mentions_deleted": 0,
            "analyses_deleted": 0,
            "alerts_deleted": 0,
            "mentions_retained": mentions_retained,
            "soft_deleted": True,
        }

    mention_ids = [
        row[0]
        for row in session.query(mention_model.id).filter(mention_model.source_id.in_(source_ids)).all()
    ]

    alerts_deleted = 0
    analyses_deleted = 0
    if mention_ids:
        if platform == "telegram":
            alerts_deleted = session.query(AlertEvent).filter(AlertEvent.mention_id.in_(mention_ids)).delete(
                synchronize_session=False,
            )
        analyses_deleted = session.query(analysis_model).filter(analysis_mention_column.in_(mention_ids)).delete(
            synchronize_session=False,
        )

    mentions_deleted = session.query(mention_model).filter(mention_model.source_id.in_(source_ids)).delete(
        synchronize_session=False,
    )
    sources_deleted = session.query(source_model).filter(source_model.id.in_(source_ids)).delete(
        synchronize_session=False,
    )
    session.commit()

    return {
        "ok": True,
        "platform": platform,
        "source_id": source_id,
        "sources_deleted": sources_deleted,
        "mentions_deleted": mentions_deleted,
        "analyses_deleted": analyses_deleted,
        "alerts_deleted": alerts_deleted,
        "mentions_retained": 0,
        "soft_deleted": False,
    }
