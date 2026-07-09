"""admin observability views and match details

Revision ID: 20260709_0001
Revises: None
Create Date: 2026-07-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260709_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("alter table messages add column if not exists sender_username varchar(255)")
    op.execute("alter table messages add column if not exists sender_phone varchar(64)")
    op.execute("alter table messages add column if not exists sender_name varchar(255)")
    op.execute("alter table matches add column if not exists matched_keyword varchar(255)")
    op.execute("alter table matches add column if not exists match_score integer")
    op.execute("alter table matches add column if not exists match_reason text")

    op.execute(
        """
        create or replace view vexa_admin_users as
        select
            u.id as user_id,
            u.telegram_user_id,
            u.username,
            u.first_name,
            u.subscription_plan,
            u.subscription_until,
            u.is_blocked,
            u.created_at,
            u.updated_at,
            count(distinct s.id) as searches_total,
            count(distinct s.id) filter (where s.is_active) as searches_active,
            count(distinct ss.source_id) filter (where ss.is_active) as sources_total,
            count(distinct ss.source_id) filter (
                where ss.is_active and src.access_status = 'available'
            ) as sources_available,
            count(distinct m.id) as matches_total,
            count(distinct m.id) filter (where m.created_at::date = current_date) as matches_today,
            count(distinct m.id) filter (where m.is_hidden) as matches_hidden,
            count(distinct f.id) as favorites_total
        from users u
        left join searches s on s.user_id = u.id
        left join search_sources ss on ss.search_id = s.id
        left join sources src on src.id = ss.source_id
        left join matches m on m.user_id = u.id
        left join favorites f on f.user_id = u.id
        group by u.id;
        """,
    )

    op.execute(
        """
        create or replace view vexa_admin_searches as
        select
            s.id as search_id,
            s.title as search_title,
            s.is_active as search_is_active,
            s.created_at as search_created_at,
            s.updated_at as search_updated_at,
            u.id as user_id,
            u.telegram_user_id,
            u.username,
            u.first_name,
            u.is_blocked as user_is_blocked,
            coalesce(string_agg(distinct sk.value, E'\\n'), '') as keywords,
            coalesce(string_agg(distinct smw.value, E'\\n'), '') as minus_words,
            count(distinct ss.source_id) filter (where ss.is_active) as sources_total,
            count(distinct ss.source_id) filter (
                where ss.is_active and src.access_status = 'available'
            ) as sources_available,
            count(distinct m.id) as matches_total,
            count(distinct m.id) filter (where m.created_at::date = current_date) as matches_today,
            count(distinct m.id) filter (where m.is_hidden) as matches_hidden
        from searches s
        join users u on u.id = s.user_id
        left join search_keywords sk on sk.search_id = s.id
        left join search_minus_words smw on smw.search_id = s.id
        left join search_sources ss on ss.search_id = s.id
        left join sources src on src.id = ss.source_id
        left join matches m on m.search_id = s.id
        group by s.id, u.id;
        """,
    )

    op.execute(
        """
        create or replace view vexa_admin_sources as
        select
            ss.id as search_source_id,
            ss.is_active as link_is_active,
            ss.created_at as link_created_at,
            s.id as search_id,
            s.title as search_title,
            u.id as user_id,
            u.telegram_user_id,
            u.username,
            u.first_name,
            src.id as source_id,
            src.telegram_id as source_telegram_id,
            src.username as source_username,
            src.title as source_title,
            src.type as source_type,
            src.input_ref,
            src.access_status,
            src.created_at as source_created_at,
            src.updated_at as source_updated_at,
            count(distinct msg.id) as messages_saved,
            count(distinct m.id) as matches_total
        from search_sources ss
        join searches s on s.id = ss.search_id
        join users u on u.id = s.user_id
        join sources src on src.id = ss.source_id
        left join messages msg on msg.source_id = src.id
        left join matches m on m.search_id = s.id and m.source_id = src.id
        group by ss.id, s.id, u.id, src.id;
        """,
    )

    op.execute(
        """
        create or replace view vexa_admin_matches as
        select
            m.id as match_id,
            m.created_at as match_created_at,
            m.is_hidden,
            m.matched_keyword,
            m.match_score,
            m.match_reason,
            u.id as user_id,
            u.telegram_user_id,
            u.username,
            u.first_name,
            u.is_blocked as user_is_blocked,
            s.id as search_id,
            s.title as search_title,
            s.is_active as search_is_active,
            src.id as source_id,
            src.title as source_title,
            src.input_ref as source_input_ref,
            src.access_status as source_status,
            msg.id as message_id,
            msg.telegram_message_id,
            msg.telegram_date,
            msg.url as message_url,
            msg.sender_username,
            msg.sender_phone,
            msg.sender_name,
            msg.text as message_text,
            nd.status as notification_status,
            nd.attempts as notification_attempts,
            nd.last_error as notification_last_error,
            nd.sent_at as notification_sent_at,
            mf.is_relevant as feedback_relevant,
            fav.id is not null as is_favorite
        from matches m
        join users u on u.id = m.user_id
        join searches s on s.id = m.search_id
        join sources src on src.id = m.source_id
        join messages msg on msg.id = m.message_id
        left join notification_deliveries nd on nd.match_id = m.id
        left join match_feedback mf on mf.match_id = m.id and mf.user_id = m.user_id
        left join favorites fav on fav.match_id = m.id and fav.user_id = m.user_id;
        """,
    )


def downgrade() -> None:
    op.execute("drop view if exists vexa_admin_matches")
    op.execute("drop view if exists vexa_admin_sources")
    op.execute("drop view if exists vexa_admin_searches")
    op.execute("drop view if exists vexa_admin_users")
    op.execute("alter table matches drop column if exists match_reason")
    op.execute("alter table matches drop column if exists match_score")
    op.execute("alter table matches drop column if exists matched_keyword")
    op.execute("alter table messages drop column if exists sender_name")
    op.execute("alter table messages drop column if exists sender_phone")
    op.execute("alter table messages drop column if exists sender_username")
