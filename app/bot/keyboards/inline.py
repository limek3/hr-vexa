from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def search_actions(search_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_text = "Пауза" if is_active else "Запустить"
    toggle_action = "off" if is_active else "on"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=toggle_text,
                    callback_data=f"search:{toggle_action}:{search_id}",
                ),
                InlineKeyboardButton(text="Источники", callback_data=f"search:sources:{search_id}"),
            ],
            [InlineKeyboardButton(text="Удалить поиск", callback_data=f"search:delete:{search_id}")],
        ],
    )
