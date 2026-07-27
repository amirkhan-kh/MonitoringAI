from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- SaaS multi-tenant layer (Brand24-style) ---------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="active")  # active | disabled
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    memberships: Mapped[list["OrganizationMember"]] = relationship(back_populates="user")


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    price_usd: Mapped[int] = mapped_column(Integer, default=0)
    price_uzs: Mapped[int] = mapped_column(Integer, default=0)
    ai_mention_limit_monthly: Mapped[int] = mapped_column(Integer, default=100)
    brands_limit: Mapped[int] = mapped_column(Integer, default=1)
    seats_limit: Mapped[int] = mapped_column(Integer, default=1)
    platforms: Mapped[list[str]] = mapped_column(JSONB, default=list)
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # trial | active | past_due | suspended
    status: Mapped[str] = mapped_column(String(32), default="trial", index=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # During trial, hard AI cap (default 100). After paid activation, plan limit applies.
    trial_ai_mention_limit: Mapped[int] = mapped_column(Integer, default=100)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    plan: Mapped["Plan | None"] = relationship()
    members: Mapped[list["OrganizationMember"]] = relationship(back_populates="organization")
    brands: Mapped[list["Brand"]] = relationship(back_populates="organization")


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_org_member"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # owner | admin | member | viewer
    role: Mapped[str] = mapped_column(String(32), default="owner")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="memberships")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False
    )
    # trial | active | cancelled | past_due
    status: Mapped[str] = mapped_column(String(32), default="trial", index=True)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # manual | payme | click | stripe
    payment_provider: Mapped[str] = mapped_column(String(32), default="manual")
    external_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    activated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class UsageMonthly(Base):
    __tablename__ = "usage_monthly"
    __table_args__ = (UniqueConstraint("organization_id", "year_month", name="uq_usage_org_month"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    year_month: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    mentions_ingested: Mapped[int] = mapped_column(Integer, default=0)
    ai_analyses: Mapped[int] = mapped_column(Integer, default=0)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_est_usd: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Brand(Base):
    __tablename__ = "brands"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_brands_org_name"),
        Index("ix_brands_organization_id", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    # Creator / login-owner of this brand workspace (privacy boundary for non-super users).
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(String(255))
    primary_category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category_path: Mapped[list[str]] = mapped_column(JSONB, default=list)
    website: Mapped[str | None] = mapped_column(String(500))
    language: Mapped[str] = mapped_column(String(16), default="uz")
    aliases: Mapped[list[str]] = mapped_column(JSONB, default=list)
    keywords: Mapped[list[str]] = mapped_column(JSONB, default=list)
    products: Mapped[list[str]] = mapped_column(JSONB, default=list)
    competitors: Mapped[list[str]] = mapped_column(JSONB, default=list)
    ignore_terms: Mapped[list[str]] = mapped_column(JSONB, default=list)
    audience: Mapped[str | None] = mapped_column(Text, nullable=True)
    region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    monitoring_goals: Mapped[list[str]] = mapped_column(JSONB, default=list)
    risk_keywords: Mapped[list[str]] = mapped_column(JSONB, default=list)
    positive_keywords: Mapped[list[str]] = mapped_column(JSONB, default=list)
    monitor_notes: Mapped[str | None] = mapped_column(Text)
    profile_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    organization: Mapped["Organization | None"] = relationship(back_populates="brands")
    telegram_sources: Mapped[list["TelegramSource"]] = relationship(back_populates="brand")
    telegram_bot_connection: Mapped["TelegramBotConnection | None"] = relationship(
        back_populates="brand",
        uselist=False,
    )


class TelegramBotConnection(Base):
    __tablename__ = "telegram_bot_connections"
    __table_args__ = (
        UniqueConstraint("brand_id", name="uq_telegram_bot_connections_brand_id"),
        UniqueConstraint("token_fingerprint", name="uq_telegram_bot_connections_token_fingerprint"),
        UniqueConstraint("bot_id", name="uq_telegram_bot_connections_bot_id"),
        Index("ix_telegram_bot_connections_mode_status", "mode", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False)
    token_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bot_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    bot_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bot_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mode: Mapped[str] = mapped_column(String(32), default="reference")
    status: Mapped[str] = mapped_column(String(32), default="reference")
    status_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_update_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    retry_after_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    brand: Mapped[Brand] = relationship(back_populates="telegram_bot_connection")
    sources: Mapped[list["TelegramSource"]] = relationship(back_populates="bot_connection")


class TelegramSource(Base):
    __tablename__ = "telegram_sources"
    __table_args__ = (
        Index(
            "uq_telegram_sources_brand_chat_id",
            "brand_id",
            "chat_id",
            unique=True,
            postgresql_nulls_not_distinct=True,
            postgresql_where=text("chat_id IS NOT NULL"),
            sqlite_where=text("chat_id IS NOT NULL"),
        ),
        Index(
            "uq_telegram_sources_brand_username",
            "brand_id",
            "username",
            unique=True,
            postgresql_nulls_not_distinct=True,
            postgresql_where=text("username IS NOT NULL"),
            sqlite_where=text("username IS NOT NULL"),
        ),
        Index("ix_telegram_sources_brand", "brand_id"),
        Index("ix_telegram_sources_bot_connection", "bot_connection_id"),
        Index("ix_telegram_sources_parent", "parent_source_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True)
    bot_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("telegram_bot_connections.id", ondelete="SET NULL"),
        nullable=True,
    )
    parent_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("telegram_sources.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_role: Mapped[str] = mapped_column(String(32), default="legacy")
    connector_managed: Mapped[bool] = mapped_column(Boolean, default=False)
    bot_access_status: Mapped[str] = mapped_column(String(32), default="unverified")
    telethon_access_status: Mapped[str] = mapped_column(String(32), default="unverified")
    access_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_kind: Mapped[str] = mapped_column(String(32), default="channel")
    source_category: Mapped[str] = mapped_column(String(64), default="unknown")
    monitoring_mode: Mapped[str] = mapped_column(String(64), default="all_messages")
    competitor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    linked_discussion_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    collect_posts: Mapped[bool] = mapped_column(Boolean, default=True)
    collect_comments: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    monitor_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=True)
    last_seen_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_backfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    # Set when the operator removed the source but chose to keep its analysed mentions.
    # The row is kept (hidden everywhere) so mentions retain a stable source_id: that id
    # is part of the mention uniqueness key, so reviving this row on re-add dedupes the
    # old messages instead of re-ingesting and re-analysing them.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    brand: Mapped[Brand | None] = relationship(back_populates="telegram_sources")
    bot_connection: Mapped[TelegramBotConnection | None] = relationship(back_populates="sources")


class YouTubeSource(Base):
    __tablename__ = "youtube_sources"
    __table_args__ = (
        UniqueConstraint(
            "brand_id",
            "source_ref",
            name="uq_youtube_sources_brand_source_ref",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_youtube_sources_brand_category", "brand_id", "source_category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True)
    source_ref: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), default="keyword")
    source_category: Mapped[str] = mapped_column(String(64), default="keyword")
    monitoring_mode: Mapped[str] = mapped_column(String(64), default="brand_matches_only")
    nickname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    channel_handle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    channel_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    uploads_playlist_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    video_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    query: Mapped[str | None] = mapped_column(String(500), nullable=True)
    competitor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hashtags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    collect_videos: Mapped[bool] = mapped_column(Boolean, default=True)
    collect_comments: Mapped[bool] = mapped_column(Boolean, default=True)
    collect_transcripts: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    monitor_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class YouTubeMention(Base):
    __tablename__ = "youtube_mentions"
    __table_args__ = (
        UniqueConstraint(
            "brand_id",
            "external_id",
            name="uq_youtube_mentions_brand_external_id",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_youtube_mentions_brand_date", "brand_id", "published_at"),
        Index("ix_youtube_mentions_source_date", "source_id", "published_at"),
        Index("ix_youtube_mentions_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("youtube_sources.id"), nullable=True)
    brand_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    item_type: Mapped[str] = mapped_column(String(32), nullable=False)
    video_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    channel_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    channel_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    author_channel_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    author_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_text: Mapped[str] = mapped_column(Text, default="")
    permalink: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    like_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reply_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    view_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    brand_match_terms: Mapped[list[str]] = mapped_column(JSONB, default=list)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class YouTubeAnalysis(Base):
    __tablename__ = "youtube_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    youtube_mention_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("youtube_mentions.id"), unique=True)
    model_provider: Mapped[str] = mapped_column(String(64), default="vertex-gemini")
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    topics: Mapped[list[str]] = mapped_column(JSONB, default=list)
    risk_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    spam_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text)
    suggested_action: Mapped[str | None] = mapped_column(Text)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Mention(Base):
    __tablename__ = "mentions"
    __table_args__ = (
        UniqueConstraint(
            "brand_id",
            "source_id",
            "platform",
            "chat_id",
            "message_id",
            name="uq_mentions_brand_source_chat_message",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_mentions_brand_date", "brand_id", "message_date"),
        Index("ix_mentions_platform_date", "platform", "message_date"),
        Index("ix_mentions_created", "created_at"),
        Index("ix_mentions_source", "source_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("telegram_sources.id"), nullable=True)
    platform: Mapped[str] = mapped_column(String(32), default="telegram")
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chat_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chat_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    chat_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    reply_to_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discussion_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    author_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    author_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    author_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_text: Mapped[str] = mapped_column(Text, default="")
    media_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    permalink: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    brand_match_terms: Mapped[list[str]] = mapped_column(JSONB, default=list)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    message_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    edit_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis: Mapped["Analysis | None"] = relationship(back_populates="mention", uselist=False)


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mention_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("mentions.id"), unique=True)
    model_provider: Mapped[str] = mapped_column(String(64), default="vertex-gemini")
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    topics: Mapped[list[str]] = mapped_column(JSONB, default=list)
    risk_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    spam_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    mention: Mapped[Mention] = relationship(back_populates="analysis")


class AlertEvent(Base):
    """A reputation-risk signal: delivered to the staff Telegram group, then worked on there.

    Two independent state machines live on this row:
      * ``status`` — *delivery* (pending → sent / failed / abandoned), owned by alert_worker.
      * ``work_status`` — *support workflow* (open → checked → answered), driven by the
        inline buttons in the staff group. ``answered`` is the only terminal state, and it
        always carries the name of the person who replied to the customer.
    """

    __tablename__ = "alert_events"
    __table_args__ = (
        Index("ix_alert_events_brand_created", "brand_id", "created_at"),
        Index("ix_alert_events_work_status", "work_status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True)
    mention_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("mentions.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), default="negative_risk")
    status: Mapped[str] = mapped_column(String(32), default="created")
    delivery_channel: Mapped[str | None] = mapped_column(String(64), nullable=True)
    delivery_target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- support workflow (inline buttons in the staff group) ---
    work_status: Mapped[str] = mapped_column(String(32), default="open", server_default="open")
    checked_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    checked_by_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answered_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    answered_by_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Where the alert card lives, so a button press can edit it in place.
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reminder_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))


class AppState(Base):
    """Tiny key/value store for singleton bot state (e.g. the pinned summary message id)."""

    __tablename__ = "app_state"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class InstagramSource(Base):
    """A connected Instagram Business/Creator account the brand monitors.

    Unlike YouTube (any public channel), Instagram monitoring is centred on an
    account you own/manage: its comments and @mentions arrive via Meta webhooks,
    and the Graph API is called with this account's ``access_token``.
    """

    __tablename__ = "instagram_sources"
    __table_args__ = (
        UniqueConstraint("ig_user_id", name="uq_instagram_sources_ig_user_id"),
        Index("ix_instagram_sources_brand", "brand_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True)
    ig_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_category: Mapped[str] = mapped_column(String(64), default="owned")
    monitoring_mode: Mapped[str] = mapped_column(String(64), default="all_messages")
    collect_comments: Mapped[bool] = mapped_column(Boolean, default=True)
    collect_mentions: Mapped[bool] = mapped_column(Boolean, default=True)
    hashtags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook_subscribed: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # token_status: unknown | active | invalid — driven by validation + worker auth errors.
    token_status: Mapped[str] = mapped_column(String(32), default="unknown")
    status_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_base: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InstagramMention(Base):
    __tablename__ = "instagram_mentions"
    __table_args__ = (
        UniqueConstraint("external_id", name="uq_instagram_mentions_external_id"),
        Index("ix_instagram_mentions_brand_created", "brand_id", "created_at"),
        Index("ix_instagram_mentions_source_created", "source_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("instagram_sources.id"), nullable=True)
    brand_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    item_type: Mapped[str] = mapped_column(String(32), nullable=False)  # post | comment | mention | caption
    media_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    parent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    author_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    author_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_text: Mapped[str] = mapped_column(Text, default="")
    permalink: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    media_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    like_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reply_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    brand_match_terms: Mapped[list[str]] = mapped_column(JSONB, default=list)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InstagramAnalysis(Base):
    __tablename__ = "instagram_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instagram_mention_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("instagram_mentions.id"), unique=True)
    model_provider: Mapped[str] = mapped_column(String(64), default="vertex-gemini")
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    topics: Mapped[list[str]] = mapped_column(JSONB, default=list)
    risk_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    spam_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text)
    suggested_action: Mapped[str | None] = mapped_column(Text)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FacebookSource(Base):
    """A connected Facebook Page the brand monitors.

    Mirrors InstagramSource but keyed on the Facebook Page id. Comments on the
    Page's posts (and visitor posts) arrive via Meta webhooks (``feed`` field) and
    are backfilled by the poller through the Graph API with this Page's token.
    """

    __tablename__ = "facebook_sources"
    __table_args__ = (
        UniqueConstraint("page_id", name="uq_facebook_sources_page_id"),
        Index("ix_facebook_sources_brand", "brand_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True)
    page_id: Mapped[str] = mapped_column(String(64), nullable=False)
    page_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_category: Mapped[str] = mapped_column(String(64), default="owned")
    monitoring_mode: Mapped[str] = mapped_column(String(64), default="all_messages")
    collect_comments: Mapped[bool] = mapped_column(Boolean, default=True)
    collect_mentions: Mapped[bool] = mapped_column(Boolean, default=True)
    hashtags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook_subscribed: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    token_status: Mapped[str] = mapped_column(String(32), default="unknown")
    status_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_base: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FacebookMention(Base):
    __tablename__ = "facebook_mentions"
    __table_args__ = (
        UniqueConstraint("external_id", name="uq_facebook_mentions_external_id"),
        Index("ix_facebook_mentions_brand_created", "brand_id", "created_at"),
        Index("ix_facebook_mentions_source_created", "source_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("facebook_sources.id"), nullable=True)
    brand_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    item_type: Mapped[str] = mapped_column(String(32), nullable=False)  # comment | reply | post | mention
    post_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    parent_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    author_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    author_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_text: Mapped[str] = mapped_column(Text, default="")
    permalink: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    like_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reply_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    brand_match_terms: Mapped[list[str]] = mapped_column(JSONB, default=list)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FacebookAnalysis(Base):
    __tablename__ = "facebook_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facebook_mention_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("facebook_mentions.id"), unique=True)
    model_provider: Mapped[str] = mapped_column(String(64), default="vertex-gemini")
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    topics: Mapped[list[str]] = mapped_column(JSONB, default=list)
    risk_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    spam_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text)
    suggested_action: Mapped[str | None] = mapped_column(Text)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
