from pyrogram import Client

from src.core.context import AppContext
from src.core.plugin import Plugin, register

_ctx: AppContext | None = None


def get_ctx() -> AppContext:
    if _ctx is None:
        raise RuntimeError("AI Assistant plugin not initialized")
    return _ctx


class AIAssistantPlugin(Plugin):
    name = "ai_assistant"
    priority = 50

    async def setup(self, client: Client, ctx: AppContext) -> None:
        global _ctx
        _ctx = ctx
        from loguru import logger

        from . import handlers

        logger.debug("AI Assistant Plugin: Loaded and configured.")


register(AIAssistantPlugin())
