from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import compact_values, search_card, source_list
from app.bot.keyboards.inline import search_actions
from app.bot.keyboards.labels import CANCEL, MY_SEARCHES
from app.bot.keyboards.menu import cancel_menu, main_menu
from app.bot.states.edit_search import EditSearch
from app.db.repositories.searches import (
    delete_user_search,
    get_user_search,
    list_user_searches,
    replace_search_keywords,
    replace_search_minus_words,
    replace_search_sources,
    set_search_active,
    update_search_title,
)
from app.db.repositories.users import get_or_create_user
from app.utils.links import split_sources
from app.utils.text import split_terms

router = Router()


async def _send_updated_search(
    message: Message,
    session: AsyncSession,
    *,
    user_id: int,
    search_id: int,
    title: str,
) -> None:
    search = await get_user_search(session, user_id=user_id, search_id=search_id)
    if not search:
        await message.answer("Поиск не найден.", reply_markup=main_menu())
        return

    await message.answer(
        f"<b>{title}</b>\n\n{search_card(search)}",
        reply_markup=search_actions(search.id, search.is_active),
        disable_web_page_preview=True,
    )


@router.message(StateFilter(EditSearch), F.text == CANCEL)
async def cancel_edit_search(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("<b>Редактирование отменено.</b>", reply_markup=main_menu())


@router.message(EditSearch.title)
async def save_search_title(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.from_user:
        return

    title = (message.text or "").strip()
    if len(title) < 2:
        await message.answer(
            "Название слишком короткое. Напишите минимум 2 символа.",
            reply_markup=cancel_menu(),
        )
        return

    data = await state.get_data()
    search_id = data.get("search_id")
    user = await get_or_create_user(session, message.from_user)
    if not isinstance(search_id, int):
        await state.clear()
        await message.answer("Не удалось определить поиск.", reply_markup=main_menu())
        return

    await update_search_title(session, user_id=user.id, search_id=search_id, title=title)
    await state.clear()
    await _send_updated_search(
        message,
        session,
        user_id=user.id,
        search_id=search_id,
        title="Название обновлено",
    )


@router.message(EditSearch.keywords)
async def save_search_keywords(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.from_user:
        return

    keywords = split_terms(message.text or "")
    if not keywords:
        await message.answer("Нужно хотя бы одно ключевое слово.", reply_markup=cancel_menu())
        return

    data = await state.get_data()
    search_id = data.get("search_id")
    user = await get_or_create_user(session, message.from_user)
    if not isinstance(search_id, int):
        await state.clear()
        await message.answer("Не удалось определить поиск.", reply_markup=main_menu())
        return

    await replace_search_keywords(session, user_id=user.id, search_id=search_id, keywords=keywords)
    await state.clear()
    await _send_updated_search(
        message,
        session,
        user_id=user.id,
        search_id=search_id,
        title="Ключевые слова обновлены",
    )


@router.message(EditSearch.minus_words)
async def save_search_minus_words(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.from_user:
        return

    text = (message.text or "").strip()
    minus_words = [] if text.casefold() in {"-", "нет", "очистить"} else split_terms(text)

    data = await state.get_data()
    search_id = data.get("search_id")
    user = await get_or_create_user(session, message.from_user)
    if not isinstance(search_id, int):
        await state.clear()
        await message.answer("Не удалось определить поиск.", reply_markup=main_menu())
        return

    await replace_search_minus_words(
        session,
        user_id=user.id,
        search_id=search_id,
        minus_words=minus_words,
    )
    await state.clear()
    await _send_updated_search(
        message,
        session,
        user_id=user.id,
        search_id=search_id,
        title="Минус-слова обновлены",
    )


@router.message(EditSearch.sources)
async def save_search_sources(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.from_user:
        return

    sources = split_sources(message.text or "")
    if not sources:
        await message.answer(
            "Не вижу источников. Отправьте @username или ссылки t.me, каждую с новой строки.",
            reply_markup=cancel_menu(),
            disable_web_page_preview=True,
        )
        return

    data = await state.get_data()
    search_id = data.get("search_id")
    user = await get_or_create_user(session, message.from_user)
    if not isinstance(search_id, int):
        await state.clear()
        await message.answer("Не удалось определить поиск.", reply_markup=main_menu())
        return

    await replace_search_sources(session, user_id=user.id, search_id=search_id, sources=sources)
    await state.clear()
    await _send_updated_search(
        message,
        session,
        user_id=user.id,
        search_id=search_id,
        title="Источники обновлены",
    )


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
async def handle_search_action(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
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

    if action == "title":
        await state.set_state(EditSearch.title)
        await state.update_data(search_id=search.id)
        if callback.message:
            await callback.message.answer(
                "<b>Новое название поиска</b>\n\n"
                "Отправьте короткое название, например:\n"
                "<blockquote>Комплектовщики Москва</blockquote>",
                reply_markup=cancel_menu(),
            )
        await callback.answer()
        return

    if action == "keywords":
        await state.set_state(EditSearch.keywords)
        await state.update_data(search_id=search.id)
        current = [item.value for item in search.keywords]
        if callback.message:
            await callback.message.answer(
                "<b>Новые ключевые слова</b>\n\n"
                "Отправьте полный новый список. "
                "Каждое слово или фразу лучше писать с новой строки.\n\n"
                f"<b>Сейчас:</b>\n<blockquote>{compact_values(current)}</blockquote>",
                reply_markup=cancel_menu(),
            )
        await callback.answer()
        return

    if action == "minus":
        await state.set_state(EditSearch.minus_words)
        await state.update_data(search_id=search.id)
        current = [item.value for item in search.minus_words]
        if callback.message:
            await callback.message.answer(
                "<b>Новые минус-слова</b>\n\n"
                "Отправьте полный новый список. "
                "Чтобы очистить минус-слова, отправьте один символ: <code>-</code>.\n\n"
                f"<b>Сейчас:</b>\n<blockquote>{compact_values(current)}</blockquote>",
                reply_markup=cancel_menu(),
            )
        await callback.answer()
        return

    if action == "replace_sources":
        await state.set_state(EditSearch.sources)
        await state.update_data(search_id=search.id)
        current = [link.source.input_ref for link in search.sources]
        if callback.message:
            await callback.message.answer(
                "<b>Новые источники</b>\n\n"
                "Отправьте полный новый список каналов или групп, "
                "каждый источник с новой строки.\n\n"
                f"<b>Сейчас:</b>\n<blockquote>{compact_values(current)}</blockquote>",
                reply_markup=cancel_menu(),
                disable_web_page_preview=True,
            )
        await callback.answer()
        return

    if action == "delete":
        deleted = await delete_user_search(session, user_id=user.id, search_id=search_id)
        if callback.message and deleted:
            await callback.message.edit_text("<b>Поиск удален.</b>")
        await callback.answer("Удалено." if deleted else "Не найдено.")
