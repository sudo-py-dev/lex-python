from datetime import datetime, timedelta

from pyrogram import Client, filters
from pyrogram.types import Message, User

from src.core.bot import bot
from src.core.context import AppContext, get_context
from src.core.plugin import Plugin, register
from src.db.repositories.chats import get_chat_settings as get_settings
from src.db.repositories.warns import (
    add_warn,
    get_warns,
    reset_all_chat_warns,
    reset_warns,
)
from src.plugins.logging import log_event
from src.utils.decorators import admin_only, resolve_target, safe_handler
from src.utils.i18n import at
from src.utils.input import finalize_input_capture, is_waiting_for_input
from src.utils.permissions import RESTRICTED_PERMISSIONS, Permission, has_permission


class WarnsPlugin(Plugin):
    name = "warns"
    priority = 40

    async def setup(self, client: Client, ctx: AppContext) -> None:
        pass


@bot.on_message(filters.command("warn") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def warn_handler(client: Client, message: Message, target_user: User) -> None:
    """Issue a warning to a user."""
    if not await has_permission(client, message.chat.id, Permission.CAN_RESTRICT):
        await message.reply(await at(message.chat.id, "error.no_permission"))
        return

    ctx = get_context()
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
                reason=await at(
                    message.chat.id, "logging.warn_limit_reason", limit=settings.warnLimit
                ),
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
    """Remove all warnings for a user."""
    if not await has_permission(client, message.chat.id, Permission.CAN_RESTRICT):
        await message.reply(await at(message.chat.id, "error.no_permission"))
        return

    await reset_warns(get_context(), message.chat.id, target_user.id)
    await message.reply(await at(message.chat.id, "warn.reset", mention=target_user.mention))


@bot.on_message(filters.command(["warns", "warnings"]) & filters.group)
@safe_handler
@resolve_target
async def warns_handler(client: Client, message: Message, target_user: User) -> None:
    """List all active warnings for a user."""
    ctx = get_context()
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
    """Remove all warnings for all users in the chat."""
    count = await reset_all_chat_warns(get_context(), message.chat.id)
    await message.reply(await at(message.chat.id, "warn.cleared_all", count=count))


# --- Admin Panel Input Handlers ---


@bot.on_message(filters.private & is_waiting_for_input("warnLimit"), group=-100)
@safe_handler
async def warn_limit_input_handler(client: Client, message: Message) -> None:
    state = message.input_state
    chat_id = state["chat_id"]
    user_id = message.from_user.id
    ctx = get_context()
    value = message.text

    if not str(value).isdigit() or int(value) < 1:
        await message.reply(await at(user_id, "panel.input_invalid_number"))
        return

    from src.plugins.admin_panel.repository import update_chat_setting

    await update_chat_setting(ctx, chat_id, "warnLimit", int(value))

    from src.plugins.admin_panel.handlers.moderation_kbs import warns_kb

    kb = await warns_kb(ctx, chat_id, user_id=user_id)

    settings = await get_settings(ctx, chat_id)
    text = await at(
        user_id,
        "panel.warns_text",
        limit=settings.warnLimit,
        action=settings.warnAction.capitalize(),
        expiry=settings.warnExpiry.capitalize(),
    )

    await finalize_input_capture(
        client,
        message,
        user_id,
        state["prompt_msg_id"],
        text,
        kb,
        success_text=await at(user_id, "panel.input_success"),
    )


register(WarnsPlugin())
