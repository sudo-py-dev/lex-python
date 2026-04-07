from collections.abc import Callable, Coroutine
from typing import Any

from loguru import logger
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, Message

from src.core.context import AppContext

InputHandler = Callable[
    [Client, Message, AppContext, int, str, Any, int | None, int], Coroutine[Any, Any, None]
]


class InputRegistry:
    def __init__(self):
        self.handlers: dict[str, InputHandler] = {}

    def register(self, fields: list[str]):
        def decorator(handler: InputHandler):
            for f in fields:
                self.handlers[f] = handler
            return handler

        return decorator

    async def dispatch(
        self,
        client: Client,
        message: Message,
        ctx: AppContext,
        chat_id: int,
        field: str,
        value: Any,
        prompt_msg_id: int | None,
        page: int,
    ) -> bool:
        handler = self.handlers.get(field)
        if handler:
            try:
                await handler(client, message, ctx, chat_id, field, value, prompt_msg_id, page)
                return True
            except Exception as e:
                logger.error(f"Error in input processor for field {field}: {e}")
                return False
        return False


input_registry = InputRegistry()


async def finalize_input_capture(
    client: Client,
    message: Message,
    user_id: int,
    prompt_msg_id: int | None,
    panel_text: str,
    kb: InlineKeyboardMarkup,
    success_text: str | None = None,
) -> None:
    """Finalize input flow: optional success reply + clean panel render."""
    import contextlib

    with contextlib.suppress(Exception):
        await message.delete()

    if success_text:
        with contextlib.suppress(Exception):
            await client.send_message(user_id, success_text)

    if prompt_msg_id:
        try:
            await client.edit_message_text(
                chat_id=user_id, message_id=prompt_msg_id, text=panel_text, reply_markup=kb
            )
        except Exception:
            await message.reply(panel_text, reply_markup=kb)
    else:
        await message.reply(panel_text, reply_markup=kb)


async def capture_next_input(
    user_id: int, chat_id: int, field: str, prompt_msg_id: int | None = None, page: int = 0
) -> None:
    """Stores the capture state in Local Cache to intercept the next message."""
    from src.cache.local_cache import get_cache

    r = get_cache()
    msg_id = prompt_msg_id or 0
    await r.set(f"panel_input:{user_id}", f"{chat_id}:{field}:{msg_id}:{page}", ttl=300)
    logger.debug(
        "capture_next_input armed: user_id={} chat_id={} field={} prompt_msg_id={} page={}",
        user_id,
        chat_id,
        field,
        msg_id,
        page,
    )
