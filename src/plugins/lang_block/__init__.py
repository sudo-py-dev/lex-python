from pyrogram import Client

from src.core.context import AppContext
from src.core.plugin import Plugin, register

_ctx: AppContext | None = None


def get_ctx() -> AppContext:
    if _ctx is None:
        raise RuntimeError("LangBlock plugin not initialized")
    return _ctx


class LangBlockPlugin(Plugin):
    name = "lang_block"
    priority = 50

    async def setup(self, client: Client, ctx: AppContext) -> None:
        global _ctx
        _ctx = ctx
        # Import handlers to register them
        from . import handlers  # noqa: F401


register(LangBlockPlugin())
