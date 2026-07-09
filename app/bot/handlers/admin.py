import logging
from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import heading, metric
from app.bot.keyboards.inline import (
    admin_back_actions,
    admin_blocked_list_actions,
    admin_panel_actions,
)
from app.core.config import get_settings
from app.db.models import User
from app.db.repositories.stats import (
    get_global_stats,
    list_admin_match_export_details,
    list_admin_search_export_details,
    list_admin_user_search_report,
)
from app.db.repositories.users import (
    count_blocked_users,
    get_user_by_telegram_id,
    list_blocked_users,
)
from app.services.admin_export import build_admin_users_workbook

logger = logging.getLogger(__name__)

router = Router()

BLOCKED_LIST_LIMIT = 10


def _is_admin(telegram_user_id: int | None) -> bool:
    if telegram_user_id is None:
        return False
    admin_ids = get_settings().admin_ids
    return bool(admin_ids) and telegram_user_id in admin_ids


def _panel_text() -> str:
    return f"{heading('Админ-панель')}\n\nВыберите раздел."


def _user_label(user: User) -> str:
    if user.username:
        return f"@{user.username}"
    return user.first_name or str(user.telegram_user_id)


def _users_export_caption(rows) -> str:
    user_ids = {row.user_id for row in rows}
    search_ids = {row.search_id for row in rows if row.search_id is not None}
    blocked_count = len({row.user_id for row in rows if row.user_is_blocked})
    active_searches = len(
        {row.search_id for row in rows if row.search_id is not None and row.search_is_active},
    )
    matches_total = sum(row.search_matches_total for row in rows if row.search_id is not None)
    return (
        f"{heading('Выгрузка пользователей')}\n\n"
        f"{metric('Пользователей', len(user_ids))}\n"
        f"{metric('Заблокировали бота', blocked_count)}\n"
        f"{metric('Поисков всего', len(search_ids))}\n"
        f"{metric('Поисков включено', active_searches)}\n"
        f"{metric('Совпадений всего', matches_total)}\n\n"
        "Файл Excel содержит листы: Сводка, Пользователи, "
        "Поиски, Источники, Совпадения, Сообщения, Ключи."
    )


async def _render_blocked_list(session: AsyncSession) -> tuple[str, list[User]]:
    total = await count_blocked_users(session)
    users = await list_blocked_users(session, limit=BLOCKED_LIST_LIMIT)

    if not users:
        return f"{heading('Заблокировавшие бота')}\n\nТаких пользователей нет.", users

    lines = [heading("Заблокировавшие бота"), "", metric("Всего", total), ""]
    lines.extend(f"- {_user_label(user)} (id {user.telegram_user_id})" for user in users)
    if total > len(users):
        lines.append(f"...и еще {total - len(users)}")
    lines.append("")
    lines.append("Нажмите, чтобы разблокировать вручную:")
    return "\n".join(lines), users


# --- /admin panel (buttons) -------------------------------------------------


@router.message(Command("admin"))
async def admin_panel(message: Message) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return
    await message.answer(_panel_text(), reply_markup=admin_panel_actions())


@router.callback_query(F.data == "admin:panel")
async def admin_panel_callback(callback: CallbackQuery) -> None:
    if not callback.from_user or not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    if callback.message:
        await callback.message.edit_text(_panel_text(), reply_markup=admin_panel_actions())
    await callback.answer()


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery, session: AsyncSession) -> None:
    if not callback.from_user or not _is_admin(callback.from_user.id):
        await callback.answer()
        return

    stats = await get_global_stats(session)
    text = (
        f"{heading('Общая статистика')}\n\n"
        f"{metric('Пользователей всего', stats.users_total)}\n"
        f"{metric('Заблокировали бота', stats.users_blocked)}\n\n"
        f"{metric('Поисков всего', stats.searches_total)}\n"
        f"{metric('Поисков включено', stats.searches_active)}\n\n"
        f"{metric('Источников всего', stats.sources_total)}\n\n"
        f"{metric('Совпадений сегодня', stats.matches_today)}\n"
        f"{metric('Совпадений всего', stats.matches_total)}"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=admin_back_actions())
    await callback.answer()


