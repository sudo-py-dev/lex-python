"""Reusable handler decorators for all plugins."""

from __future__ import annotations

import functools
import time
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger
from pyrogram import Client, ContinuePropagation, StopPropagation
from pyrogram.enums import ChatType
from pyrogram.types import CallbackQuery, Message

from src.utils.i18n import at
from src.utils.permissions import Permission, has_permission, is_admin

Handler = Callable[..., Awaitable[None]]


def admin_only(func: Handler) -> Handler:
    """Silently ignore the command if the sender is not a group admin."""

    @functools.wraps(func)
    async def wrapper(client: Client, message: Message, *args: Any, **kwargs: Any) -> None:
        if not message.from_user:
            return
        if message.chat.type == ChatType.PRIVATE:
            await func(client, message, *args, **kwargs)
            return
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return
        await func(client, message, *args, **kwargs)

    return wrapper


def require_permission(permission: Permission) -> Callable[[Handler], Handler]:
    """Reply with specific error if bot lacks the required permission."""

    def decorator(func: Handler) -> Handler:
        @functools.wraps(func)
        async def wrapper(client: Client, message: Message, *args: Any, **kwargs: Any) -> None:
            if not await has_permission(client, message.chat.id, permission):
                await message.reply(await at(message.chat.id, "error.no_permission"))
                return
            await func(client, message, *args, **kwargs)

        return wrapper

    return decorator


def safe_handler(func: Handler) -> Handler:
    """Catch all unhandled exceptions inside a handler — never crash the bot."""

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> None:
        try:
            await func(*args, **kwargs)
        except (StopPropagation, ContinuePropagation):
            raise
        except Exception as e:
            logger.exception(f"Unhandled error in {func.__name__}: {e}")

    return wrapper


def resolve_target(func: Handler) -> Handler:
    """
    Inject ``target_user`` from reply or first argument (@username / user_id).
    The wrapped function receives ``target_user`` as a keyword argument.
    """

    @functools.wraps(func)
    async def wrapper(client: Client, message: Message, **kwargs: Any) -> None:
        target_user = None

        if message.reply_to_message and message.reply_to_message.from_user:
            target_user = message.reply_to_message.from_user
        elif len(message.command) > 1:
            try:
                target_user = await client.get_users(message.command[1])
            except Exception:
                await message.reply(await at(message.chat.id, "error.resolve_user_failed"))
                return

        if target_user is None:
            await message.reply(await at(message.chat.id, "error.provide_user"))
            return

        await func(client, message, target_user=target_user, **kwargs)

    return wrapper


def rate_limit(seconds: float = 2.0) -> Callable[[Handler], Handler]:
    """Per-chat rate limiter. Silently drops calls within the cooldown window."""
    _last_call: dict[int, float] = {}

    def decorator(func: Handler) -> Handler:
        @functools.wraps(func)
        async def wrapper(client: Client, message: Message, **kwargs: Any) -> None:
            chat_id = message.chat.id
            now = time.monotonic()
            if now - _last_call.get(chat_id, 0) < seconds:
                return
            _last_call[chat_id] = now
            await func(client, message, **kwargs)

        return wrapper

    return decorator


def callback_admin_only(func: Callable[..., Awaitable[None]]) -> Callable[..., Awaitable[None]]:
    """For callback query handlers — deny non-admins with an alert."""

    @functools.wraps(func)
    async def wrapper(client: Client, callback: CallbackQuery, **kwargs: Any) -> None:
        if not callback.message or not callback.from_user:
            return
        if not await is_admin(client, callback.message.chat.id, callback.from_user.id):
            await callback.answer(
                await at(callback.message.chat.id, "error.no_membership_admin"), show_alert=True
            )
            return
        await func(client, callback, **kwargs)

    return wrapper
