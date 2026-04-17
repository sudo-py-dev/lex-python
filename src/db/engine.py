from sqlalchemy.ext.asyncio import create_async_engine

from src.config import config


def make_engine(url: str | None = None, *, echo: bool = False):
    target_url = url or config.async_db_url

    if not target_url:
        raise RuntimeError("DATABASE_URL environment variable is not set")

    return create_async_engine(
        target_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=echo,
        future=True,
    )


engine = make_engine()
