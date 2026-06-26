from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.bot.keyboards.labels import CANCEL, EXPORT_CONTACTS, HELP, MY_SEARCHES, NEW_SEARCH, SKIP


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=NEW_SEARCH)],
            [KeyboardButton(text=MY_SEARCHES)],
            [KeyboardButton(text=EXPORT_CONTACTS)],
            [KeyboardButton(text=HELP)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


def skip_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=SKIP)], [KeyboardButton(text=CANCEL)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def cancel_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
