import re


TOKEN_RE = re.compile(r"[0-9a-zа-яё]+", re.IGNORECASE)
RU_ENDINGS = (
    "иями",
    "ями",
    "ами",
    "ого",
    "его",
    "ому",
    "ему",
    "ыми",
    "ими",
    "ия",
    "ие",
    "ий",
    "ый",
    "ой",
    "ей",
    "ая",
    "яя",
    "ое",
    "ые",
    "ую",
    "юю",
    "ам",
    "ям",
    "ах",
    "ях",
    "ов",
    "ев",
    "ом",
    "ем",
    "а",
    "я",
    "ы",
    "и",
    "у",
    "ю",
    "е",
)


def _tokens(value: str) -> list[str]:
    return [token.casefold().replace("ё", "е") for token in TOKEN_RE.findall(value)]


def _stem_token(token: str) -> str:
    token = token.casefold().replace("ё", "е")
    if token.isdigit() or len(token) <= 3:
        return token

    for ending in RU_ENDINGS:
        if token.endswith(ending) and len(token) - len(ending) >= 4:
            return token[: -len(ending)]
    if token.endswith("ь") and len(token) >= 5:
        return token[:-1]
    return token


def _unique_stems(tokens: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        stem = _stem_token(token)
        if stem and stem not in seen:
            seen.add(stem)
            result.append(stem)
    return result


def _contains_term(text: str, term: str) -> bool:
    term = term.strip()
    if not term:
        return False

    normalized_text = text.casefold().replace("ё", "е")
    normalized_term = term.casefold().replace("ё", "е")
    if normalized_term in normalized_text:
        return True

    text_stems = set(_unique_stems(_tokens(text)))
    term_stems = _unique_stems(_tokens(term))
    if not term_stems:
        return False
    return all(stem in text_stems for stem in term_stems)


def is_match(text: str | None, keywords: list[str], minus_words: list[str]) -> bool:
    if not text:
        return False

    has_keyword = any(_contains_term(text, keyword) for keyword in keywords)
    has_minus_word = any(_contains_term(text, word) for word in minus_words)
    return has_keyword and not has_minus_word
