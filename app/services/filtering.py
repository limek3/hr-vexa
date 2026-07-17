from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

TOKEN_RE = re.compile(r"[0-9a-zа-яё]+", re.IGNORECASE)
URL_RE = re.compile(r"(?:https?://|www\.)\S+|tg://\S+", re.IGNORECASE)
USERNAME_RE = re.compile(r"(?<![\w@])@[a-z0-9_]{4,}", re.IGNORECASE)
HASHTAG_RE = re.compile(r"(?<!\w)#[\wа-яё]+", re.IGNORECASE)
SPACE_RE = re.compile(r"\s+")

# Intent words must never be reduced to a common stem. In particular, these
# pairs have opposite meanings for recruiting and must not be synonyms:
# "ищу работу" != "ищем сотрудника" != "нужен грузчик".
PROTECTED_INTENT_WORDS = {
    "ищу",
    "ищет",
    "ищут",
    "ищем",
    "нужен",
    "нужна",
    "нужно",
    "нужны",
    "требуется",
    "требуются",
    "требуем",
    "работал",
    "работала",
    "работаю",
    "работает",
    "работают",
}

# Conservative inflection endings. Equality of resulting stems is allowed,
# but prefix matching is deliberately forbidden: "работа" must not match
# "работодатель", and "личный" must not match "личка".
RU_INFLECTION_ENDINGS = tuple(
    sorted(
        {
            "иями",
            "ями",
            "ами",
            "ого",
            "его",
            "ому",
            "ему",
            "ыми",
            "ими",
            "иях",
            "ах",
            "ях",
            "иям",
            "ам",
            "ям",
            "ией",
            "ой",
            "ей",
            "ом",
            "ем",
            "ов",
            "ев",
            "ий",
            "ый",
            "ая",
            "яя",
            "ое",
            "ее",
            "ые",
            "ие",
            "ую",
            "юю",
            "а",
            "я",
            "ы",
            "и",
            "у",
            "ю",
            "е",
        },
        key=len,
        reverse=True,
    ),
)

# Small, directional and semantically safe token families. There is no global
# synonym graph: query intent must never be replaced by employer intent.
SAFE_TOKEN_GROUPS = (
    ("сдам", "сдаю", "сдает", "сдают", "сдается"),
    ("продам", "продаю", "продает", "продают"),
    ("куплю", "покупаю"),
    ("ищу", "ищет", "ищут"),
    ("готов", "готова"),
    ("работал", "работала"),
    ("работа", "подработка"),
    ("квартира", "квартирка"),
    ("автомобиль", "авто", "машина"),
    ("москва", "мск"),
    ("петербург", "спб"),
)

EMPLOYMENT_HINTS = {
    "работа",
    "работу",
    "работы",
    "подработка",
    "подработку",
    "вахта",
    "вахту",
    "смена",
    "смену",
    "резюме",
    "соискатель",
    "кандидат",
    "трудоустройство",
    "работал",
    "работала",
    "работаю",
}

PROFESSION_HINTS = {
    "водитель",
    "курьер",
    "грузчик",
    "разнорабочий",
    "комплектовщик",
    "кладовщик",
    "упаковщик",
    "фасовщик",
    "повар",
    "пекарь",
    "официант",
    "бариста",
    "уборщик",
    "уборщица",
    "клинер",
    "охранник",
    "продавец",
    "кассир",
    "оператор",
    "менеджер",
    "администратор",
    "сварщик",
    "слесарь",
    "электрик",
    "сантехник",
    "монтажник",
    "маляр",
    "штукатур",
    "строитель",
    "кровельщик",
    "фасадчик",
    "альпинист",
    "высотник",
    "тракторист",
    "экскаваторщик",
    "машинист",
    "механик",
    "автомеханик",
    "логист",
    "бухгалтер",
    "дизайнер",
    "маркетолог",
    "программист",
    "разработчик",
    "аналитик",
    "учитель",
    "преподаватель",
    "воспитатель",
    "няня",
    "медсестра",
    "врач",
}

