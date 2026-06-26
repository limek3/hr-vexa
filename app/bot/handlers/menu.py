from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.keyboards.labels import FAVORITES, HELP
from app.bot.keyboards.menu import main_menu
from app.bot.messages import FAVORITES_EMPTY_TEXT, HELP_TEXT

router = Router()


@router.message(Command("help"))
@router.message(lambda message: message.text == HELP)
async def help_message(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu())


@router.message(lambda message: message.text == FAVORITES)
async def favorites_placeholder(message: Message) -> None:
    await message.answer(FAVORITES_EMPTY_TEXT, reply_markup=main_menu())


@router.message()
async def fallback(message: Message) -> None:
    await message.answer(
        "Я не распознал команду.\n\n"
        "Выберите действие в меню или нажмите <b>Помощь</b>.",
        reply_markup=main_menu(),
    )
