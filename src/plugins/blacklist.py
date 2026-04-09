import fnmatch
import re

from loguru import logger
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, Message

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.blacklist import (
    add_blacklist,
    get_all_blacklist,
    remove_blacklist,
)
from src.db.repositories.chats import get_chat_settings as get_settings
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at
from src.utils.input import finalize_input_capture, is_waiting_for_input
from src.utils.moderation import execute_moderation_action, resolve_sender


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
    pattern = message.text.split(None, 1)[1].strip().lower()
    is_regex, is_wildcard, pattern = detect_pattern_type(pattern)

    try:
        success = await add_blacklist(
            ctx, message.chat.id, pattern, is_regex=is_regex, is_wildcard=is_wildcard
        )
        if success:
            await message.reply(await at(message.chat.id, "blacklist.added", pattern=pattern))
    except ValueError as e:
        if str(e) == "blacklist_limit_reached":
            await message.reply(await at(message.chat.id, "blacklist.limit_reached"))
        elif str(e) == "blacklist_already_exists":
            await message.reply(await at(message.chat.id, "blacklist.err_already_exists"))
        else:
            raise e


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
    pattern = message.text.split(None, 1)[1].strip().lower()
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


@bot.on_message(filters.group & (filters.text | filters.caption), group=-60)
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

    logger.debug(f"Blacklist: Intercepted message from {message.from_user.id} in {message.chat.id}")

    user_id, mention, is_white = await resolve_sender(client, message)
    if not user_id or is_white:
        return

    ctx = get_context()
    blacklist = await get_all_blacklist(ctx, message.chat.id)
    if not blacklist:
        return

    text = (message.text or message.caption or "").lower()

    # Extract button content if enabled
    settings = await get_settings(ctx, message.chat.id)
    scan_buttons = getattr(settings, "blacklistScanButtons", False)

    if (
        scan_buttons
        and message.reply_markup
        and isinstance(message.reply_markup, InlineKeyboardMarkup)
    ):
        for row in message.reply_markup.inline_keyboard:
            for button in row:
                if button.text:
                    text += f" {button.text.lower()}"
                if button.url:
                    text += f" {button.url.lower()}"

    triggered_blacklist = None

    for b in blacklist:
        if b.isRegex:
            try:
                if re.search(b.pattern, text, re.IGNORECASE):
                    triggered_blacklist = b
                    break
            except re.error:
                if b.pattern.lower() in text:
                    triggered_blacklist = b
                    break
        elif b.isWildcard:
            try:
                regex_str = fnmatch.translate(b.pattern)
                if re.search(regex_str, text, re.IGNORECASE | re.DOTALL):
                    triggered_blacklist = b
                    break
            except re.error:
                if b.pattern.lower() in text:
                    triggered_blacklist = b
                    break
        elif b.pattern.lower() in text:
            triggered_blacklist = b
            break

    if triggered_blacklist:
        action = settings.blacklistAction.lower()
        reason = await at(message.chat.id, "blacklist.reason", pattern=triggered_blacklist.pattern)

        acted = await execute_moderation_action(
            client=client,
            message=message,
            action=action,
            reason=reason,
            log_tag="Blacklist",
            violation_key="blacklist.violation_notice",
            pattern=triggered_blacklist.pattern,
        )
        if acted:
            await message.stop_propagation()


# --- Admin Panel Input Handlers ---


@bot.on_message(filters.private & is_waiting_for_input("blacklistInput"), group=-50)
@safe_handler
async def blacklist_input_handler(client: Client, message: Message) -> None:
    state = message.input_state
    chat_id = state["chat_id"]
    user_id = message.from_user.id
    ctx = get_context()
    value = message.text or message.caption
    if not value:
        return

    pattern_raw = str(value).strip().lower()
    is_regex, is_wildcard, pattern = detect_pattern_type(pattern_raw)

    if is_regex:
        try:
            re.compile(pattern)
        except re.error:
            await message.reply(await at(user_id, "panel.blacklist_invalid_regex"))
            return

    try:
        await add_blacklist(ctx, chat_id, pattern, is_regex=is_regex, is_wildcard=is_wildcard)
    except ValueError as e:
        if str(e) == "blacklist_already_exists":
            await message.reply(await at(user_id, "blacklist.err_already_exists"))
            return
        elif str(e) == "blacklist_limit_reached":
            await message.reply(await at(user_id, "panel.blacklist_limit_reached"))
            return
        else:
            raise e

    from src.plugins.admin_panel.handlers.moderation_kbs import blacklist_kb

    kb = await blacklist_kb(ctx, chat_id, state["page"], user_id=user_id)
    await finalize_input_capture(
        client,
        message,
        user_id,
        state["prompt_msg_id"],
        await at(user_id, "panel.blacklist_text"),
        kb,
        success_text=await at(user_id, "panel.input_success"),
    )


register(BlacklistPlugin())
