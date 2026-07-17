"""Turn a fetched Instagram comment/mention into a persisted, brand-matched mention.

Shared by the webhook receiver (real-time) and the poller worker (catch-up), so both
paths produce identical, de-duplicated rows keyed on ``external_id``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import Brand, InstagramMention, InstagramSource
from app.services.matching import BrandMatch, collect_matched_terms, match_brand, normalize_text
from app.services.realtime import publish_realtime_event


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        k = (v or "").lower()
        if k and k not in seen:
            seen.add(k)
            out.append(v)
    return out


def match_brand_for_instagram(session: Session, source: InstagramSource, normalized_text: str, *, is_mention: bool) -> BrandMatch:
    """Comments on the brand's OWN account are attached to that brand; in
    ``brand_matches_only`` mode only text that hits a brand term is kept. A direct
    @mention/tag of the account is always attached (it explicitly names the brand)."""
    source_terms = [h for h in (source.hashtags or []) if normalize_text(h.lstrip("#")) in normalized_text]
    if source.brand_id:
        brand = session.get(Brand, source.brand_id)
        if brand:
            terms = collect_matched_terms(brand, normalized_text)
            if is_mention or source.monitoring_mode != "brand_matches_only":
                return BrandMatch(brand, _unique([*terms, *source_terms]))
            if terms or source_terms:
                return BrandMatch(brand, _unique([*terms, *source_terms]))
            return BrandMatch(None, [])
    match = match_brand(session, normalized_text)
    if match.brand:
        return BrandMatch(match.brand, _unique([*match.terms, *source_terms]))
    return BrandMatch(None, source_terms)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # Graph API returns ISO 8601 with +0000 offset.
        return datetime.fromisoformat(value.replace("+0000", "+00:00"))
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")
        except ValueError:
            return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _engagement_values(item: dict[str, Any]) -> tuple[int | None, int | None, int | None]:
    replies = item.get("replies") or {}
    reply_data = replies.get("data") if isinstance(replies, dict) else None
    reply_summary = replies.get("summary") if isinstance(replies, dict) else None
    reply_count = item.get("reply_count")
    if reply_count is None and isinstance(reply_summary, dict):
        reply_count = reply_summary.get("total_count")
    if reply_count is None and isinstance(reply_data, list):
        reply_count = len(reply_data)
    return (
        _int_or_none(item.get("like_count")),
        _int_or_none(item.get("comments_count") if item.get("comments_count") is not None else item.get("comment_count")),
        _int_or_none(reply_count),
    )


def _update_existing(existing: InstagramMention, item: dict[str, Any], *, item_type: str) -> bool:
    media = item.get("media") or {}
    from_obj = item.get("from") or {}
    like_count, comment_count, reply_count = _engagement_values(item)
    values = {
        "item_type": item_type,
        "media_id": str(media.get("id")) if media.get("id") else item.get("media_id"),
        "media_type": item.get("media_type") or media.get("media_type"),
        "parent_id": item.get("parent_id"),
        "author_id": str(from_obj.get("id")) if from_obj.get("id") else None,
        "author_username": item.get("username") or from_obj.get("username"),
        "text": item.get("text") or item.get("caption") or "",
        "permalink": item.get("permalink") or media.get("permalink"),
        "media_url": item.get("media_url") or media.get("media_url"),
        "like_count": like_count,
        "comment_count": comment_count,
        "reply_count": reply_count,
        "raw": item,
        "published_at": _parse_ts(item.get("timestamp")),
    }
    changed = False
    for field, value in values.items():
        if value is not None and getattr(existing, field) != value:
            setattr(existing, field, value)
            changed = True
    if values["text"] and existing.normalized_text != normalize_text(values["text"]):
        existing.normalized_text = normalize_text(values["text"])
        changed = True
    return changed


def ingest_instagram_comment(
    session: Session,
    source: InstagramSource,
    comment: dict[str, Any],
    *,
    item_type: str = "comment",
) -> InstagramMention | None:
    external_id = str(comment.get("id") or "")
    if not external_id:
        return None

    existing = session.query(InstagramMention).filter(InstagramMention.external_id == external_id).one_or_none()
    if existing is not None:
        if _update_existing(existing, comment, item_type=item_type):
            session.commit()
        return None  # idempotent — webhook + poller can both see the same object

    text = comment.get("text") or comment.get("caption") or ""
    normalized = normalize_text(text)
    media = comment.get("media") or {}
    brand_match = match_brand_for_instagram(session, source, normalized, is_mention=item_type == "mention")
    like_count, comment_count, reply_count = _engagement_values(comment)

    from_obj = comment.get("from") or {}
    mention = InstagramMention(
        source_id=source.id,
        brand_id=brand_match.brand.id if brand_match.brand else None,
        external_id=external_id,
        item_type=item_type,
        media_id=str(media.get("id")) if media.get("id") else comment.get("media_id"),
        media_type=comment.get("media_type") or media.get("media_type"),
        parent_id=comment.get("parent_id"),
        author_id=str(from_obj.get("id")) if from_obj.get("id") else None,
        author_username=comment.get("username") or from_obj.get("username"),
        text=text,
        normalized_text=normalized,
        permalink=comment.get("permalink") or media.get("permalink"),
        media_url=comment.get("media_url") or media.get("media_url"),
        like_count=like_count,
        comment_count=comment_count,
        reply_count=reply_count,
        brand_match_terms=brand_match.terms,
        raw=comment,
        published_at=_parse_ts(comment.get("timestamp")),
    )
    session.add(mention)
    session.commit()
    session.refresh(mention)
    publish_realtime_event(
        session,
        "instagram_mention",
        {
            "id": str(mention.id),
            "brand_id": str(mention.brand_id) if mention.brand_id else None,
            "platform": "instagram",
            "item_type": mention.item_type,
            "author_username": mention.author_username,
            "created_at": mention.created_at.isoformat() if isinstance(mention.created_at, datetime) else None,
        },
    )
    return mention


def ingest_instagram_media(
    session: Session,
    source: InstagramSource,
    media: dict[str, Any],
) -> InstagramMention | None:
    """Persist an owned post/reel with aggregate like and comment counts.

    Meta exposes aggregate engagement for owned professional media, not a public
    list of every person who liked it. Repeated syncs update the counters in place.
    """
    payload = {
        **media,
        "media_id": str(media.get("id") or "") or None,
        "username": media.get("username") or source.username,
    }
    return ingest_instagram_comment(session, source, payload, item_type="post")
