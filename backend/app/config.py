from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(default="postgresql+psycopg://monitoring:monitoring@localhost:5433/monitoring")

    telegram_bot_token: str = ""
    telegram_allowed_updates: list[str] = Field(
        default_factory=lambda: [
            "message",
            "edited_message",
            "channel_post",
            "edited_channel_post",
            # Required for the staff-group alert buttons; the worker force-adds it too, so
            # an older env override cannot silently disable the workflow.
            "callback_query",
            # Bot added/removed from a group → auto-bind Supports-style staff inbox.
            "my_chat_member",
        ]
    )
    telegram_command_allowed_user_ids: list[int] = Field(default_factory=list)
    telegram_poll_timeout_seconds: int = 30
    telegram_poll_conflict_backoff_seconds: int = 300
    telegram_poll_lock_file: str = ".sessions/telegram_bot_polling.lock"
    connector_encryption_key: str = ""
    telegram_connector_poll_interval_seconds: int = Field(default=2, ge=1)
    telegram_connector_error_backoff_seconds: int = Field(default=30, ge=5)

    telegram_api_id: int | None = None
    telegram_api_hash: str = ""
    telegram_session_name: str = ".sessions/monitoring"
    telegram_live_sync_session_name: str = ".sessions/monitoring_live"
    telegram_backfill_limit: int = 100
    telegram_backfill_comments_per_post: int = 50
    telegram_live_sync_interval_seconds: int = 60
    telegram_live_sync_batch_limit: int = 100
    telegram_live_sync_initial_limit: int = 25
    telegram_live_sync_comments_per_post: int = 5

    youtube_api_key: str = ""
    youtube_poll_interval_seconds: int = Field(default=120, ge=30)
    youtube_sync_max_pages: int = Field(default=1, ge=1, le=20)
    youtube_comments_per_video: int = Field(default=100, ge=1, le=100)
    youtube_rate_limit_backoff_seconds: int = Field(default=3600, ge=60)
    # search.list costs 100 units against a 10k/day default quota, so keyword and
    # hashtag sources cannot ride the normal poll interval — one of them at 120s
    # would burn 72k units/day on its own. Channel/video sources are unaffected.
    youtube_search_min_interval_seconds: int = Field(default=3600, ge=300)
    # Re-scan a little before the last checkpoint so items that landed mid-sync,
    # or arrived slightly out of order, are not skipped by the watermark.
    youtube_sync_overlap_seconds: int = Field(default=900, ge=0)
    # How many already-known videos a non-channel source re-polls for new comments.
    youtube_comment_replay_videos: int = Field(default=10, ge=0, le=50)

    # --- Instagram (Meta Graph API + webhooks) ---
    # A brand connects its Instagram Business/Creator account (linked to a Facebook
    # Page). Real-time comments/@mentions arrive via Meta webhooks; the Graph API is
    # used to fetch full comment/media details and to backfill.
    instagram_enabled: bool = True
    ig_app_id: str = ""
    ig_app_secret: str = ""
    # Shared secret you invent; must match what you type into the Meta webhook config.
    ig_verify_token: str = "monitoringai_ig_webhook"
    ig_graph_version: str = "v21.0"
    # Optional default long-lived token (a source can also carry its own token).
    ig_access_token: str = ""
    # Business Login for Instagram (OAuth). Both default to being derived from the
    # incoming request's public host, which is right behind nginx; set them explicitly
    # only if the public URL differs from what the proxy reports. The redirect URI must
    # match the Meta app config byte for byte.
    ig_oauth_redirect_uri: str = ""
    app_public_base_url: str = ""
    instagram_poll_interval_seconds: int = 60
    instagram_comments_per_media: int = 100
    instagram_media_per_poll: int = 25
    instagram_manual_sync_media_limit: int = 500

    # --- Facebook Pages (Meta Graph API + webhooks) ---
    # A brand connects its Facebook Page. Comments on the Page's posts arrive via Meta
    # webhooks (``feed`` field); the Graph API backfills recent post comments. Same
    # graph.facebook.com base and token model as Instagram (BYOT page token).
    facebook_enabled: bool = True
    fb_app_id: str = ""
    fb_app_secret: str = ""
    fb_verify_token: str = "monitoringai_fb_webhook"
    fb_graph_version: str = "v21.0"
    fb_access_token: str = ""
    facebook_poll_interval_seconds: int = 60
    facebook_comments_per_post: int = 100
    facebook_posts_per_poll: int = 25

    gemini_use_vertex: bool = True
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    google_application_credentials: str = ""
    gemini_api_key: str = ""
    # --- Two-stage, token-saving pipeline ---
    # Stage 1 GATE (cheap flash-lite): is this text actually about the brand? Filters
    # out unrelated noise (most comments on all-messages sources) before spending Pro.
    # Stage 2 ANALYSIS (Pro): full sentiment/risk only for brand-relevant mentions.
    gemini_relevance_gate: bool = True
    gemini_gate_model: str = "gemini-2.5-flash-lite"
    gemini_analysis_model: str = "gemini-2.5-pro"
    gemini_profile_thinking_budget: int = 32768

    # Used only when gemini_relevance_gate is off (legacy tiered path in analyze_payload):
    # flash-lite primary + Pro escalation on high risk.
    gemini_model: str = "gemini-2.5-flash-lite"
    gemini_escalation_model: str = "gemini-2.5-pro"
    gemini_quota_fallback: bool = True
    gemini_escalate_high_risk: bool = True
    gemini_escalation_risk_threshold: float = 0.6

    # The ai-worker runs in cycles instead of continuously: each cycle drains up to
    # ai_max_per_cycle mentions (concurrently), then sleeps ai_cycle_seconds. This caps
    # token burn and batches real-time traffic (default: a pass every 5 minutes).
    ai_cycle_seconds: int = 60
    ai_max_per_cycle: int = 200
    ai_concurrency: int = 3
    gemini_poll_interval_seconds: int = 5

    cors_allow_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    alert_telegram_chat_id: str = ""
    alert_negative_risk_threshold: float = 0.70
    alert_negative_sentiment_threshold: float = -0.45
    alert_poll_interval_seconds: int = 10
    # --- Staff-group workflow (inline buttons + pinned counter + SLA nudges) ---
    # Minutes a delivered signal may stay unanswered before the bot nudges the group;
    # 0 disables nudging entirely.
    alert_sla_minutes: int = Field(default=30, ge=0)
    alert_reminder_repeat_minutes: int = Field(default=60, ge=5)
    alert_reminder_max: int = Field(default=3, ge=0)
    alert_summary_enabled: bool = True
    # Floor between cosmetic refreshes of the pinned counter; status changes bypass it.
    alert_summary_refresh_seconds: int = Field(default=300, ge=30)

    # --- Dashboard authentication ---
    # When enabled, every API route (except /health, /auth/login and the Instagram
    # webhook) requires a valid signed token from /auth/login. Credentials come from
    # the environment; jwt_secret signs the tokens (MUST be a strong random value in prod).
    auth_enabled: bool = True
    admin_username: str = "admin"
    admin_password: str = ""
    jwt_secret: str = "change-me-in-env"
    jwt_expire_hours: int = 168

    @field_validator("telegram_allowed_updates", "cors_allow_origins", mode="before")
    @classmethod
    def parse_allowed_updates(cls, value: Any) -> list[str]:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                return list(json.loads(stripped))
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value

    @field_validator("telegram_command_allowed_user_ids", mode="before")
    @classmethod
    def parse_telegram_command_allowed_user_ids(cls, value: Any) -> list[int]:
        if value is None or value == "":
            return []
        if isinstance(value, int):
            return [value]
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            parsed = json.loads(stripped) if stripped.startswith("[") else stripped.split(",")
            return [int(item) for item in parsed if str(item).strip()]
        return [int(item) for item in value]


@lru_cache
def get_settings() -> Settings:
    return Settings()
