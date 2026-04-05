from src.core.context import AppContext
from src.db.models import GroupRules


async def set_rules(ctx: AppContext, chat_id: int, content: str) -> GroupRules:
    """Set or update the rules for a chat."""
    async with ctx.db() as session:
        obj = await session.get(GroupRules, chat_id)
        if obj:
            obj.content = content
            session.add(obj)
        else:
            obj = GroupRules(chatId=chat_id, content=content)
            session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return obj


async def get_rules(ctx: AppContext, chat_id: int) -> GroupRules | None:
    """Get the rules for a chat."""
    async with ctx.db() as session:
        return await session.get(GroupRules, chat_id)


async def clear_rules(ctx: AppContext, chat_id: int) -> bool:
    """Clear the rules for a chat."""
    async with ctx.db() as session:
        obj = await session.get(GroupRules, chat_id)
        if obj:
            await session.delete(obj)
            await session.commit()
            return True
        return False


async def toggle_private_rules(ctx: AppContext, chat_id: int, private_mode: bool) -> GroupRules:
    """Toggle whether rules are sent in private or in the chat."""
    async with ctx.db() as session:
        obj = await session.get(GroupRules, chat_id)
        if obj:
            obj.privateMode = private_mode
            session.add(obj)
        else:
            obj = GroupRules(chatId=chat_id, content="", privateMode=private_mode)
            session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return obj
