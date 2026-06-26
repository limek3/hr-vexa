import re


SOURCE_RE = re.compile(r"^(?:https?://)?t\.me/(?P<slug>[A-Za-z0-9_+/-]+)$")


def normalize_source(raw: str) -> str | None:
    value = raw.strip()
    if not value:
        return None

    if value.startswith("@"):
        username = value[1:].strip()
        return f"@{username}" if username else None

    match = SOURCE_RE.match(value)
    if not match:
        return None

    slug = match.group("slug").strip("/")
    if not slug:
        return None

    if slug.startswith("+"):
        return f"https://t.me/{slug}"

    username = slug.split("/", maxsplit=1)[0]
    return f"@{username}"


def split_sources(text: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        normalized = normalize_source(line)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result