CANDIDATE_QUALIFIER_PATTERNS = (
    re.compile(r"\bличн(?:ый|ое|ая)\s+(?:авто|автомобиль|машина)\b"),
    re.compile(r"\b(?:свое|свой)\s+(?:авто|автомобиль|машина)\b"),
    re.compile(r"\bправа\s+категории\s+[a-zа-я]\b"),
    re.compile(r"\bстаж\s+вождения\b"),
)

JOB_SEARCH_MODIFIER = (
    r"(?:себе|срочно|новую|постоянную|официальную|стабильную|основную|"
    r"временную|разовую|удаленную|вечернюю|ночную|дневную|хорошую)"
)

ROLE_PATTERN = (
    r"(?:человек(?:а)?|люд(?:и|ей)?|персонал|исполнител(?:ь|я|ей|и)|"
    r"сотрудник(?:а|ов|и)?|работник(?:а|ов|и)?|мастер(?:а|ов|ы)?|"
    r"грузчик(?:а|ов|и)?|разнорабоч(?:ий|их)|комплектовщик(?:а|ов|и)?|"
    r"кладовщик(?:а|ов|и)?|упаковщик(?:а|ов|и)?|фасовщик(?:а|ов|и)?|"
    r"водител(?:ь|я|ей|и)|курьер(?:а|ов|ы)?|повар(?:а|ов|ы)?|"
    r"уборщиц(?:а|у|ы)?|уборщик(?:а|ов|и)?|охранник(?:а|ов|и)?|"
    r"продавц(?:а|ов|ы)?|кассир(?:а|ов|ы)?|рабоч(?:ий|его|их)|"
    r"маляр(?:а|ов|ы)?|монтажник(?:а|ов|и)?|сварщик(?:а|ов|и)?)"
)

CANDIDATE_SIGNALS: tuple[tuple[re.Pattern[str], int, str], ...] = (
    (
        re.compile(
            rf"\b(?:я\s+)?ищу(?:\s+{JOB_SEARCH_MODIFIER}){{0,3}}\s+"
            rf"(?:работу|подработку|вахту|место)\b"
        ),
        14,
        "ищет работу",
    ),
    (
        re.compile(r"\b(?:мне\s+)?нужна(?:\s+[a-zа-яё-]+){0,2}\s+(?:работа|подработка)\b"),
        14,
        "нужна работа",
    ),
    (re.compile(r"\b(?:в\s+)?поиске\s+(?:работы|подработки|вахты)\b"), 12, "в поиске работы"),
    (
        re.compile(
            rf"\b(?:мы|бригада|нас\s+\d+)\b.{{0,35}}\bищем"
            rf"(?:\s+{JOB_SEARCH_MODIFIER}){{0,2}}\s+(?:работу|подработку|вахту)\b"
        ),
        14,
        "бригада ищет работу",
    ),
    (
        re.compile(r"\b(?:готов|готова)\s+(?:выйти|приступить|работать|на\s+вахту)\b"),
        10,
        "готов приступить",
    ),
    (re.compile(r"\b(?:могу|можем)\s+приступить\b"), 9, "может приступить"),
    (re.compile(r"\b(?:могу|можем)\s+(?:выйти|работать)\b"), 9, "может выйти на работу"),
    (
        re.compile(r"\b(?:рассматриваю|рассмотрю)\s+(?:работу|подработку|вакансии|предложения)\b"),
        9,
        "рассматривает предложения",
    ),
    (re.compile(r"\b(?:у\s+меня\s+есть|имею)\s+опыт\b"), 9, "есть опыт"),
    (
        re.compile(
            r"(?:^|[.!?\n]\s*)(?:я\s+)?(?:работал|работала|работаю)\s+(?:как\s+)?[a-zа-яё-]{4,}\b"
        ),
        9,
        "личный опыт работы",
    ),
    (
        re.compile(rf"\b{ROLE_PATTERN}\s+ищет\s+(?:работу|подработку|вахту)\b"),
        14,
        "специалист ищет работу",
    ),
    (re.compile(r"\b(?:резюме|соискатель)\b"), 6, "резюме/соискатель"),
)

