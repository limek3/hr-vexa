from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import html
from app.db.models import Match, Message as DbMessage, Search
from app.db.repositories.favorites import save_favorite_once
from app.db.repositories.messages import hide_match
from app.db.repositories.users import get_or_create_user

router = Router()


def _match_id(callback_data: str | None) -> int | None:
    if not callback_data or ":" not in callback_data:
        return None
    raw_id = callback_data.split(":", maxsplit=1)[1]
    return int(raw_id) if raw_id.isdigit() else None


@router.callback_query(F.data.startswith("favorite:"))
async def save_favorite(callback: CallbackQuery, session: AsyncSession) -> None:
    if not callback.from_user:
        return

    match_id = _match_id(callback.data)
    if match_id is None:
        await callback.answer("Не удалось сохранить.")
        return

    user = await get_or_create_user(session, callback.from_user)
    created = await save_favorite_once(session, match_id=match_id, user_id=user.id)
    await callback.answer("Сохранено в избранное." if created else "Уже сохранено.")


@router.callback_query(F.data.startswith("hide:"))
async def hide_notification(callback: CallbackQuery, session: AsyncSession) -> None:
    if not callback.from_user:
        return

    match_id = _match_id(callback.data)
    if match_id is None:
        await callback.answer("Не удалось скрыть.")
        return

    user = await get_or_create_user(session, callback.from_user)
    hidden = await hide_match(session, match_id=match_id, user_id=user.id)
    if callback.message and hidden:
        await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Скрыто." if hidden else "Не найдено.")


@router.callback_query(F.data.startswith("reply_draft:"))
async def show_reply_draft(callback: CallbackQuery, session: AsyncSession) -> None:
    if not callback.from_user:
        return

    match_id = _match_id(callback.data)
    if match_id is None:
        await callback.answer("Не удалось подготовить текст.")
        return

    user = await get_or_create_user(session, callback.from_user)
    result = await session.execute(
        select(Search, DbMessage)
        .join(Match, Match.search_id == Search.id)
        .join(DbMessage, DbMessage.id == Match.message_id)
        .where(Match.id == match_id, Match.user_id == user.id),
    )
    row = result.one_or_none()
    if not row:
        await callback.answer("Совпадение не найдено.")
        return

    search, _message = row
    draft = (
        f"Здравствуйте! Увидел(а) ваше сообщение по теме «{search.title}». "
        "Подскажите, пожалуйста, вам еще актуально?"
    )

    if callback.message:
        await callback.message.answer(
            "<b>Сообщение для ответа</b>\n\n"
            f"<blockquote>{html(draft)}</blockquote>\n\n"
            "Скопируйте текст и отправьте его адресату.",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    await callback.answer("Текст подготовлен.")
