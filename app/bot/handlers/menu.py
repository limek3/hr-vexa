from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import heading
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
        f"{heading('Тихие часы')}\n"
        "\n"
        f"Статус: <i>{status}</i>\n"
        "Время: <i>00:00–07:00 по МСК</i>\n\n"
        "<b>Как работает</b>\n"
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
        f"{heading('Статистика')}\n"
        "\n"
        "<b>Сегодня</b>\n"
        f"Найдено совпадений: <i>{stats.matches_today}</i>\n"
        f"Лучший поиск: <i>{top_search}</i>\n\n"
        "<b>Поиски</b>\n"
        f"Всего: <i>{stats.searches_total}</i>\n"
        f"Активных: <i>{stats.searches_active}</i>\n\n"
        "<b>Источники</b>\n"
        f"Всего: <i>{stats.sources_total}</i>\n"
        f"Доступных: <i>{stats.sources_available}</i>\n\n"
        "<b>Разбор</b>\n"
        f"Всего совпадений: <i>{stats.matches_total}</i>\n"
        f"Сохранено: <i>{stats.favorites_total}</i>\n"
        f"Скрыто: <i>{stats.hidden_total}</i>",
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
        f"{heading('Команда не распознана')}\n"
        "\n"
        "Выберите действие в меню или отправьте /help.",
        reply_markup=main_menu(),
    )
