from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode


def create_bot(token: str, proxy_url: str = "") -> Bot:
    session = AiohttpSession(timeout=120, proxy=proxy_url or None)
    return Bot(
        token=token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
