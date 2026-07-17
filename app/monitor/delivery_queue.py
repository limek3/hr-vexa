from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

from app.bot.formatting import heading, metric
from app.core.config import get_settings
from app.db.repositories.notification_deliveries import (
    PendingNotification,
    cleanup_old_deliveries,
    list_pending_notifications,
    mark_notification_blocked,
    mark_notification_failed,
    mark_notification_filtered,
    mark_notification_sent,
)
from app.db.repositories.user_settings import notifications_paused_for_user
from app.db.session import SessionLocal
from app.services.filtering import analyze_match
from app.services.notifications import MAX_RETRY_AFTER_SECONDS, safe_send_candidate_notification

logger = logging.getLogger(__name__)

# Small pause between consecutive sends in a batch so a large backlog of
# queued notifications does not burst past Telegram's ~30 messages/second
# global rate limit.
NOTIFICATION_SEND_DELAY_SECONDS = 0.05


async def _send_digest_headers(bot: Bot, session, notifications: list[PendingNotification]) -> None:
    by_user: dict[int, list[PendingNotification]] = defaultdict(list)
    for item in notifications:
        by_user[item.user.id].append(item)

    for items in by_user.values():
        if len(items) < 2:
            continue
        user = items[0].user
        searches_count = len({item.search.id for item in items})

        for attempt in (1, 2):
            try:
                await bot.send_message(
                    chat_id=user.telegram_user_id,
                    text=(
                        f"{heading('За тихие часы')}\n\n"
                        f"{metric('Найдено совпадений', len(items))}\n"
                        f"{metric('Поисков с совпадениями', searches_count)}\n\n"
                        "Ниже отправляю найденные сообщения."
                    ),
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
                break
            except TelegramRetryAfter as exc:
                if attempt == 2:
                    logger.warning(
                        "Digest header failed after flood-control wait: user_id=%s telegram_user_id=%s "
                        "retry_after=%s",
                        user.id,
                        user.telegram_user_id,
                        exc.retry_after,
                    )
                    break
                await asyncio.sleep(min(exc.retry_after, MAX_RETRY_AFTER_SECONDS))
                continue
            except TelegramForbiddenError:
                user.is_blocked = True
                await session.flush()
                logger.warning(
                    "Digest header blocked, bot was blocked by user: user_id=%s telegram_user_id=%s "
                    "username=%s first_name=%s",
                    user.id,
                    user.telegram_user_id,
                    user.username,
                    user.first_name,
                )
                break
            except TelegramBadRequest as exc:
                if "chat not found" in str(exc).lower():
                    user.is_blocked = True
                    await session.flush()
                    logger.warning(
                        "Digest header blocked, bad request indicates blocked user: user_id=%s "
                        "telegram_user_id=%s username=%s first_name=%s error=%s",
                        user.id,
                        user.telegram_user_id,
                        user.username,
                        user.first_name,
                        exc,
                    )
                else:
                    logger.warning(
                        "Digest header failed with bad request: user_id=%s telegram_user_id=%s error=%s",
                        user.id,
                        user.telegram_user_id,
                        exc,
                    )
                break
            except Exception:
                logger.exception(
                    "Digest header failed: user_id=%s telegram_user_id=%s",
                    user.id,
                    user.telegram_user_id,
                )
                break


async def deliver_pending_notifications(bot: Bot) -> None:
    async with SessionLocal() as session:
        pending = await list_pending_notifications(session)
        deliverable: list[PendingNotification] = []
        for item in pending:
            if await notifications_paused_for_user(session, user_id=item.user.id):
                continue

            current_analysis = analyze_match(
                item.message.text,
                [keyword.value for keyword in item.search.keywords],
                [minus_word.value for minus_word in item.search.minus_words],
            )
            if not current_analysis.matched:
                await mark_notification_filtered(
                    session,
                    delivery_id=item.delivery.id,
                    reason=current_analysis.reason,
                )
                logger.info(
                    "Queued notification removed by current filter: delivery_id=%s match_id=%s "
                    "search_id=%s source_id=%s reason=%s",
                    item.delivery.id,
                    item.match.id,
                    item.search.id,
                    item.source.id,
                    current_analysis.reason,
                )
                continue
            deliverable.append(item)

        await session.commit()
        if not deliverable:
            return

        try:
            await _send_digest_headers(bot, session, deliverable)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Quiet-hours digest header failed")

        for item in deliverable:
            delivery_id = item.delivery.id
            search_id = item.search.id
            match_id = item.match.id
            source_id = item.source.id
            user = item.user

            status = await safe_send_candidate_notification(
                bot,
                session,
                user=user,
                search=item.search,
                source=item.source,
                message=item.message,
                match=item.match,
            )

            try:
                if status == "sent":
                    await mark_notification_sent(session, delivery_id=delivery_id)
                elif status in ("blocked", "skipped_blocked"):
                    await mark_notification_blocked(session, delivery_id=delivery_id, error=status)
                else:
                    await mark_notification_failed(session, delivery_id=delivery_id, error=status)
                await session.commit()
            except Exception:
                await session.rollback()
                logger.exception(
                    "Failed to persist delivery status: status=%s delivery_id=%s search_id=%s match_id=%s",
                    status,
                    delivery_id,
                    search_id,
                    match_id,
                )
                continue

            logger.info(
                "Queued notification handled: status=%s user_id=%s telegram_user_id=%s username=%s "
                "search_id=%s match_id=%s source_id=%s delivery_id=%s",
                status,
                user.id,
                user.telegram_user_id,
                user.username,
                search_id,
                match_id,
                source_id,
                delivery_id,
            )

            if NOTIFICATION_SEND_DELAY_SECONDS:
                await asyncio.sleep(NOTIFICATION_SEND_DELAY_SECONDS)


async def delivery_queue_loop(bot: Bot, *, interval_seconds: int = 60) -> None:
    while True:
        try:
            await deliver_pending_notifications(bot)
        except Exception:
            logger.exception("Delivery queue loop failed")
        await asyncio.sleep(interval_seconds)


async def cleanup_deliveries_loop(*, interval_seconds: int = 86400) -> None:
    """Periodically purge old terminal (blocked/failed) delivery records."""
    settings = get_settings()
    retention_days = max(1, settings.notification_delivery_retention_days)
    while True:
        try:
            async with SessionLocal() as session:
                removed = await cleanup_old_deliveries(session, older_than_days=retention_days)
                await session.commit()
            if removed:
                logger.info(
                    "Cleaned up old notification deliveries: removed=%s retention_days=%s",
                    removed,
                    retention_days,
                )
        except Exception:
            logger.exception("Notification delivery cleanup failed")
        await asyncio.sleep(interval_seconds)
