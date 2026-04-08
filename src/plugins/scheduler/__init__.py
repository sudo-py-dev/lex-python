from pyrogram import Client

from src.core.plugin import Plugin, register

from . import handlers  # noqa: E402
from .manager import SchedulerManager


class SchedulerPlugin(Plugin):
    name = "scheduler"
    priority = 90

    async def setup(self, client: Client, ctx) -> None:
        await SchedulerManager.sync_all(ctx)


register(SchedulerPlugin())
