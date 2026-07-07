from app.db.repositories.stats import get_global_stats
from app.db.repositories.users import list_blocked_users
from tests.factories import make_delivery, make_full_chain, make_user


async def test_list_blocked_users_returns_only_blocked_ordered_and_limited(session):
    await make_user(session, telegram_user_id=1, is_blocked=False)
    blocked_a = await make_user(session, telegram_user_id=2, is_blocked=True, username="a")
    blocked_b = await make_user(session, telegram_user_id=3, is_blocked=True, username="b")

    blocked = await list_blocked_users(session, limit=10)

    assert {u.id for u in blocked} == {blocked_a.id, blocked_b.id}


async def test_list_blocked_users_respects_limit(session):
    for i in range(5):
        await make_user(session, telegram_user_id=100 + i, is_blocked=True)

    blocked = await list_blocked_users(session, limit=2)

    assert len(blocked) == 2


async def test_get_global_stats_counts_across_all_users(session):
    user1, search1, source1, message1, match1 = await make_full_chain(
        session,
        telegram_user_id=1,
        is_blocked=False,
        source_ref="ref-global-1",
    )
    await make_delivery(session, user=user1, match=match1, status="pending")

    user2, search2, source2, message2, match2 = await make_full_chain(
        session,
        telegram_user_id=2,
        is_blocked=True,
        source_ref="ref-global-2",
    )
    await make_delivery(session, user=user2, match=match2, status="blocked")

    stats = await get_global_stats(session)

    assert stats.users_total == 2
    assert stats.users_blocked == 1
    assert stats.searches_total == 2
    assert stats.searches_active == 2
    assert stats.sources_total == 2
    assert stats.matches_total == 2
