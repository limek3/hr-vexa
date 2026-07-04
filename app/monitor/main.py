import asyncio
import logging

from aiogram import Bot
from telethon import TelegramClient, events

from app.bot.formatting import heading, html, source_status_label, text_value
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.init import init_models
from app.db.models import Source
from app.db.repositories.sources import (
    list_source_notification_targets,
    list_sources,
    mark_source_access,
)
from app.db.session import SessionLocal
from app.monitor.client import build_telegram_client
from app.monitor.delivery_queue import delivery_queue_loop
from app.monitor.handlers import handle_new_message
from app.monitor.source_checker import resolve_source_access

logger = logging.getLogger(__name__)

RECHECK_STATUSES = {
    "pending",
    "queued",
    "joining",
}
NOTIFY_FROM_STATUSES = {"pending", "queued", "joining"}
PROBLEM_STATUSES = {"unavailable", "not_found", "invite_expired", "join_limited", "join_request_sent"}


def _source_problem_hint(status: str) -> str:
    hints = {
        "unavailable": "Проверьте, что аккаунту Vexa разрешен доступ к этому источнику.",
        "not_found": "Проверьте юзернейм или ссылку: Telegram не нашел такой источник.",
        "invite_expired": "Invite-ссылка недействительна или устарела. Добавьте новую ссылку.",
        "join_limited": "Telegram временно ограничил вступления. Источник можно проверить позже.",
        "join_request_sent": "Заявка на вступление отправлена. Нужно дождаться одобрения администратора.",
    }
    return hints.get(status, "Проверьте источник и попробуйте запустить проверку заново.")


async def notify_source_problem(
    bot: Bot,
    session,
    *,
    source: Source,
    access_status: str,
) -> None:
    targets = await list_source_notification_targets(session, source_id=source.id)
    if not targets:
        return

    source_title = source.title or source.input_ref
    status_label = source_status_label(access_status)
    hint = _source_problem_hint(access_status)
    for telegram_user_id, search_title in targets:
        try:
            await bot.send_message(
                chat_id=telegram_user_id,
                text=(
                    f"{heading('Проблема с источником')}\n\n"
                    f"{text_value('Поиск', search_title)}\n"
                    f"{text_value('Источник', source_title)}\n"
                    f"{text_value('Статус', status_label)}\n\n"
                    f"<blockquote>{html(hint)}</blockquote>"
                ),
                disable_web_page_preview=True,
            )
        except Exception:
            logger.exception("Source problem notification failed: source_id=%s", source.id)


async def refresh_sources(client: TelegramClient, bot: Bot) -> None:
    settings = get_settings()
    max_joins = max(0, settings.telegram_max_joins_per_cycle)
    join_delay = max(0, settings.telegram_join_delay_seconds)
    joins_used = 0

    async with SessionLocal() as session:
        sources = await list_sources(session, statuses=RECHECK_STATUSES)
        for source in sources:
            previous_status = source.access_status
            allow_join = joins_used < max_joins
            if allow_join and settings.telegram_auto_join_sources:
                await mark_source_access(
                    session,
                    source_id=source.id,
                    telegram_id=source.telegram_id,
                    title=source.title or source.input_ref,
                    source_type=source.type,
                    access_status="joining",
                )
                await session.commit()
                joins_used += 1

            telegram_id, title, source_type, access_status, _linked_discussion = await resolve_source_access(
                client,
                source,
                allow_join=allow_join,
            )
            await mark_source_access(
                session,
                source_id=source.id,
                telegram_id=telegram_id,
                title=title,
                source_type=source_type,
                access_status=access_status,
            )
            source.title = title
            source.access_status = access_status
            if previous_status in NOTIFY_FROM_STATUSES and access_status in PROBLEM_STATUSES:
                await notify_source_problem(bot, session, source=source, access_status=access_status)
            if allow_join and join_delay:
                await asyncio.sleep(join_delay)
        await session.commit()


async def refresh_sources_loop(client: TelegramClient, bot: Bot) -> None:
    settings = get_settings()
    interval = max(10, settings.telegram_source_refresh_interval_seconds)
    while True:
        try:
            await refresh_sources(client, bot)
        except Exception:
            logger.exception("Source refresh failed")
        await asyncio.sleep(interval)


async def main(init_db: bool = True) -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is required")
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        raise RuntimeError("TELEGRAM_API_ID and TELEGRAM_API_HASH are required")
    if not settings.telegram_session_string:
        raise RuntimeError("TELEGRAM_SESSION_STRING is required. Run python -m app.monitor.login first.")

    if init_db:
        await init_models()
    bot = Bot(token=settings.bot_token)
    client = build_telegram_client()

    @client.on(events.NewMessage(incoming=True))
    async def on_new_message(event: events.NewMessage.Event) -> None:
        async with SessionLocal() as session:
            try:
                await handle_new_message(event, session, bot)
                await session.commit()
            except Exception:
                await session.rollback()
                logger.exception("New message handling failed")

    await client.start()
    me = await client.get_me()
    logger.info("MTProto monitor started as %s", getattr(me, "username", None) or me.id)
    await refresh_sources(client, bot)
    asyncio.create_task(refresh_sources_loop(client, bot))
    asyncio.create_task(delivery_queue_loop(bot))
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
