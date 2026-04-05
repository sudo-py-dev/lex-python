import contextlib

from pyrogram import Client, filters
from pyrogram.types import Message, User

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.group_settings import get_settings, update_settings
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at


class WelcomePlugin(Plugin):
    """Plugin to handle welcome and goodbye messages."""

    name = "welcome"
    priority = 100

    async def setup(self, client: Client, ctx) -> None:
        pass


def _format_welcome(text: str, user: User, chat_title: str) -> str:
    """Helper to format welcome/goodbye messages with placeholders.

    Placeholders:
    - {mention}: Mention of the user
    - {name}: First name of the user
    - {first_name}: First name of the user
    - {last_name}: Last name of the user (if any)
    - {id}: ID of the user
    - {username}: Username of the user (prefabs to @first_name if not available)
    - {chat}: Title of the chat
    - {chat_name}: Title of the chat
    """
    return (
        text.replace("{mention}", user.mention)
        .replace("{name}", user.first_name)
        .replace("{first_name}", user.first_name)
        .replace("{last_name}", user.last_name or "")
        .replace("{id}", str(user.id))
        .replace("{username}", f"@{user.username}" if user.username else user.first_name)
        .replace("{chat}", chat_title)
        .replace("{chat_name}", chat_title)
    )


async def send_welcome(client: Client, chat_id: int, chat_title: str, user: User) -> None:
    """Send a welcome message to a specific user in a chat."""
    ctx = get_context()
    settings = await get_settings(ctx, chat_id)
    if not settings.welcomeEnabled:
        return
    text = settings.welcomeText or await at(chat_id, "welcome.default")
    formatted_text = _format_welcome(text, user, chat_title)
    await client.send_message(chat_id, formatted_text)


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
    formatted_text = _format_welcome(text, left_member, message.chat.title)
    await message.reply(formatted_text)


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
    formatted_text = _format_welcome(text, message.from_user, message.chat.title)
    await message.reply(await at(message.chat.id, "welcome.test", text=formatted_text))


@bot.on_message(filters.command("goodbyetest") & filters.group)
@safe_handler
@admin_only
async def goodbye_test_handler(client: Client, message: Message) -> None:
    """Test the goodbye message with current settings."""
    ctx = get_context()
    settings = await get_settings(ctx, message.chat.id)
    text = settings.goodbyeText or await at(message.chat.id, "goodbye.default")
    formatted_text = _format_welcome(text, message.from_user, message.chat.title)
    await message.reply(await at(message.chat.id, "goodbye.test", text=formatted_text))


register(WelcomePlugin())
