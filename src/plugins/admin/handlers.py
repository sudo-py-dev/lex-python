import time

from pyrogram import Client, filters
from pyrogram.types import ChatPrivileges, Message, User

from src.core.bot import bot
from src.utils.decorators import admin_only, resolve_target, safe_handler
from src.utils.i18n import at
from src.utils.permissions import Permission, has_permission


@bot.on_message(filters.command("start") & filters.private)
@safe_handler
async def start_handler(client: Client, message: Message) -> None:
    if len(message.command) > 1:
        payload = message.command[1]
        if payload.startswith("settings_"):
            try:
                chat_id_str = payload.replace("settings_", "")
                if not chat_id_str.startswith("-") or not chat_id_str.lstrip("-").isdigit():
                    return

                chat_id = int(chat_id_str)

                # Note: open_settings_panel internally calls is_admin
                from src.plugins.admin_panel.handlers import open_settings_panel

                await open_settings_panel(client, message, chat_id)
                return
            except Exception:
                pass

    if not message.chat or not message.from_user:
        return
    me = await client.get_me()
    await message.reply(
        await at(
            message.chat.id,
            "admin.start_text",
            name=message.from_user.first_name,
            bot_name=me.first_name,
        )
    )


@bot.on_message(filters.command("ping") & filters.group)
@safe_handler
async def ping_handler(client: Client, message: Message) -> None:
    if not message.chat:
        return
    latency = (time.time() - time.time()) * 1000
    await message.reply(await at(message.chat.id, "ping.response", ms=f"{latency:.2f}"))


@bot.on_message(filters.command("id"))
@safe_handler
async def id_handler(client: Client, message: Message) -> None:
    if not message.chat or not message.from_user:
        return
    replied = ""
    if message.reply_to_message and message.reply_to_message.from_user:
        replied = await at(
            message.chat.id, "admin.replied_id", id=message.reply_to_message.from_user.id
        )

    await message.reply(
        await at(
            message.chat.id,
            "admin.id_info",
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            replied=replied,
        )
    )


@bot.on_message(filters.command(["pin", "permapin"]) & filters.group)
@safe_handler
@admin_only
async def pin_handler(client: Client, message: Message) -> None:
    if not message.chat:
        return
    if not await has_permission(client, message.chat.id, Permission.CAN_PIN):
        await message.reply(await at(message.chat.id, "error.no_permission"))
        return
    if not message.reply_to_message:
        return
    await client.pin_chat_message(
        message.chat.id,
        message.reply_to_message.id,
        disable_notification=True,
    )


@bot.on_message(filters.command("unpin") & filters.group)
@safe_handler
@admin_only
async def unpin_handler(client: Client, message: Message) -> None:
    if not message.chat:
        return
    if not await has_permission(client, message.chat.id, Permission.CAN_PIN):
        await message.reply(await at(message.chat.id, "error.no_permission"))
        return
    if message.reply_to_message:
        await client.unpin_chat_message(message.chat.id, message.reply_to_message.id)
    else:
        await client.unpin_chat_message(message.chat.id)


@bot.on_message(filters.command("unpinall") & filters.group)
@safe_handler
@admin_only
async def unpinall_handler(client: Client, message: Message) -> None:
    if not message.chat:
        return
    if not await has_permission(client, message.chat.id, Permission.CAN_PIN):
        await message.reply(await at(message.chat.id, "error.no_permission"))
        return
    await client.unpin_all_chat_messages(message.chat.id)
    await message.reply(await at(message.chat.id, "admin.unpinned_all"))


@bot.on_message(filters.command("promote") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def promote_handler(client: Client, message: Message, target_user: User) -> None:
    if not message.chat:
        return
    if not await has_permission(client, message.chat.id, Permission.CAN_PROMOTE):
        await message.reply(await at(message.chat.id, "error.no_permission"))
        return
    title = ""
    if len(message.command) > 1 and not message.command[1].startswith("@"):
        title = " ".join(message.command[1:])
    elif len(message.command) > 2:
        title = " ".join(message.command[2:])

    await client.promote_chat_member(
        message.chat.id,
        target_user.id,
        privileges=ChatPrivileges(
            can_manage_chat=True,
            can_delete_messages=True,
            can_manage_video_chats=True,
            can_restrict_members=True,
            can_promote_members=False,
            can_change_info=False,
            can_invite_users=True,
            can_pin_messages=True,
        ),
    )
    if title:
        await client.set_administrator_custom_title(message.chat.id, target_user.id, title)
    await message.reply(await at(message.chat.id, "admin.promoted", mention=target_user.mention))


@bot.on_message(filters.command("demote") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def demote_handler(client: Client, message: Message, target_user: User) -> None:
    if not message.chat:
        return
    if not await has_permission(client, message.chat.id, Permission.CAN_PROMOTE):
        await message.reply(await at(message.chat.id, "error.no_permission"))
        return
    await client.promote_chat_member(
        message.chat.id,
        target_user.id,
        privileges=ChatPrivileges(
            can_manage_chat=False,
            can_delete_messages=False,
            can_manage_video_chats=False,
            can_restrict_members=False,
            can_promote_members=False,
            can_change_info=False,
            can_invite_users=False,
            can_pin_messages=False,
        ),
    )
    await message.reply(await at(message.chat.id, "admin.demoted", mention=target_user.mention))


@bot.on_message(filters.command("invitelink") & filters.group)
@safe_handler
@admin_only
async def invitelink_handler(client: Client, message: Message) -> None:
    if not message.chat:
        return
    if not await has_permission(client, message.chat.id, Permission.CAN_INVITE):
        await message.reply(await at(message.chat.id, "error.no_permission"))
        return
    link = await client.export_chat_invite_link(message.chat.id)
    await message.reply(await at(message.chat.id, "admin.invite_link_header", link=link))


@bot.on_message(filters.command(["info", "userinfo"]) & filters.group)
@safe_handler
@resolve_target
async def info_handler(client: Client, message: Message, target_user: User) -> None:
    if not message.chat:
        return
    text = await at(
        message.chat.id,
        "admin.user_info",
        id=target_user.id,
        first_name=target_user.first_name,
        last_name=target_user.last_name or "None",
        username=target_user.username or "None",
    )
    await message.reply(text)


@bot.on_message(filters.command("chatinfo") & filters.group)
@safe_handler
async def chatinfo_handler(client: Client, message: Message) -> None:
    if not message.chat:
        return
    chat = message.chat
    text = await at(
        message.chat.id,
        "admin.chat_info",
        title=chat.title,
        id=chat.id,
        type=chat.type.name,
        username=chat.username or "None",
        count=await client.get_chat_members_count(chat.id),
    )
    await message.reply(text)
