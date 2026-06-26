from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

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