@router.callback_query(F.data == "admin:export_users")
async def admin_export_users(callback: CallbackQuery, session: AsyncSession) -> None:
    if not callback.from_user or not _is_admin(callback.from_user.id):
        await callback.answer()
        return

    await callback.answer("Готовлю выгрузку...")
    rows = await list_admin_user_search_report(session)
    search_rows = await list_admin_search_export_details(session)
    match_rows = await list_admin_match_export_details(session)
    workbook_bytes = build_admin_users_workbook(rows, search_rows, match_rows)
    filename = f"vexa_users_searches_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.xlsx"
    logger.info(
        "Admin exported users/searches report: admin_id=%s rows=%s filename=%s",
        callback.from_user.id,
        len(match_rows),
        filename,
    )

    if callback.message:
        await callback.message.answer_document(
            BufferedInputFile(workbook_bytes, filename=filename),
            caption=_users_export_caption(rows),
            reply_markup=admin_back_actions(),
        )


@router.callback_query(F.data == "admin:blocked_list")
async def admin_blocked_list(callback: CallbackQuery, session: AsyncSession) -> None:
    if not callback.from_user or not _is_admin(callback.from_user.id):
        await callback.answer()
        return

    text, users = await _render_blocked_list(session)
    reply_markup = admin_blocked_list_actions(users) if users else admin_back_actions()
    if callback.message:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:unblock:"))
async def admin_unblock_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    if not callback.from_user or not _is_admin(callback.from_user.id):
        await callback.answer()
        return

    target_token = (callback.data or "").rsplit(":", maxsplit=1)[-1]
    if not target_token.lstrip("-").isdigit():
        await callback.answer("Некорректный id.", show_alert=True)
        return

    target_id = int(target_token)
    user = await get_user_by_telegram_id(session, target_id)
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    was_blocked = user.is_blocked
    user.is_blocked = False
    await session.flush()
    logger.info(
        "Admin manually unblocked user via panel: admin_id=%s user_id=%s telegram_user_id=%s was_blocked=%s",
        callback.from_user.id,
        user.id,
        user.telegram_user_id,
        was_blocked,
    )

    text, users = await _render_blocked_list(session)
    reply_markup = admin_blocked_list_actions(users) if users else admin_back_actions()
    if callback.message:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    await callback.answer(f"Пользователь {target_id} разблокирован.")


# --- Text commands (kept for scripting / quick access without the panel) ---


@router.message(Command("unblock"))
async def unblock_user(message: Message, session: AsyncSession) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return

    parts = (message.text or "").split(maxsplit=1)
    target_token = parts[1].strip() if len(parts) > 1 else ""
    if not target_token.lstrip("-").isdigit():
        await message.answer("Использование: /unblock <telegram_user_id>")
        return

    target_id = int(target_token)
    user = await get_user_by_telegram_id(session, target_id)
    if not user:
        await message.answer(f"Пользователь с telegram_user_id={target_id} не найден.")
        return

    was_blocked = user.is_blocked
    user.is_blocked = False
    await session.flush()
    logger.info(
        "Admin manually unblocked user: admin_id=%s user_id=%s telegram_user_id=%s was_blocked=%s",
        message.from_user.id,
        user.id,
        user.telegram_user_id,
        was_blocked,
    )
    status = "уже был разблокирован" if not was_blocked else "разблокирован"
    await message.answer(f"Готово: пользователь {target_id} {status} (is_blocked=false).")


@router.message(Command("blocked_count"))
async def blocked_count(message: Message, session: AsyncSession) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return

    total = await count_blocked_users(session)
    await message.answer(f"Заблокировавших бота пользователей: {total}")
