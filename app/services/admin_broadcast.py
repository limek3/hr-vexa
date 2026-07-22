from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from app.db.models import User
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

_SEND_DELAY_SECONDS = 0.08
_MAX_RETRY_AFTER_SECONDS = 30
_broadcast_task: asyncio.Task[None] | None = None


@dataclass(frozen=True)
class BroadcastResult:
    total: int
    sent: int
    blocked: int
    failed: int


def is_broadcast_running() -> bool:
    return _broadcast_task is not None and not _broadcast_task.done()


def build_broadcast_keyboard(
    button_text: str | None,
    button_url: str | None,
) -> InlineKeyboardMarkup | None:
    if not button_text or not button_url:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=button_text, url=button_url)]],
    )


def _admin_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Вернуться в админ-панель", callback_data="admin:panel")],
        ],
    )


async def _mark_blocked(telegram_user_id: int) -> None:
    async with SessionLocal() as session:
        user = await session.scalar(
            select(User).where(User.telegram_user_id == telegram_user_id),
        )
        if user:
            user.is_blocked = True
            await session.commit()


async def _edit_progress(
    bot: Bot,
    *,
    admin_chat_id: int,
    progress_message_id: int,
    text: str,
    finished: bool = False,
) -> None:
    try:
        await bot.edit_message_text(
            chat_id=admin_chat_id,
            message_id=progress_message_id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=_admin_back_keyboard() if finished else None,
        )
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            logger.warning("Unable to update broadcast progress: %s", exc)


async def _send_one(
    bot: Bot,
    *,
    telegram_user_id: int,
    html_text: str,
    reply_markup: InlineKeyboardMarkup | None,
) -> str:
    for attempt in (1, 2):
        try:
            await bot.send_message(
                chat_id=telegram_user_id,
                text=html_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
            return "sent"
        except TelegramRetryAfter as exc:
            if attempt == 2:
                logger.warning(
                    "Broadcast delivery failed after retry: telegram_user_id=%s retry_after=%s",
                    telegram_user_id,
                    exc.retry_after,
                )
                return "failed"
            await asyncio.sleep(min(float(exc.retry_after), _MAX_RETRY_AFTER_SECONDS))
        except TelegramForbiddenError:
            await _mark_blocked(telegram_user_id)
            return "blocked"
        except TelegramBadRequest as exc:
            error = str(exc).lower()
            if "chat not found" in error or "user is deactivated" in error:
                await _mark_blocked(telegram_user_id)
                return "blocked"
            logger.warning(
                "Broadcast bad request: telegram_user_id=%s error=%s",
                telegram_user_id,
                exc,
            )
            return "failed"
        except Exception:
            logger.exception(
                "Broadcast delivery failed unexpectedly: telegram_user_id=%s",
                telegram_user_id,
            )
            return "failed"
    return "failed"


async def _run_broadcast(
    bot: Bot,
    *,
    admin_id: int,
    admin_chat_id: int,
    progress_message_id: int,
    html_text: str,
    button_text: str | None,
    button_url: str | None,
) -> None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(User.telegram_user_id)
            .where(User.is_blocked.is_(False))
            .order_by(User.id.asc()),
        )
        targets = list(result.scalars().all())

    total = len(targets)
    sent = 0
    blocked = 0
    failed = 0
    reply_markup = build_broadcast_keyboard(button_text, button_url)

    await _edit_progress(
        bot,
        admin_chat_id=admin_chat_id,
        progress_message_id=progress_message_id,
        text=(
            "<b>Рассылка запущена</b>\n\n"
            f"Получателей: <b>{total}</b>\n"
            "Отправлено: <b>0</b>\n"
            "Ошибок: <b>0</b>"
        ),
    )

    for index, telegram_user_id in enumerate(targets, start=1):
        status = await _send_one(
            bot,
            telegram_user_id=telegram_user_id,
            html_text=html_text,
            reply_markup=reply_markup,
        )
        if status == "sent":
            sent += 1
        elif status == "blocked":
            blocked += 1
        else:
            failed += 1

        if index == total or index % 25 == 0:
            await _edit_progress(
                bot,
                admin_chat_id=admin_chat_id,
                progress_message_id=progress_message_id,
                text=(
                    "<b>Рассылка выполняется</b>\n\n"
                    f"Обработано: <b>{index} из {total}</b>\n"
                    f"Отправлено: <b>{sent}</b>\n"
                    f"Заблокировали бота: <b>{blocked}</b>\n"
                    f"Ошибок: <b>{failed}</b>"
                ),
            )
        if index < total:
            await asyncio.sleep(_SEND_DELAY_SECONDS)

    logger.info(
        "Admin broadcast finished: admin_id=%s total=%s sent=%s blocked=%s failed=%s",
        admin_id,
        total,
        sent,
        blocked,
        failed,
    )
    await _edit_progress(
        bot,
        admin_chat_id=admin_chat_id,
        progress_message_id=progress_message_id,
        text=(
            "<b>Рассылка завершена</b>\n\n"
            f"Получателей: <b>{total}</b>\n"
            f"Доставлено: <b>{sent}</b>\n"
            f"Заблокировали бота: <b>{blocked}</b>\n"
            f"Ошибок: <b>{failed}</b>"
        ),
        finished=True,
    )


async def _run_broadcast_guarded(
    bot: Bot,
    *,
    admin_id: int,
    admin_chat_id: int,
    progress_message_id: int,
    html_text: str,
    button_text: str | None,
    button_url: str | None,
) -> None:
    try:
        await _run_broadcast(
            bot,
            admin_id=admin_id,
            admin_chat_id=admin_chat_id,
            progress_message_id=progress_message_id,
            html_text=html_text,
            button_text=button_text,
            button_url=button_url,
        )
    except Exception:
        logger.exception("Admin broadcast failed")
        await _edit_progress(
            bot,
            admin_chat_id=admin_chat_id,
            progress_message_id=progress_message_id,
            text=(
                "<b>Рассылка остановлена</b>\n\n"
                "Произошла внутренняя ошибка. Подробности записаны в лог Railway."
            ),
            finished=True,
        )


def start_broadcast(
    bot: Bot,
    *,
    admin_id: int,
    admin_chat_id: int,
    progress_message_id: int,
    html_text: str,
    button_text: str | None = None,
    button_url: str | None = None,
) -> bool:
    global _broadcast_task
    if is_broadcast_running():
        return False

    _broadcast_task = asyncio.create_task(
        _run_broadcast_guarded(
            bot,
            admin_id=admin_id,
            admin_chat_id=admin_chat_id,
            progress_message_id=progress_message_id,
            html_text=html_text,
            button_text=button_text,
            button_url=button_url,
        ),
        name="admin-broadcast",
    )

    def _report_task_result(task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            logger.info("Admin broadcast task was cancelled")
        except Exception:
            logger.exception("Admin broadcast task crashed")

    _broadcast_task.add_done_callback(_report_task_result)
    return True
