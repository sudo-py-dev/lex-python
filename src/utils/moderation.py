import asyncio
import contextlib
from datetime import datetime, timedelta

from loguru import logger
from pyrogram import Client
from pyrogram.types import Message

from src.core.context import get_context
from src.utils.i18n import at
from src.utils.permissions import (
    RESTRICTED_PERMISSIONS,
    Permission,
    can_restrict_members,
    has_permission,
    is_whitelisted,
)


async def resolve_sender(client: Client, message: Message) -> tuple[int | None, str, bool]:
    """
    Resolve the sender's ID, mention string, and whitelist status.
    Supports regular users, channels, and anonymous admins.
    Returns (None, ..., False) for bots or unresolvable senders.
    """
    user_id = None
    mention = "Unknown"

    if message.from_user:
        if message.from_user.is_bot:
            return None, mention, False
        user_id = message.from_user.id
        mention = message.from_user.mention
    elif message.sender_chat:
        user_id = message.sender_chat.id
        mention = message.sender_chat.title

    if user_id is None:
        unknown_label = await at(message.chat.id, "common.unknown")
        return None, unknown_label, False

    is_white = await is_whitelisted(client, message.chat.id, user_id)
    return user_id, mention, is_white


async def execute_moderation_action(
    client: Client,
    message: Message,
    action: str,
    reason: str,
    log_tag: str,
    violation_key: str,
    **i18n_kwargs,
) -> bool:
    """
    Perform a moderation action: delete, punish, and notify.
    Returns True if an action was taken and propagation should stop.
    """
    user_id, mention, is_white = await resolve_sender(client, message)
    if not user_id or is_white:
        return False

    action = action.lower()

    if not await has_permission(client, message.chat.id, Permission.CAN_DELETE):
        return False

    try:
        await message.delete()

        if action == "delete":
            return True

        if not await can_restrict_members(client, message.chat.id):
            return True

        apply_punishment = None
        notify_action = await at(message.chat.id, f"action.{action}")
        ctx = get_context()

        if action == "warn":
            from src.db.repositories.chats import get_chat_settings as get_warn_settings
            from src.db.repositories.warns import add_warn, reset_warns

            count = await add_warn(ctx, message.chat.id, user_id, client.me.id, reason=reason)
            s = await get_warn_settings(ctx, message.chat.id)

            if count >= s.warnLimit:
                apply_punishment = s.warnAction.lower()
                await reset_warns(ctx, message.chat.id, user_id)
                notify_action = await at(
                    message.chat.id,
                    "action.limit_reached_fmt",
                    action=await at(message.chat.id, f"action.{apply_punishment}"),
                )
            else:
                notify_action = f"{notify_action} ({count}/{s.warnLimit})"
        else:
            apply_punishment = action

        if apply_punishment == "ban":
            await client.ban_chat_member(message.chat.id, user_id)
        elif apply_punishment == "kick":
            await client.ban_chat_member(
                message.chat.id, user_id, until_date=datetime.now() + timedelta(minutes=1)
            )
        elif apply_punishment == "mute":
            await client.restrict_chat_member(message.chat.id, user_id, RESTRICTED_PERMISSIONS)

        logger.debug(
            f"{log_tag}: Moderated {user_id} in {message.chat.id} (Action: {notify_action})"
        )

        warn_msg = await client.send_message(
            message.chat.id,
            await at(
                message.chat.id,
                violation_key,
                mention=mention,
                reason=reason,
                action=notify_action,
                **i18n_kwargs,
            ),
        )

        asyncio.create_task(_delete_after(warn_msg, 10))
        return True

    except Exception:
        logger.exception(f"{log_tag} Action Error in {message.chat.id}")
        return True


async def _delete_after(msg: Message, delay: int) -> None:
    await asyncio.sleep(delay)
    with contextlib.suppress(Exception):
        await msg.delete()
