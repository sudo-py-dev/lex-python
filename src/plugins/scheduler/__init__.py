from datetime import UTC, datetime

from loguru import logger
from pyrogram import Client
from sqlalchemy import select

from src.core.plugin import Plugin, register


class SchedulerPlugin(Plugin):
    name = "scheduler"
    priority = 90

    async def setup(self, client: Client, ctx) -> None:

        from .manager import SchedulerManager

        await SchedulerManager.sync_all(ctx)


register(SchedulerPlugin())
