from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    import app.models.entities  # noqa: F401

    lock_id = 420260708
    with engine.connect() as connection:
        if engine.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": lock_id})
        try:
            Base.metadata.create_all(bind=connection)
            connection.commit()
            ensure_schema_upgrades()
        finally:
            if connection.in_transaction():
                connection.rollback()
            if engine.dialect.name == "postgresql":
                connection.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": lock_id})
                connection.commit()


def ensure_schema_upgrades() -> None:
    inspector = inspect(engine)
    if "telegram_sources" not in inspector.get_table_names():
        return

    table_names = set(inspector.get_table_names())
    if "brands" in table_names:
        brand_columns = {column["name"] for column in inspector.get_columns("brands")}
        brand_statements: list[str] = []
        if "primary_category" not in brand_columns:
            brand_statements.append("ALTER TABLE brands ADD COLUMN primary_category VARCHAR(255)")
        if "category_path" not in brand_columns:
            brand_statements.append("ALTER TABLE brands ADD COLUMN category_path JSONB NOT NULL DEFAULT '[]'::jsonb")
        if "products" not in brand_columns:
            brand_statements.append("ALTER TABLE brands ADD COLUMN products JSONB NOT NULL DEFAULT '[]'::jsonb")
        if "audience" not in brand_columns:
            brand_statements.append("ALTER TABLE brands ADD COLUMN audience TEXT")
        if "region" not in brand_columns:
            brand_statements.append("ALTER TABLE brands ADD COLUMN region VARCHAR(255)")
        if "monitoring_goals" not in brand_columns:
            brand_statements.append("ALTER TABLE brands ADD COLUMN monitoring_goals JSONB NOT NULL DEFAULT '[]'::jsonb")
        if "risk_keywords" not in brand_columns:
            brand_statements.append("ALTER TABLE brands ADD COLUMN risk_keywords JSONB NOT NULL DEFAULT '[]'::jsonb")
        if "positive_keywords" not in brand_columns:
            brand_statements.append("ALTER TABLE brands ADD COLUMN positive_keywords JSONB NOT NULL DEFAULT '[]'::jsonb")
        if "profile_config" not in brand_columns:
            brand_statements.append("ALTER TABLE brands ADD COLUMN profile_config JSONB NOT NULL DEFAULT '{}'::jsonb")
        if brand_statements:
            with engine.begin() as connection:
                for statement in brand_statements:
                    connection.execute(text(statement))

    columns = {column["name"] for column in inspector.get_columns("telegram_sources")}
    statements: list[str] = []
    if "source_category" not in columns:
        statements.append("ALTER TABLE telegram_sources ADD COLUMN source_category VARCHAR(64) NOT NULL DEFAULT 'unknown'")
    if "monitoring_mode" not in columns:
        statements.append("ALTER TABLE telegram_sources ADD COLUMN monitoring_mode VARCHAR(64) NOT NULL DEFAULT 'all_messages'")
    if "competitor_name" not in columns:
        statements.append("ALTER TABLE telegram_sources ADD COLUMN competitor_name VARCHAR(255)")
    if "notes" not in columns:
        statements.append("ALTER TABLE telegram_sources ADD COLUMN notes TEXT")
    if "monitor_from" not in columns:
        statements.append("ALTER TABLE telegram_sources ADD COLUMN monitor_from TIMESTAMP WITH TIME ZONE")

    # Backfill monitor_from only when the column was just added, not on every boot.
    monitor_from_added = "monitor_from" not in columns
    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
            if monitor_from_added:
                connection.execute(text("UPDATE telegram_sources SET monitor_from = created_at WHERE monitor_from IS NULL"))

    if "youtube_sources" in table_names:
        youtube_columns = {column["name"] for column in inspector.get_columns("youtube_sources")}
        youtube_statements: list[str] = []
        if "uploads_playlist_id" not in youtube_columns:
            youtube_statements.append("ALTER TABLE youtube_sources ADD COLUMN uploads_playlist_id VARCHAR(128)")
        if "nickname" not in youtube_columns:
            youtube_statements.append("ALTER TABLE youtube_sources ADD COLUMN nickname VARCHAR(255)")
        if "hashtags" not in youtube_columns:
            youtube_statements.append("ALTER TABLE youtube_sources ADD COLUMN hashtags JSONB NOT NULL DEFAULT '[]'::jsonb")
        if youtube_statements:
            with engine.begin() as connection:
                for statement in youtube_statements:
                    connection.execute(text(statement))

    if "instagram_sources" in table_names:
        ig_columns = {column["name"] for column in inspector.get_columns("instagram_sources")}
        ig_statements: list[str] = []
        if "token_status" not in ig_columns:
            ig_statements.append("ALTER TABLE instagram_sources ADD COLUMN token_status VARCHAR(32) NOT NULL DEFAULT 'unknown'")
        if "status_detail" not in ig_columns:
            ig_statements.append("ALTER TABLE instagram_sources ADD COLUMN status_detail TEXT")
        if "api_base" not in ig_columns:
            ig_statements.append("ALTER TABLE instagram_sources ADD COLUMN api_base VARCHAR(64)")
        if ig_statements:
            with engine.begin() as connection:
                for statement in ig_statements:
                    connection.execute(text(statement))

    if "instagram_mentions" in table_names:
        ig_mention_columns = {column["name"] for column in inspector.get_columns("instagram_mentions")}
        with engine.begin() as connection:
            if "comment_count" not in ig_mention_columns:
                connection.execute(text("ALTER TABLE instagram_mentions ADD COLUMN comment_count INTEGER"))
            media_url_column = next(
                (column for column in inspector.get_columns("instagram_mentions") if column["name"] == "media_url"),
                None,
            )
            if media_url_column is not None and getattr(media_url_column["type"], "length", None):
                connection.execute(text("ALTER TABLE instagram_mentions ALTER COLUMN media_url TYPE TEXT"))

    ensure_indexes()


def ensure_indexes() -> None:
    """Create hot-path indexes on already-existing tables.

    ``Base.metadata.create_all`` only creates indexes for tables it creates, so
    indexes added to the models after the tables already exist must be created
    explicitly. All are idempotent (IF NOT EXISTS).
    """
    index_statements = (
        "CREATE INDEX IF NOT EXISTS ix_mentions_created ON mentions (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_mentions_source ON mentions (source_id)",
        "CREATE INDEX IF NOT EXISTS ix_youtube_mentions_created ON youtube_mentions (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_instagram_mentions_created ON instagram_mentions (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_instagram_mentions_item_type ON instagram_mentions (item_type)",
        "CREATE INDEX IF NOT EXISTS ix_telegram_sources_brand ON telegram_sources (brand_id)",
    )
    with engine.begin() as connection:
        for statement in index_statements:
            connection.execute(text(statement))


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