EMPLOYER_SIGNALS: tuple[tuple[re.Pattern[str], int, str, bool], ...] = (
    (re.compile(r"\bсоздано\s+заказов\s*:\s*\d+"), 20, "шаблон биржи заказов", True),
    (
        re.compile(r"\bзарегистрирован\s*:\s*\d+\s+(?:день|дня|дней)"),
        15,
        "карточка заказчика",
        True,
    ),
    (re.compile(r"\bсрочн(?:ая|ую)\s+заявк"), 14, "заявка работодателя", True),
    (re.compile(r"\bтребу(?:ется|ются)\b"), 14, "требуются сотрудники", True),
    (
        re.compile(
            rf"\b(?:нужен|нужна|нужны|нужно)\b\s*[:—-]?\s*"
            rf"(?:\d+\s*(?:из\s+\d+\s*)?)?(?:бригада\s+)?{ROLE_PATTERN}\b"
        ),
        14,
        "нужны сотрудники",
        True,
    ),
    (
        re.compile(rf"\bищем\s+(?:\d+[-–—х ]*\s*)?{ROLE_PATTERN}\b"),
        14,
        "работодатель ищет сотрудников",
        True,
    ),
    (
        re.compile(
            rf"\b(?:я\s+)?ищу\s+(?:(?:пару|несколько|\d+)\s+)?{ROLE_PATTERN}"
            rf"(?:\s+на\s+(?:работу|подработку|вахту))?\b"
        ),
        16,
        "работодатель ищет исполнителей",
        True,
    ),
    (
        re.compile(
            r"\bкто\s+ищет\s+(?:работу|подработку|ворк)\b.{0,80}"
            r"\b(?:дам|предлагаю|есть)\s+(?:работу|подработку|ворк)\b",
            re.DOTALL,
        ),
        18,
        "предложение работы соискателям",
        True,
    ),
    (re.compile(r"\b(?:дам|предлагаю)\s+(?:работу|подработку)\b"), 14, "предложение работы", True),
    (
        re.compile(r"\bнабира(?:ю|ем)\s+(?:людей|сотрудников|персонал|команду)\b"),
        14,
        "набор людей",
        True,
    ),
    (re.compile(r"\bна\s+(?:постоянную\s+)?работу\s+ищем\b"), 14, "набор на работу", True),
    (re.compile(r"\bпрямой\s+работодатель\b"), 12, "прямой работодатель", True),
    (re.compile(r"\bприглашаем\s+на\s+работу\b"), 12, "приглашение на работу", True),
    (re.compile(r"\bесть\s+(?:свободный\s+)?рейс\b"), 10, "предложение рейса", True),
    (
        re.compile(r"\бу\s+кого\s+есть\s+(?:личн(?:ое|ый)\s+)?(?:авто|автомобиль|машина)\b"),
        12,
        "поиск исполнителя с автомобилем",
        True,
    ),
    (re.compile(r"\bваканси(?:я|и|ю|й|ям|ях)\b"), 7, "вакансия", False),
    (re.compile(r"\bобязанност(?:и|ь)\s*:"), 7, "раздел обязанностей", False),
    (re.compile(r"\bуслови(?:я|е)\s*:"), 7, "раздел условий", False),
    (re.compile(r"\bтребовани(?:я|е)\s*:"), 7, "раздел требований", False),
    (re.compile(r"\bмы\s+(?:предлагаем|предоставляем)\b"), 8, "предложение работодателя", False),
    (re.compile(r"\b(?:ставка|тариф)\s*:?\s*[\d️⃣]+"), 6, "ставка/тариф", False),
    (
        re.compile(r"\bоплата\b.{0,70}(?:руб|₽|час|смен|карт|руки|окончани)", re.DOTALL),
        6,
        "условия оплаты",
        False,
    ),
    (re.compile(r"\bграфик\s*(?:работы)?\s*:?\s*\d+\s*/\s*\d+"), 5, "рабочий график", False),
    (re.compile(r"\b(?:для\s+записи|по\s+всем\s+вопросам)\b"), 6, "призыв откликнуться", False),
    (
        re.compile(r"\bподробност(?:и|ей)\s+(?:в\s+)?(?:лс|личк)\b"),
        6,
        "подробности для отклика",
        False,
    ),
    (
        re.compile(r"\b(?:пишите|пишем|написать)\s+(?:в\s+)?(?:лс|личк|менеджер)\b"),
        4,
        "контакт для отклика",
        False,
    ),
    (re.compile(r"\bотдел\s+кадров\b"), 8, "отдел кадров", False),
    (re.compile(r"\bместа\s+ограничены\b"), 6, "массовый найм", False),
    (re.compile(r"\b(?:паспорт\s+(?:рф|с\s+собой)|18\+|самозанят)"), 4, "условия допуска", False),
    (
        re.compile(r"\b(?:бесплатн[a-zа-яё-]*\s+)?(?:проживание|общежитие|хостел)\b"),
        4,
        "проживание от работодателя",
        False,
    ),
    (
        re.compile(r"\b(?:бесплатн[a-zа-яё-]*\s+)?(?:обед|питание)[a-zа-яё-]*\b"),
        3,
        "питание от работодателя",
        False,
    ),
    (re.compile(r"\bвыдается\s+(?:спец[. ]*)?форма\b"), 3, "выдача формы", False),
    (
        re.compile(r"\b(?:мужчины|женщины)\b.{0,45}\b(?:рф|рб|снг)\b", re.DOTALL),
        5,
        "требования к кандидатам",
        False,
    ),
    (re.compile(r"\bдо\s+\d{2}\s+лет\b"), 3, "возрастное требование", False),
    (
        re.compile(r"\b(?:медкнижка|санкнижка|медицинская\s+книжка)\b"),
        4,
        "требование документов",
        False,
    ),
    (
        re.compile(r"\b(?:смены?|график)\b.{0,35}\b(?:день|ночь|\d+\s*/\s*\d+)\b", re.DOTALL),
        4,
        "описание смен",
        False,
    ),
    (re.compile(r'\b(?:ооо|ип)\s+[a-zа-яё0-9"«]'), 4, "организация-работодатель", False),
    (re.compile(r"\bразместил[аи]?\s+объявлени"), 4, "размещенное объявление", False),
    (re.compile(r"\b(?:адрес|ближайшее\s+метро|время)\s*:"), 2, "структурированная заявка", False),
)

