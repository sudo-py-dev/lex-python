from pyrogram import Client, ContinuePropagation, filters
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.types import ChatMemberUpdated, Message

from src.core.bot import bot
from src.core.context import get_context
from src.db.repositories.admins import remove_admin, upsert_admin
from src.utils.admin_cache import invalidate_cache

_REGISTERED_CHATS = set()


async def _ensure_chat_identity(ctx, chat):
    """Ensure the chat type and title are correctly persisted in the database."""
    if chat.id in _REGISTERED_CHATS:
        return
    from src.db.models import ChatSettings

    async with ctx.db() as session:
        settings = await session.get(ChatSettings, chat.id)
        if not settings:
            settings = ChatSettings(id=chat.id)

        raw_type = chat.type.name.lower()
        chat_type = "group" if raw_type in ("group", "supergroup") else "channel"

        if settings.chatType != chat_type or settings.title != chat.title:
            settings.chatType = chat_type
            settings.title = chat.title
            session.add(settings)
            await session.commit()
    _REGISTERED_CHATS.add(chat.id)


@bot.on_message(filters.group | filters.channel, group=-90)
async def auto_register_chat(client: Client, message: Message):
    """Automatically register chat identity on any incoming message."""
    await _ensure_chat_identity(get_context(), message.chat)
    raise ContinuePropagation


@bot.on_chat_member_updated(group=-90)
async def on_chat_member_updated(client: Client, update: ChatMemberUpdated):
    """
    Real-time synchronization of group administrators and bot identity.
    Tracks promotions, demotions, departures, and chat meta updates.
    """
    if update.chat.type == ChatType.PRIVATE:
        return

    chat_id = update.chat.id
    user_id = (
        update.new_chat_member.user.id if update.new_chat_member else update.old_chat_member.user.id
    )

    ctx = get_context()
    new_status = update.new_chat_member.status if update.new_chat_member else None

    # Handle bot's own status changes (replaces legacy status.py and registration.py)
    if user_id == client.me.id:
        from src.db.models import ChatSettings

        # Ensure identity is synced when bot joins or is updated
        await _ensure_chat_identity(ctx, update.chat)

        # Bot is active if it's an admin, owner, or regular member (in groups)
        is_active = new_status in {
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
            ChatMemberStatus.MEMBER,
        }
        async with ctx.db() as session:
            settings = await session.get(ChatSettings, chat_id)
            if settings:
                settings.isActive = is_active
                # Save actual privileges too
                if update.new_chat_member and update.new_chat_member.privileges:
                    import json

                    m = update.new_chat_member
                    privs = {
                        attr: getattr(m.privileges, attr, False)
                        for attr in dir(m.privileges)
                        if attr.startswith("can_")
                    }
                    settings.botPrivileges = json.dumps(privs)
                    # Update cache
                    await invalidate_cache(chat_id, user_id)
                    from src.utils.local_cache import get_cache

                    await get_cache().setex(f"bot_privs:{chat_id}", 3600, privs)
                else:
                    settings.botPrivileges = None

                session.add(settings)
                await session.commit()

        raise ContinuePropagation

    old_status = update.old_chat_member.status if update.old_chat_member else None

    was_admin = old_status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER}
    is_admin = new_status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER}

    # Case 1: Promoted
    if not was_admin and is_admin:
        m = update.new_chat_member
        status_name = m.status.name.lower()
        privs = None
        if m.privileges:
            privs = {
                attr: getattr(m.privileges, attr, False)
                for attr in dir(m.privileges)
                if attr.startswith("can_")
            }
        await upsert_admin(
            ctx, chat_id, user_id, status_name, m.user.first_name, m.user.username, privs
        )
        await invalidate_cache(chat_id, user_id)
        raise ContinuePropagation

    # Case 2: Demoted, Left, or Banned
    if was_admin and not is_admin:
        await remove_admin(ctx, chat_id, user_id)
        await invalidate_cache(chat_id, user_id)
        raise ContinuePropagation

    # Case 3: Role update (e.g. Administrator privileges changed)
    if was_admin and is_admin:
        m = update.new_chat_member
        status_name = m.status.name.lower()
        privs = None
        if m.privileges:
            privs = {
                attr: getattr(m.privileges, attr, False)
                for attr in dir(m.privileges)
                if attr.startswith("can_")
            }
        await upsert_admin(
            ctx, chat_id, user_id, status_name, m.user.first_name, m.user.username, privs
        )
        await invalidate_cache(chat_id, user_id)

    raise ContinuePropagation
