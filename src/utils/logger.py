import sys

from loguru import logger

from src.config import config


def setup_logger() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=config.LOG_LEVEL,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )
    logger.add(
        "logs/bot.log",
        rotation="10 MB",
        retention="1 week",
        level=config.LOG_LEVEL,
        serialize=True,
        compression="zip",
    )
