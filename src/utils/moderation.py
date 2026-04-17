import asyncio
import contextlib
from datetime import datetime, timedelta

from loguru import logger
from pyrogram import Client, ContinuePropagation, StopPropagation
from pyrogram.errors import BadRequest, FloodWait, Forbidden, RPCError
from pyrogram.types import Message

from src.core.context import get_context
from src.utils.actions import ModerationAction
from src.utils.i18n import at
from src.utils.permissions import (
    RESTRICTED_PERMISSIONS,
    Permission,
    has_permission,
    is_whitelisted,
)


async def resolve_sender(client: Client, message: Message) -> tuple[int | None, str, bool]:
    """Resolve ID, mention, and whitelist. Returns (None, ..., False) for bots/unresolvable."""
    if message.from_user:
        if message.from_user.is_bot:
            return None, "Unknown", False
        user_id, mention = message.from_user.id, message.from_user.mention
    elif message.sender_chat:
        user_id, mention = message.sender_chat.id, message.sender_chat.title
    else:
        return None, await at(message.chat.id, "common.unknown"), False

    return user_id, mention, await is_whitelisted(client, message.chat.id, user_id)


async def execute_moderation_action(
    client: Client,
    message: Message,
    action: str,
    reason: str,
    log_tag: str,
    violation_key: str,
    **kwargs,
) -> bool:
    """Delete, punish, and notify. Return True to stop propagation."""
    user_id, mention, is_white = await resolve_sender(client, message)
    if (
        not user_id
        or is_white
        or not await has_permission(client, message.chat.id, Permission.CAN_DELETE)
    ):
        return False

    try:
        await message.delete()
        action = action.lower()
        ctx = get_context()
        from src.db.repositories.actions import log_action
        from src.plugins.logging import log_event

        log_type = f"{log_tag.lower()}_{action}"
        await log_action(ctx, message.chat.id, client.me.id, user_id, log_type)
        if message.chat:
            await log_event(
                ctx,
                client,
                message.chat.id,
                log_type,
                user_id,
                client.me,
                reason=reason,
                chat_title=message.chat.title,
            )

        if action == ModerationAction.DELETE:
            return True
        if not await has_permission(client, message.chat.id, Permission.CAN_BAN):
            return True

        apply_punishment, notify_action = None, await at(message.chat.id, f"action.{action}")

        if action == ModerationAction.WARN:
            from src.db.repositories.chats import get_chat_settings as get_s
            from src.db.repositories.warns import add_warn, reset_warns

            count = await add_warn(ctx, message.chat.id, user_id, client.me.id, reason=reason)
            s = await get_s(ctx, message.chat.id)

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

        if apply_punishment:
            await _apply_punishment(client, message.chat.id, user_id, apply_punishment)

        warn_msg = await client.send_message(
            message.chat.id,
            await at(
                message.chat.id,
                violation_key,
                mention=mention,
                reason=reason,
                action=notify_action,
                **kwargs,
            ),
        )
        asyncio.create_task(_delete_after(warn_msg, 10))
        return True

    except (StopPropagation, ContinuePropagation):
        raise
    except FloodWait as e:
        logger.warning(f"{log_tag} FloodWait: sleeping {e.value}s in {message.chat.id}")
        await asyncio.sleep(e.value + 1)
        return True
    except (BadRequest, Forbidden) as e:
        logger.warning(f"{log_tag} Permission/API Error in {message.chat.id}: {e}")
        return True
    except RPCError as e:
        logger.error(f"{log_tag} Telegram API Error in {message.chat.id}: {e}")
        return True
    except Exception:
        logger.exception(f"{log_tag} Unexpected Error in {message.chat.id}")
        return True


async def _delete_after(msg: Message, delay: int) -> None:
    await asyncio.sleep(delay)
    with contextlib.suppress(RPCError, Exception):
        await msg.delete()


async def _apply_punishment(
    client: Client,
    chat_id: int,
    user_id: int,
    action: str,
) -> None:
    """Apply a punishment action (ban, kick, mute) to a user."""
    action = action.lower()

    if action == ModerationAction.BAN:
        await client.ban_chat_member(chat_id, user_id)
    elif action == ModerationAction.KICK:
        await client.ban_chat_member(
            chat_id, user_id, until_date=datetime.now() + timedelta(minutes=1)
        )
    elif action == ModerationAction.MUTE:
        await client.restrict_chat_member(chat_id, user_id, RESTRICTED_PERMISSIONS)
