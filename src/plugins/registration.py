from loguru import logger
from pyrogram import Client, filters
from pyrogram.types import ChatMemberUpdated, Message

from src.core.context import AppContext
from src.core.plugin import Plugin, register
from src.db.repositories.chats import get_chat_settings, update_chat_setting


class RegistrationPlugin(Plugin):
    name = "registration"

    def __init__(self):
        super().__init__()
        self._registered_cache = set()

    async def setup(self, bot: Client, ctx: AppContext) -> None:
        @bot.on_message(filters.group | filters.channel, group=-1)
        async def auto_register_message(client, message: Message):
            await self._ensure_chat_registered(ctx, message.chat)

        @bot.on_chat_member_updated(group=-1)
        async def auto_register_join(client, update: ChatMemberUpdated):
            if update.new_chat_member and update.new_chat_member.user.is_self:
                await self._ensure_chat_registered(ctx, update.chat)

    async def _ensure_chat_registered(self, ctx: AppContext, chat):
        """Ensures the chat is registered with the correct type."""
        if chat.id in self._registered_cache:
            return

        try:
            settings = await get_chat_settings(ctx, chat.id)
            raw_type = chat.type.name.lower()
            chat_type = "group" if raw_type in ("group", "supergroup") else "channel"

            # Update type if it is missing or is different
            if settings.chatType != chat_type or settings.title != chat.title:
                logger.info(f"Registering/Updating chat {chat.id} as {chat_type} ({chat.title})")
                await update_chat_setting(ctx, chat.id, "chatType", chat_type)
                await update_chat_setting(ctx, chat.id, "title", chat.title)

            self._registered_cache.add(chat.id)

        except Exception as e:
            logger.error(f"Failed to auto-register chat {chat.id}: {e}")


register(RegistrationPlugin())
