import asyncio
import json

from pyrogram import Client
from sqlalchemy import and_, select

from src.core.context import AppContext
from src.db.models import GroupSettings
from src.utils.i18n import at
from src.utils.permissions import is_admin


async def get_chat_settings(ctx: AppContext, chat_id: int) -> GroupSettings:
    async with ctx.db() as session:
        settings = await session.get(GroupSettings, chat_id)
        if not settings:
            settings = GroupSettings(id=chat_id)
            session.add(settings)
            await session.commit()
            await session.refresh(settings)
        return settings


async def toggle_setting(ctx: AppContext, chat_id: int, field: str) -> bool:
    async with ctx.db() as session:
        settings = await session.get(GroupSettings, chat_id)
        if not settings:
            settings = GroupSettings(id=chat_id)
            session.add(settings)
            await session.commit()
            await session.refresh(settings)

        current_value = getattr(settings, field)
        new_value = not current_value
        setattr(settings, field, new_value)

        session.add(settings)
        await session.commit()
        return new_value


async def update_chat_setting(ctx: AppContext, chat_id: int, field: str, value: int | str) -> None:
    async with ctx.db() as session:
        settings = await session.get(GroupSettings, chat_id)
        if not settings:
            settings = GroupSettings(id=chat_id)
            session.add(settings)

        setattr(settings, field, value)
        session.add(settings)
        await session.commit()


async def toggle_service_type(ctx: AppContext, chat_id: int, service_type: str) -> None:
    async with ctx.db() as session:
        settings = await session.get(GroupSettings, chat_id)
        if not settings:
            settings = GroupSettings(id=chat_id)
            session.add(settings)
            await session.commit()
            await session.refresh(settings)

        try:
            types = json.loads(settings.cleanServiceTypes)
        except (json.JSONDecodeError, TypeError):
            types = []

        if service_type in types:
            types.remove(service_type)
        else:
            types.append(service_type)

        settings.cleanServiceTypes = json.dumps(types)
        session.add(settings)
        await session.commit()


async def get_user_admin_groups(
    ctx: AppContext, client: Client, user_id: int
) -> list[tuple[int, str]]:
    async with ctx.db() as session:
        stmt = select(GroupSettings).where(and_(GroupSettings.isActive, GroupSettings.id < 0))
        result = await session.execute(stmt)
        all_settings = result.scalars().all()

    results = []
    semaphore = asyncio.Semaphore(10)

    async def check(chat_id: int):
        async with semaphore:
            if await is_admin(client, chat_id, user_id):
                try:
                    chat = await client.get_chat(chat_id)
                    title = chat.title or await at(user_id, "panel.unknown_chat", id=chat_id)
                    results.append((chat_id, title))
                except Exception:
                    # Fallback for chats bot is in but can't fetch (e.g. restricted)
                    title = await at(user_id, "panel.unknown_chat", id=chat_id)
                    results.append((chat_id, title))

    tasks = [check(int(s.id)) for s in all_settings]
    await asyncio.gather(*tasks)
    return results


async def set_chat_active_status(ctx: AppContext, chat_id: int, status: bool) -> None:
    async with ctx.db() as session:
        settings = await session.get(GroupSettings, chat_id)
        if not settings:
            settings = GroupSettings(id=chat_id)

        settings.isActive = status
        session.add(settings)
        await session.commit()