SPAM_SIGNALS: tuple[tuple[re.Pattern[str], int, str], ...] = (
    (re.compile(r"\bхотите\s+прорекламировать\b"), 20, "рекламное предложение"),
    (re.compile(r"\bмы\s+разместим\b"), 15, "услуга размещения"),
    (re.compile(r"\bпо\s+вопросам\s+рекламы\b"), 15, "реклама"),
    (re.compile(r"\b(?:переходи|переходите)\s+в\s+группу\b"), 10, "перевод в другую группу"),
    (re.compile(r"\b(?:подпишись|подпишитесь)\b"), 8, "призыв подписаться"),
    (
        re.compile(r"\b(?:продвижение|раскрутка|размещение\s+объявлени)\b"),
        10,
        "продвижение/размещение",
    ),
    (re.compile(r"\bрекламное\s+агентство\b"), 12, "рекламное агентство"),
    (re.compile(r"\b(?:партнерск|онлайн)[a-zа-яё-]*\s+задани"), 10, "партнерские онлайн-задания"),
    (re.compile(r"\bприводить\s+новых\s+людей\b"), 10, "реферальный набор"),
    (re.compile(r"\bпредлагаю\s+услуги\b"), 12, "реклама услуг"),
    (re.compile(r"\b(?:прайс|портфолио)\b"), 8, "коммерческое портфолио"),
    (re.compile(r"\bчто\s+я\s+сделаю\s+для\s+вас\b"), 8, "самореклама услуг"),
    (re.compile(r"(?<!\w)#помогу\b"), 8, "рекламный хештег"),
    (re.compile(r"\bфинансов(?:ых|ые)\s+трудност"), 10, "сомнительное финансовое предложение"),
    (re.compile(r"\bза\s+выполнени[ея]\s+задач\b"), 10, "оплата за задания"),
    (
        re.compile(r"\b(?:заходите|заходи|вступайте|вступай)\s+в\b"),
        10,
        "приглашение в стороннюю группу",
    ),
    (
        re.compile(r"(?:t\.me|telegram\.me)/[a-z0-9_]*bot\?start=", re.IGNORECASE),
        12,
        "реферальная ссылка бота",
    ),
    (re.compile(r"invite\.viber\.com", re.IGNORECASE), 12, "приглашение в Viber"),
    (
        re.compile(r"\bвыплат(?:а|ы)\s+(?:каждый|ежедневно).{0,35}\b(?:день|сутки)\b", re.DOTALL),
        8,
        "обещание ежедневных выплат",
    ),
    (re.compile(r"\bобслуживани[ея]\s+оборудования\b"), 6, "сомнительная подработка"),
)

