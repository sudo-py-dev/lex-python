import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

load_dotenv()


def make_engine(url: str | None = None, *, echo: bool = False):
    """
    Creates an asynchronous engine for database operations.
    Supports asynchronous Postgres via asyncpg.
    """
    if url is None:
        url = os.getenv("DATABASE_URL")

    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")

    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    return create_async_engine(
        url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=echo,
        future=True,
    )


engine = make_engine()
