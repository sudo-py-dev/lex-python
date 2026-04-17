from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

from src.core.bot import bot
from src.db.repositories.admins import get_admins_for_chat
from src.plugins.admin_panel.decorators import AdminPanelContext, admin_panel_context
from src.plugins.admin_panel.handlers.callbacks.common import (
    _panel_lang_id,
    safe_callback,
    safe_edit,
)
from src.plugins.admin_panel.handlers.keyboards import admins_management_kb
from src.utils.admin_cache import force_refresh
from src.utils.i18n import at


@bot.on_callback_query(filters.regex(r"^panel:admins_mgmt$"))
@admin_panel_context
@safe_callback
async def on_admins_management(_: Client, callback: CallbackQuery, ap_ctx: AdminPanelContext):
    user_id = callback.from_user.id
    chat_id = ap_ctx.chat_id
    at_id = _panel_lang_id(ap_ctx.is_pm, user_id, chat_id)
    ctx = ap_ctx.ctx

    from src.utils.admin_cache import get_chat_admins

    await get_chat_admins(bot, chat_id)
    admins = await get_admins_for_chat(ctx, chat_id)

    header = "`" + "NAME".ljust(15) + " | " + "ROLE".ljust(12) + "`\n"
    divider = "`" + "-" * 15 + " | " + "-" * 12 + "`\n"

    rows = []
    for admin in admins:
        try:
            name = f"@{admin.username}" if admin.username else admin.firstName
            if not name:
                name = f"ID:{admin.userId}"
            role = admin.status.capitalize()
            rows.append("`" + str(name)[:15].ljust(15) + " | " + str(role).ljust(12) + "`")
        except Exception:
            continue

    table = header + divider + "\n".join(rows)
    last_sync = admins[0].updatedAt.strftime("%Y-%m-%d %H:%M") if admins else "N/A"

    text = await at(at_id, "panel.admins_mgmt_text", title=ap_ctx.chat_title, date=last_sync)
    text += f"\n\n{table}"

    await safe_edit(
        callback,
        text,
        reply_markup=await admins_management_kb(ctx, chat_id, user_id, admins),
    )
    await callback.answer()


@bot.on_callback_query(filters.regex(r"^panel:admins_refresh:(-?\d+)$"))
@admin_panel_context
@safe_callback
async def on_admins_refresh(_: Client, callback: CallbackQuery, ap_ctx: AdminPanelContext):
    user_id = callback.from_user.id
    chat_id = int(callback.matches[0].group(1))
    at_id = _panel_lang_id(ap_ctx.is_pm, user_id, chat_id)
    ctx = ap_ctx.ctx

    from src.utils.local_cache import get_cache

    cache = get_cache()
    cooldown_key = f"refresh_admins_cooldown:{chat_id}"

    if await cache.exists(cooldown_key):
        return await callback.answer(
            await at(at_id, "panel.error_refresh_cooldown"), show_alert=True
        )

    await force_refresh(bot, chat_id)
    await cache.set(cooldown_key, True, ttl=3600)
    await callback.answer(await at(at_id, "panel.admin_refresh_success"), show_alert=True)

    # Re-render the menu
    admins = await get_admins_for_chat(ctx, chat_id)
    header = "`" + "NAME".ljust(15) + " | " + "ROLE".ljust(12) + "`\n"
    divider = "`" + "-" * 15 + " | " + "-" * 12 + "`\n"
    rows = [
        "`"
        + (f"@{a.username}" if a.username else a.firstName or f"ID:{a.userId}")[:15].ljust(15)
        + " | "
        + a.status.capitalize().ljust(12)
        + "`"
        for a in admins
    ]
    table = header + divider + "\n".join(rows)
    last_sync = admins[0].updatedAt.strftime("%Y-%m-%d %H:%M") if admins else "N/A"

    text = await at(at_id, "panel.admins_mgmt_text", title=ap_ctx.chat_title, date=last_sync)
    text += f"\n\n{table}"

    await safe_edit(
        callback,
        text,
        reply_markup=await admins_management_kb(ctx, chat_id, user_id, admins),
    )