# Feedback comparison deliberately ignores generic glue words and changing
# dates/prices. It is intended to recognize recurring Telegram templates, not
# to turn one rejected two-word message into a global minus-word.
FEEDBACK_STOP_WORDS = frozenset(
    {
        "а",
        "без",
        "был",
        "была",
        "были",
        "в",
        "вам",
        "вас",
        "все",
        "для",
        "до",
        "его",
        "ее",
        "если",
        "же",
        "за",
        "и",
        "или",
        "из",
        "к",
        "как",
        "мы",
        "на",
        "не",
        "но",
        "о",
        "от",
        "по",
        "при",
        "с",
        "со",
        "так",
        "у",
        "что",
        "это",
    }
)


@dataclass(frozen=True)
class MatchAnalysis:
    matched: bool
    score: int
    reason: str
    keyword: str | None = None
    minus_word: str | None = None


@dataclass(frozen=True)
class MessageTypeAnalysis:
    category: str
    candidate_score: int
    employer_score: int
    spam_score: int
    reason: str


def _normalize_token(token: str) -> str:
    return token.casefold().replace("ё", "е")


def _tokens(value: str) -> list[str]:
    return [_normalize_token(token) for token in TOKEN_RE.findall(value)]


def _positive_text(value: str) -> str:
    # Positive keywords should not be satisfied by a username, URL or hashtag.
    value = URL_RE.sub(" ", value)
    value = USERNAME_RE.sub(" ", value)
    value = HASHTAG_RE.sub(" ", value)
    return value


def _plain_text(value: str) -> str:
    return SPACE_RE.sub(" ", value.casefold().replace("ё", "е")).strip()


def _stem_token(token: str) -> str:
    token = _normalize_token(token)
    if token in PROTECTED_INTENT_WORDS or token.isdigit() or len(token) <= 4:
        return token

    for ending in RU_INFLECTION_ENDINGS:
        if token.endswith(ending) and len(token) - len(ending) >= 4:
            return token[: -len(ending)]
    if token.endswith("ь") and len(token) >= 6:
        return token[:-1]
    return token


def _feedback_signature(value: str) -> set[str]:
    cleaned = URL_RE.sub(" ", value)
    cleaned = USERNAME_RE.sub(" ", cleaned)
    signature: set[str] = set()
    for token in _tokens(cleaned):
        if token.isdigit():
            signature.add("#")
            continue
        if len(token) < 3 or token in FEEDBACK_STOP_WORDS:
            continue
        signature.add(_stem_token(token))
    return signature


