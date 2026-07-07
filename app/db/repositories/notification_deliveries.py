from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Match, Message, NotificationDelivery, Search, Source, User


MAX_DELIVERY_ATTEMPTS = 5

# Statuses that are safe to purge once they age out: they are terminal and
# carry no further action. "sent" deliveries are kept for audit purposes.
CLEANABLE_STATUSES = ("blocked", "failed")


@dataclass(slots=True)
class PendingNotification:
    delivery: NotificationDelivery
    user: User
    search: Search
    source: Source
    message: Message
    match: Match


async def enqueue_notification_once(
    session: AsyncSession,
    *,
    user_id: int,
    match_id: int,
) -> None:
    stmt = (
        pg_insert(NotificationDelivery)
        .values(user_id=user_id, match_id=match_id, status="pending", attempts=0, last_error="")
        .on_conflict_do_nothing(index_elements=["match_id"])
    )
    await session.execute(stmt)


async def list_pending_notifications(
    session: AsyncSession,
    *,
    limit: int = 50,
) -> list[PendingNotification]:
    result = await session.execute(
        select(NotificationDelivery, User, Search, Source, Message, Match)
        .join(Match, Match.id == NotificationDelivery.match_id)
        .join(User, User.id == NotificationDelivery.user_id)
        .join(Search, Search.id == Match.search_id)
        .join(Source, Source.id == Match.source_id)
        .join(Message, Message.id == Match.message_id)
        .where(
            NotificationDelivery.status == "pending",
            NotificationDelivery.attempts < MAX_DELIVERY_ATTEMPTS,
            Match.is_hidden.is_(False),
            User.is_blocked.is_(False),
        )
        .order_by(NotificationDelivery.created_at.asc(), NotificationDelivery.id.asc())
        .limit(limit),
    )
    return [
        PendingNotification(
            delivery=delivery,
            user=user,
            search=search,
            source=source,
            message=message,
            match=match,
        )
        for delivery, user, search, source, message, match in result.all()
    ]


async def mark_notification_sent(session: AsyncSession, *, delivery_id: int) -> None:
    delivery = await session.get(NotificationDelivery, delivery_id)
    if not delivery:
        return

    delivery.status = "sent"
    delivery.sent_at = datetime.now(UTC)
    delivery.last_error = ""
    await session.flush()


async def mark_notification_failed(
    session: AsyncSession,
    *,
    delivery_id: int,
    error: str,
) -> None:
    delivery = await session.get(NotificationDelivery, delivery_id)
    if not delivery:
        return

    delivery.attempts += 1
    delivery.last_error = error[:1000]
    if delivery.attempts >= MAX_DELIVERY_ATTEMPTS:
        delivery.status = "failed"
    await session.flush()


async def mark_notification_blocked(
    session: AsyncSession,
    *,
    delivery_id: int,
    error: str,
) -> None:
    delivery = await session.get(NotificationDelivery, delivery_id)
    if not delivery:
        return

    delivery.status = "blocked"
    delivery.attempts += 1
    delivery.last_error = error[:1000]
    await session.flush()


async def cleanup_old_deliveries(
    session: AsyncSession,
    *,
    older_than_days: int = 30,
) -> int:
    """Delete terminal (blocked/failed) deliveries older than the retention window.

    "sent" deliveries are intentionally kept for audit purposes.

    Uses synchronize_session="fetch" (a SELECT followed by the DELETE)
    instead of the default "evaluate" strategy: "evaluate" re-checks the
    WHERE clause against in-memory objects using plain Python operators,
    which is fragile across backends whenever a compared value's
    naive/aware timezone-ness differs from what a given DB driver returns
    (e.g. SQLite normalizes DateTime to naive values). "fetch" always
    round-trips through the database instead, which is slightly more
    expensive but correct regardless of backend.
    """
    cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
    result = await session.execute(
        delete(NotificationDelivery)
        .where(NotificationDelivery.status.in_(CLEANABLE_STATUSES))
        .where(NotificationDelivery.updated_at < cutoff)
        .returning(NotificationDelivery.id)
        .execution_options(synchronize_session="fetch"),
    )
    removed_ids = result.scalars().all()
    await session.flush()
    return len(removed_ids)
