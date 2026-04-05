import contextlib

from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.plugins.bans.repository import log_action
from src.utils.i18n import at
from src.utils.permissions import RESTRICTED_PERMISSIONS, can_restrict_members, is_admin

from . import get_ctx
from .repository import get_settings, set_flood_settings
from .service import increment_flood


@bot.on_message(filters.command("setflood") & filters.group)
async def set_flood_handler(client: Client, message: Message) -> None:
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return
    if len(message.command) < 4:
        return
    try:
        threshold = int(message.command[1])
        window = int(message.command[2])
    except ValueError:
        return
    action = message.command[3].lower()
    if action not in ("mute", "kick", "ban"):
        return
    await set_flood_settings(get_ctx(), message.chat.id, threshold, window, action)
    await message.reply(
        await at(message.chat.id, "flood.set", threshold=threshold, window=window, action=action)
    )


@bot.on_message(filters.group, group=-2)
async def flood_interceptor(client: Client, message: Message) -> None:
    if not message.from_user:
        return
    if await is_admin(client, message.chat.id, message.from_user.id):
        return
    ctx = get_ctx()
    try:
        settings = await get_settings(ctx, message.chat.id)
    except Exception:
        return
    if settings.floodThreshold <= 0:
        return

    count = await increment_flood(ctx, message.chat.id, message.from_user.id, settings.floodWindow)
    if count == settings.floodThreshold + 1:
        if not await can_restrict_members(client, message.chat.id):
            return
        action = settings.floodAction.lower()
        try:
            if action == "ban":
                await client.ban_chat_member(message.chat.id, message.from_user.id)
            elif action == "kick":
                await client.ban_chat_member(message.chat.id, message.from_user.id)
                await client.unban_chat_member(message.chat.id, message.from_user.id)
            else:
                await client.restrict_chat_member(
                    message.chat.id, message.from_user.id, RESTRICTED_PERMISSIONS
                )
            await message.reply(
                await at(
                    message.chat.id,
                    "flood.triggered",
                    mention=message.from_user.mention,
                    action=action,
                )
            )
            await log_action(
                ctx, message.chat.id, client.me.id, message.from_user.id, f"flood_{action}"
            )
        except Exception:
            pass

    if count > settings.floodThreshold:
        with contextlib.suppress(Exception):
            await message.delete()
