from pyrogram import Client, filters
from pyrogram.types import Message, User

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.approvals import (
    add_approval,
    clear_all_approvals,
    get_all_approved,
    is_user_approved,
    remove_approval,
)
from src.utils.decorators import admin_only, resolve_target, safe_handler
from src.utils.i18n import at


class ApprovalsPlugin(Plugin):
    """Plugin to manage user-specific member approvals."""

    name = "approvals"
    priority = 100

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.command("approve") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def approve_handler(client: Client, message: Message, target_user: User) -> None:
    """Approve a user to bypass certain restrictions."""
    ctx = get_context()
    await add_approval(ctx, message.chat.id, target_user.id, message.from_user.id)
    await message.reply(await at(message.chat.id, "approval.approved", mention=target_user.mention))


@bot.on_message(filters.command("unapprove") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def unapprove_handler(client: Client, message: Message, target_user: User) -> None:
    """Remove approval for a specific user."""
    ctx = get_context()
    success = await remove_approval(ctx, message.chat.id, target_user.id)
    if success:
        await message.reply(
            await at(message.chat.id, "approval.unapproved", mention=target_user.mention)
        )
    else:
        await message.reply(
            await at(message.chat.id, "approval.not_approved", mention=target_user.mention)
        )


@bot.on_message(filters.command("approved") & filters.group)
@safe_handler
async def list_approved_handler(client: Client, message: Message) -> None:
    """List all approved users in the current group."""
    ctx = get_context()
    approved = await get_all_approved(ctx, message.chat.id)
    if not approved:
        await message.reply(await at(message.chat.id, "approval.list_empty"))
        return

    text = await at(message.chat.id, "approval.list_header")
    for a in approved:
        text += f"\n• `{a.userId}`"
    await message.reply(text)


@bot.on_message(filters.command("unapproveall") & filters.group)
@safe_handler
@admin_only
async def unapproveall_handler(client: Client, message: Message) -> None:
    """Remove all user approvals in the current group."""
    ctx = get_context()
    await clear_all_approvals(ctx, message.chat.id)
    await message.reply(await at(message.chat.id, "approval.unapproveall_done"))


@bot.on_message(filters.command("approval") & filters.group)
@safe_handler
@resolve_target
async def approval_status_handler(client: Client, message: Message, target_user: User) -> None:
    """Check if a user is currently approved."""
    ctx = get_context()
    approved = await is_user_approved(ctx, message.chat.id, target_user.id)
    if approved:
        await message.reply(
            await at(message.chat.id, "approval.is_approved", mention=target_user.mention)
        )
    else:
        await message.reply(
            await at(message.chat.id, "approval.not_approved", mention=target_user.mention)
        )


register(ApprovalsPlugin())
