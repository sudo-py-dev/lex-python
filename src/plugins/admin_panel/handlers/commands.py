from loguru import logger
from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.core.bot import bot
from src.core.context import get_context
from src.plugins.connections import set_active_chat
from src.utils.i18n import at
from src.utils.permissions import is_admin

from ..decorators import AdminPanelContext, admin_panel_context
from .keyboards import main_menu_kb, my_groups_kb


@bot.on_message(filters.command("settings"))
@admin_panel_context
async def settings_handler(client: Client, message: Message, ap_ctx: AdminPanelContext) -> None:
    if not ap_ctx.is_pm:
        me = await client.get_me()
        url = f"https://t.me/{me.username}?start=settings_{ap_ctx.chat_id}"
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(await at(ap_ctx.chat_id, "panel.btn_manage_pm"), url=url)]]
        )
        await message.reply(await at(ap_ctx.chat_id, "panel.redirect_pm_text"), reply_markup=kb)
        return

    await open_settings_panel(client, message, ap_ctx.chat_id)


async def open_settings_panel(client: Client, message: Message, chat_id: int) -> None:
    ctx = get_context()
    user_id = message.from_user.id
    is_pm = message.chat.type == ChatType.PRIVATE

    if is_pm and chat_id < 0:
        await set_active_chat(ctx, user_id, chat_id)

    logger.debug(f"Verifying admin status for {user_id} in {chat_id}")
    if chat_id >= 0 or not await is_admin(client, chat_id, user_id):
        await message.reply(await at(user_id, "panel.error_not_admin"))
        if is_pm:
            kb = await my_groups_kb(ctx, client, user_id)
            await message.reply(await at(user_id, "panel.my_groups_title"), reply_markup=kb)
        return

    is_pm = message.chat.type == ChatType.PRIVATE
    await client.send_message(
        user_id,
        await at(user_id if is_pm else chat_id, "panel.main_text"),
        reply_markup=await main_menu_kb(chat_id, user_id if is_pm else None),
    )
