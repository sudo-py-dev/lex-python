from datetime import datetime, timedelta

from pyrogram import Client, filters
from pyrogram.types import Message, User

from src.core.bot import bot
from src.core.context import AppContext
from src.core.plugin import Plugin, register
from src.db.repositories.group_settings import get_settings
from src.db.repositories.warns import (
    add_warn,
    get_warns,
    reset_all_chat_warns,
    reset_warns,
)
from src.plugins.logging import log_event
from src.utils.decorators import admin_only, resolve_target, safe_handler
from src.utils.i18n import at
from src.utils.permissions import RESTRICTED_PERMISSIONS, Permission, has_permission

_ctx: AppContext | None = None


def get_ctx() -> AppContext:
    if _ctx is None:
        raise RuntimeError("Warns plugin not initialized")
    return _ctx


class WarnsPlugin(Plugin):
    name = "warns"
    priority = 40

    async def setup(self, client: Client, ctx: AppContext) -> None:
        global _ctx
        _ctx = ctx


@bot.on_message(filters.command("warn") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def warn_handler(client: Client, message: Message, target_user: User) -> None:
    if not await has_permission(client, message.chat.id, Permission.CAN_RESTRICT):
        await message.reply(await at(message.chat.id, "error.no_permission"))
        return

    ctx = get_ctx()
    settings = await get_settings(ctx, message.chat.id)
    reason = " ".join(message.command[1:]) if len(message.command) > 1 else None
    if message.reply_to_message and len(message.command) > 1:
        reason = " ".join(message.command[1:])
    elif not message.reply_to_message and len(message.command) > 2:
        reason = " ".join(message.command[2:])

    count = await add_warn(ctx, message.chat.id, target_user.id, message.from_user.id, reason)

    if count >= settings.warnLimit:
        action = settings.warnAction.lower()
        try:
            if action == "ban":
                await client.ban_chat_member(message.chat.id, target_user.id)
            elif action == "kick":
                await client.ban_chat_member(
                    message.chat.id,
                    target_user.id,
                    until_date=datetime.now() + timedelta(minutes=1),
                )
            elif action == "mute":
                await client.restrict_chat_member(
                    message.chat.id, target_user.id, RESTRICTED_PERMISSIONS
                )

            await reset_warns(ctx, message.chat.id, target_user.id)
            await log_event(
                ctx,
                client,
                message.chat.id,
                f"warn_limit_{action}",
                target_user,
                client.me,
                reason=await at(message.chat.id, "logging.warn_limit_reason", limit=settings.warnLimit),
                chat_title=message.chat.title,
            )
            await message.reply(
                await at(
                    message.chat.id,
                    "warn.limit_reached",
                    mention=target_user.mention,
                    action=await at(message.chat.id, f"action.{action}"),
                )
            )
        except Exception:
            pass
    else:
            await message.reply(
                await at(
                    message.chat.id,
                    "warn.added",
                    mention=target_user.mention,
                    count=count,
                    limit=settings.warnLimit,
                )
            )
            await log_event(
                ctx,
                client,
                message.chat.id,
                "warn",
                target_user,
                message.from_user,
                reason=reason,
                chat_title=message.chat.title,
            )


@bot.on_message(filters.command("unwarn") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def unwarn_handler(client: Client, message: Message, target_user: User) -> None:
    if not await has_permission(client, message.chat.id, Permission.CAN_RESTRICT):
        await message.reply(await at(message.chat.id, "error.no_permission"))
        return

    await reset_warns(get_ctx(), message.chat.id, target_user.id)
    await message.reply(await at(message.chat.id, "warn.reset", mention=target_user.mention))


@bot.on_message(filters.command(["warns", "warnings"]) & filters.group)
@safe_handler
@resolve_target
async def warns_handler(client: Client, message: Message, target_user: User) -> None:
    ctx = get_ctx()
    warns = await get_warns(ctx, message.chat.id, target_user.id)
    settings = await get_settings(ctx, message.chat.id)

    if not warns:
        await message.reply(await at(message.chat.id, "warn.none", mention=target_user.mention))
        return

    text = await at(
        message.chat.id,
        "warn.list_header",
        mention=target_user.mention,
        count=len(warns),
        limit=settings.warnLimit,
    )
    no_reason = await at(message.chat.id, "common.no_reason")
    for i, warn in enumerate(warns, 1):
        text += f"\n{await at(message.chat.id, 'warn.list_entry', num=i, reason=warn.reason or no_reason, actor=warn.actorId)}"

    await message.reply(text)


@bot.on_message(filters.command("resetallwarns") & filters.group)
@safe_handler
@admin_only
async def reset_all_warns_handler(client: Client, message: Message) -> None:
    count = await reset_all_chat_warns(get_ctx(), message.chat.id)
    await message.reply(await at(message.chat.id, "warn.cleared_all", count=count))


register(WarnsPlugin())
