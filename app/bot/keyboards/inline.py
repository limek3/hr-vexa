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
            [
                InlineKeyboardButton(text="Редактировать", callback_data=f"search:edit:{search_id}"),
                InlineKeyboardButton(text="Удалить", callback_data=f"search:delete:{search_id}"),
            ],
        ],
    )


def search_edit_actions(search_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Название", callback_data=f"search:title:{search_id}"),
                InlineKeyboardButton(text="Ключевые слова", callback_data=f"search:keywords:{search_id}"),
            ],
            [
                InlineKeyboardButton(text="Минус-слова", callback_data=f"search:minus:{search_id}"),
                InlineKeyboardButton(text="Источники", callback_data=f"search:replace_sources:{search_id}"),
            ],
            [InlineKeyboardButton(text="Назад", callback_data=f"search:back:{search_id}")],
        ],
    )


def search_back(search_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data=f"search:back:{search_id}")]],
    )


def edit_cancel(search_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Отменить", callback_data=f"search:cancel:{search_id}")]],
    )


def quiet_hours_actions(enabled: bool) -> InlineKeyboardMarkup:
    text = "Выключить" if enabled else "Включить"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data="settings:quiet:toggle")],
        ],
    )
