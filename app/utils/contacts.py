import re
from dataclasses import dataclass
from urllib.parse import quote


USERNAME_RE = re.compile(r"(?<![\w])@(?P<username>[A-Za-z0-9_]{5,32})")
PHONE_RE = re.compile(
    r"(?<!\d)(?P<phone>\+?\d[\d\s().-]{8,}\d)(?!\d)",
)


@dataclass(frozen=True)
class ContactCandidate:
    kind: str
    value: str
    url: str


def find_contact(text: str | None) -> ContactCandidate | None:
    if not text:
        return None

    username_match = USERNAME_RE.search(text)
    if username_match:
        username = username_match.group("username")
        return ContactCandidate(
            kind="telegram",
            value=f"@{username}",
            url=f"https://t.me/{username}",
        )

    phone_match = PHONE_RE.search(text)
    if phone_match:
        normalized = normalize_phone(phone_match.group("phone"))
        if normalized:
            return ContactCandidate(
                kind="phone",
                value=pretty_phone(normalized),
                url=f"tg://resolve?phone={quote(normalized.lstrip('+'))}",
            )

    return None


def normalize_phone(raw_phone: str) -> str | None:
    has_plus = raw_phone.strip().startswith("+")
    digits = re.sub(r"\D", "", raw_phone)
    if len(digits) < 10 or len(digits) > 15:
        return None
    return f"+{digits}" if has_plus else digits


def pretty_phone(phone: str) -> str:
    return phone if phone.startswith("+") else f"+{phone}"


def build_dm_text(search_title: str, source_title: str) -> str:
    return (
        "Здравствуйте! Увидел(а) ваше сообщение в Telegram.\n\n"
        f"Пишу по поводу: {search_title}.\n"
        f"Источник: {source_title}.\n\n"
        "Подскажите, пожалуйста, актуально ли еще предложение/поиск?"
    )
