from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import heading
from app.core.config import get_settings
from app.db.models import User
from app.db.repositories.users import (
    list_users_for_channel_reminder,
    mark_channel_reminder_sent,
)
from app.db.session import SessionLocal
from app.services.notifications import MAX_RETRY_AFTER_SECONDS

logger = logging.getLogger(__name__)

REMINDER_BATCH_LIMIT = 500
REMINDER_SEND_DELAY_SECONDS = 0.05
REMINDER_LOOP_INTERVAL_SECONDS = 300


def _parse_clock(value: str) -> time:
    hour, minute = value.strip().split(":", maxsplit=1)
    return time(hour=int(hour), minute=int(minute))


def _reminder_timezone() -> ZoneInfo:
    timezone_name = get_settings().subscription_reminder_timezone
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        logger.warning(
            "Subscription reminder timezone is invalid, falling back to Europe/Moscow: timezone=%s",
            timezone_name,
        )
        return ZoneInfo("Europe/Moscow")


def _channel_url() -> str:
    settings = get_settings()
    if settings.subscription_channel_url.strip():
        return settings.subscription_channel_url.strip()
    channel_id = settings.subscription_channel_id.strip()
    if channel_id.startswith("@"):
        return f"https://t.me/{channel_id[1:]}"
    return "https://t.me/vexa_group"


def _subscribe_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📣 Подписаться на канал",
                    url=_channel_url(),
                ),
            ],
        ],
    )


def _reminder_text() -> str:
    return (
        f"{heading('Vexa на связи')}\n\n"
        "Я тут каждый день ищу для вас совпадения, слежу за источниками и стараюсь не пропустить "
        "ничего полезного.\n\n"
        "А вы на мой канал ещё не подписаны.\n\n"
        "<blockquote>Подпишитесь: там новости Vexa, обновления, примеры настроек, база ключей "
        "и полезные штуки для поиска кандидатов.</blockquote>"
    )


def _is_subscribed_status(member: object) -> bool:
    status = getattr(member, "status", "")
    status_value = getattr(status, "value", str(status)).casefold()
    if status_value in {"creator", "administrator", "member"}:
        return True
    if status_value == "restricted":
        return bool(getattr(member, "is_member", False))
    return False


async def _is_user_subscribed(bot: Bot, user: User) -> bool | None:
    channel_id = get_settings().subscription_channel_id.strip()
    if not channel_id:
        return None

    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user.telegram_user_id)
        return _is_subscribed_status(member)
    except TelegramBadRequest as exc:
        error_text = str(exc).lower()
        if "user not found" in error_text or "participant_id_invalid" in error_text:
            return False
        logger.warning(
            "Subscription check failed: user_id=%s telegram_user_id=%s channel_id=%s error=%s",
            user.id,
            user.telegram_user_id,
            channel_id,
            exc,
        )
        return None
    except Exception:
        logger.exception(
            "Subscription check failed unexpectedly: user_id=%s telegram_user_id=%s channel_id=%s",
            user.id,
            user.telegram_user_id,
            channel_id,
        )
        return None


async def _send_subscription_reminder(
    bot: Bot,
    session: AsyncSession,
    *,
    user: User,
    today: date,
) -> str:
    subscribed = await _is_user_subscribed(bot, user)
    if subscribed is None:
        return "check_failed"
    if subscribed:
        return "subscribed"

    for attempt in (1, 2):
        try:
            await bot.send_message(
                chat_id=user.telegram_user_id,
                text=_reminder_text(),
                reply_markup=_subscribe_keyboard(),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            await mark_channel_reminder_sent(session, user=user, today=today)
            return "sent"
        except TelegramRetryAfter as exc:
            if attempt == 2:
                logger.warning(
                    "Subscription reminder failed after flood-control wait: user_id=%s "
                    "telegram_user_id=%s retry_after=%s",
                    user.id,
                    user.telegram_user_id,
                    exc.retry_after,
                )
                return "failed"
            await asyncio.sleep(min(exc.retry_after, MAX_RETRY_AFTER_SECONDS))
            continue
        except TelegramForbiddenError:
            user.is_blocked = True
            await session.flush()
            logger.warning(
                "Subscription reminder blocked, bot was blocked by user: user_id=%s "
                "telegram_user_id=%s username=%s first_name=%s",
                user.id,
                user.telegram_user_id,
                user.username,
                user.first_name,
            )
            return "blocked"
        except TelegramBadRequest as exc:
            if "chat not found" in str(exc).lower():
                user.is_blocked = True
                await session.flush()
                return "blocked"
            logger.warning(
                "Subscription reminder failed with bad request: user_id=%s telegram_user_id=%s "
                "error=%s",
                user.id,
                user.telegram_user_id,
                exc,
            )
            return "failed"
        except Exception:
            logger.exception(
                "Subscription reminder failed: user_id=%s telegram_user_id=%s",
                user.id,
                user.telegram_user_id,
            )
            return "failed"
    return "failed"


async def send_subscription_reminders(bot: Bot, session: AsyncSession, *, today: date) -> None:
    users = await list_users_for_channel_reminder(session, today=today, limit=REMINDER_BATCH_LIMIT)
    if not users:
        return

    stats = {
        "sent": 0,
        "subscribed": 0,
        "blocked": 0,
        "failed": 0,
        "check_failed": 0,
    }
    for user in users:
        status = await _send_subscription_reminder(bot, session, user=user, today=today)
        stats[status] = stats.get(status, 0) + 1
        await asyncio.sleep(REMINDER_SEND_DELAY_SECONDS)

    logger.info("Subscription reminder finished: today=%s stats=%s", today, stats)


def _seconds_until_next_check(now: datetime) -> float:
    scheduled_time = _parse_clock(get_settings().subscription_reminder_time)
    scheduled = datetime.combine(now.date(), scheduled_time, tzinfo=now.tzinfo)
    if now < scheduled:
        return min((scheduled - now).total_seconds(), REMINDER_LOOP_INTERVAL_SECONDS)
    return REMINDER_LOOP_INTERVAL_SECONDS


async def subscription_reminder_loop(bot: Bot) -> None:
    settings = get_settings()
    if not settings.subscription_reminder_enabled:
        logger.info("Subscription reminder is disabled")
        return
    if not settings.subscription_channel_id.strip():
        logger.info("Subscription reminder is disabled, SUBSCRIPTION_CHANNEL_ID is empty")
        return

    last_run_date: date | None = None
    while True:
        timezone = _reminder_timezone()
        now = datetime.now(timezone)
        scheduled_time = _parse_clock(get_settings().subscription_reminder_time)
        if now.time() >= scheduled_time and last_run_date != now.date():
            try:
                async with SessionLocal() as session:
                    await send_subscription_reminders(bot, session, today=now.date())
                    await session.commit()
                last_run_date = now.date()
            except Exception:
                logger.exception("Subscription reminder loop failed")
        await asyncio.sleep(max(1, _seconds_until_next_check(datetime.now(timezone))))
