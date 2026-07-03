from html import escape

from app.db.models import Search

DIVIDER = "━━━━━━━━━━━━"
HEADING_PAD = "\u00a0\u00a0\u00a0"
MAX_VALUE_LENGTH = 34


def html(value: object) -> str:
    return escape(str(value), quote=False)


def heading(title: str) -> str:
    return f"{HEADING_PAD}━━━━ <b>{title}</b> ━━━━"


def metric(label: str, value: object) -> str:
    return f"<i>{label}:</i> <b>{html(value)}</b>"


def text_value(label: str, value: object) -> str:
    return f"<i>{label}:</i> <i>{html(value)}</i>"


def _short_value(value: str, *, limit: int = MAX_VALUE_LENGTH) -> str:
    value = value.strip()
    return f"{value[: limit - 3]}..." if len(value) > limit else value


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
    visible = [_short_value(value) for value in values[:limit]]
    suffix = f"\n...и еще {len(values) - limit}" if len(values) > limit else ""
    return "\n".join(f"- {html(value)}" for value in visible) + suffix


def compact_inline(values: list[str], *, limit: int = 4) -> str:
    if not values:
        return "ключевые слова не заданы"
    visible = ", ".join(html(_short_value(value, limit=22)) for value in values[:limit])
    if len(values) > limit:
        visible = f"{visible}, +{len(values) - limit}"
    return visible


def title_with_status(title: str, status: str) -> str:
    return f"{heading(title)}\n{text_value('Статус', status)}"


def search_card(search: Search, *, index: int | None = None) -> str:
    title = f"{index}. {html(search.title)}" if index is not None else html(search.title)
    status = "включен" if search.is_active else "на паузе"
    keywords = [item.value for item in search.keywords]
    minus_words = [item.value for item in search.minus_words]
    active_sources = [link for link in search.sources if link.is_active]

    return (
        f"{title_with_status(title, status)}\n"
        "\n"
        "<b>Настройка</b>\n"
        f"{metric('Ключи', len(keywords))}\n"
        f"{metric('Минус-слова', len(minus_words))}\n"
        f"{metric('Источники', len(active_sources))}\n\n"
        "<b>Ключевые слова</b>\n"
        f"<i>{compact_inline(keywords)}</i>"
    )


def search_edit_card(search: Search) -> str:
    keywords = [item.value for item in search.keywords]
    minus_words = [item.value for item in search.minus_words]
    sources = [link.source.input_ref for link in search.sources]
    status = "включен" if search.is_active else "на паузе"

    return (
        f"{heading('Настройка поиска')}\n"
        f"{text_value('Название', search.title)}\n"
        f"{text_value('Статус', status)}\n\n"
        "Выберите, что нужно изменить.\n\n"
        f"{DIVIDER}\n\n"
        "<b>Ключи</b>\n"
        f"<i>{compact_values(keywords, limit=8)}</i>\n\n"
        "<b>Минус</b>\n"
        f"<i>{compact_values(minus_words, limit=8)}</i>\n\n"
        "<b>Источники</b>\n"
        f"<i>{compact_values(sources, limit=8)}</i>"
    )


def source_list(search: Search) -> str:
    if not search.sources:
        return (
            f"{heading('Источники')}\n"
            "<i>Источники не добавлены.</i>"
        )

    lines = [
        f"{heading('Источники')}\n"
        "<b>Поиск</b>\n"
        f"<i>{html(search.title)}</i>",
    ]
    for index, link in enumerate(search.sources, start=1):
        source = link.source
        source_title = _short_value(source.title or source.input_ref)
        lines.append(
            f"<b>{index}. {html(source_title)}</b>\n"
            f"{html(_short_value(source.input_ref))}\n"
            f"{text_value('Статус', source_status_label(source.access_status))}",
        )
    return "\n\n".join(lines)
