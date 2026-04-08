from loguru import logger
from pyrogram import Client, filters
from pyrogram.types import Message, ReplyKeyboardRemove

from src.cache.local_cache import get_cache
from src.core.bot import bot
from src.utils.i18n import at

from ..repository import get_chat_settings, update_chat_setting
from .moderation_kbs import logging_kb


@bot.on_message(filters.private, group=-1)
async def logging_picker_debug_handler(client: Client, message: Message) -> None:
    """Debug handler to inspect all private messages for chat_shared attributes."""
    cache = get_cache()
    user_id = message.from_user.id

    is_picking = await cache.exists(f"ap:logging_picker:{user_id}")

    if message.chat_shared or is_picking:
        logger.debug(
            f"LOGGING PICKER DEBUG: msg_id={message.id}, chat_shared={message.chat_shared is not None}, is_picking={is_picking}"
        )

        if message.chat_shared:
            await logging_picker_handler(client, message)
            return

        cancel_text = await at(user_id, "common.btn_cancel")
        if message.text == cancel_text:
            await logging_picker_cancel_handler(client, message)
            return

    await message.continue_propagation()


async def logging_picker_handler(client: Client, message: Message) -> None:
    """Handles the selection of a logging channel from a ReplyKeyboardMarkup."""
    user_id = message.from_user.id
    logger.debug(f"Received chat_shared from {user_id}: {message.chat_shared}")
    cache = get_cache()

    chat_id = await cache.get(f"ap:logging_picker:{user_id}")
    if not chat_id:
        logger.warning(f"No active logging_picker for user {user_id}")
        return

    new_log_id = message.chat_shared.chat.id
    button_id = message.chat_shared.button_id
    logger.info(f"User {user_id} selected channel {new_log_id} (button_id: {button_id})")

    from src.core.context import get_context

    ctx = get_context()
    await update_chat_setting(ctx, chat_id, "logChannelId", new_log_id)

    await cache.delete(f"ap:logging_picker:{user_id}")
    kb = await logging_kb(ctx, chat_id, user_id=user_id)
    settings = await get_chat_settings(ctx, chat_id)

    await message.reply(
        await at(
            user_id,
            "panel.logging_set_success",
            title=f"Channel {new_log_id}",
            id=new_log_id,
        ),
        reply_markup=ReplyKeyboardRemove(),
    )

    await message.reply(
        await at(
            user_id,
            "panel.logging_text",
            channel=settings.logChannelId or await at(user_id, "panel.not_set"),
        ),
        reply_markup=kb,
    )


async def logging_picker_cancel_handler(client: Client, message: Message) -> None:
    """Handles textual cancel or other inputs during logging picker mode."""
    if not message.text:
        return

    user_id = message.from_user.id
    cache = get_cache()

    chat_id = await cache.get(f"ap:logging_picker:{user_id}")
    if not chat_id:
        return

    from src.utils.i18n import list_locales, t

    is_cancel = False
    for lang in list_locales():
        if message.text == t(lang, "common.btn_cancel"):
            is_cancel = True
            break

    if is_cancel:
        logger.info(f"User {user_id} canceled logging selection.")
        await cache.delete(f"ap:logging_picker:{user_id}")

        from src.core.context import get_context

        ctx = get_context()
        kb = await logging_kb(ctx, chat_id, user_id=user_id)
        settings = await get_chat_settings(ctx, chat_id)

        await message.reply(
            await at(user_id, "panel.logging_cancel_text"),
            reply_markup=ReplyKeyboardRemove(),
        )

        await message.reply(
            await at(
                user_id,
                "panel.logging_text",
                channel=settings.logChannelId or await at(user_id, "panel.not_set"),
            ),
            reply_markup=kb,
        )
