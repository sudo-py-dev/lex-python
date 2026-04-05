from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from loguru import logger
from pyrogram import Client
from pyrogram.enums import ChatType
from pyrogram.types import CallbackQuery, Message

from src.core.context import AppContext
from src.plugins.connections import get_active_chat
from src.utils.i18n import at
from src.utils.permissions import is_admin

from . import get_ctx


@dataclass
class AdminPanelContext:
    chat_id: int
    at_id: int
    ctx: AppContext
    is_pm: bool


def admin_panel_context(func: Callable[..., Awaitable[None]]) -> Callable[..., Awaitable[None]]:
    """
    Decorator for admin panel handlers (Messages or Callbacks).
    Resolves the target chat_id (connected chat in PM or current chat in Group)
    and verifies admin permissions.
    """

    @functools.wraps(func)
    async def wrapper(
        client: Client, event: Message | CallbackQuery, *args: Any, **kwargs: Any
    ) -> None:
        user_id = event.from_user.id
        is_pm = False

        message = event if isinstance(event, Message) else event.message
        if message and message.chat.type == ChatType.PRIVATE:
            is_pm = True

        ctx = get_ctx()

        if not is_pm:
            chat_id = message.chat.id
        else:
            chat_id = await get_active_chat(ctx, user_id)
            if not chat_id:
                logger.debug(f"No active connection for user {user_id} in PM.")
                from .handlers.keyboards import my_groups_kb

                kb = await my_groups_kb(ctx, client, user_id)
                text = await at(user_id, "panel.pick_group")
                if isinstance(event, CallbackQuery):
                    await event.message.edit_text(text, reply_markup=kb)
                    await event.answer()
                else:
                    await event.reply(text, reply_markup=kb)
                return

        at_id = user_id if is_pm else chat_id
        if not await is_admin(client, chat_id, user_id):
            logger.warning(f"User {user_id} is NOT admin in resolved chat {chat_id}. Redirecting.")
            from .handlers.keyboards import my_groups_kb

            if is_pm:
                kb = await my_groups_kb(ctx, client, user_id)
                text = await at(user_id, "panel.access_denied_repick")
                if isinstance(event, CallbackQuery):
                    await event.message.edit_text(text, reply_markup=kb)
                    await event.answer()
                else:
                    await event.reply(text, reply_markup=kb)
            else:
                text = await at(at_id, "panel.error_not_admin")
                if isinstance(event, CallbackQuery):
                    await event.answer(text, show_alert=True)
                else:
                    await event.reply(text)
            return

        ap_ctx = AdminPanelContext(chat_id=chat_id, at_id=at_id, ctx=ctx, is_pm=is_pm)

        await func(client, event, ap_ctx, *args, **kwargs)

    return wrapper
