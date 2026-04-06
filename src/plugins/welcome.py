import contextlib

from pyrogram import Client, filters
from pyrogram.types import Message, User

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.group_settings import get_settings, update_settings
from src.utils.decorators import admin_only, safe_handler
from src.utils.formatters import TelegramFormatter
from src.utils.i18n import at


class WelcomePlugin(Plugin):
    """Plugin to handle welcome and goodbye messages."""

    name = "welcome"
    priority = 100

    async def setup(self, client: Client, ctx) -> None:
        pass


async def send_welcome(client: Client, chat_id: int, chat_title: str, user: User) -> None:
    """Send a welcome message to a specific user in a chat."""
    ctx = get_context()
    settings = await get_settings(ctx, chat_id)
    if not settings.welcomeEnabled:
        return
    text = settings.welcomeText or await at(chat_id, "welcome.default")
    parsed = TelegramFormatter.parse_message(
        text=text,
        user=user,
        chat_id=chat_id,
        chat_title=chat_title,
        bot_username=client.me.username,
    )
    await TelegramFormatter.send_parsed(client, chat_id, parsed)


@bot.on_message(filters.new_chat_members & filters.group)
@safe_handler
async def welcome_handler(client: Client, message: Message) -> None:
    """Detect new members and send welcome messages."""
    ctx = get_context()
    settings = await get_settings(ctx, message.chat.id)
    if settings.cleanJoin:
        with contextlib.suppress(Exception):
            await message.delete()

    for new_member in message.new_chat_members:
        if new_member.id == client.me.id:
            continue
        await send_welcome(client, message.chat.id, message.chat.title, new_member)


@bot.on_message(filters.left_chat_member & filters.group)
@safe_handler
async def goodbye_handler(client: Client, message: Message) -> None:
    """Detect departing members and send goodbye messages."""
    ctx = get_context()
    settings = await get_settings(ctx, message.chat.id)
    if settings.cleanLeave:
        with contextlib.suppress(Exception):
            await message.delete()

    if not settings.goodbyeEnabled:
        return

    left_member = message.left_chat_member
    if left_member.id == client.me.id:
        return

    text = settings.goodbyeText or await at(message.chat.id, "goodbye.default")
    parsed = TelegramFormatter.parse_message(
        text=text,
        user=left_member,
        chat_id=message.chat.id,
        chat_title=message.chat.title,
        bot_username=client.me.username,
    )
    await TelegramFormatter.send_parsed(client, message.chat.id, parsed)


@bot.on_message(filters.command("setwelcome") & filters.group)
@safe_handler
@admin_only
async def set_welcome_handler(client: Client, message: Message) -> None:
    """Force enable/disable welcome or update the greeting text."""
    ctx = get_context()
    if len(message.command) < 2:
        settings = await get_settings(ctx, message.chat.id)
        new_state = not settings.welcomeEnabled
        await update_settings(ctx, message.chat.id, welcomeEnabled=new_state)
        await message.reply(
            await at(message.chat.id, f"welcome.{'enabled' if new_state else 'disabled'}")
        )
        return

    welcome_text = message.text.split(None, 1)[1]
    await update_settings(ctx, message.chat.id, welcomeEnabled=True, welcomeText=welcome_text)
    await message.reply(await at(message.chat.id, "welcome.updated"))


@bot.on_message(filters.command("setgoodbye") & filters.group)
@safe_handler
@admin_only
async def set_goodbye_handler(client: Client, message: Message) -> None:
    """Force enable/disable goodbye or update the farewell text."""
    ctx = get_context()
    if len(message.command) < 2:
        settings = await get_settings(ctx, message.chat.id)
        new_state = not settings.goodbyeEnabled
        await update_settings(ctx, message.chat.id, goodbyeEnabled=new_state)
        await message.reply(
            await at(message.chat.id, f"goodbye.{'enabled' if new_state else 'disabled'}")
        )
        return

    goodbye_text = message.text.split(None, 1)[1]
    await update_settings(ctx, message.chat.id, goodbyeEnabled=True, goodbyeText=goodbye_text)
    await message.reply(await at(message.chat.id, "goodbye.updated"))


@bot.on_message(filters.command("resetwelcome") & filters.group)
@safe_handler
@admin_only
async def reset_welcome_handler(client: Client, message: Message) -> None:
    """Reset welcome text to default."""
    ctx = get_context()
    await update_settings(ctx, message.chat.id, welcomeText=None, welcomeEnabled=True)
    await message.reply(await at(message.chat.id, "welcome.reset"))


@bot.on_message(filters.command("welcometest") & filters.group)
@safe_handler
@admin_only
async def welcome_test_handler(client: Client, message: Message) -> None:
    """Test the welcome message with current settings."""
    ctx = get_context()
    settings = await get_settings(ctx, message.chat.id)
    text = settings.welcomeText or await at(message.chat.id, "welcome.default")
    parsed = TelegramFormatter.parse_message(
        text=text,
        user=message.from_user,
        chat_id=message.chat.id,
        chat_title=message.chat.title,
        bot_username=client.me.username,
    )
    parsed["text"] = await at(message.chat.id, "welcome.test", text=parsed["text"])
    await TelegramFormatter.send_parsed(client, message.chat.id, parsed)


@bot.on_message(filters.command("goodbyetest") & filters.group)
@safe_handler
@admin_only
async def goodbye_test_handler(client: Client, message: Message) -> None:
    """Test the goodbye message with current settings."""
    ctx = get_context()
    settings = await get_settings(ctx, message.chat.id)
    text = settings.goodbyeText or await at(message.chat.id, "goodbye.default")
    parsed = TelegramFormatter.parse_message(
        text=text,
        user=message.from_user,
        chat_id=message.chat.id,
        chat_title=message.chat.title,
        bot_username=client.me.username,
    )
    parsed["text"] = await at(message.chat.id, "goodbye.test", text=parsed["text"])
    await TelegramFormatter.send_parsed(client, message.chat.id, parsed)


register(WelcomePlugin())
