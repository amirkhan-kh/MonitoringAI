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
    if "bot_connection_id" not in columns:
        statements.append(
            "ALTER TABLE telegram_sources ADD COLUMN bot_connection_id UUID "
            "REFERENCES telegram_bot_connections(id) ON DELETE SET NULL"
        )
    if "parent_source_id" not in columns:
        statements.append(
            "ALTER TABLE telegram_sources ADD COLUMN parent_source_id UUID "
            "REFERENCES telegram_sources(id) ON DELETE SET NULL"
        )
    if "source_role" not in columns:
        statements.append("ALTER TABLE telegram_sources ADD COLUMN source_role VARCHAR(32) NOT NULL DEFAULT 'legacy'")
    if "connector_managed" not in columns:
        statements.append("ALTER TABLE telegram_sources ADD COLUMN connector_managed BOOLEAN NOT NULL DEFAULT FALSE")
    if "bot_access_status" not in columns:
        statements.append("ALTER TABLE telegram_sources ADD COLUMN bot_access_status VARCHAR(32) NOT NULL DEFAULT 'unverified'")
    if "telethon_access_status" not in columns:
        statements.append("ALTER TABLE telegram_sources ADD COLUMN telethon_access_status VARCHAR(32) NOT NULL DEFAULT 'unverified'")
    if "access_checked_at" not in columns:
        statements.append("ALTER TABLE telegram_sources ADD COLUMN access_checked_at TIMESTAMP WITH TIME ZONE")

    # Backfill monitor_from only when the column was just added, not on every boot.
    monitor_from_added = "monitor_from" not in columns
    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
            if monitor_from_added:
                connection.execute(text("UPDATE telegram_sources SET monitor_from = created_at WHERE monitor_from IS NULL"))

    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE telegram_sources SET connector_managed = TRUE "
                "WHERE bot_connection_id IS NOT NULL OR source_role = 'bot_inbox'"
            )
        )
        connection.execute(
            text(
                "UPDATE telegram_sources SET source_role = "
                "CASE WHEN collect_posts THEN 'channel' ELSE 'discussion' END "
                "WHERE connector_managed = TRUE AND source_role = 'group'"
            )
        )
        connection.execute(
            text(
                "UPDATE telegram_sources SET source_role = 'legacy' "
                "WHERE connector_managed = FALSE AND source_role = 'group'"
            )
        )

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

    ensure_telegram_brand_scoped_uniqueness(table_names)
    ensure_youtube_brand_scoped_uniqueness(table_names)

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

    if "alert_events" in table_names:
        alert_columns = {column["name"] for column in inspector.get_columns("alert_events")}
        alert_statements = [
            f"ALTER TABLE alert_events ADD COLUMN {definition}"
            for name, definition in (
                ("work_status", "work_status VARCHAR(32) NOT NULL DEFAULT 'open'"),
                ("checked_by", "checked_by VARCHAR(255)"),
                ("checked_by_user_id", "checked_by_user_id BIGINT"),
                ("checked_at", "checked_at TIMESTAMP WITH TIME ZONE"),
                ("answered_by", "answered_by VARCHAR(255)"),
                ("answered_by_user_id", "answered_by_user_id BIGINT"),
                ("answered_at", "answered_at TIMESTAMP WITH TIME ZONE"),
                ("telegram_chat_id", "telegram_chat_id VARCHAR(64)"),
                ("telegram_message_id", "telegram_message_id BIGINT"),
                ("reminded_at", "reminded_at TIMESTAMP WITH TIME ZONE"),
                ("reminder_count", "reminder_count INTEGER NOT NULL DEFAULT 0"),
            )
            if name not in alert_columns
        ]
        if alert_statements:
            with engine.begin() as connection:
                for statement in alert_statements:
                    connection.execute(text(statement))
                if "work_status" not in alert_columns:
                    # Alerts delivered before the staff-group workflow existed carry no
                    # buttons, so nobody can ever close them: counting them as "open"
                    # would start the counter on a backlog that cannot be worked off.
                    connection.execute(
                        text("UPDATE alert_events SET work_status = 'archived' WHERE status IN ('sent', 'abandoned')")
                    )

    # Soft-delete marker: a removed source whose mentions the operator chose to keep stays
    # in the table with deleted_at set, so re-adding it revives the same row and its id.
    for source_table in ("telegram_sources", "youtube_sources", "instagram_sources", "facebook_sources"):
        if source_table not in table_names:
            continue
        if "deleted_at" in {column["name"] for column in inspector.get_columns(source_table)}:
            continue
        with engine.begin() as connection:
            connection.execute(text(f"ALTER TABLE {source_table} ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE"))

    ensure_indexes()


