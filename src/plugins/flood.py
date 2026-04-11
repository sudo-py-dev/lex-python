import contextlib

from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.core.constants import CacheKeys
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.chats import get_chat_settings as get_settings
from src.db.repositories.chats import update_settings
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at
from src.utils.input import finalize_input_capture, is_waiting_for_input
from src.utils.moderation import execute_moderation_action, resolve_sender
from src.utils.permissions import can_restrict_members


class FloodPlugin(Plugin):
    """Plugin to detect and mitigate message flooding from users."""

    name = "flood"
    priority = 30

    async def setup(self, client: Client, ctx) -> None:
        pass


async def increment_flood(ctx, cid: int, uid: int, win: int) -> int:
    k = CacheKeys.flood(cid, uid)
    c = await ctx.cache.incr(k)
    if c == 1:
        await ctx.cache.expire(k, win)
    return c


async def reset_flood(ctx, cid: int, uid: int) -> None:
    await ctx.cache.delete(CacheKeys.flood(cid, uid))


@bot.on_message(filters.command("setflood") & filters.group)
@safe_handler
@admin_only
async def set_flood_handler(client: Client, message: Message) -> None:
    if len(message.command) < 4:
        return
    try:
        th, win = int(message.command[1]), int(message.command[2])
    except ValueError:
        return
    act = message.command[3].lower()
    if act not in ("mute", "kick", "ban"):
        return
    await update_settings(
        get_context(), message.chat.id, floodThreshold=th, floodWindow=win, floodAction=act
    )
    await message.reply(
        await at(message.chat.id, "flood.set", threshold=th, window=win, action=act)
    )


@bot.on_message(filters.group, group=-100)
@safe_handler
async def flood_interceptor(client: Client, message: Message) -> None:
    if getattr(message, "command", None):
        return
    uid, _, white = await resolve_sender(client, message)
    if not uid or white:
        return
    ctx = get_context()
    s = await get_settings(ctx, message.chat.id)
    if s.floodThreshold <= 0:
        return

    c = await increment_flood(ctx, message.chat.id, uid, s.floodWindow)
    if c == s.floodThreshold + 1:
        if not await can_restrict_members(client, message.chat.id):
            return
        r = await at(
            message.chat.id,
            "logging.flood_reason",
            threshold=s.floodThreshold,
            window=s.floodWindow,
        )
        await execute_moderation_action(
            client, message, s.floodAction.lower(), r, "Flood", "flood.triggered"
        )

    if c > s.floodThreshold:
        with contextlib.suppress(Exception):
            await message.delete()
        await message.stop_propagation()


# --- Admin Panel Input Handlers ---


@bot.on_message(
    filters.private & is_waiting_for_input(["floodThreshold", "floodWindow"]), group=-50
)
@safe_handler
async def flood_settings_input_handler(client: Client, message: Message) -> None:
    state = message.input_state
    chat_id = state["chat_id"]
    field = state["field"]
    user_id = message.from_user.id
    ctx = get_context()
    value = message.text

    if not str(value).isdigit() or int(value) < 0:
        await message.reply(await at(user_id, "panel.input_invalid_number"))
        return

    await update_settings(ctx, chat_id, **{field: int(value)})

    from src.plugins.admin_panel.handlers.keyboards import flood_kb

    kb = await flood_kb(ctx, chat_id, user_id=user_id)

    text = await at(user_id, "panel.flood_text")

    await finalize_input_capture(
        client,
        message,
        user_id,
        state["prompt_msg_id"],
        text,
        kb,
        success_text=await at(user_id, "panel.input_success"),
    )


register(FloodPlugin())
