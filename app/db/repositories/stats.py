from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DailyStats, Favorite, Match, Search, SearchSource, Source, User


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
