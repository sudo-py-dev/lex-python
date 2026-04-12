from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.rules import (
    clear_rules,
    get_rules,
    set_rules,
    toggle_private_rules,
)
from src.utils.decorators import admin_permission_required, safe_handler
from src.utils.i18n import at
from src.utils.input import finalize_input_capture, is_waiting_for_input
from src.utils.permissions import Permission


class RulesPlugin(Plugin):
    name = "rules"
    priority = 100

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.command("setrules") & filters.group)
@safe_handler
@admin_permission_required(Permission.CAN_CHANGE_INFO)
async def set_rules_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        return

    ctx = get_context()
    content = message.text.split(None, 1)[1]
    await set_rules(ctx, message.chat.id, content)
    await message.reply(await at(message.chat.id, "rules.set"))


@bot.on_message(filters.command("rules") & filters.group)
@safe_handler
async def rules_handler(client: Client, message: Message) -> None:
    ctx = get_context()
    rules = await get_rules(ctx, message.chat.id)
    if not rules or not rules.content:
        await message.reply(await at(message.chat.id, "rules.not_set"))
        return

    header = await at(message.chat.id, "rules.header")
    text = f"{header}\n\n{rules.content}"
    if rules.privateMode:
        try:
            await client.send_message(message.from_user.id, text)
            await message.reply(await at(message.chat.id, "rules.sent_dm"))
        except Exception:
            await message.reply(await at(message.chat.id, "common.err_start_private"))
    else:
        await message.reply(text)


@bot.on_message(filters.command("resetrules") & filters.group)
@safe_handler
@admin_permission_required(Permission.CAN_CHANGE_INFO)
async def reset_rules_handler(client: Client, message: Message) -> None:
    ctx = get_context()
    await clear_rules(ctx, message.chat.id)
    await message.reply(await at(message.chat.id, "rules.reset"))


@bot.on_message(filters.command("privaterules") & filters.group)
@safe_handler
@admin_permission_required(Permission.CAN_CHANGE_INFO)
async def private_rules_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        return

    ctx = get_context()
    mode = message.command[1].lower() in ("on", "yes", "true")
    await toggle_private_rules(ctx, message.chat.id, mode)
    if mode:
        await message.reply(await at(message.chat.id, "rules.private_on"))
    else:
        await message.reply(await at(message.chat.id, "rules.private_off"))


@bot.on_message(filters.private & filters.regex(r"^/start rules_(-?\d+)$"), group=1)
@safe_handler
async def start_rules_deeplink_handler(client: Client, message: Message) -> None:
    """Intercept deep-links from {rules} buttons and deliver rules in PM."""
    ctx = get_context()
    chat_id = int(message.matches[0].group(1))
    rules = await get_rules(ctx, chat_id)
    if not rules or not rules.content:
        await message.reply(await at(chat_id, "rules.not_set"))
        return

    header = await at(chat_id, "rules.header")
    await message.reply(f"{header}\n\n{rules.content}")


# --- Admin Panel Input Handlers ---


@bot.on_message(filters.private & is_waiting_for_input("rulesText"), group=-50)
@safe_handler
async def rules_input_handler(client: Client, message: Message) -> None:
    state = message.input_state
    user_id = message.from_user.id
    chat_id = state["chat_id"]
    ctx = get_context()
    value = message.text

    from src.db.repositories.rules import set_rules
    from src.plugins.admin_panel.handlers.keyboards import rules_kb

    await set_rules(ctx, chat_id, str(value))
    kb = await rules_kb(chat_id, user_id=user_id)

    await finalize_input_capture(
        client,
        message,
        user_id,
        state["prompt_msg_id"],
        await at(user_id, "panel.rules_text"),
        kb,
        success_text=await at(user_id, "panel.input_success"),
    )


register(RulesPlugin())
