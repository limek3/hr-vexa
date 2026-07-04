from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from aiogram import Bot
from aiogram.enums import ParseMode

from app.bot.formatting import heading, metric
from app.db.repositories.notification_deliveries import (
    PendingNotification,
    list_pending_notifications,
    mark_notification_failed,
    mark_notification_sent,
)
from app.db.repositories.user_settings import notifications_paused_for_user
from app.db.session import SessionLocal
from app.services.notifications import send_candidate_notification

logger = logging.getLogger(__name__)


async def _send_digest_headers(bot: Bot, notifications: list[PendingNotification]) -> None:
    by_user: dict[int, list[PendingNotification]] = defaultdict(list)
    for item in notifications:
        by_user[item.user.id].append(item)

    for items in by_user.values():
        if len(items) < 2:
            continue
        user = items[0].user
        searches_count = len({item.search.id for item in items})
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


async def deliver_pending_notifications(bot: Bot) -> None:
    async with SessionLocal() as session:
        pending = await list_pending_notifications(session)
        deliverable: list[PendingNotification] = []
        for item in pending:
            if await notifications_paused_for_user(session, user_id=item.user.id):
                continue
            deliverable.append(item)

        if not deliverable:
            await session.commit()
            return

        try:
            await _send_digest_headers(bot, deliverable)
        except Exception:
            logger.exception("Quiet-hours digest header failed")

        for item in deliverable:
            delivery_id = item.delivery.id
            search_id = item.search.id
            match_id = item.match.id
            try:
                await send_candidate_notification(
                    bot,
                    user=item.user,
                    search=item.search,
                    source=item.source,
                    message=item.message,
                    match=item.match,
                )
                await mark_notification_sent(session, delivery_id=delivery_id)
                await session.commit()
                logger.info(
                    "Queued notification sent: search_id=%s match_id=%s delivery_id=%s",
                    search_id,
                    match_id,
                    delivery_id,
                )
            except Exception as exc:
                await session.rollback()
                await mark_notification_failed(session, delivery_id=delivery_id, error=str(exc))
                await session.commit()
                logger.exception(
                    "Queued notification failed: search_id=%s match_id=%s delivery_id=%s",
                    search_id,
                    match_id,
                    delivery_id,
                )


async def delivery_queue_loop(bot: Bot, *, interval_seconds: int = 60) -> None:
    while True:
        try:
            await deliver_pending_notifications(bot)
        except Exception:
            logger.exception("Delivery queue loop failed")
        await asyncio.sleep(interval_seconds)
