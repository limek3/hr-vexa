from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.labels import MY_SEARCHES
from app.bot.keyboards.menu import main_menu
from app.db.repositories.searches import list_user_searches
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

    lines = ["<b>Мои поиски</b>\n"]
    for index, search in enumerate(searches, start=1):
        active_sources = [link for link in search.sources if link.is_active]
        status = "включен" if search.is_active else "выключен"
        lines.append(
            f"<b>{index}. {search.title}</b>\n"
            f"Статус: {status}\n"
            f"Ключевых слов: {len(search.keywords)}\n"
            f"Источников: {len(active_sources)}\n",
        )

    await message.answer("\n".join(lines), reply_markup=main_menu())
