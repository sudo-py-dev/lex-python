from pyrogram import Client

from src.core.context import AppContext
from src.core.plugin import Plugin, register

_ctx: AppContext | None = None


def get_ctx() -> AppContext:
    if _ctx is None:
        raise RuntimeError("Slowmode plugin not initialized")
    return _ctx


class SlowmodePlugin(Plugin):
    name = "slowmode"
    priority = 8

    async def setup(self, client: Client, ctx: AppContext) -> None:
        global _ctx
        _ctx = ctx
        from . import handlers


register(SlowmodePlugin())
