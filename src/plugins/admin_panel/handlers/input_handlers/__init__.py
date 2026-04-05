from loguru import logger
from pyrogram import Client, filters
from pyrogram.types import Message

from src.cache.local_cache import get_cache
from src.core.bot import bot
from src.plugins.admin_panel import get_ctx
from src.utils.i18n import at
from src.utils.permissions import is_admin

# Import all modules to trigger registration
from .ai_processor import ai_settings_processor
from .content_processor import content_settings_processor
from .dispatch_logic import capture_next_input, input_registry
from .security_processor import numeric_security_processor
from .system_processor import system_settings_processor


@bot.on_message(filters.private & filters.text & ~filters.regex(r"^/.*"))
async def dispatch_admin_input(client: Client, message: Message) -> None:
    """
    Main entry point for Admin Panel input capture.
    Dispatches to specialized processors via the input_registry.
    """
    user_id = message.from_user.id
    r = get_cache()
    state = await r.get(f"panel_input:{user_id}")
    if not state:
        return

    parts = state.split(":")
    if len(parts) >= 3:
        chat_id = int(parts[0])
        field = parts[1]
        prompt_msg_id = int(parts[2])
        page = int(parts[3]) if len(parts) > 3 else 0
    elif len(parts) == 2:
        chat_id = int(parts[0])
        field = parts[1]
        prompt_msg_id = None
        page = 0
    else:
        return

    # Delete state before processing to prevent loops
    await r.delete(f"panel_input:{user_id}")

    if not await is_admin(client, chat_id, user_id):
        await message.reply(await at(user_id, "panel.error_not_admin"))
        return

    ctx = get_ctx()
    value = message.text

    # Dispatch to specialized handlers
    handled = await input_registry.dispatch(
        client, message, ctx, chat_id, field, value, prompt_msg_id, page
    )

    if not handled:
        logger.warning(f"No input processor registered for field: {field}")
        from src.plugins.admin_panel.handlers.keyboards import main_menu_kb
        kb = await main_menu_kb(chat_id, True)
        await message.reply(await at(user_id, "panel.error_generic"), reply_markup=kb)

__all__ = ["input_registry", "dispatch_admin_input", "capture_next_input"]
