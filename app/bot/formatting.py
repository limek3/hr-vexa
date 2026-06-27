from html import escape

from app.db.models import Search

DIVIDER = "━━━━━━━━━━━━━━"


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


def compact_inline(values: list[str], *, limit: int = 4) -> str:
    if not values:
        return "ключевые слова не заданы"
    visible = ", ".join(html(value) for value in values[:limit])
    if len(values) > limit:
        visible = f"{visible}, +{len(values) - limit}"
    return visible


def search_card(search: Search, *, index: int | None = None) -> str:
    title = f"{index}. {html(search.title)}" if index is not None else html(search.title)
    status = "включен" if search.is_active else "на паузе"
    keywords = [item.value for item in search.keywords]
    minus_words = [item.value for item in search.minus_words]
    active_sources = [link for link in search.sources if link.is_active]
    keyword_word = "ключ" if len(keywords) == 1 else "ключей"
    source_word = "источник" if len(active_sources) == 1 else "источников"

    return (
        f"<b>{title}</b>\n"
        f"{DIVIDER}\n"
        f"<b>{status}</b> · {len(keywords)} {keyword_word} · "
        f"{len(active_sources)} {source_word} · минус: {len(minus_words)}\n\n"
        f"<blockquote>{compact_inline(keywords)}</blockquote>"
    )


def search_edit_card(search: Search) -> str:
    keywords = [item.value for item in search.keywords]
    minus_words = [item.value for item in search.minus_words]
    sources = [link.source.input_ref for link in search.sources]
    status = "включен" if search.is_active else "на паузе"

    return (
        f"<b>{html(search.title)}</b>\n"
        f"Статус: <b>{status}</b>\n"
        f"{DIVIDER}\n\n"
        "▌ <b>Ключевые слова</b>\n"
        f"<blockquote>{compact_values(keywords, limit=8)}</blockquote>\n\n"
        "▌ <b>Минус-слова</b>\n"
        f"<blockquote>{compact_values(minus_words, limit=8)}</blockquote>\n\n"
        "▌ <b>Источники</b>\n"
        f"<blockquote>{compact_values(sources, limit=8)}</blockquote>"
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
