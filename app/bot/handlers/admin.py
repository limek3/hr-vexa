import logging
from datetime import UTC, datetime
from urllib.parse import urlparse

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import heading, html, metric
from app.bot.keyboards.inline import (
    admin_back_actions,
    admin_blocked_list_actions,
    admin_broadcast_cancel_actions,
    admin_broadcast_preview_actions,
    admin_panel_actions,
)
from app.bot.states.admin import AdminBroadcast
from app.core.config import get_settings
from app.db.models import User
from app.db.repositories.stats import (
    get_admin_health_stats,
    get_global_stats,
    list_admin_match_export_details,
    list_admin_search_export_details,
    list_admin_user_search_report,
    list_recent_delivery_issues,
)
from app.db.repositories.users import (
    count_blocked_users,
    get_user_by_telegram_id,
    list_blocked_users,
)
from app.services.admin_broadcast import (
    build_broadcast_keyboard,
    is_broadcast_running,
    start_broadcast,
)
from app.services.admin_export import build_admin_users_workbook

logger = logging.getLogger(__name__)
router = Router()

BLOCKED_LIST_LIMIT = 10
MAX_BROADCAST_TEXT_LENGTH = 3900


def _valid_button_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https", "tg"} and bool(
        parsed.netloc or parsed.scheme == "tg",
    )


def _short_error(value: str, *, limit: int = 120) -> str:
    compact = " ".join(value.split())
    return f"{compact[: limit - 3]}..." if len(compact) > limit else compact


def _is_admin(telegram_user_id: int | None) -> bool:
    if telegram_user_id is None:
        return False
    admin_ids = get_settings().admin_ids
    return bool(admin_ids) and telegram_user_id in admin_ids


def _panel_text() -> str:
    broadcast_status = "выполняется" if is_broadcast_running() else "свободна"
    return (
        f"{heading('Админ-панель')}\n\n"
        "Выберите раздел.\n\n"
        f"{metric('Рассылка', broadcast_status)}"
    )


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
    lines.extend(
        f"- {html(_user_label(user))} (id {user.telegram_user_id})" for user in users
    )
    if total > len(users):
        lines.append(f"...и еще {total - len(users)}")
    lines.extend(["", "Нажмите, чтобы разблокировать вручную:"])
    return "\n".join(lines), users


@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer(_panel_text(), reply_markup=admin_panel_actions())


@router.callback_query(F.data == "admin:panel")
async def admin_panel_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.from_user or not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
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


@router.callback_query(F.data == "admin:health")
async def admin_health(callback: CallbackQuery, session: AsyncSession) -> None:
    if not callback.from_user or not _is_admin(callback.from_user.id):
        await callback.answer()
        return

    health = await get_admin_health_stats(session)
    issues = await list_recent_delivery_issues(session)
    source_labels = {
        "available": "доступны",
        "pending": "проверяются",
        "queued": "в очереди",
        "joining": "подключаются",
        "unavailable": "нет доступа",
        "not_found": "не найдены",
        "invite_expired": "ссылка истекла",
        "join_limited": "лимит Telegram",
        "join_request_sent": "ждут одобрения",
    }
    delivery_labels = {
        "pending": "ожидают отправки",
        "sent": "доставлены",
        "filtered": "отфильтрованы",
        "failed": "ошибки",
        "blocked": "бот заблокирован",
    }

    lines = [heading("Здоровье системы"), "", "<b>Источники</b>"]
    if health.sources_by_status:
        for status, count in sorted(health.sources_by_status.items()):
            lines.append(metric(source_labels.get(status, status), count))
    else:
        lines.append("Источников нет.")

    lines.extend(["", "<b>Уведомления</b>"])
    if health.deliveries_by_status:
        for status, count in sorted(health.deliveries_by_status.items()):
            lines.append(metric(delivery_labels.get(status, status), count))
    else:
        lines.append("Уведомлений пока нет.")

    lines.extend(["", "<b>Последние проблемы доставки</b>"])
    if not issues:
        lines.append("Ошибок доставки нет.")
    else:
        for issue in issues:
            user_label = f"@{issue.username}" if issue.username else str(issue.telegram_user_id)
            lines.append(
                f"• <b>{html(user_label)}</b> · {html(issue.search_title)} · "
                f"{html(issue.status)}\n"
                f"  {html(_short_error(issue.error or 'без описания'))}"
            )

    if callback.message:
        await callback.message.edit_text("\n".join(lines), reply_markup=admin_back_actions())
    await callback.answer()


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.from_user or not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    if is_broadcast_running():
        await callback.answer("Рассылка уже выполняется.", show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminBroadcast.message)
    if callback.message:
        await callback.message.edit_text(
            f"{heading('Новая рассылка')}\n\n"
            "Отправьте текст сообщения. Можно использовать форматирование Telegram: "
            "жирный текст, курсив, цитаты и ссылки.\n\n"
            f"Максимальная длина: <b>{MAX_BROADCAST_TEXT_LENGTH}</b> символов.",
            reply_markup=admin_broadcast_cancel_actions(),
        )
    await callback.answer()