def _feedback_similarity(left: str, right: str) -> float:
    if _plain_text(left) == _plain_text(right):
        return 1.0

    left_tokens = _feedback_signature(left)
    right_tokens = _feedback_signature(right)
    if min(len(left_tokens), len(right_tokens)) < 4:
        return 0.0

    shared = len(left_tokens & right_tokens)
    if shared < 4:
        return 0.0

    containment = shared / min(len(left_tokens), len(right_tokens))
    jaccard = shared / len(left_tokens | right_tokens)
    if shared < 6 and containment < 0.8:
        return 0.0
    return max(jaccard, containment * 0.9)


def _feedback_decision(
    text: str,
    examples: Iterable[tuple[str, bool]],
) -> tuple[bool | None, int]:
    best_relevant = 0.0
    best_irrelevant = 0.0
    for example_text, is_relevant in examples:
        if not example_text:
            continue
        similarity = _feedback_similarity(text, example_text)
        if is_relevant:
            best_relevant = max(best_relevant, similarity)
        else:
            best_irrelevant = max(best_irrelevant, similarity)

    threshold = 0.74
    margin = 0.08
    if best_irrelevant >= threshold and best_irrelevant >= best_relevant + margin:
        return False, round(best_irrelevant * 100)
    if best_relevant >= threshold and best_relevant >= best_irrelevant + margin:
        return True, round(best_relevant * 100)
    return None, round(max(best_relevant, best_irrelevant) * 100)


def _build_safe_alias_index() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    raw_result: dict[str, set[str]] = {}
    stem_result: dict[str, set[str]] = {}
    for group in SAFE_TOKEN_GROUPS:
        normalized = {_normalize_token(item) for item in group}
        stems = {_stem_token(item) for item in normalized}
        for item in normalized:
            raw_result[item] = normalized
        for stem in stems:
            stem_result[stem] = stems
    return raw_result, stem_result


SAFE_ALIAS_INDEX, SAFE_STEM_ALIAS_INDEX = _build_safe_alias_index()
EMPLOYMENT_HINT_STEMS = frozenset(_stem_token(value) for value in EMPLOYMENT_HINTS)
PROFESSION_HINT_STEMS = frozenset(_stem_token(value) for value in PROFESSION_HINTS)


def _edit_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if abs(len(left) - len(right)) > 1:
        return 2

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


def _token_match_kind(query_token: str, text_token: str, *, allow_typo: bool) -> str | None:
    query_token = _normalize_token(query_token)
    text_token = _normalize_token(text_token)
    if query_token == text_token:
        return "точно"

    if text_token in SAFE_ALIAS_INDEX.get(query_token, set()):
        return "синоним"

    query_stem = _stem_token(query_token)
    text_stem = _stem_token(text_token)
    if text_stem in SAFE_STEM_ALIAS_INDEX.get(query_stem, set()):
        return "синоним"
    if query_stem == text_stem and len(query_stem) >= 4:
        return "форма"

    if (
        allow_typo
        and query_token not in PROTECTED_INTENT_WORDS
        and text_token not in PROTECTED_INTENT_WORDS
        and len(query_token) >= 7
        and len(text_token) >= 7
        and query_token[:4] == text_token[:4]
        and _edit_distance(query_token, text_token) == 1
    ):
        return "опечатка"

    return None


