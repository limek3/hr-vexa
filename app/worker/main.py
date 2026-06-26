import asyncio
import logging

from telethon.errors import AuthKeyDuplicatedError

from app.bot.main import main as run_bot
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.init import init_models
from app.monitor.main import main as run_monitor

logger = logging.getLogger(__name__)


async def run_monitor_forever() -> None:
    while True:
        try:
            await run_monitor(init_db=False)
        except AuthKeyDuplicatedError:
            logger.exception(
                "MTProto session is invalid: TELEGRAM_SESSION_STRING was used from multiple "
                "places. Generate a new session string and update Railway variables.",
            )
            await asyncio.sleep(300)
        except Exception:
            logger.exception("Monitor crashed; restarting in 30 seconds")
            await asyncio.sleep(30)


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    await init_models()
    logger.info("Starting combined worker: bot + monitor")
    await asyncio.gather(run_bot(init_db=False), run_monitor_forever())


if __name__ == "__main__":
    asyncio.run(main())
