from pyrogram import Client, filters
from pyrogram.types import Message
from sqlalchemy import select

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.models import DisabledCommand
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at


class DisablePlugin(Plugin):
    """Plugin to disable and enable specific bot commands on a per-chat basis."""

    name = "disable"
    priority = 1

    async def setup(self, client: Client, ctx) -> None:
        pass


async def disable_command(ctx, chat_id: int, command: str) -> DisabledCommand:
    """Add a command to the disabled list for a specific chat."""
    async with ctx.db() as session:
        stmt = select(DisabledCommand).where(
            DisabledCommand.chatId == chat_id, DisabledCommand.command == command
        )
        result = await session.execute(stmt)
        cmd = result.scalars().first()
        if cmd:
            return cmd
        cmd = DisabledCommand(chatId=chat_id, command=command)
        session.add(cmd)
        await session.commit()
        await session.refresh(cmd)
        return cmd


async def enable_command(ctx, chat_id: int, command: str) -> bool:
    """Remove a command from the disabled list for a specific chat."""
    async with ctx.db() as session:
        stmt = select(DisabledCommand).where(
            DisabledCommand.chatId == chat_id, DisabledCommand.command == command
        )
        result = await session.execute(stmt)
        cmd = result.scalars().first()
        if cmd:
            await session.delete(cmd)
            await session.commit()
            return True
        return False


async def is_command_disabled(ctx, chat_id: int, command: str) -> bool:
    """Check if a specific command is disabled in a chat."""
    async with ctx.db() as session:
        stmt = select(DisabledCommand).where(
            DisabledCommand.chatId == chat_id, DisabledCommand.command == command
        )
        result = await session.execute(stmt)
        cmd = result.scalars().first()
        return cmd is not None


async def get_disabled_commands(ctx, chat_id: int) -> list[DisabledCommand]:
    """Retrieve all disabled commands for a specific chat."""
    async with ctx.db() as session:
        stmt = select(DisabledCommand).where(DisabledCommand.chatId == chat_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def clear_all_disabled(ctx, chat_id: int) -> int:
    """Remove all disabled command restrictions for a specific chat."""
    async with ctx.db() as session:
        stmt = select(DisabledCommand).where(DisabledCommand.chatId == chat_id)
        result = await session.execute(stmt)
        cmds = result.scalars().all()
        count = len(cmds)
        for cmd in cmds:
            await session.delete(cmd)
        await session.commit()
        return count


NON_DISABLEABLE = {"enable", "disable", "disabled", "settings", "start", "help"}


@bot.on_message(filters.command("disable") & filters.group)
@safe_handler
@admin_only
async def disable_handler(client: Client, message: Message) -> None:
    """Disable a specific command in the current group."""
    if len(message.command) < 2:
        return
    ctx = get_context()
    command = message.command[1].lower().replace("/", "")
    if command in NON_DISABLEABLE:
        await message.reply(await at(message.chat.id, "disable.not_disableable"))
        return
    await disable_command(ctx, message.chat.id, command)
    await message.reply(await at(message.chat.id, "disable.done", command=command))


@bot.on_message(filters.command("enable") & filters.group)
@safe_handler
@admin_only
async def enable_handler(client: Client, message: Message) -> None:
    """Enable a previously disabled command in the current group."""
    if len(message.command) < 2:
        return
    ctx = get_context()
    command = message.command[1].lower().replace("/", "")
    await enable_command(ctx, message.chat.id, command)
    await message.reply(await at(message.chat.id, "disable.enabled", command=command))


@bot.on_message(filters.command("disabled") & filters.group)
@safe_handler
async def list_disabled_handler(client: Client, message: Message) -> None:
    """List all currently disabled commands in the group."""
    ctx = get_context()
    disabled = await get_disabled_commands(ctx, message.chat.id)
    if not disabled:
        await message.reply(await at(message.chat.id, "disable.list_empty"))
        return
    text = await at(message.chat.id, "disable.list_header")
    for d in disabled:
        text += f"\n• `/{d.command}`"
    await message.reply(text)


@bot.on_message(filters.group, group=-2)
@safe_handler
async def disable_interceptor(client: Client, message: Message) -> None:
    """Interceptor to block execution of disabled commands."""
    if not message.command:
        return
    ctx = get_context()
    command = message.command[0].lower()
    if command in NON_DISABLEABLE:
        return
    if await is_command_disabled(ctx, message.chat.id, command):
        message.stop_propagation()


register(DisablePlugin())
