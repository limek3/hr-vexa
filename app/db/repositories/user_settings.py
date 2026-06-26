from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserSettings


DEFAULT_QUIET_START = "00:00"
DEFAULT_QUIET_END = "07:00"
DEFAULT_TIMEZONE = "Europe/Moscow"


async def get_or_create_user_settings(session: AsyncSession, *, user_id: int) -> UserSettings:
    result = await session.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    settings = result.scalar_one_or_none()
    if settings:
        return settings

    settings = UserSettings(
        user_id=user_id,
        quiet_hours_enabled=True,
        quiet_hours_start=DEFAULT_QUIET_START,
        quiet_hours_end=DEFAULT_QUIET_END,
        timezone=DEFAULT_TIMEZONE,
    )
    session.add(settings)
    await session.flush()
    return settings


async def toggle_quiet_hours(session: AsyncSession, *, user_id: int) -> UserSettings:
    settings = await get_or_create_user_settings(session, user_id=user_id)
    settings.quiet_hours_enabled = not settings.quiet_hours_enabled
    await session.flush()
    return settings


async def notifications_paused_for_user(session: AsyncSession, *, user_id: int) -> bool:
    settings = await get_or_create_user_settings(session, user_id=user_id)
    if not settings.quiet_hours_enabled:
        return False

    now = datetime.now(ZoneInfo(settings.timezone)).time()
    start = _parse_clock(settings.quiet_hours_start)
    end = _parse_clock(settings.quiet_hours_end)

    if start == end:
        return True
    if start < end:
        return start <= now < end
    return now >= start or now < end


def _parse_clock(value: str) -> time:
    hour, minute = value.split(":", maxsplit=1)
    return time(hour=int(hour), minute=int(minute))
