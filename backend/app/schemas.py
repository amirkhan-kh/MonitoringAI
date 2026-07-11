from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class BrandCreate(BaseModel):
    name: str
    description: str | None = None
    industry: str | None = None
    website: str | None = None
    language: str = "uz"
    aliases: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    ignore_terms: list[str] = Field(default_factory=list)
    monitor_notes: str | None = None


class BrandOut(BrandCreate):
    id: uuid.UUID
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TelegramSourceCreate(BaseModel):
    brand_id: uuid.UUID | None = None
    source_kind: str = "channel"
    source_category: str = "unknown"
    monitoring_mode: str = "all_messages"
    competitor_name: str | None = None
    chat_id: int | None = None
    username: str | None = None
    title: str | None = None
    description: str | None = None
    notes: str | None = None
    collect_posts: bool = True
    collect_comments: bool = True
    active: bool = True
    monitor_from: date | None = None


class TelegramSourceResolve(BaseModel):
    chat_id_or_username: int | str
    brand_id: uuid.UUID | None = None
    source_category: str = "unknown"
    monitoring_mode: str = "all_messages"
    competitor_name: str | None = None
    notes: str | None = None
    collect_posts: bool = True
    collect_comments: bool = True
    monitor_from: date | None = None


class TelegramSourceUpdate(BaseModel):
    brand_id: uuid.UUID | None = None
    source_category: str | None = None
    monitoring_mode: str | None = None
    competitor_name: str | None = None
    notes: str | None = None
    collect_posts: bool | None = None
    collect_comments: bool | None = None
    active: bool | None = None
    monitor_from: date | None = None


class TelegramSourceImport(BaseModel):
    brand_id: uuid.UUID | None = None
    raw_text: str
    default_source_category: str = "industry"
    default_monitoring_mode: str = "brand_matches_only"
    default_monitor_from: date | None = None
    collect_posts: bool = True
    collect_comments: bool = True


class TelegramSourceBackfillRequest(BaseModel):
    limit: int | None = Field(default=None, ge=1, le=10000)
    comments_per_post: int = Field(default=50, ge=0, le=500)
    from_date: date | None = None


class TelegramSourceBackfillResult(BaseModel):
    source_id: uuid.UUID
    source_ref: str | int
    posts_seen: int = 0
    comments_seen: int = 0
    ok: bool = True
    error: str | None = None


class TelegramSourceImportResult(BaseModel):
    ref: str
    status: str
    source: "TelegramSourceOut | None" = None
    error: str | None = None


class TelegramSourceAccessCheck(BaseModel):
    chat_id_or_username: int | str


class TelegramSourceAccessStatus(BaseModel):
    ok: bool
    chat_id_or_username: int | str
    bot_username: str | None = None
    chat_id: int | None = None
    chat_username: str | None = None
    chat_title: str | None = None
    chat_type: str | None = None
    bot_status: str | None = None
    can_read_posts: bool = False
    can_read_comments: bool = False
    linked_discussion_chat_id: int | None = None
    linked_discussion_bot_status: str | None = None
    issues: list[str] = Field(default_factory=list)


class TelegramSourceRefreshResult(BaseModel):
    source: "TelegramSourceOut"
    access: TelegramSourceAccessStatus
    linked_source: "TelegramSourceOut | None" = None


class TelegramBotStatus(BaseModel):
    ok: bool
    id: int | None = None
    username: str | None = None
    first_name: str | None = None
    can_join_groups: bool | None = None
    can_read_all_group_messages: bool | None = None
    error: str | None = None


class TelegramSessionStatus(BaseModel):
    configured: bool
    authorized: bool
    session_name: str | None = None
    user_id: int | None = None
    username: str | None = None
    phone: str | None = None
    error: str | None = None


class TelegramSourceCategory(BaseModel):
    key: str
    label: str
    default_monitoring_mode: str
    description: str


class TelegramSourceOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID | None
    source_kind: str
    source_category: str
    monitoring_mode: str
    competitor_name: str | None
    chat_id: int | None
    username: str | None
    title: str | None
    description: str | None
    linked_discussion_chat_id: int | None
    notes: str | None
    collect_posts: bool
    collect_comments: bool
    active: bool
    monitor_from: datetime | None
    last_seen_message_id: int | None
    last_backfilled_at: datetime | None

    model_config = {"from_attributes": True}


