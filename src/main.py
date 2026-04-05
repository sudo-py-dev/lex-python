import asyncio
import contextlib
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from src.cache.local_cache import get_cache
from src.config import config
from src.core.context import AppContext, set_context
from src.core.plugin import autodiscover, get_plugins
from src.db.client import AsyncSessionLocal, disconnect_db
from src.utils.logger import setup_logger


def run() -> None:
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())


async def main() -> None:
    setup_logger()

    from src.core.bot import bot

    logger.info(f"Starting {config.BOT_NAME}...")

    cache = get_cache()
    await cache.load_snapshot()

    scheduler = AsyncIOScheduler()
    scheduler.start()

    scheduler.add_job(cache.save_snapshot, "interval", minutes=4, id="cache_snapshot")

    ctx = AppContext(session_factory=AsyncSessionLocal, cache=cache, scheduler=scheduler)
    set_context(ctx)

    autodiscover("src.plugins")
    for plugin in get_plugins():
        try:
            await plugin.setup(bot, ctx)
            logger.debug(f"Plugin initialized: {plugin.name}")
        except Exception as e:
            logger.error(f"Failed to initialize plugin {plugin.name}: {e}")

    try:
        async with bot:
            logger.info(f"{config.BOT_NAME} is running!")
            await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.warning(f"{config.BOT_NAME} is shutting down...")
    except Exception as e:
        logger.exception(f"{config.BOT_NAME} execution failed: {e}")
    finally:
        for plugin in reversed(get_plugins()):
            try:
                await asyncio.wait_for(plugin.teardown(), timeout=5.0)
            except Exception as e:
                logger.error(f"Failed to teardown plugin {plugin.name}: {e}")

        scheduler.shutdown(wait=False)
        await cache.save_snapshot()
        await disconnect_db()

        if bot.is_connected:
            try:
                logger.debug("Closing Telegram connection...")
                await asyncio.wait_for(bot.stop(block=False), timeout=10.0)
            except (TimeoutError, Exception) as e:
                logger.warning(f"Forced Telegram connection closure after timeout: {e}")

        logger.debug(f"{config.BOT_NAME} shutdown complete.")


if __name__ == "__main__":
    run()