def _ordered_term_match(
    text_tokens: list[str],
    term_tokens: list[str],
    *,
    allow_typo: bool,
    max_gap: int,
) -> tuple[bool, int, str]:
    if not term_tokens or not text_tokens:
        return False, 0, ""

    scores = {"точно": 100, "форма": 94, "синоним": 90, "опечатка": 84}
    best_match: tuple[int, list[str], list[int]] | None = None

    for start_index, text_token in enumerate(text_tokens):
        first_kind = _token_match_kind(term_tokens[0], text_token, allow_typo=allow_typo)
        if not first_kind:
            continue

        kinds = [first_kind]
        positions = [start_index]
        cursor = start_index
        success = True
        for term_token in term_tokens[1:]:
            found: tuple[int, str] | None = None
            upper = min(len(text_tokens), cursor + max_gap + 2)
            for next_index in range(cursor + 1, upper):
                kind = _token_match_kind(term_token, text_tokens[next_index], allow_typo=allow_typo)
                if kind:
                    found = next_index, kind
                    break
            if found is None:
                success = False
                break
            cursor, kind = found
            positions.append(cursor)
            kinds.append(kind)

        if not success:
            continue

        average = round(sum(scores[kind] for kind in kinds) / len(kinds))
        gaps = positions[-1] - positions[0] - (len(positions) - 1)
        final_score = max(0, average - gaps * 2)
        parts = [
            f"{query}→{text_tokens[position]} ({kind})"
            for query, position, kind in zip(term_tokens, positions, kinds, strict=True)
        ]
        candidate = final_score, parts, positions
        if best_match is None or candidate[0] > best_match[0]:
            best_match = candidate

    if best_match is None:
        return False, 0, ""

    score, parts, _positions = best_match
    return True, score, "; ".join(parts)


def _term_match_details(
    text: str,
    term: str,
    *,
    positive: bool,
    allow_typo: bool,
) -> tuple[bool, int, str]:
    term_tokens = _tokens(term.strip())
    if not term_tokens:
        return False, 0, ""

    searchable = _positive_text(text) if positive else text
    text_tokens = _tokens(searchable)
    max_gap = 0 if len(term_tokens) == 1 else 3
    matched, score, reason = _ordered_term_match(
        text_tokens,
        term_tokens,
        allow_typo=allow_typo,
        max_gap=max_gap,
    )
    if not matched:
        return False, 0, ""

    if score == 100 and len(term_tokens) > 1:
        return True, score, f"точная фраза: {term.strip()}"
    return True, score, reason


def _is_candidate_search(keywords: list[str]) -> bool:
    for keyword in keywords:
        normalized = _plain_text(keyword)
        tokens = _tokens(keyword)
        stems = {_stem_token(token) for token in tokens}
        if normalized in {"ищу", "ищу работу", "нужна работа", "нужна подработка"}:
            return True
        if stems & EMPLOYMENT_HINT_STEMS or stems & PROFESSION_HINT_STEMS:
            return True
        if any(pattern.search(normalized) for pattern in CANDIDATE_QUALIFIER_PATTERNS):
            return True
        if any(
            fragment in normalized
            for fragment in ("готов выйти", "есть опыт", "работал", "работала", "работаю")
        ):
            return True
    return False


