import contextlib

from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import Message

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.models import ChannelProtect
from src.db.repositories.allowed_channels import (
    add_allowed_channel,
    get_allowed_channels,
    remove_allowed_channel,
)
from src.utils.allowlist_cache import (
    invalidate_allowlist_cache,
)
from src.utils.allowlist_cache import (
    is_channel_allowed as cached_is_channel_allowed,
)
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at


class ChannelProtectPlugin(Plugin):
    """Plugin to prevent messages from channels and anonymous senders in groups."""

    name = "channel_protect"
    priority = 18

    async def setup(self, client: Client, ctx) -> None:
        pass


async def set_channel_protect(
    ctx, cid: int, anti_c: bool = False, anti_a: bool = False
) -> ChannelProtect:
    async with ctx.db() as s:
        if not (o := await s.get(ChannelProtect, cid)):
            o = ChannelProtect(chatId=cid)
            s.add(o)
        o.antiChannel, o.antiAnon = anti_c, anti_a
        await s.commit()
        await s.refresh(o)
        return o


async def get_channel_protect(ctx, cid: int) -> ChannelProtect | None:
    async with ctx.db() as s:
        return await s.get(ChannelProtect, cid)


@bot.on_message(filters.command("antichannel") & filters.group)
@safe_handler
@admin_only
async def antichannel_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        return
    ctx, m = get_context(), message.command[1].lower() in ("on", "yes", "true")
    cp = await get_channel_protect(ctx, message.chat.id)
    await set_channel_protect(ctx, message.chat.id, anti_c=m, anti_a=cp.antiAnon if cp else False)
    await message.reply(
        await at(
            message.chat.id,
            "channel_protect.set",
            type="Anti-channel",
            mode="enabled" if m else "disabled",
        )
    )


@bot.on_message(filters.command("antianon") & filters.group)
@safe_handler
@admin_only
async def antianon_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        return
    ctx, m = get_context(), message.command[1].lower() in ("on", "yes", "true")
    cp = await get_channel_protect(ctx, message.chat.id)
    await set_channel_protect(
        ctx, message.chat.id, anti_c=cp.antiChannel if cp else False, anti_a=m
    )
    await message.reply(
        await at(
            message.chat.id,
            "channel_protect.set",
            type="Anti-anon",
            mode="enabled" if m else "disabled",
        )
    )


@bot.on_message(filters.command("allowlist") & filters.group)
@safe_handler
@admin_only
async def allowlist_handler(client: Client, message: Message) -> None:
    tid = (
        message.reply_to_message.sender_chat.id
        if message.reply_to_message and message.reply_to_message.sender_chat
        else None
    )
    if not tid and len(message.command) > 1:
        with contextlib.suppress(ValueError):
            tid = int(message.command[1])
    if not tid:
        return
    try:
        await add_allowed_channel(get_context(), message.chat.id, tid)
        await invalidate_allowlist_cache(message.chat.id)
        await message.reply(await at(message.chat.id, "allowlist.added", channel_id=tid))
    except ValueError as e:
        if str(e) == "allowlist_limit_reached":
            await message.reply(await at(message.chat.id, "allowlist.limit_reached"))
        else:
            raise e


@bot.on_message(filters.command("unallowlist") & filters.group)
@safe_handler
@admin_only
async def unallowlist_handler(client: Client, message: Message) -> None:
    tid = (
        message.reply_to_message.sender_chat.id
        if message.reply_to_message and message.reply_to_message.sender_chat
        else None
    )
    if not tid and len(message.command) > 1:
        with contextlib.suppress(ValueError):
            tid = int(message.command[1])
    if not tid:
        return
    if await remove_allowed_channel(get_context(), message.chat.id, tid):
        await invalidate_allowlist_cache(message.chat.id)
        await message.reply(await at(message.chat.id, "allowlist.removed", channel_id=tid))
    else:
        await message.reply(await at(message.chat.id, "allowlist.not_found"))


@bot.on_message(filters.command("allowlisted") & filters.group)
@safe_handler
async def list_allowed_handler(client: Client, message: Message) -> None:
    if not (als := await get_allowed_channels(get_context(), message.chat.id)):
        return await message.reply(await at(message.chat.id, "allowlist.empty"))
    await message.reply(
        f"{await at(message.chat.id, 'allowlist.header')}\n"
        + "\n".join(f"• `{a.channelId}`" for a in als)
    )


@bot.on_message(filters.group, group=-80)
@safe_handler
async def channel_protect_interceptor(client: Client, message: Message) -> None:
    if (
        message.sender_chat
        and message.sender_chat.type == ChatType.CHANNEL
        and await cached_is_channel_allowed(message.chat.id, message.sender_chat.id)
    ):
        return
    if not (cp := await get_channel_protect(get_context(), message.chat.id)):
        return
    if (
        cp.antiChannel and message.sender_chat and message.sender_chat.type == ChatType.CHANNEL
    ) or (
        cp.antiAnon
        and not message.from_user
        and message.sender_chat
        and message.sender_chat.id != message.chat.id
    ):
        with contextlib.suppress(Exception):
            await message.delete()


register(ChannelProtectPlugin())
