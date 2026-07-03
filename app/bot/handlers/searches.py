from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import compact_values, heading, metric, search_card, search_edit_card, source_list
from app.bot.keyboards.inline import edit_cancel, search_actions, search_back, search_edit_actions, searches_list_actions
from app.bot.keyboards.labels import CANCEL, MY_SEARCHES
from app.bot.keyboards.menu import main_menu
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
from app.services.policy import find_forbidden_terms, forbidden_terms_message
from app.utils.links import split_sources
from app.utils.text import split_terms

router = Router()


def _searches_list_text(count: int) -> str:
    return (
        f"{heading('Мои поиски')}\n"
        "\n"
        "Ниже последние поиски.\n"
        "Нажмите на нужный поиск, чтобы открыть настройки, источники и управление.\n\n"
        f"{metric('Всего поисков', count)}\n"
        "<i>Показываю:</i> <i>до</i> <b>10</b>"
    )


async def _delete_user_input(message: Message) -> None:
    try:
        await message.delete()
    except TelegramBadRequest:
        pass


async def _edit_saved_card(
    message: Message,
    state_data: dict[str, object],
    session: AsyncSession,
    *,
    user_id: int,
    search_id: int,
) -> None:
    search = await get_user_search(session, user_id=user_id, search_id=search_id)
    if not search:
        await message.answer("Поиск не найден.", reply_markup=main_menu())
        return

    editor_chat_id = state_data.get("editor_chat_id")
    editor_message_id = state_data.get("editor_message_id")
    if isinstance(editor_chat_id, int) and isinstance(editor_message_id, int):
        try:
            await message.bot.edit_message_text(
                chat_id=editor_chat_id,
                message_id=editor_message_id,
                text=search_card(search),
                reply_markup=search_actions(search.id, search.is_active),
                disable_web_page_preview=True,
            )
            return
        except TelegramBadRequest:
            pass

    await message.answer(
        search_card(search),
        reply_markup=search_actions(search.id, search.is_active),
        disable_web_page_preview=True,
    )


async def _edit_prompt_message(
    message: Message,
    state_data: dict[str, object],
    *,
    text: str,
    search_id: int,
) -> None:
    editor_chat_id = state_data.get("editor_chat_id")
    editor_message_id = state_data.get("editor_message_id")
    if isinstance(editor_chat_id, int) and isinstance(editor_message_id, int):
        try:
            await message.bot.edit_message_text(
                chat_id=editor_chat_id,
                message_id=editor_message_id,
                text=text,
                reply_markup=edit_cancel(search_id),
                disable_web_page_preview=True,
            )
            return
        except TelegramBadRequest:
            pass

    await message.answer(text, reply_markup=edit_cancel(search_id), disable_web_page_preview=True)


