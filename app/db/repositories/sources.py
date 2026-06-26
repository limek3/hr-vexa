from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SearchSource, Source


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


async def upsert_linked_discussion_source(
    session: AsyncSession,
    *,
    parent_source_id: int,
    telegram_id: int,
    title: str,
    source_type: str,
) -> None:
    parent = await session.get(Source, parent_source_id)
    if not parent or parent.telegram_id == telegram_id:
        return

    result = await session.execute(select(Source).where(Source.telegram_id == telegram_id))
    source = result.scalar_one_or_none()
    if not source:
        source = Source(
            telegram_id=telegram_id,
            input_ref=f"discussion:{telegram_id}",
            title=title,
            type=source_type,
            access_status="available",
        )
        session.add(source)
        await session.flush()
    else:
        source.title = title
        source.type = source_type
        source.access_status = "available"

    result = await session.execute(
        select(SearchSource.search_id).where(SearchSource.source_id == parent_source_id),
    )
    search_ids = list(result.scalars().all())
    for search_id in search_ids:
        stmt = (
            pg_insert(SearchSource)
            .values(search_id=search_id, source_id=source.id, is_active=True)
            .on_conflict_do_nothing(index_elements=["search_id", "source_id"])
        )
        await session.execute(stmt)
