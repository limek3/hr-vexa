import asyncio
import logging

from aiogram import Bot
from telethon import TelegramClient, events

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.init import init_models
from app.db.repositories.sources import list_sources, mark_source_access
from app.db.session import SessionLocal
from app.monitor.client import build_telegram_client
from app.monitor.delivery_queue import delivery_queue_loop
from app.monitor.handlers import handle_new_message
from app.monitor.source_checker import resolve_source_access

logger = logging.getLogger(__name__)


async def refresh_sources(client: TelegramClient) -> None:
    async with SessionLocal() as session:
        sources = await list_sources(session, statuses={"pending", "unavailable", "not_found"})
        for source in sources:
            telegram_id, title, source_type, access_status, _linked_discussion = await resolve_source_access(
                client,
                source,
            )
            await mark_source_access(
                session,
                source_id=source.id,
                telegram_id=telegram_id,
                title=title,
                source_type=source_type,
                access_status=access_status,
            )
        await session.commit()


async def refresh_sources_loop(client: TelegramClient) -> None:
    while True:
        try:
            await refresh_sources(client)
        except Exception:
            logger.exception("Source refresh failed")
        await asyncio.sleep(60)


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
    await refresh_sources(client)
    asyncio.create_task(refresh_sources_loop(client))
    asyncio.create_task(delivery_queue_loop(bot))
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