class YouTubeSourceImport(BaseModel):
    brand_id: uuid.UUID | None = None
    raw_text: str
    default_source_category: str = "keyword"
    default_monitoring_mode: str = "brand_matches_only"
    default_monitor_from: date | None = None
    default_hashtags: list[str] = Field(default_factory=list)
    collect_videos: bool = True
    collect_comments: bool = True
    collect_transcripts: bool = False


class YouTubeSourceUpdate(BaseModel):
    brand_id: uuid.UUID | None = None
    source_category: str | None = None
    monitoring_mode: str | None = None
    competitor_name: str | None = None
    nickname: str | None = None
    hashtags: list[str] | None = None
    notes: str | None = None
    collect_videos: bool | None = None
    collect_comments: bool | None = None
    collect_transcripts: bool | None = None
    active: bool | None = None
    monitor_from: date | None = None


class YouTubeSourceSyncRequest(BaseModel):
    max_pages: int = Field(default=1, ge=1, le=5)
    comments_per_video: int = Field(default=100, ge=0, le=500)


class YouTubeSourceSyncResult(BaseModel):
    source_id: uuid.UUID
    ok: bool = True
    videos_seen: int = 0
    comments_seen: int = 0
    imported: int = 0
    error: str | None = None


class YouTubeSourceImportResult(BaseModel):
    ref: str
    status: str
    source: "YouTubeSourceOut | None" = None
    error: str | None = None


class YouTubeSourceCategory(BaseModel):
    key: str
    label: str
    default_monitoring_mode: str
    description: str


class YouTubeStatus(BaseModel):
    configured: bool
    api_key_present: bool
    comments_supported: bool = True
    videos_supported: bool = True
    transcripts_supported: bool = False
    notes: list[str] = Field(default_factory=list)


class YouTubeSourceOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID | None
    source_ref: str
    source_kind: str
    source_category: str
    monitoring_mode: str
    nickname: str | None
    title: str | None
    description: str | None
    channel_id: str | None
    channel_handle: str | None
    channel_title: str | None
    uploads_playlist_id: str | None
    video_id: str | None
    query: str | None
    competitor_name: str | None
    hashtags: list[str]
    notes: str | None
    collect_videos: bool
    collect_comments: bool
    collect_transcripts: bool
    active: bool
    monitor_from: datetime | None
    last_checked_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class YouTubeMentionOut(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID | None
    brand_id: uuid.UUID | None
    external_id: str
    item_type: str
    video_id: str | None
    channel_id: str | None
    channel_title: str | None
    author_channel_id: str | None
    author_name: str | None
    title: str | None
    text: str | None
    permalink: str | None
    thumbnail_url: str | None
    like_count: int | None
    reply_count: int | None
    view_count: int | None
    comment_count: int | None
    brand_match_terms: list[str]
    published_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class YouTubeSummary(BaseModel):
    sources_total: int
    mentions_total: int
    comments_total: int
    videos_total: int
    high_risk: int = 0
    latest_mentions: list[YouTubeMentionOut]


class MentionOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID | None
    platform: str
    source_type: str
    chat_id: int
    chat_username: str | None
    chat_title: str | None
    message_id: int
    author_username: str | None
    author_name: str | None
    text: str | None
    caption: str | None
    media_type: str | None
    permalink: str | None
    brand_match_terms: list[str]
    message_date: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalysisOut(BaseModel):
    id: uuid.UUID
    mention_id: uuid.UUID
    model_provider: str
    model_name: str
    language: str | None
    sentiment: str | None
    sentiment_score: float | None
    topics: list[str]
    risk_level: str | None
    risk_score: float | None
    spam_score: float | None
    summary: str | None
    suggested_action: str | None
    error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MentionDetailOut(MentionOut):
    raw: dict[str, Any]
    analysis: AnalysisOut | None = None

    model_config = {"from_attributes": True}


class DashboardSummary(BaseModel):
    mentions_total: int
    analyzed_total: int
    sentiment_counts: dict[str, int]
    risk_counts: dict[str, int]
    top_topics: dict[str, int]
    latest_mentions: list[MentionOut]


class AlertEventOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID | None
    mention_id: uuid.UUID | None
    event_type: str
    status: str
    delivery_channel: str | None
    delivery_target: str | None
    payload: dict[str, Any]
    error: str | None
    created_at: datetime
    sent_at: datetime | None

    model_config = {"from_attributes": True}
