from datetime import date, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DailyStats, Match, MatchFeedback, Message, SearchKeyword, SearchMinusWord


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


async def save_match_feedback(
    session: AsyncSession,
    *,
    match_id: int,
    user_id: int,
    is_relevant: bool,
) -> bool:
    result = await session.execute(
        select(Match, Message)
        .join(Message, Message.id == Match.message_id)
        .where(Match.id == match_id, Match.user_id == user_id),
    )
    row = result.one_or_none()
    if not row:
        return False

    match, message = row
    keyword_result = await session.execute(
        select(SearchKeyword.value).where(SearchKeyword.search_id == match.search_id),
    )
    minus_result = await session.execute(
        select(SearchMinusWord.value).where(SearchMinusWord.search_id == match.search_id),
    )
    keyword_snapshot = "\n".join(keyword_result.scalars().all())
    minus_word_snapshot = "\n".join(minus_result.scalars().all())

    stmt = (
        pg_insert(MatchFeedback)
        .values(
            user_id=user_id,
            match_id=match.id,
            search_id=match.search_id,
            message_id=match.message_id,
            is_relevant=is_relevant,
            keyword_snapshot=keyword_snapshot,
            minus_word_snapshot=minus_word_snapshot,
            message_text=message.text,
        )
        .on_conflict_do_update(
            index_elements=["user_id", "match_id"],
            set_={
                "is_relevant": is_relevant,
                "keyword_snapshot": keyword_snapshot,
                "minus_word_snapshot": minus_word_snapshot,
                "message_text": message.text,
            },
        )
    )
    await session.execute(stmt)
    return True
