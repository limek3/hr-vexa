from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.models import Match, Message, Search, Source, User


def match_keyboard(match_id: int, url: str | None) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="Сохранить", callback_data=f"favorite:{match_id}")],
        [InlineKeyboardButton(text="Скрыть", callback_data=f"hide:{match_id}")],
    ]
    if url:
        buttons.insert(0, [InlineKeyboardButton(text="Открыть источник", url=url)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def send_candidate_notification(
    bot: Bot,
    *,
    user: User,
    search: Search,
    source: Source,
    message: Message,
    match: Match,
) -> None:
    text = message.text.strip()
    if len(text) > 900:
        text = f"{text[:900]}..."

    await bot.send_message(
        chat_id=user.telegram_user_id,
        text=(
            "Найдено совпадение\n\n"
            f"Поиск: {search.title}\n"
            f"Источник: {source.title or source.input_ref}\n\n"
            f"{text}"
        ),
        reply_markup=match_keyboard(match.id, message.url),
        disable_web_page_preview=True,
    )
