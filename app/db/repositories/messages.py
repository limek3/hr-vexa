from datetime import date, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DailyStats, Match, Message


async def save_message_if_new(
    session: AsyncSession,
    *,
    source_id: int,
    telegram_message_id: int,
    telegram_date: datetime,
    text: str,
    url: str | None,
) -> Message | None:
    stmt = (
        pg_insert(Message)
        .values(
            source_id=source_id,
            telegram_message_id=telegram_message_id,
            telegram_date=telegram_date,
            text=text,
            url=url,
        )
        .on_conflict_do_nothing(index_elements=["source_id", "telegram_message_id"])
        .returning(Message.id)
    )
    result = await session.execute(stmt)
    message_id = result.scalar_one_or_none()
    if message_id is None:
        return None

    result = await session.execute(select(Message).where(Message.id == message_id))
    return result.scalar_one()


async def create_match_once(
    session: AsyncSession,
    *,
    user_id: int,
    search_id: int,
    source_id: int,
    message_id: int,
) -> Match | None:
    stmt = (
        pg_insert(Match)
        .values(
            user_id=user_id,
            search_id=search_id,
            source_id=source_id,
            message_id=message_id,
        )
        .on_conflict_do_nothing(index_elements=["search_id", "message_id"])
        .returning(Match.id)
    )
    result = await session.execute(stmt)
    match_id = result.scalar_one_or_none()
    if match_id is None:
        return None

    result = await session.execute(select(Match).where(Match.id == match_id))
    return result.scalar_one()


async def increment_daily_stats(
    session: AsyncSession,
    *,
    user_id: int,
    search_id: int,
    stat_date: date,
) -> None:
    stmt = (
        pg_insert(DailyStats)
        .values(user_id=user_id, search_id=search_id, date=stat_date, matches_count=1)
        .on_conflict_do_update(
            index_elements=["user_id", "search_id", "date"],
            set_={"matches_count": DailyStats.matches_count + 1},
        )
    )
    await session.execute(stmt)


async def hide_match(session: AsyncSession, *, match_id: int, user_id: int) -> bool:
    result = await session.execute(
        update(Match)
        .where(Match.id == match_id, Match.user_id == user_id)
        .values(is_hidden=True)
        .returning(Match.id),
    )
    return result.scalar_one_or_none() is not None

