from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import DIVIDER
from app.bot.keyboards.inline import quiet_hours_actions
from app.bot.keyboards.labels import HELP, QUIET_HOURS, STATISTICS
from app.bot.keyboards.menu import main_menu
from app.bot.messages import HELP_TEXT
from app.db.models import UserSettings
from app.db.repositories.stats import get_user_stats
from app.db.repositories.user_settings import get_or_create_user_settings, toggle_quiet_hours
from app.db.repositories.users import get_or_create_user

router = Router()


def _quiet_hours_text(settings: UserSettings) -> str:
    status = "включены" if settings.quiet_hours_enabled else "выключены"
    return (
        "▌ <b>Тихие часы</b>\n"
        f"Статус: <b>{status}</b>\n"
        f"{DIVIDER}\n\n"
        "Время: <b>00:00–07:00 по МСК</b>\n\n"
        "▌ <b>Как работает</b>\n"
        "<blockquote>Когда тихие часы включены, Vexa продолжает находить совпадения, "
        "но не присылает уведомления ночью.</blockquote>"
    )


@router.message(Command("help"))
@router.message(lambda message: message.text == HELP)
async def help_message(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu())


@router.message(lambda message: message.text == STATISTICS)
async def statistics(message: Message, session: AsyncSession) -> None:
    if not message.from_user:
        return

    user = await get_or_create_user(session, message.from_user)
    stats = await get_user_stats(session, user_id=user.id)
    top_search = (
        f"{stats.top_search_title} · {stats.top_search_matches}"
        if stats.top_search_title
        else "пока нет данных"
    )

    await message.answer(
        "▌ <b>Статистика</b>\n"
        f"{DIVIDER}\n\n"
        "▌ <b>Сегодня</b>\n"
        f"<blockquote>Найдено совпадений: {stats.matches_today}\n"
        f"Лучший поиск: {top_search}</blockquote>\n\n"
        "▌ <b>Всего</b>\n"
        f"<blockquote>Поисков: {stats.searches_total}\n"
        f"Активных: {stats.searches_active}\n"
        f"Источников: {stats.sources_total}\n"
        f"Доступных источников: {stats.sources_available}</blockquote>\n\n"
        "▌ <b>Разбор</b>\n"
        f"<blockquote>Всего совпадений: {stats.matches_total}\n"
        f"Сохранено: {stats.favorites_total}\n"
        f"Скрыто: {stats.hidden_total}</blockquote>",
        reply_markup=main_menu(),
    )


@router.message(lambda message: message.text == QUIET_HOURS)
async def quiet_hours(message: Message, session: AsyncSession) -> None:
    if not message.from_user:
        return

    user = await get_or_create_user(session, message.from_user)
    settings = await get_or_create_user_settings(session, user_id=user.id)
    await message.answer(
        _quiet_hours_text(settings),
        reply_markup=quiet_hours_actions(settings.quiet_hours_enabled),
    )


@router.callback_query(F.data == "settings:quiet:toggle")
async def toggle_quiet_hours_setting(callback: CallbackQuery, session: AsyncSession) -> None:
    if not callback.from_user:
        return

    user = await get_or_create_user(session, callback.from_user)
    settings = await toggle_quiet_hours(session, user_id=user.id)
    if callback.message:
        await callback.message.edit_text(
            _quiet_hours_text(settings),
            reply_markup=quiet_hours_actions(settings.quiet_hours_enabled),
        )
    await callback.answer("Настройка обновлена.")


@router.message()
async def fallback(message: Message) -> None:
    await message.answer(
        "▌ <b>Команда не распознана</b>\n"
        f"{DIVIDER}\n\n"
        "Выберите действие в меню или отправьте /help.",
        reply_markup=main_menu(),
    )
