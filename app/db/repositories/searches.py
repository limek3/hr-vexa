from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Search, SearchKeyword, SearchMinusWord, SearchSource, Source


async def create_search(
    session: AsyncSession,
    *,
    user_id: int,
    title: str,
    keywords: list[str],
    minus_words: list[str],
    sources: list[str],
) -> Search:
    search = Search(user_id=user_id, title=title, is_active=True)
    session.add(search)
    await session.flush()

    session.add_all(SearchKeyword(search_id=search.id, value=value) for value in keywords)
    session.add_all(SearchMinusWord(search_id=search.id, value=value) for value in minus_words)

    for source_ref in sources:
        source = await get_or_create_source(session, source_ref)
        session.add(SearchSource(search_id=search.id, source_id=source.id, is_active=True))

    await session.flush()
    return search


async def get_or_create_source(session: AsyncSession, input_ref: str) -> Source:
    result = await session.execute(select(Source).where(Source.input_ref == input_ref))
    source = result.scalar_one_or_none()
    if source:
        return source

    username = input_ref[1:] if input_ref.startswith("@") else None
    source = Source(input_ref=input_ref, username=username, title=input_ref, access_status="pending")
    session.add(source)
    await session.flush()
    return source


async def list_user_searches(session: AsyncSession, user_id: int) -> list[Search]:
    result = await session.execute(
        select(Search)
        .where(Search.user_id == user_id)
        .options(
            selectinload(Search.keywords),
            selectinload(Search.minus_words),
            selectinload(Search.sources).selectinload(SearchSource.source),
        )
        .order_by(Search.created_at.desc()),
    )
    return list(result.scalars().all())


async def list_active_searches_for_source(session: AsyncSession, source_id: int) -> list[Search]:
    result = await session.execute(
        select(Search)
        .join(SearchSource, SearchSource.search_id == Search.id)
        .where(Search.is_active.is_(True))
        .where(SearchSource.is_active.is_(True))
        .where(SearchSource.source_id == source_id)
        .options(selectinload(Search.keywords), selectinload(Search.minus_words)),
    )
    return list(result.scalars().all())
