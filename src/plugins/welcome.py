import contextlib

from pyrogram import Client, filters
from pyrogram.types import Message, User

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.chats import get_chat_settings as get_settings
from src.db.repositories.chats import update_settings
from src.utils.decorators import admin_only, safe_handler
from src.utils.formatters import TelegramFormatter
from src.utils.i18n import at
from src.utils.input import finalize_input_capture, is_waiting_for_input
from src.utils.permissions import Permission, has_permission


class WelcomePlugin(Plugin):
    """Plugin to handle welcome and goodbye messages."""

    name = "welcome"
    priority = 100

    async def setup(self, client: Client, ctx) -> None:
        pass


async def send_welcome_goodbye(
    client: Client, chat_id: int, chat_title: str, user: User, is_welcome: bool = True
) -> None:
    """Universal sender for welcome/goodbye messages."""
    s = await get_settings(get_context(), chat_id)
    if not getattr(s, "welcomeEnabled" if is_welcome else "goodbyeEnabled"):
        return
    text = getattr(s, "welcomeText" if is_welcome else "goodbyeText") or await at(
        chat_id, f"{'welcome' if is_welcome else 'goodbye'}.default"
    )
    parsed = TelegramFormatter.parse_message(
        text=text,
        user=user,
        chat_id=chat_id,
        chat_title=chat_title,
        bot_username=client.me.username,
    )
    await TelegramFormatter.send_parsed(client, chat_id, parsed)


@bot.on_message(filters.new_chat_members & filters.group, group=-40)
@safe_handler
async def welcome_handler(client: Client, message: Message) -> None:
    settings = await get_settings(get_context(), message.chat.id)
    if settings.cleanJoin:
        with contextlib.suppress(Exception):
            await message.delete()
    for m in message.new_chat_members:
        if m.id != client.me.id:
            await send_welcome_goodbye(client, message.chat.id, message.chat.title, m, True)


@bot.on_message(filters.left_chat_member & filters.group, group=-40)
@safe_handler
async def goodbye_handler(client: Client, message: Message) -> None:
    settings = await get_settings(get_context(), message.chat.id)
    if settings.cleanLeave:
        with contextlib.suppress(Exception):
            await message.delete()
    if message.left_chat_member.id != client.me.id:
        await send_welcome_goodbye(
            client, message.chat.id, message.chat.title, message.left_chat_member, False
        )


@bot.on_message(filters.command(["setwelcome", "setgoodbye"]) & filters.group)
@safe_handler
@admin_only
async def set_handler(client: Client, message: Message) -> None:
    is_w = "welcome" in message.command[0]
    key, field = ("welcome", "welcomeEnabled") if is_w else ("goodbye", "goodbyeEnabled")
    txt_field = f"{key}Text"
    ctx = get_context()

    if len(message.command) < 2:
        s = await get_settings(ctx, message.chat.id)
        new = not getattr(s, field)
        if not await has_permission(client, message.chat.id, Permission.CAN_RESTRICT):
            return await message.reply(await at(message.chat.id, "error.no_permission"))
        await update_settings(ctx, message.chat.id, **{field: new})
        return await message.reply(
            await at(message.chat.id, f"{key}.{'enabled' if new else 'disabled'}")
        )

    val = message.text.split(None, 1)[1]
    await update_settings(ctx, message.chat.id, **{field: True, txt_field: val})
    await message.reply(await at(message.chat.id, f"{key}.updated"))


@bot.on_message(filters.command("resetwelcome") & filters.group)
@safe_handler
@admin_only
async def reset_welcome_handler(client: Client, message: Message) -> None:
    await update_settings(get_context(), message.chat.id, welcomeText=None, welcomeEnabled=True)
    await message.reply(await at(message.chat.id, "welcome.reset"))


@bot.on_message(filters.command(["welcometest", "goodbyetest"]) & filters.group)
@safe_handler
@admin_only
async def test_handler(client: Client, message: Message) -> None:
    is_w = "welcome" in message.command[0]
    await send_welcome_goodbye(client, message.chat.id, message.chat.title, message.from_user, is_w)


# --- Admin Panel Input Handlers ---


@bot.on_message(filters.private & is_waiting_for_input("welcomeText"), group=-50)
@safe_handler
async def welcome_input_handler(client: Client, message: Message) -> None:
    state = message.input_state
    chat_id = state["chat_id"]
    user_id = message.from_user.id
    ctx = get_context()
    value = message.text

    from src.plugins.admin_panel.handlers.keyboards import welcome_kb
    from src.plugins.admin_panel.repository import resolve_chat_type
    from src.plugins.admin_panel.validation import is_setting_allowed

    # Validation Guard
    chat_type = await resolve_chat_type(ctx, chat_id)
    if not is_setting_allowed("welcomeText", chat_type.name.lower()):
        await message.reply(await at(user_id, "panel.setting_not_allowed_for_type"))
        return

    await update_settings(ctx, chat_id, welcomeText=str(value), welcomeEnabled=True)
    kb = await welcome_kb(ctx, chat_id, user_id=user_id)

    await finalize_input_capture(
        client,
        message,
        user_id,
        state["prompt_msg_id"],
        await at(user_id, "panel.welcome_text"),
        kb,
        success_text=await at(user_id, "panel.input_success"),
    )


register(WelcomePlugin())
