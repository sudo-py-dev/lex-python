from loguru import logger
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from src.cache.local_cache import get_cache
from src.core.bot import bot
from src.plugins.admin_panel.decorators import AdminPanelContext, admin_panel_context
from src.plugins.admin_panel.handlers.callbacks.common import _panel_lang_id, _plain
from src.plugins.admin_panel.handlers.keyboards import main_menu_kb
from src.plugins.admin_panel.repository import resolve_chat_type
from src.plugins.admin_panel.validation import is_setting_allowed
from src.plugins.ai_assistant.repository import AIRepository
from src.utils.i18n import at
from src.utils.input import capture_next_input


@bot.on_callback_query(filters.regex(r"^panel:input:(\w+):?(-?\d+)?$"))
@admin_panel_context
async def on_panel_input(_: Client, callback: CallbackQuery, ap_ctx: AdminPanelContext):
    user_id = callback.from_user.id
    chat_id = ap_ctx.chat_id
    ctx = ap_ctx.ctx
    field = callback.matches[0].group(1)
    target_id_str = callback.matches[0].group(2)

    logger.debug(f"Admin Panel: input action triggered for field {field} by user {user_id}")

    is_channel_field = field in ("reactions", "watermarkText", "signatureText")
    validate_chat_id = int(target_id_str) if is_channel_field and target_id_str else chat_id

    chat_type = await resolve_chat_type(ctx, validate_chat_id)
    if not is_setting_allowed(field, chat_type.name.lower()):
        await callback.answer(
            await at(user_id, "panel.setting_not_allowed_for_type"), show_alert=True
        )
        return

    at_id = _panel_lang_id(ap_ctx.is_pm, user_id, chat_id)

    if is_channel_field:
        channel_id = int(target_id_str)
        await capture_next_input(user_id, channel_id, field, prompt_msg_id=callback.message.id)
        cancel_cb = f"panel:channel_settings:{channel_id}"
    else:
        page = int(target_id_str) if target_id_str and target_id_str.isdigit() else 0
        await capture_next_input(
            user_id, chat_id, field, prompt_msg_id=callback.message.id, page=page
        )

        cancel_map = {
            "floodThreshold": "panel:flood",
            "floodWindow": "panel:flood",
            "welcomeText": "panel:welcome",
            "rulesText": "panel:rules",
            "warnLimit": "panel:warns",
            "slowmode": "panel:slowmode",
            "raidThreshold": "panel:raid",
            "raidWindow": "panel:raid",
            "raidTime": "panel:raid",
            "raidActionTime": "panel:raid",
            "captchaTimeout": "panel:captcha",
            "gsbKey": "panel:urlscanner",
            "reminderText": "panel:reminders",
            "chatnightlockStart": "panel:chatnightlock",
            "chatnightlockEnd": "panel:chatnightlock",
            "cleanerInactive": "panel:cleaner",
            "purgeMessagesCount": "panel:category:moderation",
        }
        if field.startswith("ai"):
            cancel_cb = "panel:category:ai"
        elif field == "blacklistInput":
            cancel_cb = f"panel:blacklist:{page}"
        elif field == "langblockInput":
            cancel_cb = f"panel:langblock:{page}"
        elif field == "stickerInput":
            cancel_cb = f"panel:stickers:{page}"
        else:
            cancel_cb = cancel_map.get(field, "panel:main")

    prompt_key = f"panel.input_prompt_{field}"

    if field == "aiApiKey":
        settings = await AIRepository.get_settings(ctx, chat_id)
        provider = (settings.provider if settings else "openai").upper()
        prompt_text = await at(at_id, prompt_key, provider=provider)
    else:
        prompt_text = await at(at_id, prompt_key)

    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton(await at(at_id, "common.btn_cancel"), callback_data=cancel_cb)]]
    )
    await callback.message.edit_text(prompt_text, reply_markup=kb)
    await callback.answer()


@bot.on_callback_query(filters.regex(r"^panel:cancel_input$"))
@admin_panel_context
async def on_cancel_input(_: Client, callback: CallbackQuery, ap_ctx: AdminPanelContext):
    user_id = callback.from_user.id
    chat_id = ap_ctx.chat_id
    at_id = _panel_lang_id(ap_ctx.is_pm, user_id, chat_id)

    r = get_cache()
    await r.delete(f"panel_input:{user_id}")
    await callback.answer(_plain(await at(at_id, "panel.input_cancelled")), show_alert=True)
    await callback.message.edit_text(
        await at(at_id, "panel.main_text"),
        reply_markup=await main_menu_kb(chat_id, user_id=user_id if ap_ctx.is_pm else None),
    )
