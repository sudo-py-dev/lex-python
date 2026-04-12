from loguru import logger
from pyrogram import Client, filters
from pyrogram.types import Message, ReplyKeyboardRemove

from src.core.bot import bot
from src.core.context import get_context
from src.utils.i18n import at
from src.utils.local_cache import get_cache
from src.utils.permissions import Permission, check_user_permission

from ..repository import get_chat_settings, update_settings
from .moderation_kbs import logging_kb


@bot.on_message(filters.private & (filters.chat_shared | filters.text), group=-1)
async def on_logging_picker_input(client: Client, message: Message) -> None:
    """Handles channel selection and cancellation for the logging picker."""
    if message.chat_shared:
        await logging_picker_handler(client, message)
        return

    if message.text:
        user_id = message.from_user.id
        cache = get_cache()
        if await cache.exists(f"ap:logging_picker:{user_id}"):
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

    if not await check_user_permission(client, chat_id, user_id, Permission.CAN_BAN):
        await message.reply(
            await at(user_id, "error.admin_no_permission"), reply_markup=ReplyKeyboardRemove()
        )
        await cache.delete(f"ap:logging_picker:{user_id}")
        return

    new_log_id = message.chat_shared.chat.id
    button_id = message.chat_shared.button_id
    logger.debug(f"User {user_id} selected channel {new_log_id} (button_id: {button_id})")

    chat_title = message.chat_shared.chat.title or str(new_log_id)

    ctx = get_context()
    await update_settings(ctx, chat_id, logChannelId=new_log_id, logChannelName=chat_title)

    await cache.delete(f"ap:logging_picker:{user_id}")
    kb = await logging_kb(ctx, chat_id, user_id=user_id)
    settings = await get_chat_settings(ctx, chat_id)

    await message.reply(
        await at(
            user_id,
            "panel.logging_set_success",
            title=chat_title,
            id=new_log_id,
        ),
        reply_markup=ReplyKeyboardRemove(),
    )

    await client.send_message(
        user_id,
        await at(
            user_id,
            "panel.logging_text",
            channel=settings.logChannelName
            or settings.logChannelId
            or await at(user_id, "panel.not_set"),
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
        logger.debug(f"User {user_id} canceled logging selection.")
        await cache.delete(f"ap:logging_picker:{user_id}")

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
                channel=settings.logChannelName
                or settings.logChannelId
                or await at(user_id, "panel.not_set"),
            ),
            reply_markup=kb,
        )
