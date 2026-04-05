from pyrogram import Client

from src.core.context import AppContext
from src.core.plugin import Plugin, register


class AdminPlugin(Plugin):
    name = "admin"
    priority = 100

    async def setup(self, client: Client, ctx: AppContext) -> None:
        from . import handlers  # noqa: F401


register(AdminPlugin())
