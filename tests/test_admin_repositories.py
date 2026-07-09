from datetime import UTC, datetime

from app.db.models import DailyStats, SearchKeyword, SearchMinusWord
from app.db.repositories.stats import get_global_stats, list_admin_user_search_report
from app.db.repositories.users import list_blocked_users
from tests.factories import (
    link_search_source,
    make_delivery,
    make_full_chain,
    make_search,
    make_source,
    make_user,
)


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


async def test_list_admin_user_search_report_includes_users_and_search_metrics(session):
    user, search, source, message, match = await make_full_chain(
        session,
        telegram_user_id=10,
        is_blocked=True,
        source_ref="ref-admin-report-1",
        search_title="Main search",
    )
    unavailable_source = await make_source(
        session,
        input_ref="ref-admin-report-2",
        access_status="unavailable",
    )
    await link_search_source(session, search=search, source=unavailable_source)
    session.add_all(
        [
            SearchKeyword(search_id=search.id, value="python"),
            SearchMinusWord(search_id=search.id, value="spam"),
            DailyStats(
                user_id=user.id,
                search_id=search.id,
                date=datetime.now(UTC).date(),
                matches_count=3,
            ),
        ],
    )
    match.is_hidden = True

    user_without_search = await make_user(session, telegram_user_id=11, username="empty")
    await session.flush()

    rows = await list_admin_user_search_report(session)

    by_user = {row.telegram_user_id: row for row in rows}
    search_row = by_user[10]
    empty_row = by_user[11]

    assert search_row.user_id == user.id
    assert search_row.user_is_blocked is True
    assert search_row.search_id == search.id
    assert search_row.search_title == "Main search"
    assert search_row.user_searches_total == 1
    assert search_row.user_searches_active == 1
    assert search_row.keywords_count == 1
    assert search_row.minus_words_count == 1
    assert search_row.sources_total == 2
    assert search_row.sources_available == 1
    assert search_row.user_matches_today == 3
    assert search_row.search_matches_today == 3
    assert search_row.search_matches_total == 1
    assert search_row.search_hidden_total == 1

    assert empty_row.user_id == user_without_search.id
    assert empty_row.search_id is None
    assert empty_row.user_searches_total == 0
    assert empty_row.search_matches_total == 0