def ensure_telegram_brand_scoped_uniqueness(table_names: set[str]) -> None:
    if engine.dialect.name != "postgresql":
        return
    if "telegram_sources" not in table_names or "mentions" not in table_names:
        return

    with engine.begin() as connection:
        connection_inspector = inspect(connection)
        quote = connection.dialect.identifier_preparer.quote
        removals: list[str] = []
        if "telegram_bot_connections" in table_names:
            connection_constraints = connection_inspector.get_unique_constraints("telegram_bot_connections")
            connection_unique_columns = {
                tuple(constraint.get("column_names") or ())
                for constraint in connection_constraints
            }
            if ("bot_id",) not in connection_unique_columns:
                connection.execute(
                    text(
                        "ALTER TABLE telegram_bot_connections "
                        "ADD CONSTRAINT uq_telegram_bot_connections_bot_id UNIQUE (bot_id)"
                    )
                )
        source_constraints = connection_inspector.get_unique_constraints("telegram_sources")
        for constraint in source_constraints:
            columns = tuple(constraint.get("column_names") or ())
            name = constraint.get("name")
            if name and columns in {
                ("chat_id",),
                ("username",),
                ("brand_id", "chat_id"),
                ("brand_id", "username"),
            }:
                removals.append(
                    f"ALTER TABLE {quote('telegram_sources')} DROP CONSTRAINT {quote(name)}"
                )

        mention_constraints = connection_inspector.get_unique_constraints("mentions")
        mention_columns = {
            tuple(constraint.get("column_names") or ()): constraint.get("name")
            for constraint in mention_constraints
        }
        desired_mention_columns = ("brand_id", "source_id", "platform", "chat_id", "message_id")
        if desired_mention_columns not in mention_columns:
            connection.execute(
                text(
                    "ALTER TABLE mentions ADD CONSTRAINT uq_mentions_brand_source_chat_message "
                    "UNIQUE NULLS NOT DISTINCT (brand_id, source_id, platform, chat_id, message_id)"
                )
            )
        legacy_mention_name = mention_columns.get(("platform", "chat_id", "message_id"))
        if legacy_mention_name:
            removals.append(
                f"ALTER TABLE {quote('mentions')} DROP CONSTRAINT {quote(legacy_mention_name)}"
            )

        for statement in removals:
            connection.execute(text(statement))
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_telegram_sources_brand_chat_id "
                "ON telegram_sources (brand_id, chat_id) NULLS NOT DISTINCT WHERE chat_id IS NOT NULL"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_telegram_sources_brand_username "
                "ON telegram_sources (brand_id, username) NULLS NOT DISTINCT WHERE username IS NOT NULL"
            )
        )


def ensure_youtube_brand_scoped_uniqueness(table_names: set[str]) -> None:
    if engine.dialect.name != "postgresql":
        return

    constraint_specs = (
        (
            "youtube_sources",
            "uq_youtube_sources_brand_source_ref",
            ("brand_id", "source_ref"),
            ("source_ref",),
        ),
        (
            "youtube_mentions",
            "uq_youtube_mentions_brand_external_id",
            ("brand_id", "external_id"),
            ("external_id",),
        ),
    )
    applicable_specs = [spec for spec in constraint_specs if spec[0] in table_names]
    if not applicable_specs:
        return

    with engine.begin() as connection:
        connection_inspector = inspect(connection)
        additions: list[str] = []
        removals: list[str] = []
        quote = connection.dialect.identifier_preparer.quote

        for table_name, desired_name, desired_columns, legacy_columns in applicable_specs:
            constraints = connection_inspector.get_unique_constraints(table_name)
            constraint_columns = {
                tuple(constraint.get("column_names") or ()): constraint.get("name")
                for constraint in constraints
            }
            if desired_columns not in constraint_columns:
                additions.append(
                    f"ALTER TABLE {quote(table_name)} ADD CONSTRAINT {quote(desired_name)} "
                    f"UNIQUE NULLS NOT DISTINCT ({', '.join(quote(column) for column in desired_columns)})"
                )
            legacy_name = constraint_columns.get(legacy_columns)
            if legacy_name:
                removals.append(
                    f"ALTER TABLE {quote(table_name)} DROP CONSTRAINT {quote(legacy_name)}"
                )

        for statement in additions:
            connection.execute(text(statement))
        for statement in removals:
            connection.execute(text(statement))


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
        # Every hot YouTube read orders/filters by coalesce(published_at, created_at),
        # which a plain (brand_id, published_at) b-tree cannot serve.
        "CREATE INDEX IF NOT EXISTS ix_youtube_mentions_brand_recency "
        "ON youtube_mentions (brand_id, (coalesce(published_at, created_at)) DESC)",
        "CREATE INDEX IF NOT EXISTS ix_youtube_mentions_source_recency "
        "ON youtube_mentions (source_id, (coalesce(published_at, created_at)) DESC)",
        "CREATE INDEX IF NOT EXISTS ix_youtube_sources_due "
        "ON youtube_sources (last_checked_at) WHERE active AND deleted_at IS NULL",
        "CREATE INDEX IF NOT EXISTS ix_instagram_mentions_created ON instagram_mentions (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_instagram_mentions_item_type ON instagram_mentions (item_type)",
        "CREATE INDEX IF NOT EXISTS ix_telegram_sources_brand ON telegram_sources (brand_id)",
        "CREATE INDEX IF NOT EXISTS ix_telegram_sources_bot_connection ON telegram_sources (bot_connection_id)",
        "CREATE INDEX IF NOT EXISTS ix_telegram_sources_parent ON telegram_sources (parent_source_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_telegram_sources_bot_inbox_connection "
        "ON telegram_sources (bot_connection_id) "
        "WHERE source_role = 'bot_inbox' AND bot_connection_id IS NOT NULL",
        # The staff-group inbox reads "everything still unanswered, oldest first" on every
        # summary refresh and every SLA sweep, so that filter needs its own index.
        "CREATE INDEX IF NOT EXISTS ix_alert_events_work_status "
        "ON alert_events (work_status, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_alert_events_open "
        "ON alert_events (created_at) WHERE work_status <> 'answered'",
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
