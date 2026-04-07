import asyncio
import contextlib
import json
from typing import Any

from pyrogram import Client
from pyrogram.enums import ChatType
from sqlalchemy import and_, select

from src.core.context import AppContext
from src.db.models import ChatSettings
from src.utils.i18n import at
from src.utils.permissions import is_admin


async def get_chat_settings(ctx: AppContext, chat_id: int) -> ChatSettings:
    """Get chat settings, creating them if they don't exist."""
    async with ctx.db() as session:
        settings = await session.get(ChatSettings, chat_id)
        if not settings:
            settings = ChatSettings(id=chat_id)
            session.add(settings)
            await session.commit()
            await session.refresh(settings)
        return settings


async def toggle_setting(ctx: AppContext, chat_id: int, field: str) -> bool:
    """Toggle a boolean setting field."""
    async with ctx.db() as session:
        settings = await session.get(ChatSettings, chat_id)
        if not settings:
            settings = ChatSettings(id=chat_id)
            session.add(settings)
            await session.commit()
            await session.refresh(settings)

        current_value = getattr(settings, field)
        new_value = not current_value
        setattr(settings, field, new_value)

        session.add(settings)
        await session.commit()
        return new_value


async def update_chat_setting(ctx: AppContext, chat_id: int, field: str, value: Any) -> None:
    """Update a specific setting field with a value."""
    async with ctx.db() as session:
        settings = await session.get(ChatSettings, chat_id)
        if not settings:
            settings = ChatSettings(id=chat_id)
            session.add(settings)
            await session.commit()
            await session.refresh(settings)

        setattr(settings, field, value)
        session.add(settings)
        await session.commit()


async def update_settings(ctx: AppContext, chat_id: int, **kwargs) -> ChatSettings:
    """Update multiple fields in ChatSettings (Legacy compatibility)."""
    async with ctx.db() as session:
        settings = await session.get(ChatSettings, chat_id)
        if not settings:
            settings = ChatSettings(id=chat_id, **kwargs)
            session.add(settings)
        else:
            for key, value in kwargs.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
            session.add(settings)

        await session.commit()
        await session.refresh(settings)
        return settings


async def update_chat_title(ctx: AppContext, chat_id: int, title: str) -> None:
    """Update the persistent chat title in the database."""
    async with ctx.db() as session:
        settings = await session.get(ChatSettings, chat_id)
        if not settings:
            settings = ChatSettings(id=chat_id)

        settings.title = title
        session.add(settings)
        await session.commit()


async def toggle_service_type(ctx: AppContext, chat_id: int, service_type: str) -> None:
    """Toggle a service message type in the cleanServiceTypes JSON array."""
    async with ctx.db() as session:
        settings = await session.get(ChatSettings, chat_id)
        if not settings:
            settings = ChatSettings(id=chat_id)
            session.add(settings)
            await session.commit()
            await session.refresh(settings)

        try:
            types = json.loads(settings.cleanServiceTypes) if settings.cleanServiceTypes else []
        except (json.JSONDecodeError, TypeError):
            types = []

        if service_type in types:
            types.remove(service_type)
        else:
            types.append(service_type)

        settings.cleanServiceTypes = json.dumps(types)
        session.add(settings)
        await session.commit()


async def get_user_admin_chats(
    ctx: AppContext, client: Client, user_id: int, chat_type: ChatType | None = None
) -> list[tuple[int, str]]:
    """Get active chats where user is admin, optionally filtered by type."""
    async with ctx.db() as session:
        stmt = select(ChatSettings).where(and_(ChatSettings.isActive, ChatSettings.id < 0))
        if chat_type:
            stmt = stmt.where(ChatSettings.chatType == chat_type.name.lower())
        result = await session.execute(stmt)
        all_settings = result.scalars().all()

    results = []
    semaphore = asyncio.Semaphore(10)

    async def check(chat_id: int, stored_type: str):
        async with semaphore:
            if await is_admin(client, chat_id, user_id):
                try:
                    chat = await client.get_chat(chat_id)
                    if chat.type.name.lower() != stored_type:
                        await update_chat_setting(ctx, chat_id, "chatType", chat.type.name.lower())

                    title = chat.title or await at(user_id, "panel.unknown_chat", id=chat_id)
                    results.append((chat_id, title))
                except Exception:
                    title = await at(user_id, "panel.unknown_chat", id=chat_id)
                    results.append((chat_id, title))

    tasks = [check(int(s.id), s.chatType) for s in all_settings]
    await asyncio.gather(*tasks)
    return results


async def get_chat_info(ctx: AppContext, chat_id: int) -> tuple[ChatType, str]:
    """Resolve ChatType and title for a chat, with fallbacks."""
    settings = await get_chat_settings(ctx, chat_id)
    chat_type = ChatType.SUPERGROUP
    title = settings.title or f"Chat {chat_id}"

    if settings and settings.chatType:
        with contextlib.suppress(KeyError, AttributeError):
            chat_type = ChatType[settings.chatType.upper()]

    from src.core.bot import bot

    try:
        chat = await bot.get_chat(chat_id)
        chat_type = chat.type
        title = chat.title or chat.first_name or title
        if title != settings.title:
            await update_chat_title(ctx, chat_id, title)
    except Exception:
        pass

    return chat_type, title


async def resolve_chat_type(ctx: AppContext, chat_id: int) -> ChatType:
    """Resolve ChatType from DB with Pyrogram fallback."""
    chat_type, _ = await get_chat_info(ctx, chat_id)
    return chat_type


async def set_chat_active_status(ctx: AppContext, chat_id: int, is_active: bool) -> None:
    """Set the active status of a chat."""
    async with ctx.db() as session:
        settings = await session.get(ChatSettings, chat_id)
        if not settings:
            settings = ChatSettings(id=chat_id, isActive=is_active)
            session.add(settings)
        else:
            settings.isActive = is_active
            session.add(settings)
        await session.commit()
