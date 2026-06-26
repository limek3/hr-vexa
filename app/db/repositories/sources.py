from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Source


async def list_sources(session: AsyncSession, statuses: set[str] | None = None) -> list[Source]:
    query = select(Source).order_by(Source.created_at.asc())
    if statuses:
        query = query.where(Source.access_status.in_(statuses))
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_source_by_telegram_id(session: AsyncSession, telegram_id: int) -> Source | None:
    result = await session.execute(select(Source).where(Source.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def mark_source_access(
    session: AsyncSession,
    *,
    source_id: int,
    telegram_id: int | None,
    title: str,
    source_type: str,
    access_status: str,
) -> None:
    await session.execute(
        update(Source)
        .where(Source.id == source_id)
        .values(
            telegram_id=telegram_id,
            title=title,
            type=source_type,
            access_status=access_status,
        ),
    )
