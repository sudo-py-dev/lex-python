from pyrogram import Client

from src.core.context import AppContext
from src.core.plugin import Plugin, register


class AIAssistantPlugin(Plugin):
    name = "ai_assistant"
    priority = 50

    async def setup(self, client: Client, ctx: AppContext) -> None:
        from loguru import logger

        from . import handlers

        logger.debug("AI Assistant Plugin: Loaded and configured.")


register(AIAssistantPlugin())
