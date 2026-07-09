from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.models import (
    DailyStats,
    Favorite,
    Match,
    Search,
    SearchKeyword,
    SearchMinusWord,
    SearchSource,
    Source,
    User,
)


@dataclass(frozen=True)
class UserStats:
    searches_total: int
    searches_active: int
    sources_total: int
    sources_available: int
    matches_today: int
    matches_total: int
    favorites_total: int
    hidden_total: int
    top_search_title: str | None
    top_search_matches: int


@dataclass(frozen=True)
class GlobalStats:
    users_total: int
    users_blocked: int
    searches_total: int
    searches_active: int
    sources_total: int
    matches_today: int
    matches_total: int


@dataclass(frozen=True)
class AdminUserSearchReportRow:
    user_id: int
    telegram_user_id: int
    username: str | None
    first_name: str | None
    user_is_blocked: bool
    user_created_at: object
    user_updated_at: object
    user_searches_total: int
    user_searches_active: int
    user_matches_today: int
    user_matches_total: int
    search_id: int | None
    search_title: str | None
    search_is_active: bool | None
    keywords_count: int
    minus_words_count: int
    sources_total: int
    sources_available: int
    search_matches_today: int
    search_matches_total: int
    search_hidden_total: int


async def get_user_stats(session: AsyncSession, *, user_id: int) -> UserStats:
    today = datetime.now(UTC).date()

    searches_total = await session.scalar(
        select(func.count(Search.id)).where(Search.user_id == user_id),
    )
    searches_active = await session.scalar(
        select(func.count(Search.id)).where(Search.user_id == user_id, Search.is_active.is_(True)),
    )
    sources_total = await session.scalar(
        select(func.count(func.distinct(Source.id)))
        .join(SearchSource, SearchSource.source_id == Source.id)
        .join(Search, Search.id == SearchSource.search_id)
        .where(Search.user_id == user_id),
    )
    sources_available = await session.scalar(
        select(func.count(func.distinct(Source.id)))
        .join(SearchSource, SearchSource.source_id == Source.id)
        .join(Search, Search.id == SearchSource.search_id)
        .where(Search.user_id == user_id, Source.access_status == "available"),
    )
    matches_today = await session.scalar(
        select(func.coalesce(func.sum(DailyStats.matches_count), 0)).where(
            DailyStats.user_id == user_id,
            DailyStats.date == today,
        ),
    )
    matches_total = await session.scalar(
        select(func.count(Match.id)).where(Match.user_id == user_id),
    )
    favorites_total = await session.scalar(
        select(func.count(Favorite.id)).where(Favorite.user_id == user_id),
    )
    hidden_total = await session.scalar(
        select(func.count(Match.id)).where(Match.user_id == user_id, Match.is_hidden.is_(True)),
    )
    top_result = await session.execute(
        select(Search.title, DailyStats.matches_count)
        .join(Search, Search.id == DailyStats.search_id)
        .where(DailyStats.user_id == user_id, DailyStats.date == today)
        .order_by(desc(DailyStats.matches_count))
        .limit(1),
    )
    top_row = top_result.one_or_none()

    return UserStats(
        searches_total=int(searches_total or 0),
        searches_active=int(searches_active or 0),
        sources_total=int(sources_total or 0),
        sources_available=int(sources_available or 0),
        matches_today=int(matches_today or 0),
        matches_total=int(matches_total or 0),
        favorites_total=int(favorites_total or 0),
        hidden_total=int(hidden_total or 0),
        top_search_title=top_row[0] if top_row else None,
        top_search_matches=int(top_row[1]) if top_row else 0,
    )


