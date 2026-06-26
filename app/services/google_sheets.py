from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.repositories.messages import list_matches_for_export
from app.services.contacts import extract_phone, extract_username


HEADERS = [
    "created_at",
    "search",
    "source",
    "telegram",
    "phone",
    "message",
    "url",
]


class GoogleSheetsNotConfiguredError(RuntimeError):
    pass


def _worksheet():
    settings = get_settings()
    if not settings.google_service_account_json or not settings.google_sheet_id:
        raise GoogleSheetsNotConfiguredError("GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_SHEET_ID are required")

    import gspread
    from google.oauth2.service_account import Credentials

    info = json.loads(settings.google_service_account_json)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = Credentials.from_service_account_info(info, scopes=scopes)
    client = gspread.authorize(credentials)
    sheet = client.open_by_key(settings.google_sheet_id)
    try:
        worksheet = sheet.worksheet("HR Vexa")
    except gspread.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title="HR Vexa", rows=1000, cols=len(HEADERS))
    return worksheet, settings.google_sheet_id


async def export_contacts_to_google_sheets(session: AsyncSession, *, user_id: int) -> tuple[int, str]:
    rows = await list_matches_for_export(session, user_id=user_id)
    worksheet, sheet_id = _worksheet()

    values = [HEADERS]
    for match, search, source, message in rows:
        text = message.text or ""
        values.append(
            [
                _format_dt(match.created_at),
                search.title,
                source.title or source.input_ref,
                extract_username(text),
                extract_phone(text),
                text[:1000],
                message.url or "",
            ],
        )

    worksheet.clear()
    worksheet.update(values=values, range_name="A1")
    return max(len(values) - 1, 0), f"https://docs.google.com/spreadsheets/d/{sheet_id}"


def _format_dt(value: datetime) -> str:
    return value.isoformat(timespec="seconds") if value else ""
