from pyrogram import Client

from src.core.context import AppContext
from src.core.plugin import Plugin, register

from . import handlers  # Register handlers early


class AdminPanelPlugin(Plugin):
    name = "admin_panel"
    priority = 100

    async def setup(self, client: Client, ctx: AppContext) -> None:
        pass


register(AdminPanelPlugin())
