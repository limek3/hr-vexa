from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.models import Search, User


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
        status = "вкл" if search.is_active else "выкл"
        style = "success" if search.is_active else "danger"
        title = search.title.strip()
        if len(title) > 28:
            title = f"{title[:25]}..."
        rows.append(
            [
                button(
                    text=f"{index}. {title} · {status}",
                    style=style,
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


def search_sources_actions(search_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(
                    text="Проверить источники заново",
                    callback_data=f"search:check_sources:{search_id}",
                ),
            ],
            [button(text="Назад", callback_data=f"search:back:{search_id}")],
        ],
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


# --- Admin panel -----------------------------------------------------------
# These keyboards are only ever sent to chats whose telegram_user_id is in
# ADMIN_TELEGRAM_IDS (enforced in app/bot/handlers/admin.py), so the
# callback_data namespace below ("admin:...") is never exposed to regular
# users.

def admin_panel_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [button(text="Рассылка пользователям", callback_data="admin:broadcast")],
            [button(text="Общая статистика", callback_data="admin:stats")],
            [button(text="Здоровье системы", callback_data="admin:health")],
            [button(text="Заблокировавшие бота", callback_data="admin:blocked_list")],
            [button(text="Выгрузка Excel", callback_data="admin:export_users")],
            [button(text="Обновить", callback_data="admin:panel")],
        ],
    )


def admin_back_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[button(text="Назад", callback_data="admin:panel")]],
    )


def admin_blocked_list_actions(users: list[User]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for user in users:
        label = (
            f"@{user.username}"
            if user.username
            else (user.first_name or str(user.telegram_user_id))
        )
        if len(label) > 28:
            label = f"{label[:25]}..."
        rows.append(
            [
                button(
                    text=f"Разблокировать {label}",
                    style="success",
                    callback_data=f"admin:unblock:{user.telegram_user_id}",
                ),
            ],
        )
    rows.append([button(text="Назад", callback_data="admin:panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_broadcast_cancel_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [button(text="Отменить", style="danger", callback_data="admin:broadcast_cancel")],
        ],
    )


def admin_broadcast_preview_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button(
                    text="Отправить всем",
                    style="success",
                    callback_data="admin:broadcast_confirm",
                ),
            ],
            [button(text="Отменить", style="danger", callback_data="admin:broadcast_cancel")],
        ],
    )

