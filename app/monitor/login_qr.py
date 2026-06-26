import asyncio
import getpass

import qrcode
from telethon.errors import SessionPasswordNeededError

from app.core.config import get_settings
from app.monitor.client import build_telegram_client


async def main() -> None:
    settings = get_settings()
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        raise RuntimeError("TELEGRAM_API_ID and TELEGRAM_API_HASH are required")

    client = build_telegram_client()
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
