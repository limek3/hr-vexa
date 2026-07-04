from app.core.config import get_settings


def max_sources_per_search() -> int:
    return max(1, get_settings().max_sources_per_search)


def sources_limit_error(count: int) -> str | None:
    limit = max_sources_per_search()
    if count <= limit:
        return None
    return (
        f"Слишком много источников: {count}. "
        f"Сейчас можно добавить максимум {limit} источников на один поиск."
    )
