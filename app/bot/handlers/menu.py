from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import heading, metric, text_value
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
        f"{text_value('Статус', status)}\n"
        f"{text_value('Время', '00:00–07:00 по МСК')}\n\n"
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
    top_search_line = text_value("Самый активный поиск", top_search)

    await message.answer(
        f"{heading('Статистика')}\n"
        "\n"
        "<b>Сегодня</b>\n"
        f"{metric('Найдено сегодня', stats.matches_today)}\n"
        f"{top_search_line}\n\n"
        "<b>Поиски</b>\n"
        f"{metric('Всего поисков', stats.searches_total)}\n"
        f"{metric('Включено поисков', stats.searches_active)}\n\n"
        "<b>Источники</b>\n"
        f"{metric('Всего источников', stats.sources_total)}\n"
        f"{metric('Доступно источников', stats.sources_available)}\n\n"
        "<b>Совпадения</b>\n"
        f"{metric('Найдено за все время', stats.matches_total)}\n"
        f"{metric('Сохранено в избранное', stats.favorites_total)}\n"
        f"{metric('Скрыто как шум', stats.hidden_total)}",
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
