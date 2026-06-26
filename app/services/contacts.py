from __future__ import annotations

import re


PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
USERNAME_RE = re.compile(r"(?<!\w)@([A-Za-z0-9_]{5,32})")


def extract_phone(text: str) -> str:
    match = PHONE_RE.search(text)
    if not match:
        return ""
    phone = re.sub(r"\s+", " ", match.group(0)).strip()
    return phone if len(re.sub(r"\D", "", phone)) >= 8 else ""


def extract_username(text: str) -> str:
    match = USERNAME_RE.search(text)
    return f"@{match.group(1)}" if match else ""
