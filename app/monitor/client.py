from telethon import TelegramClient
from telethon.network.connection.tcpabridged import ConnectionTcpAbridged
from telethon.sessions import StringSession

from app.core.config import get_settings


def build_telegram_client() -> TelegramClient:
    settings = get_settings()
    return TelegramClient(
        StringSession(settings.telegram_session_string or None),
        settings.telegram_api_id,
        settings.telegram_api_hash,
        connection=ConnectionTcpAbridged,
        connection_retries=5,
        retry_delay=3,
        timeout=20,
        auto_reconnect=True,
    )
