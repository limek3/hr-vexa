from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.bot.keyboards.labels import CANCEL, HELP, MY_SEARCHES, NEW_SEARCH, QUIET_HOURS, SKIP, STATISTICS


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=STATISTICS)],
            [KeyboardButton(text=NEW_SEARCH), KeyboardButton(text=MY_SEARCHES)],
            [KeyboardButton(text=QUIET_HOURS), KeyboardButton(text=HELP)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Vexa: выберите действие",
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
