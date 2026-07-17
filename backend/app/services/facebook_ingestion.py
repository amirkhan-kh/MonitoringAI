"""Turn a fetched Facebook Page comment into a persisted, brand-matched mention.

Shared by the webhook receiver (real-time) and the poller worker (catch-up), so both
paths produce identical, de-duplicated rows keyed on ``external_id``. Mirrors
instagram_ingestion.py; Facebook comment fields differ (``message``/``created_time``/
``from{name}``).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import Brand, FacebookMention, FacebookSource
from app.services.matching import BrandMatch, collect_matched_terms, match_brand, normalize_text


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        k = (v or "").lower()
        if k and k not in seen:
            seen.add(k)
            out.append(v)
    return out


def match_brand_for_facebook(
    session: Session, source: FacebookSource, normalized_text: str, *, is_mention: bool
) -> BrandMatch:
    """Comments on the brand's OWN Page are attached to that brand; in
    ``brand_matches_only`` mode only text hitting a brand term is kept."""
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


def _publish_event(session: Session, mention: FacebookMention) -> None:
    from app.services.realtime import publish_realtime_event

    publish_realtime_event(
        session,
        "facebook_mention",
        {
            "id": str(mention.id),
            "brand_id": str(mention.brand_id) if mention.brand_id else None,
            "platform": "facebook",
            "item_type": mention.item_type,
            "author_name": mention.author_name,
            "created_at": mention.created_at.isoformat() if isinstance(mention.created_at, datetime) else None,
        },
    )


def ingest_facebook_comment(
    session: Session,
    source: FacebookSource,
    comment: dict[str, Any],
    *,
    item_type: str = "comment",
) -> FacebookMention | None:
    external_id = str(comment.get("id") or "")
    if not external_id:
        return None

    existing = session.query(FacebookMention).filter(FacebookMention.external_id == external_id).one_or_none()
    if existing is not None:
        return None  # idempotent — webhook + poller can both see the same comment

    text = comment.get("message") or comment.get("text") or ""
    normalized = normalize_text(text)
    brand_match = match_brand_for_facebook(session, source, normalized, is_mention=item_type == "mention")

    from_obj = comment.get("from") or {}
    parent = comment.get("parent") or {}
    mention = FacebookMention(
        source_id=source.id,
        brand_id=brand_match.brand.id if brand_match.brand else None,
        external_id=external_id,
        item_type=item_type,
        post_id=comment.get("post_id") or (str(parent.get("id")) if parent.get("id") else None),
        parent_id=comment.get("parent_id") or (str(parent.get("id")) if parent.get("id") else None),
        author_id=str(from_obj.get("id")) if from_obj.get("id") else None,
        author_name=from_obj.get("name") or comment.get("from_name"),
        text=text,
        normalized_text=normalized,
        permalink=comment.get("permalink_url"),
        like_count=comment.get("like_count"),
        reply_count=comment.get("comment_count"),
        brand_match_terms=brand_match.terms,
        raw=comment,
        published_at=_parse_ts(comment.get("created_time")),
    )
    session.add(mention)
    session.commit()
    session.refresh(mention)
    _publish_event(session, mention)
    return mention
