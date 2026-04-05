import json
from enum import Enum

from loguru import logger
from pyrogram import Client
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import ChatMember, ChatPermissions

from .admin_cache import is_admin as cached_is_admin

_BOT_ID: int | None = None

RESTRICTED_PERMISSIONS = ChatPermissions(
    can_send_messages=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
    can_change_info=False,
    can_invite_users=False,
    can_pin_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
)

UNRESTRICTED_PERMISSIONS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_add_web_page_previews=True,
    can_change_info=True,
    can_invite_users=True,
    can_pin_messages=True,
)


class Permission(Enum):
    CAN_BAN = "can_restrict_members"
    CAN_RESTRICT = "can_restrict_members"
    CAN_PROMOTE = "can_promote_members"
    CAN_DELETE = "can_delete_messages"
    CAN_PIN = "can_pin_messages"
    CAN_INVITE = "can_invite_users"


async def is_admin(client: Client, chat_id: int | None, user_id: int | None) -> bool:
    """Check if user is admin. Now uses Redis cache by default."""
    if chat_id is None or user_id is None:
        return False
    return await cached_is_admin(client, chat_id, user_id)


async def has_permission(client: Client, chat_id: int | None, permission: Permission) -> bool:
    """Check if the BOT has a specific permission in a chat."""
    if chat_id is None:
        return False
    global _BOT_ID
    try:
        if _BOT_ID is None:
            me = await client.get_me()
            _BOT_ID = me.id

        member: ChatMember = await client.get_chat_member(chat_id, _BOT_ID)

        if member.status == ChatMemberStatus.OWNER:
            return True

        if member.status == ChatMemberStatus.ADMINISTRATOR:
            if not member.privileges:
                return False
            can_do = getattr(member.privileges, permission.value, False)
            logger.debug(
                f"{client.me.username} permission check in {chat_id}: {permission.value} -> {can_do}"
            )
            return can_do

        return False
    except Exception as e:
        logger.error(f"Permission check error in {chat_id}: {e}")
        return False


async def can_restrict_members(client: Client, chat_id: int | None) -> bool:
    return await has_permission(client, chat_id, Permission.CAN_BAN)


def serialize_permissions(perms: ChatPermissions) -> str:
    """Serialize ChatPermissions to a JSON string."""
    data = {
        k: v for k, v in perms.__dict__.items() if not k.startswith("_") and isinstance(v, bool)
    }
    return json.dumps(data)


def deserialize_permissions(data_str: str) -> ChatPermissions:
    """Deserialize a JSON string back into a ChatPermissions object."""
    try:
        data = json.loads(data_str)
        return ChatPermissions(**data)
    except Exception as e:
        logger.error(f"Failed to deserialize permissions: {e}")
        return UNRESTRICTED_PERMISSIONS
