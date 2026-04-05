from dataclasses import dataclass
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.cache.local_cache import AsyncSnapshotCache

_global_ctx: Optional["AppContext"] = None


@dataclass
class AppContext:
    session_factory: async_sessionmaker[AsyncSession]
    cache: AsyncSnapshotCache
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
