from types import SimpleNamespace

from app.db.repositories.users import count_blocked_users, get_or_create_user, get_user_by_telegram_id


def _telegram_user(telegram_id: int, username: str, first_name: str):
    return SimpleNamespace(id=telegram_id, username=username, first_name=first_name)


async def test_get_or_create_user_creates_new_user_not_blocked(session):
    user = await get_or_create_user(session, _telegram_user(777, "bob", "Bob"))
    assert user.is_blocked is False
    assert user.telegram_user_id == 777


async def test_get_or_create_user_resets_is_blocked_on_return(session):
    user = await get_or_create_user(session, _telegram_user(555, "alice", "Alice"))
    user.is_blocked = True
    await session.flush()

    returning_user = await get_or_create_user(session, _telegram_user(555, "alice2", "Alice2"))

    assert returning_user.id == user.id
    assert returning_user.is_blocked is False
    assert returning_user.username == "alice2"
    assert returning_user.first_name == "Alice2"


async def test_count_blocked_users(session):
    await get_or_create_user(session, _telegram_user(1, "a", "A"))
    blocked_user = await get_or_create_user(session, _telegram_user(2, "b", "B"))
    blocked_user.is_blocked = True
    await session.flush()

    assert await count_blocked_users(session) == 1


async def test_get_user_by_telegram_id(session):
    created = await get_or_create_user(session, _telegram_user(42, "c", "C"))

    found = await get_user_by_telegram_id(session, 42)
    missing = await get_user_by_telegram_id(session, 4242)

    assert found is not None
    assert found.id == created.id
    assert missing is None
