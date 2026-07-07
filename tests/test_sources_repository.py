from app.db.repositories.sources import SourceNotificationTarget, list_source_notification_targets
from tests.factories import link_search_source, make_search, make_source, make_user


async def test_list_source_notification_targets_excludes_blocked_users(session):
    source = await make_source(session, input_ref="ref-targets-1")

    active_user = await make_user(session, telegram_user_id=10, username="active", is_blocked=False)
    active_search = await make_search(session, user=active_user, title="Active search")
    await link_search_source(session, search=active_search, source=source)

    blocked_user = await make_user(session, telegram_user_id=11, username="blocked", is_blocked=True)
    blocked_search = await make_search(session, user=blocked_user, title="Blocked search")
    await link_search_source(session, search=blocked_search, source=source)

    targets = await list_source_notification_targets(session, source_id=source.id)

    assert len(targets) == 1
    target = targets[0]
    assert isinstance(target, SourceNotificationTarget)
    assert target.user_id == active_user.id
    assert target.telegram_user_id == 10
    assert target.search_title == "Active search"


async def test_list_source_notification_targets_excludes_inactive_links(session):
    source = await make_source(session, input_ref="ref-targets-2")
    user = await make_user(session, telegram_user_id=20, username="user")
    search = await make_search(session, user=user, title="Search", is_active=True)
    await link_search_source(session, search=search, source=source, is_active=False)

    targets = await list_source_notification_targets(session, source_id=source.id)

    assert targets == []
