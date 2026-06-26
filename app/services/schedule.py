from __future__ import annotations

from datetime import datetime, time

from app.core.config import get_settings


def _parse_clock(value: str) -> time:
    hour, minute = value.strip().split(":", maxsplit=1)
    return time(hour=int(hour), minute=int(minute))


def notifications_paused_now(now: datetime | None = None) -> bool:
    settings = get_settings()
    if not settings.quiet_hours_enabled:
        return False

    now_time = (now or datetime.now()).time()
    start = _parse_clock(settings.quiet_hours_start)
    end = _parse_clock(settings.quiet_hours_end)

    if start == end:
        return True
    if start < end:
        return start <= now_time < end
    return now_time >= start or now_time < end
