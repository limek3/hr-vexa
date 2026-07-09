import logging
from datetime import UTC

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telethon import events

from app.db.models import Message, Source, User
from app.db.repositories.messages import create_match_once, increment_daily_stats, save_message_if_new
from app.db.repositories.notification_deliveries import enqueue_notification_once
from app.db.repositories.searches import list_active_searches_for_source
from app.db.repositories.sources import get_source_by_telegram_id
from app.db.repositories.user_settings import notifications_paused_for_user
from app.services.filtering import analyze_match
from app.services.notifications import safe_send_candidate_notification

logger = logging.getLogger(__name__)


def message_url(source: Source, telegram_message_id: int) -> str | None:
    if source.username:
        return f"https://t.me/{source.username}/{telegram_message_id}"
    return None


async def handle_new_message(event: events.NewMessage.Event, session: AsyncSession, bot: Bot) -> None:
    chat = await event.get_chat()
    telegram_id = getattr(chat, "id", None)
    if telegram_id is None:
        return

    source = await get_source_by_telegram_id(session, telegram_id)
    if not source or source.access_status != "available":
        return

    raw_text = event.raw_text or ""
    sender = await event.get_sender()
    sender_username = getattr(sender, "username", None) if sender else None
    sender_phone = getattr(sender, "phone", None) if sender else None
    sender_name_parts = [
        getattr(sender, "first_name", None) if sender else None,
        getattr(sender, "last_name", None) if sender else None,
    ]
    sender_name = " ".join(part for part in sender_name_parts if part) or None

    saved_message = await save_message_if_new(
        session,
        source_id=source.id,
        telegram_message_id=event.message.id,
        telegram_date=event.message.date,
        text=raw_text,
        url=message_url(source, event.message.id),
        sender_username=sender_username,
        sender_phone=sender_phone,
        sender_name=sender_name,
    )
    if saved_message is None:
        return

    searches = await list_active_searches_for_source(session, source.id)
    for search in searches:
        keywords = [keyword.value for keyword in search.keywords]
        minus_words = [minus_word.value for minus_word in search.minus_words]
        analysis = analyze_match(raw_text, keywords, minus_words)
        if not analysis.matched:
            continue

        match = await create_match_once(
            session,
            user_id=search.user_id,
            search_id=search.id,
            source_id=source.id,
            message_id=saved_message.id,
            matched_keyword=analysis.keyword,
            match_score=analysis.score,
            match_reason=analysis.reason,
        )
        if not match:
            continue

        await increment_daily_stats(
            session,
            user_id=search.user_id,
            search_id=search.id,
            stat_date=event.message.date.astimezone(UTC).date(),
        )
        user = await session.scalar(select(User).where(User.id == search.user_id))
        message = await session.get(Message, saved_message.id)
        if user and message:
            if await notifications_paused_for_user(session, user_id=user.id):
                await enqueue_notification_once(session, user_id=user.id, match_id=match.id)
                logger.info("Notification queued by quiet hours: search_id=%s match_id=%s", search.id, match.id)
                continue

            if user.is_blocked:
                logger.info(
                    "Notification skipped, user is blocked: user_id=%s telegram_user_id=%s "
                    "username=%s search_id=%s match_id=%s source_id=%s",
                    user.id,
                    user.telegram_user_id,
                    user.username,
                    search.id,
                    match.id,
                    source.id,
                )
                continue

            try:
                status = await safe_send_candidate_notification(
                    bot,
                    session,
                    user=user,
                    search=search,
                    source=source,
                    message=message,
                    match=match,
                    sender_username=sender_username,
                    sender_phone=sender_phone,
                    sender_name=sender_name,
                )
            except Exception:
                logger.exception(
                    "Notification handling raised unexpectedly: user_id=%s telegram_user_id=%s "
                    "username=%s search_id=%s match_id=%s source_id=%s",
                    user.id,
                    user.telegram_user_id,
                    user.username,
                    search.id,
                    match.id,
                    source.id,
                )
                status = "failed"

            logger.info(
                "Notification handled: status=%s user_id=%s telegram_user_id=%s username=%s "
                "search_id=%s match_id=%s source_id=%s",
                status,
                user.id,
                user.telegram_user_id,
                user.username,
                search.id,
                match.id,
                source.id,
            )
