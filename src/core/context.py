from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.cache.local_cache import AsyncSnapshotCache

_context_var: ContextVar[AppContext] = ContextVar("app_context")


@dataclass(frozen=True)
class AppContext:
    db: async_sessionmaker[AsyncSession]
    cache: AsyncSnapshotCache
    scheduler: AsyncIOScheduler


def set_context(ctx: AppContext) -> None:
    _context_var.set(ctx)


def get_context() -> AppContext:
    try:
        return _context_var.get()
    except LookupError:
        raise RuntimeError("AppContext is not initialized") from None
