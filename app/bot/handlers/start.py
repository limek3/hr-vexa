from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.menu import main_menu
from app.bot.messages import WELCOME_TEXT
from app.db.repositories.users import get_or_create_user

router = Router()


@router.message(CommandStart())
async def start(message: Message, session: AsyncSession) -> None:
    if not message.from_user:
        return

    await get_or_create_user(session, message.from_user)
    await message.answer(WELCOME_TEXT, reply_markup=main_menu())
