import contextlib
import re

from pyrogram import Client, StopPropagation, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.chats import get_chat_settings
from src.db.repositories.stickers import (
    add_blocked_sticker_set,
    get_blocked_sticker_sets,
    is_sticker_set_blocked,
    remove_blocked_sticker_set,
)
from src.utils.decorators import admin_permission_required, safe_handler
from src.utils.i18n import at
from src.utils.input import finalize_input_capture, is_waiting_for_input
from src.utils.moderation import execute_moderation_action, resolve_sender
from src.utils.permissions import Permission, has_permission


class StickersPlugin(Plugin):
    """Plugin to manage sticker set blocking."""

    name = "stickers"
    priority = 45  # Run before generic entity_block (priority 50)

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.command(["addstickerset", "addsticker"]) & filters.group)
@safe_handler
@admin_permission_required(Permission.CAN_RESTRICT)
async def add_stickerset_handler(client: Client, message: Message) -> None:
    if not await has_permission(client, message.chat.id, Permission.CAN_RESTRICT):
        return await message.reply(await at(message.chat.id, "error.bot_no_permission"))
    set_name = None
    if message.reply_to_message and message.reply_to_message.sticker:
        set_name = message.reply_to_message.sticker.set_name
    elif len(message.command) > 1:
        match = re.search(
            r"(?:t\.me/addstickers/|telegram\.me/addstickers/)?([a-zA-Z0-9_]+)", message.command[1]
        )
        if match:
            set_name = match.group(1)

    if not set_name:
        await message.reply(await at(message.chat.id, "stickers.add_usage"))
        return

    ctx = get_context()
    added = await add_blocked_sticker_set(ctx, message.chat.id, set_name)

    if added:
        await message.reply(await at(message.chat.id, "stickers.added_blocked", set_name=set_name))
    else:
        await message.reply(await at(message.chat.id, "stickers.err_already_blocked"))


@bot.on_message(filters.command(["rmstickerset", "rmsticker"]) & filters.group)
@safe_handler
@admin_permission_required(Permission.CAN_RESTRICT)
async def rm_stickerset_handler(client: Client, message: Message) -> None:
    if not await has_permission(client, message.chat.id, Permission.CAN_RESTRICT):
        return await message.reply(await at(message.chat.id, "error.bot_no_permission"))
    set_name = None
    if message.reply_to_message and message.reply_to_message.sticker:
        set_name = message.reply_to_message.sticker.set_name
    elif len(message.command) > 1:
        match = re.search(
            r"(?:t\.me/addstickers/|telegram\.me/addstickers/)?([a-zA-Z0-9_]+)", message.command[1]
        )
        if match:
            set_name = match.group(1)

    if not set_name:
        await message.reply(await at(message.chat.id, "stickers.rm_usage"))
        return

    ctx = get_context()
    removed = await remove_blocked_sticker_set(ctx, message.chat.id, set_name)

    if removed:
        await message.reply(await at(message.chat.id, "stickers.removed", set_name=set_name))
    else:
        await message.reply(await at(message.chat.id, "stickers.not_found"))


@bot.on_message(filters.command("stickers") & filters.group)
@safe_handler
@admin_permission_required(Permission.CAN_RESTRICT)
async def list_stickersets_handler(client: Client, message: Message) -> None:
    if not await has_permission(client, message.chat.id, Permission.CAN_RESTRICT):
        return await message.reply(await at(message.chat.id, "error.bot_no_permission"))
    ctx = get_context()
    blocked_sets = await get_blocked_sticker_sets(ctx, message.chat.id)
    if not blocked_sets:
        await message.reply(await at(message.chat.id, "stickers.list_empty"))
        return

    text = await at(message.chat.id, "stickers.list_header")
    for s in blocked_sets:
        text += f"\n• `{s.setName}`"

    await message.reply(text)


@bot.on_message(filters.group & filters.sticker, group=-35)
@safe_handler
async def sticker_interceptor(client: Client, message: Message) -> None:
    if not message.sticker or not message.sticker.set_name:
        return

    user_id, _, is_white = await resolve_sender(client, message)
    if not user_id or is_white:
        return

    ctx = get_context()
    is_blocked = await is_sticker_set_blocked(ctx, message.chat.id, message.sticker.set_name)

    if is_blocked:
        settings = await get_chat_settings(ctx, message.chat.id)
        action = settings.stickerAction or "delete"

        reason = await at(message.chat.id, "stickers.violation_reason")
        acted = await execute_moderation_action(
            client=client,
            message=message,
            action=action,
            reason=reason,
            log_tag="StickerBlock",
            violation_key="stickers.violation_notice",
            set_name=message.sticker.set_name,
        )
        if acted:
            raise StopPropagation


@bot.on_message(
    filters.private & (filters.sticker | filters.text) & is_waiting_for_input("stickerInput"),
    group=-50,
)
@safe_handler
async def on_sticker_input(client: Client, message: Message):
    """Handle sticker or set link sent in admin panel input capture flow."""
    user_id = message.from_user.id
    state = message.input_state
    chat_id = state["chat_id"]
    page = state.get("page", 0)
    prompt_msg_id = state.get("prompt_msg_id")

    set_name = None
    if message.sticker and message.sticker.set_name:
        set_name = message.sticker.set_name
    elif message.text:
        match = re.search(
            r"(?:https?://)?(?:t\.me|telegram\.me)/addstickers/([a-zA-Z0-9_]+)|^([a-zA-Z0-9_]+)$",
            message.text.strip(),
        )
        if match:
            set_name = match.group(1) or match.group(2)

    if not set_name:
        await message.reply(await at(chat_id, "stickers.err_not_in_set"))
        return

    ctx = get_context()
    added = await add_blocked_sticker_set(ctx, chat_id, set_name)

    from src.plugins.admin_panel.handlers.callbacks.common import _panel_lang_id
    from src.plugins.admin_panel.handlers.moderation_kbs import stickers_kb

    at_id = _panel_lang_id(True, user_id, chat_id)

    if not added:
        with contextlib.suppress(Exception):
            await message.delete()
        await client.send_message(user_id, await at(at_id, "stickers.err_already_blocked"))
        return

    panel_text = await at(at_id, "panel.stickers_text")
    kb = await stickers_kb(ctx, chat_id, page, user_id=user_id)
    await finalize_input_capture(client, message, user_id, prompt_msg_id, panel_text, kb)


register(StickersPlugin())
