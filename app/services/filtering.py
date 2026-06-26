def is_match(text: str | None, keywords: list[str], minus_words: list[str]) -> bool:
    if not text:
        return False

    normalized = text.casefold()
    has_keyword = any(keyword.casefold() in normalized for keyword in keywords)
    has_minus_word = any(word.casefold() in normalized for word in minus_words)
    return has_keyword and not has_minus_word
