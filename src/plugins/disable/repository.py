from sqlalchemy import select

from src.core.context import AppContext
from src.db.models import DisabledCommand


async def disable_command(ctx: AppContext, chat_id: int, command: str) -> DisabledCommand:
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


async def enable_command(ctx: AppContext, chat_id: int, command: str) -> bool:
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


async def is_command_disabled(ctx: AppContext, chat_id: int, command: str) -> bool:
    async with ctx.db() as session:
        stmt = select(DisabledCommand).where(
            DisabledCommand.chatId == chat_id, DisabledCommand.command == command
        )
        result = await session.execute(stmt)
        cmd = result.scalars().first()
        return cmd is not None


async def get_disabled_commands(ctx: AppContext, chat_id: int) -> list[DisabledCommand]:
    async with ctx.db() as session:
        stmt = select(DisabledCommand).where(DisabledCommand.chatId == chat_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def clear_all_disabled(ctx: AppContext, chat_id: int) -> int:
    async with ctx.db() as session:
        stmt = select(DisabledCommand).where(DisabledCommand.chatId == chat_id)
        result = await session.execute(stmt)
        cmds = result.scalars().all()
        count = len(cmds)
        for cmd in cmds:
            await session.delete(cmd)
        await session.commit()
        return count
