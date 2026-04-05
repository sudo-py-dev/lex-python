import re

from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.plugins.warns.repository import add_warn
from src.plugins.warns.repository import get_settings as get_warn_settings
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at
from src.utils.permissions import RESTRICTED_PERMISSIONS, Permission, has_permission

from . import get_ctx
from .repository import add_blacklist, get_all_blacklist, remove_blacklist


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
    if len(message.command) < 2:
        return
    pattern = message.command[1].lower()
    is_regex, is_wildcard, pattern = detect_pattern_type(pattern)

    success = await add_blacklist(
        get_ctx(), message.chat.id, pattern, is_regex=is_regex, is_wildcard=is_wildcard
    )
    if success:
        await message.reply(await at(message.chat.id, "blacklist.added", pattern=pattern))
    else:
        await message.reply("❌ Limit of 150 blacklist patterns reached for this group.")


@bot.on_message(filters.command(["rmblacklist", "unblacklist"]) & filters.group)
@safe_handler
@admin_only
async def rm_blacklist_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        return
    pattern = message.command[1].lower()
    success = await remove_blacklist(get_ctx(), message.chat.id, pattern)
    if success:
        await message.reply(await at(message.chat.id, "blacklist.removed", pattern=pattern))
    else:
        await message.reply(await at(message.chat.id, "blacklist.not_found"))


@bot.on_message(filters.command("blacklist") & filters.group)
@safe_handler
async def list_blacklist_handler(client: Client, message: Message) -> None:
    blacklist = await get_all_blacklist(get_ctx(), message.chat.id)
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
    if not message.text and not message.caption:
        return

    if message.from_user and await has_permission(client, message.chat.id, Permission.CAN_BAN):
        from src.utils.admin_cache import is_admin

        if await is_admin(client, message.chat.id, message.from_user.id):
            return

    blacklist = await get_all_blacklist(get_ctx(), message.chat.id)
    if not blacklist:
        return

    text = (message.text or message.caption).lower()
    triggered_blacklist = None

    import fnmatch

    for b in blacklist:
        if b.isRegex:
            if re.search(b.pattern, text, re.IGNORECASE):
                triggered_blacklist = b
                break
        elif b.isWildcard:
            import fnmatch

            regex_str = fnmatch.translate(b.pattern)
            if re.search(regex_str, text, re.IGNORECASE | re.DOTALL):
                triggered_blacklist = b
                break
        elif b.pattern.lower() in text:
            triggered_blacklist = b
            break

    if triggered_blacklist:
        from src.plugins.admin_panel.repository import get_chat_settings

        settings = await get_chat_settings(get_ctx(), message.chat.id)
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
                ctx = get_ctx()
                warn_settings = await get_warn_settings(ctx, message.chat.id)
                count = await add_warn(
                    ctx, message.chat.id, message.from_user.id, client.me.id, "Blacklisted word"
                )
                if count >= warn_settings.warnLimit:
                    w_action = warn_settings.warnAction.lower()
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

                    from src.plugins.warns.repository import reset_warns

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
                            limit=warn_settings.warnLimit,
                        )
                    )
        except Exception:
            pass
