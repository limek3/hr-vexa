"""Small helpers to build minimal, valid ORM object graphs for tests."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Match, Message, NotificationDelivery, Search, SearchSource, Source, User


async def make_user(
    session: AsyncSession,
    *,
    telegram_user_id: int,
    username: str | None = "user",
    first_name: str | None = "First",
    is_blocked: bool = False,
) -> User:
    user = User(
        telegram_user_id=telegram_user_id,
        username=username,
        first_name=first_name,
        is_blocked=is_blocked,
    )
    session.add(user)
    await session.flush()
    return user


async def make_source(
    session: AsyncSession,
    *,
    input_ref: str,
    title: str = "Source",
    access_status: str = "available",
) -> Source:
    source = Source(input_ref=input_ref, title=title, type="channel", access_status=access_status)
    session.add(source)
    await session.flush()
    return source


async def make_search(
    session: AsyncSession,
    *,
    user: User,
    title: str = "Search",
    is_active: bool = True,
) -> Search:
    # Explicitly assign empty relationship collections so accessing
    # search.keywords / search.minus_words later does not trigger a lazy
    # load (which would fail on an AsyncSession outside of a greenlet).
    search = Search(user_id=user.id, title=title, is_active=is_active, keywords=[], minus_words=[])
    session.add(search)
    await session.flush()
    return search


async def link_search_source(
    session: AsyncSession,
    *,
    search: Search,
    source: Source,
    is_active: bool = True,
) -> SearchSource:
    link = SearchSource(search_id=search.id, source_id=source.id, is_active=is_active)
    session.add(link)
    await session.flush()
    return link


async def make_message(
    session: AsyncSession,
    *,
    source: Source,
    telegram_message_id: int = 1,
    text: str = "hello",
) -> Message:
    message = Message(
        source_id=source.id,
        telegram_message_id=telegram_message_id,
        telegram_date=datetime.now(UTC),
        text=text,
        sender_username=None,
        sender_phone=None,
        sender_name=None,
    )
    session.add(message)
    await session.flush()
    return message


async def make_match(
    session: AsyncSession,
    *,
    user: User,
    search: Search,
    source: Source,
    message: Message,
) -> Match:
    match = Match(
        user_id=user.id,
        search_id=search.id,
        source_id=source.id,
        message_id=message.id,
        matched_keyword=None,
        match_score=None,
        match_reason=None,
    )
    session.add(match)
    await session.flush()
    return match


async def make_delivery(
    session: AsyncSession,
    *,
    user: User,
    match: Match,
    status: str = "pending",
    attempts: int = 0,
    updated_at: datetime | None = None,
) -> NotificationDelivery:
    delivery = NotificationDelivery(
        user_id=user.id,
        match_id=match.id,
        status=status,
        attempts=attempts,
        last_error="",
    )
    session.add(delivery)
    await session.flush()
    if updated_at is not None:
        delivery.updated_at = updated_at
        await session.flush()
    return delivery


async def make_full_chain(
    session: AsyncSession,
    *,
    telegram_user_id: int,
    is_blocked: bool = False,
    source_ref: str,
    search_title: str = "Search",
    message_text: str = "hello",
):
    """Create user -> search -> source -> message -> match, linked together."""
    user = await make_user(session, telegram_user_id=telegram_user_id, is_blocked=is_blocked)
    source = await make_source(session, input_ref=source_ref)
    search = await make_search(session, user=user, title=search_title)
    await link_search_source(session, search=search, source=source)
    message = await make_message(session, source=source, text=message_text)
    match = await make_match(session, user=user, search=search, source=source, message=message)
    return user, search, source, message, match
