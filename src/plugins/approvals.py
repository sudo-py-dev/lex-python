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
    """
    Approve a specific user in the current chat, allowing them to bypass restrictions
    defined by other plugins (e.g., entity blocks, word filters).

    Requires the user to be an admin.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.
        target_user (User): The user to be approved (resolved by @resolve_target).

    Side Effects:
        - Inserts an approval record into the database.
        - Invalidates the chat's approval cache.
        - Sends a confirmation message.
    """
    ctx = get_context()
    try:
        await add_approval(ctx, message.chat.id, target_user.id, message.from_user.id)
        await invalidate_approved_cache(message.chat.id)
        await message.reply(
            await at(message.chat.id, "approval.approved", mention=target_user.mention)
        )
    except ValueError as e:
        if str(e) == "approval_limit_reached":
            await message.reply(await at(message.chat.id, "approval.limit_reached"))
        else:
            raise e


@bot.on_message(filters.command("unapprove") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def unapprove_handler(client: Client, message: Message, target_user: User) -> None:
    """
    Remove the approval status of a specific user in the current chat.

    The user will once again be subject to all group restrictions.
    Requires the user to be an admin.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.
        target_user (User): The user to be unapproved (resolved by @resolve_target).

    Side Effects:
        - Deletes the approval record from the database.
        - Invalidates the chat's approval cache.
        - Sends a confirmation message.
    """
    ctx = get_context()
    success = await remove_approval(ctx, message.chat.id, target_user.id)
    if success:
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
    """
    List all currently approved users in the group.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Fetches all approved users for the current chat from the database.
        - Sends a message containing the list of user IDs.
    """
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
    """
    Remove all user approvals for the current group in a single action.

    Requires the user to be an admin.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Deletes all approval records for the current chat from the database.
        - Invalidates the chat's approval cache.
        - Sends a confirmation message.
    """
    ctx = get_context()
    await clear_all_approvals(ctx, message.chat.id)
    await invalidate_approved_cache(message.chat.id)
    await message.reply(await at(message.chat.id, "approval.unapproveall_done"))


@bot.on_message(filters.command("approval") & filters.group)
@safe_handler
@resolve_target
async def approval_status_handler(client: Client, message: Message, target_user: User) -> None:
    """
    Check and report the current approval status of a specific user.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.
        target_user (User): The user whose status is being checked (resolved by @resolve_target).

    Side Effects:
        - Queries the database for the user's approval status.
        - Sends a reply message indicating whether the user is approved.
    """
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
