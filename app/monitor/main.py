import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import select
from telethon import TelegramClient, events

from app.bot.formatting import heading, html, metric, source_status_label, text_value
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.init import init_models
from app.db.models import Source, User
from app.db.repositories.sources import (
    list_source_notification_targets,
    list_sources,
    list_sources_pending_folder_sync,
    mark_source_access,
    mark_source_folder_synced,
)
from app.db.repositories.users import count_blocked_users
from app.db.session import SessionLocal
from app.monitor.client import build_telegram_client
from app.monitor.delivery_queue import cleanup_deliveries_loop, delivery_queue_loop
from app.monitor.folders import add_source_to_telegram_folder
from app.monitor.handlers import handle_new_message
from app.monitor.source_checker import resolve_source_access
from app.services.channel_reminder import subscription_reminder_loop
from app.services.notifications import MAX_RETRY_AFTER_SECONDS

logger = logging.getLogger(__name__)

RECHECK_STATUSES = {
    "pending",
    "queued",
    "joining",
}
NOTIFY_FROM_STATUSES = {"pending", "queued", "joining"}
PROBLEM_STATUSES = {"unavailable", "not_found", "invite_expired", "join_limited", "join_request_sent"}
FOLDER_SYNCED_STATUSES = {"added", "already_present", "created"}
FOLDER_TERMINAL_STATUSES = FOLDER_SYNCED_STATUSES | {"entity_missing", "folder_full"}


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
    for target in targets:
        for attempt in (1, 2):
            try:
                await bot.send_message(
                    chat_id=target.telegram_user_id,
                    text=(
                        f"{heading('Проблема с источником')}\n\n"
                        f"{text_value('Поиск', target.search_title)}\n"
                        f"{text_value('Источник', source_title)}\n"
                        f"{text_value('Статус', status_label)}\n\n"
                        f"<blockquote>{html(hint)}</blockquote>"
                    ),
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
                break
            except TelegramRetryAfter as exc:
                if attempt == 2:
                    logger.warning(
                        "Source problem notification failed after flood-control wait: user_id=%s "
                        "telegram_user_id=%s source_id=%s retry_after=%s",
                        target.user_id,
                        target.telegram_user_id,
                        source.id,
                        exc.retry_after,
                    )
                    break
                await asyncio.sleep(min(exc.retry_after, MAX_RETRY_AFTER_SECONDS))
                continue
            except TelegramForbiddenError:
                user = await session.scalar(select(User).where(User.id == target.user_id))
                if user:
                    user.is_blocked = True
                    await session.flush()
                logger.warning(
                    "Source problem notification blocked, bot was blocked by user: user_id=%s "
                    "telegram_user_id=%s username=%s first_name=%s source_id=%s status=%s",
                    target.user_id,
                    target.telegram_user_id,
                    target.username,
                    target.first_name,
                    source.id,
                    access_status,
                )
                break
            except TelegramBadRequest as exc:
                if "chat not found" in str(exc).lower():
                    user = await session.scalar(select(User).where(User.id == target.user_id))
                    if user:
                        user.is_blocked = True
                        await session.flush()
                logger.warning(
                    "Source problem notification failed with bad request: user_id=%s telegram_user_id=%s "
                    "username=%s first_name=%s source_id=%s status=%s error=%s",
                    target.user_id,
                    target.telegram_user_id,
                    target.username,
                    target.first_name,
                    source.id,
                    access_status,
                    exc,
                )
                break
            except Exception:
                logger.exception(
                    "Source problem notification failed: user_id=%s telegram_user_id=%s username=%s "
                    "first_name=%s source_id=%s status=%s",
                    target.user_id,
                    target.telegram_user_id,
                    target.username,
                    target.first_name,
                    source.id,
                    access_status,
                )
                break


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

            (
                telegram_id,
                title,
                source_type,
                access_status,
                _linked_discussion,
                source_entity,
            ) = await resolve_source_access(
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
            source.telegram_id = telegram_id
            source.title = title
            source.type = source_type
            source.access_status = access_status
            if access_status == "available":
                folder_status = await add_source_to_telegram_folder(client, source_entity, source=source)
                if folder_status in FOLDER_TERMINAL_STATUSES:
                    await mark_source_folder_synced(
                        session,
                        source_id=source.id,
                        synced_at=datetime.now(timezone.utc),
                    )
            if previous_status in NOTIFY_FROM_STATUSES and access_status in PROBLEM_STATUSES:
                await notify_source_problem(bot, session, source=source, access_status=access_status)
            if allow_join and join_delay:
                await asyncio.sleep(join_delay)
        await session.commit()


async def sync_available_sources_folder(client: TelegramClient) -> None:
    settings = get_settings()
    if not settings.telegram_sources_folder_title.strip():
        return

    async with SessionLocal() as session:
        sources = await list_sources_pending_folder_sync(session)
        for source in sources:
            entity = None
            for ref in (source.input_ref, source.telegram_id):
                if not ref:
                    continue
                try:
                    entity = await client.get_input_entity(ref)
                    break
                except Exception:
                    continue

            status = await add_source_to_telegram_folder(client, entity, source=source)
            if status in FOLDER_TERMINAL_STATUSES:
                await mark_source_folder_synced(
                    session,
                    source_id=source.id,
                    synced_at=datetime.now(timezone.utc),
                )
            if status in {"added", "created", "folder_missing", "folder_full", "failed", "entity_missing"}:
                logger.info(
                    "Telegram sources folder sync result: status=%s source_id=%s input_ref=%s "
                    "telegram_id=%s folder_title=%s",
                    status,
                    source.id,
                    source.input_ref,
                    source.telegram_id,
                    settings.telegram_sources_folder_title,
                )
        await session.commit()


async def _check_session_health(client: TelegramClient) -> None:
    if not client.is_connected():
        logger.critical("MTProto monitor is disconnected from Telegram")
        return
    try:
        authorized = await client.is_user_authorized()
    except Exception:
        logger.exception("MTProto session health check failed")
        return
    if not authorized:
        logger.critical(
            "MTProto session is no longer authorized; monitoring and notifications will stop "
            "working. Re-run python -m app.monitor.login to refresh TELEGRAM_SESSION_STRING.",
        )


async def refresh_sources_loop(client: TelegramClient, bot: Bot) -> None:
    settings = get_settings()
    interval = max(10, settings.telegram_source_refresh_interval_seconds)
    while True:
        await _check_session_health(client)
        try:
            await refresh_sources(client, bot)
            await sync_available_sources_folder(client)
        except Exception:
            logger.exception("Source refresh failed")
        await asyncio.sleep(interval)


async def _notify_admins_blocked_report(bot: Bot, total_blocked: int) -> None:
    """Send the daily blocked-users count to configured admins over Telegram."""
    admin_ids = get_settings().admin_ids
    if not admin_ids:
        return

    text = f"{heading('Отчёт: заблокировавшие бота')}\n\n{metric('Всего заблокировали', total_blocked)}"
    for admin_id in admin_ids:
        try:
            await bot.send_message(chat_id=admin_id, text=text, parse_mode=ParseMode.HTML)
        except TelegramForbiddenError:
            logger.warning(
                "Blocked users report: admin has blocked the bot, cannot notify: admin_id=%s",
                admin_id,
            )
        except TelegramBadRequest as exc:
            logger.warning(
                "Blocked users report: failed to notify admin (bad request): admin_id=%s error=%s",
                admin_id,
                exc,
            )
        except Exception:
            logger.exception("Blocked users report: failed to notify admin: admin_id=%s", admin_id)


async def blocked_users_report_loop(bot: Bot, *, interval_seconds: int = 86400) -> None:
    """Periodically log how many users currently have the bot blocked, and
    notify configured admins (ADMIN_TELEGRAM_IDS) over Telegram."""
    while True:
        try:
            async with SessionLocal() as session:
                total_blocked = await count_blocked_users(session)
            logger.info("Blocked users report: total_blocked=%s", total_blocked)
            await _notify_admins_blocked_report(bot, total_blocked)
        except Exception:
            logger.exception("Blocked users report failed")
        await asyncio.sleep(interval_seconds)


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
    asyncio.create_task(cleanup_deliveries_loop())
    asyncio.create_task(blocked_users_report_loop(bot))
    asyncio.create_task(subscription_reminder_loop(bot))
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
