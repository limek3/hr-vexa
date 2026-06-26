import asyncio
import getpass

import qrcode
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.network.connection.tcpabridged import ConnectionTcpAbridged
from telethon.sessions import StringSession

from app.core.config import get_settings


async def main() -> None:
    settings = get_settings()
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        raise RuntimeError("TELEGRAM_API_ID and TELEGRAM_API_HASH are required")

    client = TelegramClient(
        StringSession(),
        settings.telegram_api_id,
        settings.telegram_api_hash,
        connection=ConnectionTcpAbridged,
        connection_retries=5,
        retry_delay=3,
        timeout=20,
        auto_reconnect=True,
    )
    await client.connect()

    qr_login = await client.qr_login()
    qr = qrcode.QRCode(border=1)
    qr.add_data(qr_login.url)
    qr.make(fit=True)
    qr.print_ascii(invert=True)

    print("\nScan this QR in Telegram:")
    print("Telegram mobile -> Settings -> Devices -> Link Desktop Device")
    print("\nWaiting for QR scan...")

    try:
        await qr_login.wait(timeout=120)
    except SessionPasswordNeededError:
        password = getpass.getpass("Two-step verification password: ")
        await client.sign_in(password=password)

    me = await client.get_me()
    print(f"Logged in as: {getattr(me, 'username', None) or me.id}")
    print("\nTELEGRAM_SESSION_STRING=")
    print(client.session.save())
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
