from pyrogram import Client

from src.core.context import AppContext
from src.core.plugin import Plugin, register

_ctx: AppContext | None = None


def get_ctx() -> AppContext:
    if _ctx is None:
        raise RuntimeError("Channel Protect plugin not initialized")
    return _ctx


class ChannelProtectPlugin(Plugin):
    name = "channel_protect"
    priority = 18

    async def setup(self, client: Client, ctx: AppContext) -> None:
        global _ctx
        _ctx = ctx
        from . import handlers


register(ChannelProtectPlugin())
