from pyrogram import Client

from src.core.context import AppContext
from src.core.plugin import Plugin, register

_ctx: AppContext | None = None


def get_ctx() -> AppContext:
    if _ctx is None:
        raise RuntimeError("Privacy plugin not initialized")
    return _ctx


class PrivacyPlugin(Plugin):
    name = "privacy"
    priority = 120

    async def setup(self, client: Client, ctx: AppContext) -> None:
        global _ctx
        _ctx = ctx
        from . import handlers  # noqa: F401


register(PrivacyPlugin())
