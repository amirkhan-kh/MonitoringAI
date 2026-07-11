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
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": lock_id})
        try:
            Base.metadata.create_all(bind=connection)
            ensure_schema_upgrades()
        finally:
            if engine.dialect.name == "postgresql":
                connection.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": lock_id})


def ensure_schema_upgrades() -> None:
    inspector = inspect(engine)
    if "telegram_sources" not in inspector.get_table_names():
        return

    table_names = set(inspector.get_table_names())
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
