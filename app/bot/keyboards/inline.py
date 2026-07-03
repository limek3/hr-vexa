from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.models import Search


def button(text: str, *, style: str = "primary", **kwargs: object) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, style=style, **kwargs)


def search_actions(search_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_text = "Выключить" if is_active else "Включить"
    toggle_action = "off" if is_active else "on"
    toggle_style = "danger" if is_active else "success"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [button(text="К списку поисков", callback_data=f"search:list:{search_id}")],
            [
                button(
                    text=toggle_text,
                    style=toggle_style,
                    callback_data=f"search:{toggle_action}:{search_id}",
                ),
                button(text="Источники", callback_data=f"search:sources:{search_id}"),
            ],
            [
                button(text="Настроить", callback_data=f"search:edit:{search_id}"),
                button(
                    text="Удалить",
                    style="danger",
                    callback_data=f"search:delete:{search_id}",
                ),
            ],
        ],
    )


def searches_list_actions(searches: list[Search]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, search in enumerate(searches[:10], start=1):
        status = "вкл" if search.is_active else "пауза"
        title = search.title.strip()
        if len(title) > 28:
            title = f"{title[:25]}..."
        rows.append(
            [
                button(
                    text=f"{index}. {title} · {status}",
                    callback_data=f"search:open:{search.id}",
                ),
            ],
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def search_edit_actions(search_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(text="Название", callback_data=f"search:title:{search_id}"),
                button(text="Ключевые слова", callback_data=f"search:keywords:{search_id}"),
            ],
            [
                button(text="Минус-слова", callback_data=f"search:minus:{search_id}"),
                button(text="Источники", callback_data=f"search:replace_sources:{search_id}"),
            ],
            [button(text="Назад", callback_data=f"search:back:{search_id}")],
        ],
    )


def search_back(search_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[button(text="Назад", callback_data=f"search:back:{search_id}")]],
    )


def edit_cancel(search_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [button(text="Отменить", style="danger", callback_data=f"search:cancel:{search_id}")],
        ],
    )


def quiet_hours_actions(enabled: bool) -> InlineKeyboardMarkup:
    text = "Выключить" if enabled else "Включить"
    style = "danger" if enabled else "success"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [button(text=text, style=style, callback_data="settings:quiet:toggle")],
        ],
    )
