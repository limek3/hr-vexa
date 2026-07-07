from datetime import UTC, datetime, timedelta

from app.db.models import NotificationDelivery
from app.db.repositories.notification_deliveries import (
    cleanup_old_deliveries,
    list_pending_notifications,
    mark_notification_blocked,
    mark_notification_failed,
    mark_notification_sent,
)
from tests.factories import make_delivery, make_full_chain


async def test_list_pending_notifications_excludes_blocked_users(session):
    user, search, source, message, match = await make_full_chain(
        session,
        telegram_user_id=1,
        is_blocked=False,
        source_ref="ref-pending-1",
    )
    await make_delivery(session, user=user, match=match, status="pending")

    blocked_user, blocked_search, blocked_source, blocked_message, blocked_match = await make_full_chain(
        session,
        telegram_user_id=2,
        is_blocked=True,
        source_ref="ref-pending-2",
    )
    await make_delivery(session, user=blocked_user, match=blocked_match, status="pending")

    pending = await list_pending_notifications(session)

    assert len(pending) == 1
    assert pending[0].user.id == user.id


async def test_mark_notification_blocked_sets_status_and_attempts(session):
    user, search, source, message, match = await make_full_chain(
        session,
        telegram_user_id=3,
        source_ref="ref-blocked-mark",
    )
    delivery = await make_delivery(session, user=user, match=match, status="pending", attempts=0)

    await mark_notification_blocked(session, delivery_id=delivery.id, error="blocked")

    assert delivery.status == "blocked"
    assert delivery.attempts == 1
    assert delivery.last_error == "blocked"


async def test_mark_notification_sent_and_failed(session):
    user, search, source, message, match = await make_full_chain(
        session,
        telegram_user_id=4,
        source_ref="ref-sent-failed",
    )
    sent_delivery = await make_delivery(session, user=user, match=match, status="pending")
    await mark_notification_sent(session, delivery_id=sent_delivery.id)
    assert sent_delivery.status == "sent"
    assert sent_delivery.last_error == ""

    user2, search2, source2, message2, match2 = await make_full_chain(
        session,
        telegram_user_id=5,
        source_ref="ref-sent-failed-2",
    )
    failed_delivery = await make_delivery(session, user=user2, match=match2, status="pending", attempts=4)
    await mark_notification_failed(session, delivery_id=failed_delivery.id, error="boom")
    assert failed_delivery.attempts == 5
    assert failed_delivery.status == "failed"


async def test_cleanup_old_deliveries_removes_only_old_terminal_rows(session):
    old_cutoff = datetime.now(UTC) - timedelta(days=45)

    user, _search, _source, _message, match = await make_full_chain(
        session,
        telegram_user_id=6,
        source_ref="ref-cleanup-old-blocked",
    )
    old_blocked = await make_delivery(session, user=user, match=match, status="blocked", updated_at=old_cutoff)

    user2, _search2, _source2, _message2, match2 = await make_full_chain(
        session,
        telegram_user_id=7,
        source_ref="ref-cleanup-recent-failed",
    )
    recent_failed = await make_delivery(session, user=user2, match=match2, status="failed")

    user3, _search3, _source3, _message3, match3 = await make_full_chain(
        session,
        telegram_user_id=8,
        source_ref="ref-cleanup-old-sent",
    )
    old_sent = await make_delivery(session, user=user3, match=match3, status="sent", updated_at=old_cutoff)

    old_blocked_id = old_blocked.id
    recent_failed_id = recent_failed.id
    old_sent_id = old_sent.id

    removed = await cleanup_old_deliveries(session, older_than_days=30)

    assert removed == 1
    assert await session.get(NotificationDelivery, old_blocked_id) is None
    assert await session.get(NotificationDelivery, recent_failed_id) is not None
    assert await session.get(NotificationDelivery, old_sent_id) is not None
