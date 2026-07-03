from __future__ import annotations

import re
from collections.abc import Iterable

from app.bot.formatting import heading, text_value


FORBIDDEN_SEARCH_TERMS = {
    # drugs and controlled substances
    "наркотик",
    "наркотики",
    "наркота",
    "закладка",
    "закладки",
    "кладмен",
    "клад",
    "мефедрон",
    "меф",
    "амфетамин",
    "амф",
    "кокаин",
    "героин",
    "метадон",
    "экстази",
    "мдма",
    "lsd",
    "лсд",
    "марихуана",
    "каннабис",
    "гашиш",
    "спайс",
    "соль",
    "соли",
    "метамфетамин",
    "псилоцибин",
    "мухомор",
    "грибы",
    "тгк",
    "thc",
    "cbd",
    "mdma",
    "cocaine",
    "heroin",
    "meth",
    "amphetamine",
    "marijuana",
    "cannabis",
    "weed",
    "hash",
    # sexual exploitation and adult content
    "порно",
    "порнография",
    "эротика",
    "интим",
    "интим услуги",
    "проституция",
    "эскорт",
    "секс услуги",
    "секс-услуги",
    "вебкам",
    "webcam",
    "onlyfans",
    "онлифанс",
    "adult",
    "porn",
    "porno",
    "escort",
    "prostitution",
    "sex work",
    # terrorism and extremism
    "терроризм",
    "террорист",
    "террористы",
    "теракт",
    "смертник",
    "взрывчатка",
    "бомба",
    "бомбы",
    "игил",
    "isis",
    "isil",
    "daesh",
    "аль-каида",
    "al qaeda",
    "хамас",
    "hаmas",
    "terrorism",
    "terrorist",
    "bomb",
    "explosive",
    "explosives",
    # weapons, violence, illegal arms
    "оружие",
    "огнестрел",
    "пистолет",
    "автомат",
    "граната",
    "патроны",
    "боеприпасы",
    "ствол",
    "киллер",
    "убийство",
    "weapon",
    "gun",
    "firearm",
    "ammo",
    "ammunition",
    "grenade",
    "hitman",
    # fraud and financial crime
    "обнал",
    "обналичка",
    "дроп",
    "дропы",
    "кардинг",
    "скимминг",
    "фишинг",
    "скам",
    "мамонт",
    "отмыв",
    "поддельные документы",
    "купить паспорт",
    "купить права",
    "carding",
    "phishing",
    "scam",
    "money mule",
    "fake passport",
    "fake id",
    "laundering",
    # hacking, malware, account theft
    "взлом",
    "хакер",
    "хакеры",
    "ботнет",
    "малварь",
    "вирус",
    "стилер",
    "rat",
    "ddos",
    "ддос",
    "пробив",
    "слив базы",
    "украсть аккаунт",
    "hacking",
    "hacker",
    "malware",
    "botnet",
    "stealer",
    "account theft",
    "credential",
    # self-harm and dangerous services
    "самоубийство",
    "суицид",
    "эвтаназия",
    "suicide",
    "self harm",
    # hate/extremist hiring
    "нацист",
    "нацизм",
    "неонацист",
    "расист",
    "white power",
    "nazi",
    "neo nazi",
}


def normalize_policy_text(value: str) -> str:
    value = value.casefold().replace("ё", "е")
    value = re.sub(r"[^0-9a-zа-я+_\-\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def find_forbidden_terms(values: Iterable[str]) -> list[str]:
    text = normalize_policy_text(" ".join(values))
    found: list[str] = []
    for term in sorted(FORBIDDEN_SEARCH_TERMS, key=len, reverse=True):
        normalized = normalize_policy_text(term)
        if not normalized:
            continue
        pattern = rf"(?<![0-9a-zа-я]){re.escape(normalized)}(?![0-9a-zа-я])"
        if re.search(pattern, text):
            found.append(term)
    return found


def forbidden_terms_message(found: list[str]) -> str:
    visible = ", ".join(found[:8])
    suffix = "..." if len(found) > 8 else ""
    return (
        f"{heading('⚠️ Поиск запрещен')}\n"
        "\n"
        "Vexa нельзя использовать для поиска запрещенных тем: наркотики, порно, "
        "терроризм, оружие, мошенничество, взлом и другие незаконные направления.\n\n"
        f"{text_value('Найдено в запросе', f'{visible}{suffix}')}"
    )
