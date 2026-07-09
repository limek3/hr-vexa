import logging

from sqlalchemy import text

from app.db.models import Base
from app.db.session import engine

logger = logging.getLogger(__name__)

# Indexes that may be missing on databases created before the index was added
# to the model. Base.metadata.create_all() only creates missing tables, so an
# already-existing "users" table would not automatically get this index.
# CREATE INDEX IF NOT EXISTS makes this safe to run on every startup.
_EXTRA_INDEX_STATEMENTS = (
    "CREATE INDEX IF NOT EXISTS ix_users_is_blocked ON users (is_blocked)",
)

_EXTRA_SCHEMA_STATEMENTS = (
    "ALTER TABLE messages ADD COLUMN IF NOT EXISTS sender_username varchar(255)",
    "ALTER TABLE messages ADD COLUMN IF NOT EXISTS sender_phone varchar(64)",
    "ALTER TABLE messages ADD COLUMN IF NOT EXISTS sender_name varchar(255)",
    "ALTER TABLE matches ADD COLUMN IF NOT EXISTS matched_keyword varchar(255)",
    "ALTER TABLE matches ADD COLUMN IF NOT EXISTS match_score integer",
    "ALTER TABLE matches ADD COLUMN IF NOT EXISTS match_reason text",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS channel_reminder_sent_on date",
    """
    CREATE OR REPLACE VIEW vexa_admin_users AS
    SELECT
        u.id AS user_id,
        u.telegram_user_id,
        u.username,
        u.first_name,
        u.subscription_plan,
        u.subscription_until,
        u.is_blocked,
        u.created_at,
        u.updated_at,
        count(distinct s.id) AS searches_total,
        count(distinct s.id) FILTER (WHERE s.is_active) AS searches_active,
        count(distinct ss.source_id) FILTER (WHERE ss.is_active) AS sources_total,
        count(distinct ss.source_id) FILTER (
            WHERE ss.is_active AND src.access_status = 'available'
        ) AS sources_available,
        count(distinct m.id) AS matches_total,
        count(distinct m.id) FILTER (WHERE m.created_at::date = current_date) AS matches_today,
        count(distinct m.id) FILTER (WHERE m.is_hidden) AS matches_hidden,
        count(distinct f.id) AS favorites_total
    FROM users u
    LEFT JOIN searches s ON s.user_id = u.id
    LEFT JOIN search_sources ss ON ss.search_id = s.id
    LEFT JOIN sources src ON src.id = ss.source_id
    LEFT JOIN matches m ON m.user_id = u.id
    LEFT JOIN favorites f ON f.user_id = u.id
    GROUP BY u.id
    """,
    """
    CREATE OR REPLACE VIEW vexa_admin_searches AS
    SELECT
        s.id AS search_id,
        s.title AS search_title,
        s.is_active AS search_is_active,
        s.created_at AS search_created_at,
        s.updated_at AS search_updated_at,
        u.id AS user_id,
        u.telegram_user_id,
        u.username,
        u.first_name,
        u.is_blocked AS user_is_blocked,
        coalesce(string_agg(distinct sk.value, E'\n'), '') AS keywords,
        coalesce(string_agg(distinct smw.value, E'\n'), '') AS minus_words,
        count(distinct ss.source_id) FILTER (WHERE ss.is_active) AS sources_total,
        count(distinct ss.source_id) FILTER (
            WHERE ss.is_active AND src.access_status = 'available'
        ) AS sources_available,
        count(distinct m.id) AS matches_total,
        count(distinct m.id) FILTER (WHERE m.created_at::date = current_date) AS matches_today,
        count(distinct m.id) FILTER (WHERE m.is_hidden) AS matches_hidden
    FROM searches s
    JOIN users u ON u.id = s.user_id
    LEFT JOIN search_keywords sk ON sk.search_id = s.id
    LEFT JOIN search_minus_words smw ON smw.search_id = s.id
    LEFT JOIN search_sources ss ON ss.search_id = s.id
    LEFT JOIN sources src ON src.id = ss.source_id
    LEFT JOIN matches m ON m.search_id = s.id
    GROUP BY s.id, u.id
    """,
    """
    CREATE OR REPLACE VIEW vexa_admin_sources AS
    SELECT
        ss.id AS search_source_id,
        ss.is_active AS link_is_active,
        ss.created_at AS link_created_at,
        s.id AS search_id,
        s.title AS search_title,
        u.id AS user_id,
        u.telegram_user_id,
        u.username,
        u.first_name,
        src.id AS source_id,
        src.telegram_id AS source_telegram_id,
        src.username AS source_username,
        src.title AS source_title,
        src.type AS source_type,
        src.input_ref,
        src.access_status,
        src.created_at AS source_created_at,
        src.updated_at AS source_updated_at,
        count(distinct msg.id) AS messages_saved,
        count(distinct m.id) AS matches_total
    FROM search_sources ss
    JOIN searches s ON s.id = ss.search_id
    JOIN users u ON u.id = s.user_id
    JOIN sources src ON src.id = ss.source_id
    LEFT JOIN messages msg ON msg.source_id = src.id
    LEFT JOIN matches m ON m.search_id = s.id AND m.source_id = src.id
    GROUP BY ss.id, s.id, u.id, src.id
    """,
    """
    CREATE OR REPLACE VIEW vexa_admin_matches AS
    SELECT
        m.id AS match_id,
        m.created_at AS match_created_at,
        m.is_hidden,
        m.matched_keyword,
        m.match_score,
        m.match_reason,
        u.id AS user_id,
        u.telegram_user_id,
        u.username,
        u.first_name,
        u.is_blocked AS user_is_blocked,
        s.id AS search_id,
        s.title AS search_title,
        s.is_active AS search_is_active,
        src.id AS source_id,
        src.title AS source_title,
        src.input_ref AS source_input_ref,
        src.access_status AS source_status,
        msg.id AS message_id,
        msg.telegram_message_id,
        msg.telegram_date,
        msg.url AS message_url,
        msg.sender_username,
        msg.sender_phone,
        msg.sender_name,
        msg.text AS message_text,
        nd.status AS notification_status,
        nd.attempts AS notification_attempts,
        nd.last_error AS notification_last_error,
        nd.sent_at AS notification_sent_at,
        mf.is_relevant AS feedback_relevant,
        fav.id IS NOT NULL AS is_favorite
    FROM matches m
    JOIN users u ON u.id = m.user_id
    JOIN searches s ON s.id = m.search_id
    JOIN sources src ON src.id = m.source_id
    JOIN messages msg ON msg.id = m.message_id
    LEFT JOIN notification_deliveries nd ON nd.match_id = m.id
    LEFT JOIN match_feedback mf ON mf.match_id = m.id AND mf.user_id = m.user_id
    LEFT JOIN favorites fav ON fav.match_id = m.id AND fav.user_id = m.user_id
    """,
)


async def init_models() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for statement in _EXTRA_SCHEMA_STATEMENTS:
            try:
                await conn.execute(text(statement))
            except Exception:
                logger.exception("Failed to ensure schema statement: %s", statement)
        for statement in _EXTRA_INDEX_STATEMENTS:
            try:
                await conn.execute(text(statement))
            except Exception:
                logger.exception("Failed to ensure index: %s", statement)
