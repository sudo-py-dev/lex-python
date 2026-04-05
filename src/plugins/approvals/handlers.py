from pyrogram import Client, filters
from pyrogram.types import Message, User

from src.core.bot import bot
from src.utils.decorators import admin_only, resolve_target, safe_handler
from src.utils.i18n import at

from . import get_ctx
from .repository import (
    add_approval,
    clear_all_approvals,
    get_all_approved,
    is_user_approved,
    remove_approval,
)


@bot.on_message(filters.command("approve") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def approve_handler(client: Client, message: Message, target_user: User) -> None:
    await add_approval(get_ctx(), message.chat.id, target_user.id, message.from_user.id)
    await message.reply(await at(message.chat.id, "approval.approved", mention=target_user.mention))


@bot.on_message(filters.command("unapprove") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def unapprove_handler(client: Client, message: Message, target_user: User) -> None:
    success = await remove_approval(get_ctx(), message.chat.id, target_user.id)
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
    approved = await get_all_approved(get_ctx(), message.chat.id)
    if not approved:
        await message.reply(await at(message.chat.id, "approval.list_empty"))
        return

    text = await at(message.chat.id, "approval.list_header")
    for a in approved:
        # Here we only have IDs in DB for now.
        text += f"\n• `{a.userId}`"
    await message.reply(text)


@bot.on_message(filters.command("unapproveall") & filters.group)
@safe_handler
@admin_only
async def unapproveall_handler(client: Client, message: Message) -> None:
    await clear_all_approvals(get_ctx(), message.chat.id)
    await message.reply(await at(message.chat.id, "approval.unapproveall_done"))


@bot.on_message(filters.command("approval") & filters.group)
@safe_handler
@resolve_target
async def approval_status_handler(client: Client, message: Message, target_user: User) -> None:
    approved = await is_user_approved(get_ctx(), message.chat.id, target_user.id)
    if approved:
        await message.reply(
            await at(message.chat.id, "approval.is_approved", mention=target_user.mention)
        )
    else:
        await message.reply(
            await at(message.chat.id, "approval.not_approved", mention=target_user.mention)
        )
