import contextlib

from pyrogram import Client, filters
from pyrogram.types import Message, User

from src.core.bot import bot
from src.plugins.admin_panel.repository import get_chat_settings
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at

from . import get_ctx


def _format_welcome(text: str, user: User, chat_title: str) -> str:
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
    ctx = get_ctx()
    settings = await get_chat_settings(ctx, chat_id)
    if not settings.welcomeEnabled:
        return
    text = settings.welcomeText or await at(chat_id, "welcome.default")
    formatted_text = _format_welcome(text, user, chat_title)
    await client.send_message(chat_id, formatted_text)


@bot.on_message(filters.new_chat_members & filters.group)
@safe_handler
async def welcome_handler(client: Client, message: Message) -> None:
    ctx = get_ctx()
    settings = await get_chat_settings(ctx, message.chat.id)
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
    ctx = get_ctx()
    settings = await get_chat_settings(ctx, message.chat.id)
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
    ctx = get_ctx()
    if len(message.command) < 2:
        settings = await get_chat_settings(ctx, message.chat.id)
        new_state = not settings.welcomeEnabled
        await ctx.db.groupsettings.update(
            where={"id": message.chat.id}, data={"welcomeEnabled": new_state}
        )
        await message.reply(
            await at(message.chat.id, f"welcome.{'enabled' if new_state else 'disabled'}")
        )
        return

    welcome_text = message.text.split(None, 1)[1]
    await ctx.db.groupsettings.update(
        where={"id": message.chat.id}, data={"welcomeEnabled": True, "welcomeText": welcome_text}
    )
    await message.reply(await at(message.chat.id, "welcome.updated"))


@bot.on_message(filters.command("setgoodbye") & filters.group)
@safe_handler
@admin_only
async def set_goodbye_handler(client: Client, message: Message) -> None:
    ctx = get_ctx()
    if len(message.command) < 2:
        settings = await get_chat_settings(ctx, message.chat.id)
        new_state = not settings.goodbyeEnabled
        await ctx.db.groupsettings.update(
            where={"id": message.chat.id}, data={"goodbyeEnabled": new_state}
        )
        await message.reply(
            await at(message.chat.id, f"goodbye.{'enabled' if new_state else 'disabled'}")
        )
        return

    goodbye_text = message.text.split(None, 1)[1]
    await ctx.db.groupsettings.update(
        where={"id": message.chat.id}, data={"goodbyeEnabled": True, "goodbyeText": goodbye_text}
    )
    await message.reply(await at(message.chat.id, "goodbye.updated"))


@bot.on_message(filters.command("resetwelcome") & filters.group)
@safe_handler
@admin_only
async def reset_welcome_handler(client: Client, message: Message) -> None:
    ctx = get_ctx()
    await ctx.db.groupsettings.update(
        where={"id": message.chat.id}, data={"welcomeText": None, "welcomeEnabled": True}
    )
    await message.reply(await at(message.chat.id, "welcome.reset"))


@bot.on_message(filters.command("welcometest") & filters.group)
@safe_handler
@admin_only
async def welcome_test_handler(client: Client, message: Message) -> None:
    ctx = get_ctx()
    settings = await get_chat_settings(ctx, message.chat.id)
    text = settings.welcomeText or await at(message.chat.id, "welcome.default")
    formatted_text = _format_welcome(text, message.from_user, message.chat.title)
    await message.reply(await at(message.chat.id, "welcome.test", text=formatted_text))


@bot.on_message(filters.command("goodbyetest") & filters.group)
@safe_handler
@admin_only
async def goodbye_test_handler(client: Client, message: Message) -> None:
    ctx = get_ctx()
    settings = await get_chat_settings(ctx, message.chat.id)
    text = settings.goodbyeText or await at(message.chat.id, "goodbye.default")
    formatted_text = _format_welcome(text, message.from_user, message.chat.title)
    await message.reply(await at(message.chat.id, "goodbye.test", text=formatted_text))
