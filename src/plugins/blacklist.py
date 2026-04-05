import fnmatch
import re

from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.blacklist import add_blacklist, get_all_blacklist, remove_blacklist
from src.db.repositories.group_settings import get_settings
from src.db.repositories.warns import add_warn, reset_warns
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at
from src.utils.permissions import RESTRICTED_PERMISSIONS, Permission, has_permission


class BlacklistPlugin(Plugin):
    """Plugin to manage blacklisted words and patterns in group chats."""

    name = "blacklist"
    priority = 100

    async def setup(self, client: Client, ctx) -> None:
        pass


def detect_pattern_type(pattern: str) -> tuple[bool, bool, str]:
    """Auto-detects if the pattern is Regex, Wildcard, or Literal."""
    regex_chars = "^$+.?{}[]()|"
    is_regex = any(c in regex_chars for c in pattern)
    is_wildcard = "*" in pattern and not is_regex
    return is_regex, is_wildcard, pattern


@bot.on_message(filters.command(["addblacklist", "blacklistadd"]) & filters.group)
@safe_handler
@admin_only
async def add_blacklist_handler(client: Client, message: Message) -> None:
    """Add a new word or pattern to the blacklist."""
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
        await message.reply("❌ Limit of 150 blacklist patterns reached for this group.")


@bot.on_message(filters.command(["rmblacklist", "unblacklist"]) & filters.group)
@safe_handler
@admin_only
async def rm_blacklist_handler(client: Client, message: Message) -> None:
    """Remove a word or pattern from the blacklist."""
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
    """List all blacklisted words/patterns in the current group."""
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
    """Intercept messages and check for blacklisted content."""
    if not message.text and not message.caption:
        return

    if message.from_user and await has_permission(client, message.chat.id, Permission.CAN_BAN):
        from src.utils.admin_cache import is_admin

        if await is_admin(client, message.chat.id, message.from_user.id):
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
            if action == "mute":
                await client.restrict_chat_member(
                    message.chat.id, message.from_user.id, RESTRICTED_PERMISSIONS
                )
            elif action == "kick":
                await client.ban_chat_member(message.chat.id, message.from_user.id)
                await client.unban_chat_member(message.chat.id, message.from_user.id)
            elif action == "ban":
                await client.ban_chat_member(message.chat.id, message.from_user.id)
            elif action == "warn":
                count = await add_warn(
                    ctx, message.chat.id, message.from_user.id, client.me.id, "Blacklisted word"
                )
                if count >= settings.warnLimit:
                    w_action = settings.warnAction.lower()
                    if w_action == "ban":
                        await client.ban_chat_member(message.chat.id, message.from_user.id)
                    elif w_action == "kick":
                        await client.ban_chat_member(message.chat.id, message.from_user.id)
                        await client.unban_chat_member(message.chat.id, message.from_user.id)
                    elif w_action == "mute":
                        await client.restrict_chat_member(
                            message.chat.id,
                            message.from_user.id,
                            RESTRICTED_PERMISSIONS,
                        )

                    await reset_warns(ctx, message.chat.id, message.from_user.id)
                    await message.reply(
                        await at(
                            message.chat.id,
                            "warn.limit_reached",
                            mention=message.from_user.mention,
                            action=await at(message.chat.id, f"action.{w_action}"),
                        )
                    )
                else:
                    await message.reply(
                        await at(
                            message.chat.id,
                            "warn.added",
                            mention=message.from_user.mention,
                            count=count,
                            limit=settings.warnLimit,
                        )
                    )
        except Exception:
            pass


register(BlacklistPlugin())
