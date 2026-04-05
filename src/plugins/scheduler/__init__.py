from datetime import UTC, datetime

from loguru import logger
from pyrogram import Client
from sqlalchemy import select

from src.core.context import AppContext
from src.core.plugin import Plugin, register

_ctx: AppContext | None = None


def get_ctx() -> AppContext:
    if _ctx is None:
        raise RuntimeError("Scheduler plugin not initialized")
    return _ctx


class SchedulerPlugin(Plugin):
    name = "scheduler"
    priority = 90

    async def setup(self, client: Client, ctx: AppContext) -> None:
        global _ctx
        _ctx = ctx

        from .manager import SchedulerManager

        await SchedulerManager.sync_all(ctx)


register(SchedulerPlugin())
