import asyncio
import logging

from app.bot.client import create_bot
from app.bot.factory import create_dispatcher
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.init import init_models


async def main(init_db: bool = True) -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is required")

    if init_db:
        await init_models()

    bot = create_bot(settings.bot_token, settings.bot_proxy_url)
    dp = create_dispatcher()

    logging.getLogger(__name__).info("Bot polling started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
