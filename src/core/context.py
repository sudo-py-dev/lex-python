from dataclasses import dataclass
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_global_ctx: Optional["AppContext"] = None


@dataclass
class AppContext:
    session_factory: async_sessionmaker[AsyncSession]
    redis: Redis
    scheduler: AsyncIOScheduler

    @property
    def db(self) -> async_sessionmaker[AsyncSession]:
        return self.session_factory


def set_context(ctx: AppContext) -> None:
    global _global_ctx
    _global_ctx = ctx


def get_context() -> AppContext:
    if _global_ctx is None:
        raise RuntimeError("AppContext is not initialized")
    return _global_ctx
