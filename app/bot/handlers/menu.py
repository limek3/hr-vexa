import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.labels import EXPORT_CONTACTS, HELP
from app.bot.keyboards.menu import main_menu
from app.bot.messages import HELP_TEXT
from app.db.repositories.users import get_or_create_user
from app.services.google_sheets import (
    GoogleSheetsNotConfiguredError,
    export_contacts_to_google_sheets,
)

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("help"))
@router.message(lambda message: message.text == HELP)
async def help_message(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu())


@router.message(lambda message: message.text == EXPORT_CONTACTS)
async def export_contacts(message: Message, session: AsyncSession) -> None:
    if not message.from_user:
        return

    user = await get_or_create_user(session, message.from_user)
    try:
        count, url = await export_contacts_to_google_sheets(session, user_id=user.id)
    except GoogleSheetsNotConfiguredError:
        await message.answer(
            "<b>Google Sheets не подключен.</b>\n\n"
            "Добавьте в Railway Variables:\n"
            "<blockquote>GOOGLE_SERVICE_ACCOUNT_JSON\nGOOGLE_SHEET_ID</blockquote>\n"
            "После этого кнопка будет выгружать найденные контакты в таблицу.",
            reply_markup=main_menu(),
            disable_web_page_preview=True,
        )
        return
    except Exception:
        logger.exception("Google Sheets export failed")
        await message.answer(
            "<b>Экспорт не выполнен.</b>\n\n"
            "Проверьте, что Google Sheet расшарен на email service account "
            "и что переменные GOOGLE_SERVICE_ACCOUNT_JSON / GOOGLE_SHEET_ID заполнены верно.",
            reply_markup=main_menu(),
            disable_web_page_preview=True,
        )
        return

    await message.answer(
        "<b>Экспорт готов.</b>\n\n"
        f"Строк выгружено: <b>{count}</b>\n"
        f"<blockquote>{url}</blockquote>",
        reply_markup=main_menu(),
        disable_web_page_preview=True,
    )


@router.message()
async def fallback(message: Message) -> None:
    await message.answer(
        "Я не распознал команду.\n\n"
        "Выберите действие в меню или нажмите <b>Помощь</b>.",
        reply_markup=main_menu(),
    )