@router.message(StateFilter(EditSearch), F.text == CANCEL)
async def cancel_edit_search(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    await state.clear()
    await _delete_user_input(message)
    search_id = data.get("search_id")
    if isinstance(search_id, int) and message.from_user:
        user = await get_or_create_user(session, message.from_user)
        await _edit_saved_card(message, data, session, user_id=user.id, search_id=search_id)
        return
    await message.answer(
        f"{heading('Редактирование отменено')}\n"
        "",
        reply_markup=main_menu(),
    )


@router.message(EditSearch.title)
async def save_search_title(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.from_user:
        return

    data = await state.get_data()
    search_id = data.get("search_id")
    title = (message.text or "").strip()
    if len(title) < 2:
        await _delete_user_input(message)
        if isinstance(search_id, int):
            await _edit_prompt_message(
                message,
                data,
                text=(
                    f"{heading('Новое название поиска')}\n"
                    "\n"
                    "Название слишком короткое. Напишите минимум 2 символа."
                ),
                search_id=search_id,
            )
        return

    user = await get_or_create_user(session, message.from_user)
    if not isinstance(search_id, int):
        await state.clear()
        await message.answer("Не удалось определить поиск.", reply_markup=main_menu())
        return

    await update_search_title(session, user_id=user.id, search_id=search_id, title=title)
    await state.clear()
    await _delete_user_input(message)
    await _edit_saved_card(message, data, session, user_id=user.id, search_id=search_id)


@router.message(EditSearch.keywords)
async def save_search_keywords(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.from_user:
        return

    data = await state.get_data()
    search_id = data.get("search_id")
    keywords = split_terms(message.text or "")
    if not keywords:
        await _delete_user_input(message)
        if isinstance(search_id, int):
            await _edit_prompt_message(
                message,
                data,
                text=(
                    f"{heading('Новые ключевые слова')}\n"
                    "\n"
                    "Нужно хотя бы одно ключевое слово. Отправьте список заново."
                ),
                search_id=search_id,
            )
        return
    forbidden = find_forbidden_terms(keywords)
    if forbidden:
        await _delete_user_input(message)
        if isinstance(search_id, int):
            await _edit_prompt_message(
                message,
                data,
                text=forbidden_terms_message(forbidden),
                search_id=search_id,
            )
        return

    user = await get_or_create_user(session, message.from_user)
    if not isinstance(search_id, int):
        await state.clear()
        await message.answer("Не удалось определить поиск.", reply_markup=main_menu())
        return

    await replace_search_keywords(session, user_id=user.id, search_id=search_id, keywords=keywords)
    await state.clear()
    await _delete_user_input(message)
    await _edit_saved_card(message, data, session, user_id=user.id, search_id=search_id)


@router.message(EditSearch.minus_words)
async def save_search_minus_words(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    if not message.from_user:
        return

    data = await state.get_data()
    search_id = data.get("search_id")
    text = (message.text or "").strip()
    minus_words = [] if text.casefold() in {"-", "нет", "очистить"} else split_terms(text)

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
    await _delete_user_input(message)
    await _edit_saved_card(message, data, session, user_id=user.id, search_id=search_id)


@router.message(EditSearch.sources)
async def save_search_sources(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.from_user:
        return

    data = await state.get_data()
    search_id = data.get("search_id")
    sources = split_sources(message.text or "")
    if not sources:
        await _delete_user_input(message)
        if isinstance(search_id, int):
            await _edit_prompt_message(
                message,
                data,
                text=(
                    f"{heading('Новые источники')}\n"
                    "\n"
                    "Не вижу источников. Отправьте @username или ссылки t.me, "
                    "каждую с новой строки."
                ),
                search_id=search_id,
            )
        return

    user = await get_or_create_user(session, message.from_user)
    if not isinstance(search_id, int):
        await state.clear()
        await message.answer("Не удалось определить поиск.", reply_markup=main_menu())
        return

    await replace_search_sources(session, user_id=user.id, search_id=search_id, sources=sources)
    await state.clear()
    await _delete_user_input(message)
    await _edit_saved_card(message, data, session, user_id=user.id, search_id=search_id)


@router.message(F.text == MY_SEARCHES)
async def my_searches(message: Message, session: AsyncSession) -> None:
    if not message.from_user:
        return

    user = await get_or_create_user(session, message.from_user)
    searches = await list_user_searches(session, user.id)
    if not searches:
        await message.answer(
            f"{heading('Поисков пока нет')}\n"
            "\n"
            "Нажмите <b>Новый поиск</b>, чтобы создать первый мониторинг.",
            reply_markup=main_menu(),
        )
        return

    await message.answer(
        _searches_list_text(len(searches)),
        reply_markup=searches_list_actions(searches),
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

    if action == "open":
        if callback.message:
            await callback.message.edit_text(
                search_card(search),
                reply_markup=search_actions(search.id, search.is_active),
                disable_web_page_preview=True,
            )
        await callback.answer()
        return

    if action == "list":
        searches = await list_user_searches(session, user.id)
        if callback.message:
            await callback.message.edit_text(
                _searches_list_text(len(searches)),
                reply_markup=searches_list_actions(searches),
                disable_web_page_preview=True,
            )
        await callback.answer()
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
            await callback.message.edit_text(
                source_list(search),
                reply_markup=search_back(search.id),
                disable_web_page_preview=True,
            )
        await callback.answer()
        return

    if action == "edit":
        if callback.message:
            await callback.message.edit_text(
                search_edit_card(search),
                reply_markup=search_edit_actions(search.id),
                disable_web_page_preview=True,
            )
        await callback.answer()
        return

    if action == "back":
        await state.clear()
        if callback.message:
            await callback.message.edit_text(
                search_card(search),
                reply_markup=search_actions(search.id, search.is_active),
                disable_web_page_preview=True,
            )
        await callback.answer()
        return

    if action == "cancel":
        await state.clear()
        if callback.message:
            await callback.message.edit_text(
                search_card(search),
                reply_markup=search_actions(search.id, search.is_active),
                disable_web_page_preview=True,
            )
        await callback.answer("Редактирование отменено.")
        return

    if action == "title":
        await state.set_state(EditSearch.title)
        if callback.message:
            await state.update_data(
                search_id=search.id,
                editor_chat_id=callback.message.chat.id,
                editor_message_id=callback.message.message_id,
            )
            await callback.message.edit_text(
                f"{search_card(search)}\n\n"
                f"{heading('Новое название поиска')}\n"
                "<blockquote>Например: Аренда Москва</blockquote>",
                reply_markup=edit_cancel(search.id),
                disable_web_page_preview=True,
            )
        await callback.answer()
        return

    if action == "keywords":
        await state.set_state(EditSearch.keywords)
        current = [item.value for item in search.keywords]
        if callback.message:
            await state.update_data(
                search_id=search.id,
                editor_chat_id=callback.message.chat.id,
                editor_message_id=callback.message.message_id,
            )
            await callback.message.edit_text(
                f"{search_card(search)}\n\n"
                f"{heading('Новые ключевые слова')}\n"
                "Отправьте полный новый список. "
                "Каждое слово или фразу лучше писать с новой строки.\n\n"
                "<b>Сейчас</b>\n"
                f"<i>{compact_values(current)}</i>",
                reply_markup=edit_cancel(search.id),
                disable_web_page_preview=True,
            )
        await callback.answer()
        return

    if action == "minus":
        await state.set_state(EditSearch.minus_words)
        current = [item.value for item in search.minus_words]
        if callback.message:
            await state.update_data(
                search_id=search.id,
                editor_chat_id=callback.message.chat.id,
                editor_message_id=callback.message.message_id,
            )
            await callback.message.edit_text(
                f"{search_card(search)}\n\n"
                f"{heading('Новые минус-слова')}\n"
                "Отправьте полный новый список. "
                "Чтобы очистить минус-слова, отправьте один символ: <code>-</code>.\n\n"
                "<b>Сейчас</b>\n"
                f"<i>{compact_values(current)}</i>",
                reply_markup=edit_cancel(search.id),
                disable_web_page_preview=True,
            )
        await callback.answer()
        return

    if action == "replace_sources":
        await state.set_state(EditSearch.sources)
        current = [link.source.input_ref for link in search.sources]
        if callback.message:
            await state.update_data(
                search_id=search.id,
                editor_chat_id=callback.message.chat.id,
                editor_message_id=callback.message.message_id,
            )
            await callback.message.edit_text(
                f"{search_card(search)}\n\n"
                f"{heading('Новые источники')}\n"
                "Отправьте полный новый список каналов или групп, "
                "каждый источник с новой строки.\n\n"
                "<b>Сейчас</b>\n"
                f"<i>{compact_values(current)}</i>",
                reply_markup=edit_cancel(search.id),
                disable_web_page_preview=True,
            )
        await callback.answer()
        return

    if action == "delete":
        deleted = await delete_user_search(session, user_id=user.id, search_id=search_id)
        if callback.message and deleted:
            searches = await list_user_searches(session, user.id)
            if searches:
                await callback.message.edit_text(
                    f"{heading('Поиск удален')}\n"
                    "\n"
                    "Ниже обновленный список.",
                    reply_markup=searches_list_actions(searches),
                    disable_web_page_preview=True,
                )
            else:
                await callback.message.edit_text(
                    f"{heading('Поиск удален')}\n"
                    "\n"
                    "Поисков больше нет. Чтобы создать новый, нажмите <b>Новый поиск</b> в меню.",
                    disable_web_page_preview=True,
                )
        await callback.answer("Удалено." if deleted else "Не найдено.")
