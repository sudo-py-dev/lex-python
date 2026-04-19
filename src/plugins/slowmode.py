import contextlib

from pyrogram import Client, StopPropagation, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.core.constants import CacheKeys
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.slowmode import clear_slowmode, get_slowmode, set_slowmode
from src.utils.decorators import admin_permission_required, safe_handler
from src.utils.i18n import at
from src.utils.input import finalize_input_capture, is_waiting_for_input
from src.utils.moderation import resolve_sender
from src.utils.permissions import Permission, has_permission
from src.utils.time_parser import parse_time


class SlowmodePlugin(Plugin):
    """Plugin to manage message frequency for non-admin users."""

    name = "slowmode"
    priority = 80

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.command("slowmode") & filters.group)
@safe_handler
@admin_permission_required(Permission.CAN_RESTRICT)
async def slowmode_handler(client: Client, message: Message) -> None:
    if not await has_permission(client, message.chat.id, Permission.CAN_RESTRICT):
        return await message.reply(await at(message.chat.id, "error.bot_no_permission"))
    """
    Set or clear the slowmode interval for the current chat.

    If no argument is provided, it returns the current slowmode setting.
    Intervals can be specified in seconds or human-readable formats (e.g., 30s, 1m).
    Requires the user to be an admin.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Updates the chat's slowmode settings in the database.
        - Sends an informational or confirmation message.
    """
    ctx = get_context()
    if len(message.command) < 2:
        interval = await get_slowmode(ctx, message.chat.id)
        await message.reply(await at(message.chat.id, "slowmode.current", duration=f"{interval}s"))
        return

    duration_str = message.command[1].lower()
    if duration_str in ("off", "none", "0"):
        await clear_slowmode(ctx, message.chat.id)
        await message.reply(await at(message.chat.id, "slowmode.off"))
        return

    interval = int(parse_time(duration_str))
    if interval <= 0:
        return

    await set_slowmode(ctx, message.chat.id, interval)
    await message.reply(await at(message.chat.id, "slowmode.set", duration=f"{interval}s"))


@bot.on_message(filters.group, group=40)
@safe_handler
async def slowmode_interceptor(client: Client, message: Message) -> None:
    """
    Enforce message frequency limits on non-admin users.

    Checks the cache for a recent message timestamp from the user in the
    current chat. If the user is within the slowmode interval, their
    message is deleted.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object to inspect.

    Side Effects:
        - Deletes the message if the user is violating the slowmode limit.
        - Sets a "cooldown" key in the cache for the user on success.
        - Stops message propagation on violation.
    """
    if getattr(message, "command", None):
        return

    user_id, _, is_white = await resolve_sender(client, message)
    if not user_id or is_white:
        return

    ctx = get_context()
    interval = await get_slowmode(ctx, message.chat.id)
    if interval <= 0:
        return

    key = CacheKeys.slowmode(message.chat.id, user_id)

    if await ctx.cache.get(key):
        with contextlib.suppress(Exception):
            await message.delete()
        raise StopPropagation
    else:
        await ctx.cache.set(key, "1", ttl=interval)


# --- Admin Panel Input Handlers ---


@bot.on_message(filters.private & is_waiting_for_input("slowmode"), group=-50)
@safe_handler
async def slowmode_input_handler(client: Client, message: Message) -> None:
    state = message.input_state
    chat_id = state["chat_id"]
    user_id = message.from_user.id
    ctx = get_context()
    value = message.text

    if not str(value).isdigit() or int(value) < 0:
        await message.reply(await at(user_id, "panel.input_invalid_number"))
        return

    num_value = int(value)
    if num_value > 0:
        await set_slowmode(ctx, chat_id, num_value)
    else:
        await clear_slowmode(ctx, chat_id)

    from src.plugins.admin_panel.handlers.moderation_kbs import slowmode_kb

    kb = await slowmode_kb(ctx, chat_id, user_id=user_id)

    text = await at(user_id, "panel.slowmode_text", interval=num_value)

    await finalize_input_capture(
        client,
        message,
        user_id,
        state["prompt_msg_id"],
        text,
        kb,
        success_text=await at(user_id, "panel.input_success"),
    )


register(SlowmodePlugin())
