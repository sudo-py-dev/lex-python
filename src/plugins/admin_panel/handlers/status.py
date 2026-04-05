from pyrogram import Client
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.types import ChatMemberUpdated

from src.core.bot import bot
from src.plugins.admin_panel import get_ctx
from src.plugins.admin_panel.repository import set_chat_active_status
from src.utils.admin_cache import invalidate_cache


@bot.on_chat_member_updated()
async def on_my_status_update(client: Client, update: ChatMemberUpdated):
    """
    Autodetect when the bot joins/leaves a group or is promoted/demoted.
    """
    if not (update.new_chat_member and update.new_chat_member.user.is_self):
        return
    chat_id = update.chat.id
    if update.chat.type == ChatType.PRIVATE:
        return

    new_status = update.new_chat_member.status
    old_status = update.old_chat_member.status
    ctx = get_ctx()

    if new_status == ChatMemberStatus.ADMINISTRATOR:
        await set_chat_active_status(ctx, chat_id, True)
        await invalidate_cache(chat_id)

    elif new_status == ChatMemberStatus.MEMBER:
        if old_status in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED, None} or old_status == ChatMemberStatus.ADMINISTRATOR:
            await set_chat_active_status(ctx, chat_id, False)
            await invalidate_cache(chat_id)

    elif new_status in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}:
        await set_chat_active_status(ctx, chat_id, False)
        await invalidate_cache(chat_id)
