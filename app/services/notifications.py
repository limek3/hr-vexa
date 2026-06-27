import re
from urllib.parse import quote

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.formatting import DIVIDER, html
from app.db.models import Match, Message, Search, Source, User


PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
USERNAME_RE = re.compile(r"(?<!\w)@([A-Za-z0-9_]{5,32})")


def _clean_phone(value: str | None) -> str | None:
    if not value:
        return None
    phone = value.strip()
    if not phone.startswith("+") and phone.isdigit():
        phone = f"+{phone}"
    return phone


def _first_phone(text: str) -> str | None:
    match = PHONE_RE.search(text)
    if not match:
        return None
    phone = re.sub(r"\s+", " ", match.group(0)).strip()
    return phone if len(re.sub(r"\D", "", phone)) >= 8 else None


def _first_username(text: str) -> str | None:
    match = USERNAME_RE.search(text)
    return match.group(1) if match else None


def _short_text(text: str, *, limit: int = 900) -> str:
    text = text.strip()
    return f"{text[:limit]}..." if len(text) > limit else text


def _reply_draft(search_title: str) -> str:
    return (
        f"Доброго времени суток! Увидел(а) ваше сообщение по теме «{search_title}». "
        "Подскажите, пожалуйста, это еще актуально?"
    )


def _private_chat_url(username: str, draft: str) -> str:
    return f"tg://resolve?domain={username}&text={quote(draft)}"


def match_keyboard(
    match_id: int,
    url: str | None,
    username: str | None,
    draft: str,
) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="Скрыть", callback_data=f"hide:{match_id}")],
    ]
    if username:
        buttons.insert(0, [InlineKeyboardButton(text="Написать в ЛС", url=_private_chat_url(username, draft))])
    else:
        buttons.insert(0, [InlineKeyboardButton(text="Написать в ЛС", callback_data=f"reply_draft:{match_id}")])
    if url:
        insert_at = 1
        buttons.insert(insert_at, [InlineKeyboardButton(text="Открыть источник", url=url)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def send_candidate_notification(
    bot: Bot,
    *,
    user: User,
    search: Search,
    source: Source,
    message: Message,
    match: Match,
    sender_username: str | None = None,
    sender_phone: str | None = None,
    sender_name: str | None = None,
) -> None:
    text = _short_text(message.text)
    username = sender_username or _first_username(text)
    phone = _clean_phone(sender_phone) or _first_phone(text)

    telegram_line = f"@{html(username)}" if username else "не найден"
    phone_line = html(phone) if phone else "не найден"
    name_line = f"\nАвтор: {html(sender_name)}" if sender_name else ""
    draft = _reply_draft(search.title)

    await bot.send_message(
        chat_id=user.telegram_user_id,
        text=(
            "▌ <b>Найдено совпадение</b>\n"
            f"{DIVIDER}\n\n"
            "▌ <b>Данные</b>\n"
            f"<blockquote>Поиск: {html(search.title)}\n"
            f"Источник: {html(source.title or source.input_ref)}\n"
            f"Telegram: {telegram_line}\n"
            f"Телефон: {phone_line}"
            f"{name_line}</blockquote>\n\n"
            "▌ <b>Сообщение</b>\n"
            f"<blockquote>{html(text) or 'без текста'}</blockquote>"
        ),
        reply_markup=match_keyboard(match.id, message.url, username, draft),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )
