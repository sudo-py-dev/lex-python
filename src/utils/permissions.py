import json

from pyrogram import Client
from pyrogram.types import ChatPermissions

from .admin_cache import (
    RESTRICTED_PERMISSIONS,
    UNRESTRICTED_PERMISSIONS,
    Permission,
)
from .admin_cache import check_user_permission as fast_check_user_permission
from .admin_cache import has_permission as fast_has_permission
from .admin_cache import is_admin as fast_is_admin

__all__ = [
    "Permission",
    "RESTRICTED_PERMISSIONS",
    "UNRESTRICTED_PERMISSIONS",
    "is_admin",
    "is_whitelisted",
    "check_user_permission",
    "has_permission",
    "serialize_permissions",
    "deserialize_permissions",
]


async def is_admin(client: Client, chat_id: int | None, user_id: int | None) -> bool:
    """Check if user is admin. Redirects to unified 3-tier cache."""
    if chat_id is None or user_id is None:
        return False

    if user_id == chat_id:
        return True

    if user_id == client.me.id:
        return True

    return await fast_is_admin(client, chat_id, user_id)


async def is_whitelisted(client: Client, chat_id: int | None, user_id: int | None) -> bool:
    """Check if user is admin OR approved. Uses unified admin cache."""
    if chat_id is None or user_id is None:
        return False

    if user_id == chat_id:
        return True

    if user_id == client.me.id:
        return True

    if await is_admin(client, chat_id, user_id):
        return True

    if chat_id and user_id and chat_id < 0 and user_id < 0:
        from src.core.context import get_context
        from src.db.repositories.chats import get_chat_settings

        settings = await get_chat_settings(get_context(), chat_id)
        if settings and settings.linkedChatId == user_id:
            if await is_admin(client, user_id, client.me.id):
                return True

    from .approved_cache import is_approved as cached_is_approved

    return await cached_is_approved(chat_id, user_id)


async def check_user_permission(
    client: Client, chat_id: int | None, user_id: int, permission: Permission
) -> bool:
    """Check specific user privilege. Redirects to unified 3-tier cache."""
    return await fast_check_user_permission(client, chat_id, user_id, permission)


async def has_permission(client: Client, chat_id: int | None, permission: Permission) -> bool:
    """Check if BOT has specific permission. Redirects to unified optimized cache."""
    return await fast_has_permission(client, chat_id, permission)


def serialize_permissions(perms: ChatPermissions) -> str:
    """Serialize ChatPermissions object to JSON string."""
    return json.dumps(
        {
            attr: getattr(perms, attr, False)
            for attr in dir(perms)
            if not attr.startswith("_") and not callable(getattr(perms, attr))
        }
    )


def deserialize_permissions(data: str | None) -> ChatPermissions:
    """Deserialize JSON string to ChatPermissions object."""
    if not data:
        return UNRESTRICTED_PERMISSIONS
    try:
        return ChatPermissions(**json.loads(data))
    except (json.JSONDecodeError, TypeError):
        return UNRESTRICTED_PERMISSIONS
