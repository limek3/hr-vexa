import asyncio
import logging

from app.bot.main import main as run_bot
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.init import init_models
from app.monitor.main import main as run_monitor

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    await init_models()
    logger.info("Starting combined worker: bot + monitor")
    await asyncio.gather(run_bot(init_db=False), run_monitor(init_db=False))


if __name__ == "__main__":
    asyncio.run(main())
