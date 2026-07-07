import asyncio
import logging
import re
from urllib.parse import quote

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import heading, html, metric, text_value
from app.bot.keyboards.inline import button
from app.db.models import Match, Message, Search, Source, User
from app.services.filtering import analyze_match

logger = logging.getLogger(__name__)

# Cap how long we are willing to wait out a Telegram flood-control pause
# before giving up on a single notification. Telegram can report much
# larger retry_after values under heavy flood conditions; we do not want
# a single send to block the whole delivery loop for minutes.
MAX_RETRY_AFTER_SECONDS = 30


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
        [
            button(text="Подходит", style="success", callback_data=f"feedback:good:{match_id}"),
            button(text="Не подходит", style="danger", callback_data=f"feedback:bad:{match_id}"),
        ],
        [
            button(text="Сохранить", callback_data=f"favorite:{match_id}"),
            button(text="Скрыть", style="danger", callback_data=f"hide:{match_id}"),
        ],
    ]
    if username:
        buttons.insert(0, [button(text="Написать в ЛС", style="success", url=_private_chat_url(username, draft))])
    else:
        buttons.insert(0, [button(text="Написать в ЛС", style="success", callback_data=f"reply_draft:{match_id}")])
    if url:
        insert_at = 1
        buttons.insert(insert_at, [button(text="Открыть источник", url=url)])
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

    telegram_line = f"@{username}" if username else "не найден"
    phone_line = phone if phone else "не найден"
    name_line = f"\n{text_value('Автор', sender_name)}" if sender_name else ""
    draft = _reply_draft(search.title)
    analysis = analyze_match(
        message.text,
        [keyword.value for keyword in search.keywords],
        [minus_word.value for minus_word in search.minus_words],
    )
    keyword_line = analysis.keyword or "не определен"
    reason_line = html(analysis.reason)

    await bot.send_message(
        chat_id=user.telegram_user_id,
        text=(
            f"{heading('Новое совпадение')}\n"
            "\n"
            "<b>Совпадение</b>\n"
            f"{text_value('Поиск', search.title)}\n"
            f"{text_value('Источник', source.title or source.input_ref)}\n"
            f"{text_value('Ключ', keyword_line)}\n"
            f"{metric('Оценка', f'{analysis.score}%')}\n\n"
            "<b>Контакты</b>\n"
            f"{text_value('Telegram', telegram_line)}\n"
            f"{text_value('Телефон', phone_line)}"
            f"{name_line}\n\n"
            "<b>Сообщение</b>\n"
            f"<blockquote>{html(text) or 'без текста'}</blockquote>\n\n"
            "<b>⚠️ Почему найдено</b>\n"
            f"{reason_line}"
        ),
        reply_markup=match_keyboard(match.id, message.url, username, draft),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def safe_send_candidate_notification(
    bot: Bot,
    session: AsyncSession,
    *,
    user: User,
    search: Search,
    source: Source,
    message: Message,
    match: Match,
    sender_username: str | None = None,
    sender_phone: str | None = None,
    sender_name: str | None = None,
) -> str:
    """Safe wrapper around send_candidate_notification.

    Never raises. Returns one of: "sent", "skipped_blocked", "blocked", "failed".
    """
    context = {
        "user_id": user.id,
        "telegram_user_id": user.telegram_user_id,
        "username": user.username,
        "first_name": user.first_name,
        "search_id": search.id,
        "match_id": match.id,
        "source_id": source.id,
    }

    if user.is_blocked:
        logger.info("Notification skipped, user is blocked: %s", context)
        return "skipped_blocked"

    # Up to one retry: a flood-control pause (TelegramRetryAfter) is not a
    # permanent failure, so we wait it out once instead of burning through
    # the delivery attempt budget or mislabeling the user as blocked.
    for attempt in (1, 2):
        try:
            await send_candidate_notification(
                bot,
                user=user,
                search=search,
                source=source,
                message=message,
                match=match,
                sender_username=sender_username,
                sender_phone=sender_phone,
                sender_name=sender_name,
            )
            return "sent"
        except TelegramRetryAfter as exc:
            if attempt == 2:
                logger.warning(
                    "Notification failed after flood-control wait: %s | retry_after=%s",
                    context,
                    exc.retry_after,
                )
                return "failed"
            delay = min(exc.retry_after, MAX_RETRY_AFTER_SECONDS)
            logger.warning(
                "Notification delayed by flood control, retrying once: %s | retry_after=%s delay=%s",
                context,
                exc.retry_after,
                delay,
            )
            await asyncio.sleep(delay)
            continue
        except TelegramForbiddenError:
            user.is_blocked = True
            await session.flush()
            logger.warning("Notification blocked, bot was blocked by user: %s", context)
            return "blocked"
        except TelegramBadRequest as exc:
            error_text = str(exc).lower()
            if "chat not found" in error_text or "user is deactivated" in error_text or "bot was blocked" in error_text:
                user.is_blocked = True
                await session.flush()
                logger.warning("Notification blocked, bad request indicates blocked user: %s | error=%s", context, exc)
                return "blocked"
            logger.warning("Notification failed with bad request: %s | error=%s", context, exc)
            return "failed"
        except Exception:
            logger.exception("Notification failed: %s", context)
            return "failed"

    return "failed"
