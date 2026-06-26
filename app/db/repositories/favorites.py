from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Favorite, Match


async def save_favorite_once(session: AsyncSession, *, match_id: int, user_id: int) -> bool:
    match = await session.scalar(select(Match).where(Match.id == match_id, Match.user_id == user_id))
    if not match:
        return False

    stmt = (
        pg_insert(Favorite)
        .values(user_id=user_id, match_id=match_id)
        .on_conflict_do_nothing(index_elements=["user_id", "match_id"])
        .returning(Favorite.id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None