async def list_admin_user_search_report(
    session: AsyncSession,
    *,
    limit: int = 5000,
) -> list[AdminUserSearchReportRow]:
    """Return one admin export row per user search, including users without searches."""
    today = datetime.now(UTC).date()

    user_search = aliased(Search)
    user_match = aliased(Match)

    user_searches_total = (
        select(func.count(user_search.id))
        .where(user_search.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    user_searches_active = (
        select(func.count(user_search.id))
        .where(user_search.user_id == User.id, user_search.is_active.is_(True))
        .correlate(User)
        .scalar_subquery()
    )
    user_matches_today = (
        select(func.coalesce(func.sum(DailyStats.matches_count), 0))
        .where(DailyStats.user_id == User.id, DailyStats.date == today)
        .correlate(User)
        .scalar_subquery()
    )
    user_matches_total = (
        select(func.count(user_match.id))
        .where(user_match.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    keywords_count = (
        select(func.count(SearchKeyword.id))
        .where(SearchKeyword.search_id == Search.id)
        .correlate(Search)
        .scalar_subquery()
    )
    minus_words_count = (
        select(func.count(SearchMinusWord.id))
        .where(SearchMinusWord.search_id == Search.id)
        .correlate(Search)
        .scalar_subquery()
    )
    sources_total = (
        select(func.count(func.distinct(Source.id)))
        .select_from(SearchSource)
        .join(Source, Source.id == SearchSource.source_id)
        .where(SearchSource.search_id == Search.id, SearchSource.is_active.is_(True))
        .correlate(Search)
        .scalar_subquery()
    )
    sources_available = (
        select(func.count(func.distinct(Source.id)))
        .select_from(SearchSource)
        .join(Source, Source.id == SearchSource.source_id)
        .where(
            SearchSource.search_id == Search.id,
            SearchSource.is_active.is_(True),
            Source.access_status == "available",
        )
        .correlate(Search)
        .scalar_subquery()
    )
    search_matches_today = (
        select(func.coalesce(func.sum(DailyStats.matches_count), 0))
        .where(DailyStats.search_id == Search.id, DailyStats.date == today)
        .correlate(Search)
        .scalar_subquery()
    )
    search_matches_total = (
        select(func.count(Match.id))
        .where(Match.search_id == Search.id)
        .correlate(Search)
        .scalar_subquery()
    )
    search_hidden_total = (
        select(func.count(Match.id))
        .where(Match.search_id == Search.id, Match.is_hidden.is_(True))
        .correlate(Search)
        .scalar_subquery()
    )

    result = await session.execute(
        select(
            User.id,
            User.telegram_user_id,
            User.username,
            User.first_name,
            User.is_blocked,
            User.created_at,
            User.updated_at,
            user_searches_total,
            user_searches_active,
            user_matches_today,
            user_matches_total,
            Search.id,
            Search.title,
            Search.is_active,
            keywords_count,
            minus_words_count,
            sources_total,
            sources_available,
            search_matches_today,
            search_matches_total,
            search_hidden_total,
        )
        .select_from(User)
        .outerjoin(Search, Search.user_id == User.id)
        .order_by(User.created_at.desc(), Search.created_at.desc())
        .limit(limit),
    )

    return [
        AdminUserSearchReportRow(
            user_id=row[0],
            telegram_user_id=row[1],
            username=row[2],
            first_name=row[3],
            user_is_blocked=bool(row[4]),
            user_created_at=row[5],
            user_updated_at=row[6],
            user_searches_total=int(row[7] or 0),
            user_searches_active=int(row[8] or 0),
            user_matches_today=int(row[9] or 0),
            user_matches_total=int(row[10] or 0),
            search_id=row[11],
            search_title=row[12],
            search_is_active=row[13],
            keywords_count=int(row[14] or 0),
            minus_words_count=int(row[15] or 0),
            sources_total=int(row[16] or 0),
            sources_available=int(row[17] or 0),
            search_matches_today=int(row[18] or 0),
            search_matches_total=int(row[19] or 0),
            search_hidden_total=int(row[20] or 0),
        )
        for row in result.all()
    ]


async def get_global_stats(session: AsyncSession) -> GlobalStats:
    """Instance-wide numbers for the admin panel (all users, not just one)."""
    today = datetime.now(UTC).date()

    users_total = await session.scalar(select(func.count(User.id)))
    users_blocked = await session.scalar(
        select(func.count(User.id)).where(User.is_blocked.is_(True)),
    )
    searches_total = await session.scalar(select(func.count(Search.id)))
    searches_active = await session.scalar(
        select(func.count(Search.id)).where(Search.is_active.is_(True)),
    )
    sources_total = await session.scalar(select(func.count(Source.id)))
    matches_today = await session.scalar(
        select(func.coalesce(func.sum(DailyStats.matches_count), 0)).where(DailyStats.date == today),
    )
    matches_total = await session.scalar(select(func.count(Match.id)))

    return GlobalStats(
        users_total=int(users_total or 0),
        users_blocked=int(users_blocked or 0),
        searches_total=int(searches_total or 0),
        searches_active=int(searches_active or 0),
        sources_total=int(sources_total or 0),
        matches_today=int(matches_today or 0),
        matches_total=int(matches_total or 0),
    )