def _sum_signals(
    text: str,
    signals: tuple[tuple[re.Pattern[str], int, str], ...],
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    for pattern, weight, label in signals:
        if pattern.search(text):
            score += weight
            reasons.append(label)
    return score, reasons


def _message_type_analysis(text: str) -> MessageTypeAnalysis:
    plain = _plain_text(text)
    candidate_score, candidate_reasons = _sum_signals(plain, CANDIDATE_SIGNALS)
    spam_score, spam_reasons = _sum_signals(plain, SPAM_SIGNALS)

    employer_score = 0
    employer_reasons: list[str] = []
    hard_employer = False
    for pattern, weight, label, hard in EMPLOYER_SIGNALS:
        if pattern.search(plain):
            employer_score += weight
            employer_reasons.append(label)
            hard_employer = hard_employer or hard

    hashtag_count = len(HASHTAG_RE.findall(text))
    contact_count = len(USERNAME_RE.findall(text)) + len(re.findall(r"\+?\d[\d\s()\-]{8,}\d", text))
    if hashtag_count >= 6 and contact_count:
        spam_score += 6
        spam_reasons.append("массовые хештеги и контакты")
    if contact_count >= 3:
        employer_score += 3
        employer_reasons.append("повторяющиеся контакты")

    if spam_score >= 8:
        return MessageTypeAnalysis(
            "spam",
            candidate_score,
            employer_score,
            spam_score,
            ", ".join(spam_reasons[:3]),
        )

    # Strong first-person candidate intent may contain words such as "вакансия",
    # "оплата" or "график". It wins over weak vacancy formatting, but not over
    # hard recruitment templates such as "требуются" or "нужен 1 грузчик".
    if hard_employer and candidate_score < 18:
        return MessageTypeAnalysis(
            "employer",
            candidate_score,
            employer_score,
            spam_score,
            ", ".join(employer_reasons[:4]),
        )
    if employer_score >= 12 and employer_score >= candidate_score + 3:
        return MessageTypeAnalysis(
            "employer",
            candidate_score,
            employer_score,
            spam_score,
            ", ".join(employer_reasons[:4]),
        )
    if candidate_score >= 8:
        return MessageTypeAnalysis(
            "candidate",
            candidate_score,
            employer_score,
            spam_score,
            ", ".join(candidate_reasons[:3]),
        )
    if employer_score >= 8:
        return MessageTypeAnalysis(
            "employer",
            candidate_score,
            employer_score,
            spam_score,
            ", ".join(employer_reasons[:4]),
        )
    return MessageTypeAnalysis(
        "unknown", candidate_score, employer_score, spam_score, "нет сильных признаков"
    )


def analyze_match(
    text: str | None,
    keywords: list[str],
    minus_words: list[str],
    *,
    feedback_examples: Iterable[tuple[str, bool]] = (),
) -> MatchAnalysis:
    if not text:
        return MatchAnalysis(False, 0, "нет текста")

    best_keyword: tuple[int, str, str] | None = None
    for keyword in keywords:
        matched, score, reason = _term_match_details(
            text,
            keyword,
            positive=True,
            allow_typo=True,
        )
        if matched and (best_keyword is None or score > best_keyword[0]):
            best_keyword = score, keyword, reason

    if best_keyword is None:
        return MatchAnalysis(False, 0, "ключевые слова не найдены")

    for minus_word in minus_words:
        matched, _score, reason = _term_match_details(
            text,
            minus_word,
            positive=False,
            allow_typo=False,
        )
        if matched:
            return MatchAnalysis(
                False,
                0,
                f"сработало минус-слово «{minus_word}»: {reason}",
                keyword=best_keyword[1],
                minus_word=minus_word,
            )

    feedback_verdict, feedback_similarity = _feedback_decision(text, feedback_examples)
    if feedback_verdict is False:
        return MatchAnalysis(
            False,
            0,
            f"автообучение: похоже на ранее отмеченное «Не подходит» ({feedback_similarity}%)",
            keyword=best_keyword[1],
        )

    if _is_candidate_search(keywords):
        message_type = _message_type_analysis(text)
        if message_type.category in {"employer", "spam"}:
            return MatchAnalysis(
                False,
                0,
                (
                    f"автофильтр: {message_type.category}; {message_type.reason}; "
                    f"candidate={message_type.candidate_score}, "
                    f"employer={message_type.employer_score}, spam={message_type.spam_score}"
                ),
                keyword=best_keyword[1],
            )

        # Generic keys such as "работа", a profession or even "ищу" are not
        # enough on their own. Candidate searches need an actual first-person
        # job-seeking signal. A user's positive feedback can explicitly teach
        # the search an unusual but recurring candidate wording.
        if message_type.category != "candidate" and feedback_verdict is not True:
            return MatchAnalysis(
                False,
                0,
                (
                    "автофильтр: недостаточно признаков, что сообщение написал соискатель; "
                    f"candidate={message_type.candidate_score}, "
                    f"employer={message_type.employer_score}, spam={message_type.spam_score}"
                ),
                keyword=best_keyword[1],
            )

    score, keyword, reason = best_keyword
    if feedback_verdict is True:
        reason = f"{reason}; подтверждено похожей оценкой «Подходит» ({feedback_similarity}%)"
    return MatchAnalysis(True, score, reason, keyword=keyword)


def is_match(text: str | None, keywords: list[str], minus_words: list[str]) -> bool:
    return analyze_match(text, keywords, minus_words).matched
