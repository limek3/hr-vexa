import asyncio
import getpass

from telethon.errors import SessionPasswordNeededError

from app.core.config import get_settings
from app.monitor.client import build_telegram_client


async def main() -> None:
    settings = get_settings()
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        raise RuntimeError("TELEGRAM_API_ID and TELEGRAM_API_HASH are required")

    client = build_telegram_client()
    await client.connect()

    phone = input("Phone number, for example +79990000000: ").strip()
    if not phone:
        raise RuntimeError("Phone number is required")

    sent = await client.send_code_request(phone)
    code = input("Code from Telegram, or type sms to request SMS: ").strip()
    if code.casefold() == "sms":
        sent = await client.send_code_request(phone, force_sms=True)
        code = input("SMS code: ").strip()

    try:
        await client.sign_in(phone=phone, code=code, phone_code_hash=sent.phone_code_hash)
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
