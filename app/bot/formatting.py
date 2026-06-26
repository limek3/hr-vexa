from html import escape

from app.db.models import Search


def html(value: object) -> str:
    return escape(str(value), quote=False)


def source_status_label(status: str) -> str:
    labels = {
        "available": "доступен",
        "pending": "проверяется",
        "unavailable": "нет доступа",
        "not_found": "не найден",
    }
    return labels.get(status, status)


def compact_values(values: list[str], *, limit: int = 5) -> str:
    if not values:
        return "нет"
    visible = values[:limit]
    suffix = f"\n...и еще {len(values) - limit}" if len(values) > limit else ""
    return "\n".join(f"- {html(value)}" for value in visible) + suffix


def search_card(search: Search, *, index: int | None = None) -> str:
    title = f"{index}. {html(search.title)}" if index is not None else html(search.title)
    status = "включен" if search.is_active else "выключен"
    keywords = [item.value for item in search.keywords]
    minus_words = [item.value for item in search.minus_words]
    active_sources = [link for link in search.sources if link.is_active]

    return (
        f"<b>{title}</b>\n"
        f"Статус: <b>{status}</b>\n"
        f"Ключевых слов: {len(keywords)}\n"
        f"Минус-слов: {len(minus_words)}\n"
        f"Источников: {len(active_sources)}\n\n"
        "<b>Ключевые слова</b>\n"
        f"<blockquote>{compact_values(keywords)}</blockquote>"
    )


def source_list(search: Search) -> str:
    if not search.sources:
        return "Источники не добавлены."

    lines = [f"<b>Источники поиска «{html(search.title)}»</b>\n"]
    for index, link in enumerate(search.sources, start=1):
        source = link.source
        lines.append(
            f"{index}. {html(source.title or source.input_ref)}\n"
            f"<blockquote>{html(source.input_ref)}\n"
            f"Статус: {source_status_label(source.access_status)}</blockquote>",
        )
    return "\n".join(lines)
