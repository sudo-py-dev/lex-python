import contextlib
import json

from loguru import logger
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, Message

from src.cache.local_cache import get_cache


def is_waiting_for_input(fields: str | list[str] | None = None):
    """
    Custom filter to check if a user is currently in an active input flow.
    If match, attaches 'input_state' dictionary to the message object.

    Args:
        fields: Specific field name or list of field names to match.
                If None, matches any active input state for the user.
    """

    async def func(flt, client, message: Message) -> bool:
        fid = getattr(flt, "filter_id", "unknown")
        # logger.debug(f"Input Filter Trace: {fid} triggered")
        if not message.from_user:
            return False

        user_id = message.from_user.id
        r = get_cache()

        state_raw = await r.get(f"panel_input:{user_id}")
        if not state_raw:
            return False

        try:
            if isinstance(state_raw, str) and state_raw.startswith("{"):
                state = json.loads(state_raw)
            elif isinstance(state_raw, dict):
                state = state_raw
            else:
                parts = str(state_raw).split(":")
                state = {
                    "chat_id": int(parts[0]),
                    "field": parts[1],
                    "prompt_msg_id": int(parts[2]) if len(parts) > 2 and parts[2] != "0" else None,
                    "page": int(parts[3]) if len(parts) > 3 else 0,
                }
        except Exception as e:
            logger.error(f"Input Filter [{fid}]: Failed to parse state for user {user_id}: {e}")
            return False

        current_field = state.get("field")
        filter_fields = getattr(flt, "fields", None)

        if filter_fields:
            allowed = [filter_fields] if isinstance(filter_fields, str) else filter_fields
            if current_field not in allowed:
                logger.trace(
                    f"Input Filter [{fid}]: Field mismatch for user {user_id}. Current: {current_field}, Allowed: {allowed}"
                )
                return False

        logger.debug(
            f"Input Filter [{fid}]: Match success for user {user_id}, field: {current_field}"
        )
        message.input_state = state
        return True

    # Use a cleaner filter_id based on fields instead of id(func) which changes every time
    filter_id = (
        f"input_{fields}"
        if isinstance(fields, str)
        else f"input_{'_'.join(fields) if fields else 'any'}"
    )
    logger.debug(f"Input Filter: Initializing instance for fields {fields}")
    return filters.create(func, fields=fields, filter_id=filter_id)


async def capture_next_input(
    user_id: int, chat_id: int, field: str, prompt_msg_id: int | None = None, page: int = 0
) -> None:
    """
    Arms the capture state in Local Cache to intercept the next private message from the user.
    Stores state as JSON for better field expansion and robustness.
    """
    r = get_cache()
    state = {
        "chat_id": chat_id,
        "field": field,
        "prompt_msg_id": prompt_msg_id or 0,
        "page": page,
    }

    logger.debug(
        f"Input Capture: Arming capture for user {user_id}, field: {field}, chat: {chat_id}"
    )
    await r.set(f"panel_input:{user_id}", json.dumps(state), ttl=300)


async def finalize_input_capture(
    client,
    message: Message,
    user_id: int,
    prompt_msg_id: int | None,
    panel_text: str,
    kb: InlineKeyboardMarkup,
    success_text: str | None = None,
) -> None:
    """
    Finalize input flow:
    1. Delete the user's input message if possible.
    2. Send an optional success notification.
    3. Update the original panel message or send a new one.
    4. Remove the capture state from cache.
    """

    # 1. Cleanup user message
    with contextlib.suppress(Exception):
        await message.delete()

    # 2. Cleanup capture state
    r = get_cache()
    await r.delete(f"panel_input:{user_id}")
    logger.debug(f"Finalize: Cache cleared for user {user_id}")

    # 3. Handle success notification
    if success_text:
        with contextlib.suppress(Exception):
            # Since we are answering a message input, we can't answer_callback_query.
            # We can either send a brief reply or just rely on the UI edit.
            # For now, let's keep it quiet to keep the chat clean, or use a reply if preferred.
            pass

    # 4. Update UI
    if prompt_msg_id:
        try:
            if prompt_msg_id > 0:
                await client.edit_message_text(
                    chat_id=user_id, message_id=prompt_msg_id, text=panel_text, reply_markup=kb
                )
                logger.debug(f"Finalize: UI Edited for user {user_id}, msg: {prompt_msg_id}")
            else:
                await client.send_message(user_id, panel_text, reply_markup=kb)
                logger.debug(f"Finalize: UI Sent (New) for user {user_id}")
        except Exception as e:
            logger.debug(f"Finalize Error: UI update failed: {e}")
            await client.send_message(user_id, panel_text, reply_markup=kb)
    else:
        await client.send_message(user_id, panel_text, reply_markup=kb)
        logger.debug(f"Finalize: UI Sent (No Prompt ID) for user {user_id}")