@router.message(AdminBroadcast.message)
async def admin_broadcast_receive_message(message: Message, state: FSMContext) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return
    if not message.text:
        await message.answer("Для рассылки отправьте текстовое сообщение.")
        return
    if len(message.text) > MAX_BROADCAST_TEXT_LENGTH:
        await message.answer(
            f"Сообщение слишком длинное: {len(message.text)} символов. "
            f"Максимум — {MAX_BROADCAST_TEXT_LENGTH}.",
        )
        return

    await state.update_data(
        broadcast_html=message.html_text,
        broadcast_plain=message.text,
    )
    await state.set_state(AdminBroadcast.button)
    await message.answer(
        f"{heading('Кнопка под сообщением')}\n\n"
        "Отправьте кнопку в формате:\n"
        "<code>Текст кнопки | https://example.com</code>\n\n"
        "Если кнопка не нужна, отправьте <code>-</code>.",
        reply_markup=admin_broadcast_cancel_actions(),
    )


@router.message(AdminBroadcast.button)
async def admin_broadcast_receive_button(message: Message, state: FSMContext) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    button_text: str | None = None
    button_url: str | None = None

    if raw != "-":
        if "|" not in raw:
            await message.answer(
                "Некорректный формат. Используйте:\n"
                "<code>Текст кнопки | https://example.com</code>\n"
                "Или отправьте <code>-</code>.",
            )
            return
        button_text, button_url = (part.strip() for part in raw.split("|", maxsplit=1))
        if not button_text or len(button_text) > 64 or not _valid_button_url(button_url):
            await message.answer(
                "Проверьте текст и ссылку. Ссылка должна начинаться с http://, https:// "
                "или tg://, а текст кнопки должен быть короче 65 символов.",
            )
            return

    await state.update_data(button_text=button_text, button_url=button_url)
    await state.set_state(AdminBroadcast.preview)
    data = await state.get_data()
    preview_markup = build_broadcast_keyboard(button_text, button_url)

    await message.answer(heading("Предпросмотр рассылки"))
    await message.answer(
        data["broadcast_html"],
        parse_mode=ParseMode.HTML,
        reply_markup=preview_markup,
        disable_web_page_preview=True,
    )
    await message.answer(
        "Проверьте сообщение. После подтверждения оно будет отправлено всем пользователям, "
        "которые не заблокировали бота.",
        reply_markup=admin_broadcast_preview_actions(),
    )


@router.callback_query(AdminBroadcast.preview, F.data == "admin:broadcast_confirm")
async def admin_broadcast_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if not callback.from_user or not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    if not callback.message:
        await callback.answer("Не удалось запустить рассылку.", show_alert=True)
        return

    data = await state.get_data()
    html_text = data.get("broadcast_html")
    if not html_text:
        await state.clear()
        await callback.answer("Текст рассылки потерян. Создайте её заново.", show_alert=True)
        return

    started = start_broadcast(
        bot,
        admin_id=callback.from_user.id,
        admin_chat_id=callback.message.chat.id,
        progress_message_id=callback.message.message_id,
        html_text=html_text,
        button_text=data.get("button_text"),
        button_url=data.get("button_url"),
    )
    await state.clear()
    if not started:
        await callback.answer("Рассылка уже выполняется.", show_alert=True)
        return
    await callback.answer("Рассылка запущена.")


@router.callback_query(F.data == "admin:broadcast_cancel")
async def admin_broadcast_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.from_user or not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    if callback.message:
        await callback.message.edit_text(_panel_text(), reply_markup=admin_panel_actions())
    await callback.answer("Рассылка отменена.")


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
        "Admin manually unblocked user via panel: admin_id=%s user_id=%s "
        "telegram_user_id=%s was_blocked=%s",
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
        "Admin manually unblocked user: admin_id=%s user_id=%s "
        "telegram_user_id=%s was_blocked=%s",
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
