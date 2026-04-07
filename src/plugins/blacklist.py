import fnmatch
import re
from datetime import datetime, timedelta

from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.blacklist import add_blacklist, get_all_blacklist, remove_blacklist
from src.db.repositories.chats import get_chat_settings as get_settings
from src.db.repositories.warns import add_warn, reset_warns
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at
from src.utils.moderation import resolve_sender
from src.utils.permissions import RESTRICTED_PERMISSIONS


class BlacklistPlugin(Plugin):
    """Plugin to manage blacklisted words and patterns in group chats."""

    name = "blacklist"
    priority = 100

    async def setup(self, client: Client, ctx) -> None:
        pass


def detect_pattern_type(pattern: str) -> tuple[bool, bool, str]:
    """
    Auto-detects the matching strategy for a given blacklist pattern.

    Identifies if a pattern should be treated as a Regular Expression, a
    Wildcard pattern (using *), or a literal string.

    Args:
        pattern (str): The pattern string to analyze.

    Returns:
        tuple[bool, bool, str]: A tuple containing (is_regex, is_wildcard, pattern).
    """
    regex_chars = "^$+.?{}[]()|"
    is_regex = any(c in regex_chars for c in pattern)
    is_wildcard = "*" in pattern and not is_regex
    return is_regex, is_wildcard, pattern


@bot.on_message(filters.command(["addblacklist", "blacklistadd"]) & filters.group)
@safe_handler
@admin_only
async def add_blacklist_handler(client: Client, message: Message) -> None:
    """
    Add a new word or pattern to the chat's blacklist.

    Automatically detects if the pattern is a regex or wildcard.
    Requires the user to be an admin.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Inserts the pattern into the database blacklist table.
        - Sends a confirmation message.
    """
    if len(message.command) < 2:
        return

    ctx = get_context()
    pattern = message.command[1].lower()
    is_regex, is_wildcard, pattern = detect_pattern_type(pattern)

    success = await add_blacklist(
        ctx, message.chat.id, pattern, is_regex=is_regex, is_wildcard=is_wildcard
    )
    if success:
        await message.reply(await at(message.chat.id, "blacklist.added", pattern=pattern))
    else:
        await message.reply(await at(message.chat.id, "blacklist.limit_error"))


@bot.on_message(filters.command(["rmblacklist", "unblacklist"]) & filters.group)
@safe_handler
@admin_only
async def rm_blacklist_handler(client: Client, message: Message) -> None:
    """
    Remove an existing word or pattern from the chat's blacklist.

    Requires the user to be an admin.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Deletes the pattern from the database blacklist table.
        - Sends a confirmation message.
    """
    if len(message.command) < 2:
        return

    ctx = get_context()
    pattern = message.command[1].lower()
    success = await remove_blacklist(ctx, message.chat.id, pattern)
    if success:
        await message.reply(await at(message.chat.id, "blacklist.removed", pattern=pattern))
    else:
        await message.reply(await at(message.chat.id, "blacklist.not_found"))


@bot.on_message(filters.command("blacklist") & filters.group)
@safe_handler
async def list_blacklist_handler(client: Client, message: Message) -> None:
    """
    List all blacklisted words and patterns for the current chat.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Fetches all blacklist entries from the database.
        - Sends a message containing the list of patterns.
    """
    ctx = get_context()
    blacklist = await get_all_blacklist(ctx, message.chat.id)
    if not blacklist:
        await message.reply(await at(message.chat.id, "blacklist.list_empty"))
        return

    text = await at(message.chat.id, "blacklist.list_header")
    for b in blacklist:
        text += f"\n• `{b.pattern}` ({b.action})"
    await message.reply(text)


@bot.on_message(filters.group & (filters.text | filters.caption), group=3)
@safe_handler
async def blacklist_interceptor(client: Client, message: Message) -> None:
    """
    Intercept group messages to check for blacklisted content.

    If a match is found, the message is deleted, propagation is stopped, and
    the configured blacklist action (mute, kick, ban, or warn) is performed
    on the sender.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Deletes the triggering message.
        - Stops message propagation.
        - May restrict, kick, or ban the user based on chat settings.
        - May increment user's warn count.
    """
    if not message.text and not message.caption:
        return

    user_id, mention, is_white = await resolve_sender(client, message)
    if not user_id or is_white:
        return

    ctx = get_context()
    blacklist = await get_all_blacklist(ctx, message.chat.id)
    if not blacklist:
        return

    text = (message.text or message.caption).lower()
    triggered_blacklist = None

    for b in blacklist:
        if b.isRegex:
            if re.search(b.pattern, text, re.IGNORECASE):
                triggered_blacklist = b
                break
        elif b.isWildcard:
            regex_str = fnmatch.translate(b.pattern)
            if re.search(regex_str, text, re.IGNORECASE | re.DOTALL):
                triggered_blacklist = b
                break
        elif b.pattern.lower() in text:
            triggered_blacklist = b
            break

    if triggered_blacklist:
        settings = await get_settings(ctx, message.chat.id)
        action = settings.blacklistAction.lower()
        try:
            await message.delete()
            await message.stop_propagation()
            if action == "mute":
                await client.restrict_chat_member(message.chat.id, user_id, RESTRICTED_PERMISSIONS)
            elif action == "kick":
                await client.ban_chat_member(
                    message.chat.id,
                    user_id,
                    until_date=datetime.now() + timedelta(minutes=1),
                )
            elif action == "ban":
                await client.ban_chat_member(message.chat.id, user_id)
            elif action == "warn":
                count = await add_warn(
                    ctx,
                    message.chat.id,
                    user_id,
                    client.me.id,
                    await at(message.chat.id, "blacklist.reason"),
                )
                if count >= settings.warnLimit:
                    w_action = settings.warnAction.lower()
                    if w_action == "ban":
                        await client.ban_chat_member(message.chat.id, message.from_user.id)
                    elif w_action == "kick":
                        await client.ban_chat_member(
                            message.chat.id,
                            user_id,
                            until_date=datetime.now() + timedelta(minutes=1),
                        )
                    elif w_action == "mute":
                        await client.restrict_chat_member(
                            message.chat.id,
                            user_id,
                            RESTRICTED_PERMISSIONS,
                        )

                    await reset_warns(ctx, message.chat.id, user_id)
                    await message.reply(
                        await at(
                            message.chat.id,
                            "warn.limit_reached",
                            mention=mention,
                            action=await at(message.chat.id, f"action.{w_action}"),
                        )
                    )
                else:
                    await message.reply(
                        await at(
                            message.chat.id,
                            "warn.added",
                            mention=mention,
                            count=count,
                            limit=settings.warnLimit,
                        )
                    )
        except Exception:
            pass


register(BlacklistPlugin())
