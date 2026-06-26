from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import search_card, source_list
from app.bot.keyboards.inline import search_actions
from app.bot.keyboards.labels import MY_SEARCHES
from app.bot.keyboards.menu import main_menu
from app.db.repositories.searches import (
    delete_user_search,
    get_user_search,
    list_user_searches,
    set_search_active,
)
from app.db.repositories.users import get_or_create_user

router = Router()


@router.message(F.text == MY_SEARCHES)
async def my_searches(message: Message, session: AsyncSession) -> None:
    if not message.from_user:
        return

    user = await get_or_create_user(session, message.from_user)
    searches = await list_user_searches(session, user.id)
    if not searches:
        await message.answer(
            "<b>Поисков пока нет.</b>\n\n"
            "Нажмите <b>Новый поиск</b>, чтобы создать первый мониторинг.",
            reply_markup=main_menu(),
        )
        return

    await message.answer(
        "<b>Мои поиски</b>\n\n"
        "Ниже показаны последние поиски. Можно включить, выключить, посмотреть источники или удалить.",
        reply_markup=main_menu(),
    )

    for index, search in enumerate(searches[:10], start=1):
        await message.answer(
            search_card(search, index=index),
            reply_markup=search_actions(search.id, search.is_active),
        )


def _search_callback(callback_data: str | None) -> tuple[str, int] | None:
    if not callback_data:
        return None
    parts = callback_data.split(":")
    if len(parts) != 3 or parts[0] != "search" or not parts[2].isdigit():
        return None
    return parts[1], int(parts[2])


@router.callback_query(F.data.startswith("search:"))
async def handle_search_action(callback: CallbackQuery, session: AsyncSession) -> None:
    if not callback.from_user:
        return

    parsed = _search_callback(callback.data)
    if not parsed:
        await callback.answer("Не удалось обработать действие.")
        return

    action, search_id = parsed
    user = await get_or_create_user(session, callback.from_user)
    search = await get_user_search(session, user_id=user.id, search_id=search_id)
    if not search:
        await callback.answer("Поиск не найден.")
        return

    if action in {"on", "off"}:
        is_active = action == "on"
        await set_search_active(session, user_id=user.id, search_id=search_id, is_active=is_active)
        search.is_active = is_active
        if callback.message:
            await callback.message.edit_text(
                search_card(search),
                reply_markup=search_actions(search.id, search.is_active),
            )
        await callback.answer("Поиск включен." if is_active else "Поиск выключен.")
        return

    if action == "sources":
        if callback.message:
            await callback.message.answer(source_list(search), reply_markup=main_menu())
        await callback.answer()
        return

    if action == "delete":
        deleted = await delete_user_search(session, user_id=user.id, search_id=search_id)
        if callback.message and deleted:
            await callback.message.edit_text("<b>Поиск удален.</b>")
        await callback.answer("Удалено." if deleted else "Не найдено.")
