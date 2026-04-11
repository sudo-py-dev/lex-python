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
from src.utils.approved_cache import invalidate_approved_cache
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
    ctx = get_context()
    try:
        await add_approval(ctx, message.chat.id, target_user.id, message.from_user.id)
        await invalidate_approved_cache(message.chat.id)
        await message.reply(
            await at(message.chat.id, "approval.approved", mention=target_user.mention)
        )
    except ValueError as e:
        await message.reply(
            await at(
                message.chat.id,
                "approval.limit_reached" if str(e) == "approval_limit_reached" else "error.generic",
            )
        )


@bot.on_message(filters.command("unapprove") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def unapprove_handler(client: Client, message: Message, target_user: User) -> None:
    if await remove_approval(get_context(), message.chat.id, target_user.id):
        await invalidate_approved_cache(message.chat.id)
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
    approved = await get_all_approved(get_context(), message.chat.id)
    if not approved:
        return await message.reply(await at(message.chat.id, "approval.list_empty"))
    await message.reply(
        f"{await at(message.chat.id, 'approval.list_header')}\n"
        + "\n".join(f"• `{a.userId}`" for a in approved)
    )


@bot.on_message(filters.command("unapproveall") & filters.group)
@safe_handler
@admin_only
async def unapproveall_handler(client: Client, message: Message) -> None:
    await clear_all_approvals(get_context(), message.chat.id)
    await invalidate_approved_cache(message.chat.id)
    await message.reply(await at(message.chat.id, "approval.unapproveall_done"))


@bot.on_message(filters.command("approval") & filters.group)
@safe_handler
@resolve_target
async def approval_status_handler(client: Client, message: Message, target_user: User) -> None:
    k = (
        "approval.is_approved"
        if await is_user_approved(get_context(), message.chat.id, target_user.id)
        else "approval.not_approved"
    )
    await message.reply(await at(message.chat.id, k, mention=target_user.mention))


register(ApprovalsPlugin())
