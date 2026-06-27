from dataclasses import dataclass
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
SHORT_VERB_ENDINGS = ("м", "ю", "л", "ла", "ло", "ли", "ет", "ют", "ем", "им", "ете", "ите", "ется")
SYNONYM_GROUPS = (
    ("ищу", "ищем", "нужен", "нужна", "нужно", "нужны", "требуется", "требуются"),
    ("сдам", "сдаю", "сдает", "сдают", "сдал", "сдала", "сдается", "аренда"),
    ("куплю", "купить", "покупка", "ищу"),
    ("продам", "продаю", "продажа"),
    ("поставщик", "подрядчик", "исполнитель"),
    ("кандидат", "соискатель", "работник", "сотрудник"),
    ("работа", "вакансия", "подработка", "смена"),
    ("ремонт", "мастер", "услуга", "подрядчик"),
    ("квартира", "комната", "студия", "апартаменты", "жилье"),
    ("москва", "мск"),
    ("санкт", "петербург", "спб"),
)


@dataclass(frozen=True)
class MatchAnalysis:
    matched: bool
    score: int
    reason: str
    keyword: str | None = None
    minus_word: str | None = None


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


def _build_synonym_index() -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for group in SYNONYM_GROUPS:
        stems = {_stem_token(token) for token in group}
        for stem in stems:
            index.setdefault(stem, set()).update(stems)
    return index


SYNONYM_INDEX = _build_synonym_index()


def _unique_stems(tokens: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        stem = _stem_token(token)
        if stem and stem not in seen:
            seen.add(stem)
            result.append(stem)
    return result


def _edit_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if abs(len(left) - len(right)) > 2:
        return 3

    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            current.append(
                min(
                    previous[right_index] + 1,
                    current[right_index - 1] + 1,
                    previous[right_index - 1] + (left_char != right_char),
                ),
            )
        previous = current
    return previous[-1]


def _token_match_kind(query_token: str, text_token: str) -> str | None:
    if query_token == text_token:
        return "точно"

    if text_token in SYNONYM_INDEX.get(query_token, set()):
        return "синоним"

    min_len = min(len(query_token), len(text_token))
    if min_len <= 3:
        return None

    if query_token.startswith(text_token) or text_token.startswith(query_token):
        return "форма"

    if (
        len(query_token) <= 5
        and query_token.startswith(text_token[:3])
        and query_token.endswith(SHORT_VERB_ENDINGS)
        and len(text_token) >= 4
    ):
        return "форма"

    if query_token[:3] == text_token[:3]:
        max_distance = 1 if min_len <= 5 else 2
        if _edit_distance(query_token, text_token) <= max_distance:
            return "похоже"

    return None


def _term_match_details(text: str, term: str) -> tuple[bool, int, str]:
    term = term.strip()
    if not term:
        return False, 0, ""

    normalized_text = text.casefold().replace("ё", "е")
    normalized_term = term.casefold().replace("ё", "е")
    if normalized_term in normalized_text:
        return True, 100, f"точная фраза: {term}"

    text_stems = _unique_stems(_tokens(text))
    term_stems = _unique_stems(_tokens(term))
    if not term_stems:
        return False, 0, ""

    scores = {"точно": 100, "форма": 88, "синоним": 82, "похоже": 76}
    matched_parts: list[str] = []
    total_score = 0
    for term_stem in term_stems:
        best: tuple[int, str, str] | None = None
        for text_stem in text_stems:
            kind = _token_match_kind(term_stem, text_stem)
            if not kind:
                continue
            score = scores[kind]
            if best is None or score > best[0]:
                best = score, text_stem, kind
        if best is None:
            return False, 0, ""
        total_score += best[0]
        _score, text_stem, kind = best
        matched_parts.append(f"{term_stem}→{text_stem} ({kind})")

    score = round(total_score / len(term_stems))
    return True, score, "; ".join(matched_parts)


def _contains_term(text: str, term: str) -> bool:
    matched, _score, _reason = _term_match_details(text, term)
    return matched


def analyze_match(text: str | None, keywords: list[str], minus_words: list[str]) -> MatchAnalysis:
    if not text:
        return MatchAnalysis(False, 0, "нет текста")

    best_keyword: tuple[int, str, str] | None = None
    for keyword in keywords:
        matched, score, reason = _term_match_details(text, keyword)
        if matched and (best_keyword is None or score > best_keyword[0]):
            best_keyword = score, keyword, reason

    if best_keyword is None:
        return MatchAnalysis(False, 0, "ключевые слова не найдены")

    for minus_word in minus_words:
        matched, _score, reason = _term_match_details(text, minus_word)
        if matched:
            return MatchAnalysis(
                False,
                0,
                f"сработало минус-слово «{minus_word}»: {reason}",
                keyword=best_keyword[1],
                minus_word=minus_word,
            )

    score, keyword, reason = best_keyword
    return MatchAnalysis(True, score, reason, keyword=keyword)


def is_match(text: str | None, keywords: list[str], minus_words: list[str]) -> bool:
    return analyze_match(text, keywords, minus_words).matched
