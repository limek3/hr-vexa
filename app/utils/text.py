import re


WORD_SPLIT_RE = re.compile(r"[,;\n]+")


def split_terms(text: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for part in WORD_SPLIT_RE.split(text):
        value = part.strip().casefold()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
