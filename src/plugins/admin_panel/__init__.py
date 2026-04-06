from pyrogram import Client

from src.core.context import AppContext
from src.core.plugin import Plugin, register


class AdminPanelPlugin(Plugin):
    name = "admin_panel"
    priority = 100

    async def setup(self, client: Client, ctx: AppContext) -> None:
        from . import handlers


register(AdminPanelPlugin())
