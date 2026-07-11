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
        default_factory=lambda: ["message", "edited_message", "channel_post", "edited_channel_post"]
    )
    telegram_poll_timeout_seconds: int = 30

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
    youtube_poll_interval_seconds: int = 300
    youtube_sync_max_pages: int = 1
    youtube_comments_per_video: int = 100

    gemini_use_vertex: bool = True
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-pro"
    gemini_poll_interval_seconds: int = 5

    alert_telegram_chat_id: str = ""
    alert_negative_risk_threshold: float = 0.70
    alert_negative_sentiment_threshold: float = -0.45

    @field_validator("telegram_allowed_updates", mode="before")
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
