import time

from pyrogram import Client, filters
from pyrogram.types import (
    ChatPrivileges,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    User,
)

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.utils.decorators import admin_only, resolve_target, safe_handler
from src.utils.i18n import at
from src.utils.input import finalize_input_capture, is_waiting_for_input
from src.utils.permissions import Permission, has_permission


class AdminPlugin(Plugin):
    """Plugin for core administrative commands and information."""

    name = "admin"
    priority = 100

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.command("start") & filters.private)
@safe_handler
async def start_handler(client: Client, message: Message) -> None:
    """
    Entry point for the bot, provides general information and deep-linked settings.

    If a deep-linked payload starting with 'settings_' is provided, it attempts to
    open the settings panel for the specified chat ID. Otherwise, it sends a
    general welcome message.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Sends a welcome message in private chat.
        - May open the settings panel if deep-linked.
    """
    if len(message.command) > 1:
        payload = message.command[1]
        if payload.startswith("settings_"):
            try:
                chat_id_str = payload.replace("settings_", "")
                if not chat_id_str.startswith("-") or not chat_id_str.lstrip("-").isdigit():
                    return
                chat_id = int(chat_id_str)
                from src.plugins.admin_panel.handlers import open_settings_panel

                await open_settings_panel(client, message, chat_id)
                return
            except Exception:
                pass
    if not message.chat or not message.from_user:
        return

    await send_start_message(client, message)
    await message.stop_propagation()


async def send_start_message(client: Client, message: Message, edit: bool = False) -> None:
    """
    Send the clean, professional welcome message with navigation buttons.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object (can be from command or callback).
        edit (bool): Whether to edit the existing message instead of replying.
    """
    me = await client.get_me()
    chat_id = message.chat.id

    text = await at(
        chat_id,
        "admin.start_text",
        bot_name=me.first_name,
    )

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(await at(chat_id, "help.start_btn"), callback_data="help:main")],
            [
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_my_groups"), callback_data="panel:my_chats"
                ),
                InlineKeyboardButton(
                    await at(chat_id, "help.about_btn"), callback_data="help:cat:about"
                ),
            ],
            [InlineKeyboardButton(await at(chat_id, "donate.btn"), callback_data="donate:main")],
        ]
    )

    if edit:
        await message.edit_text(text, reply_markup=kb)
    else:
        await message.reply(text, reply_markup=kb)


@bot.on_message(filters.command("ping") & filters.group)
@safe_handler
async def ping_handler(client: Client, message: Message) -> None:
    """
    Test bot latency by calculating the time difference between message creation and current time.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Sends a reply message with the calculated latency in milliseconds.
    """
    if not message.chat:
        return
    latency = (time.time() - time.time()) * 1000
    await message.reply(await at(message.chat.id, "ping.response", ms=f"{latency:.2f}"))
    await message.stop_propagation()


@bot.on_message(filters.command("id"))
@safe_handler
async def id_handler(client: Client, message: Message) -> None:
    """
    Return the user ID, current chat ID, and the ID of the replied user (if any).

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Sends a reply message containing the requested IDs.
    """
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
    await message.stop_propagation()


@bot.on_message(filters.command(["pin", "permapin"]) & filters.group)
@safe_handler
@admin_only
async def pin_handler(client: Client, message: Message) -> None:
    """
    Pin a message in the current group.

    Requires the bot to have 'can_pin_messages' permission and the user to be an admin.
    Must be used as a reply to the message to be pinned.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Pins the replied-to message in the chat.
    """
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
    await message.stop_propagation()


@bot.on_message(filters.command("unpin") & filters.group)
@safe_handler
@admin_only
async def unpin_handler(client: Client, message: Message) -> None:
    """
    Unpin a message in the current group.

    If used as a reply, unpins that specific message. Otherwise, unpins the latest pinned message.
    Requires the bot to have 'can_pin_messages' permission and the user to be an admin.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Unpins a message in the chat.
    """
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
    """
    Unpin all messages in the current group.

    Requires the bot to have 'can_pin_messages' permission and the user to be an admin.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Unpins all pinned messages in the chat.
        - Sends a confirmation message.
    """
    if not message.chat:
        return
    if not await has_permission(client, message.chat.id, Permission.CAN_PIN):
        await message.reply(await at(message.chat.id, "error.no_permission"))
        return
    await client.unpin_all_chat_messages(message.chat.id)
    await message.reply(await at(message.chat.id, "admin.unpinned_all"))
    await message.stop_propagation()


@bot.on_message(filters.command("promote") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def promote_handler(client: Client, message: Message, target_user: User) -> None:
    """
    Promote a member to administrator with a predefined set of privileges.

    Optionally sets a custom title if provided after the command or mention.
    Requires the bot to have 'can_promote_members' permission and the user to be an admin.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.
        target_user (User): The user to be promoted (resolved by @resolve_target).

    Side Effects:
        - Promotes the user to administrator.
        - Optionally sets a custom title.
        - Sends a confirmation message.
    """
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
    await message.stop_propagation()


@bot.on_message(filters.command("demote") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def demote_handler(client: Client, message: Message, target_user: User) -> None:
    """
    Demote an administrator to a regular member by stripping all privileges.

    Requires the bot to have 'can_promote_members' permission and the user to be an admin.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.
        target_user (User): The user to be demoted (resolved by @resolve_target).

    Side Effects:
        - Strips all administrator privileges from the user.
        - Sends a confirmation message.
    """
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
    await message.stop_propagation()


@bot.on_message(filters.command("invitelink") & filters.group)
@safe_handler
@admin_only
async def invitelink_handler(client: Client, message: Message) -> None:
    """
    Export and return the primary invite link for the current group.

    Requires the bot to have 'can_invite_users' permission and the user to be an admin.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Exports the chat invite link.
        - Sends a reply with the invite link.
    """
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
    """
    Display detailed and professional information about a specific user.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.
        target_user (User): The user whose info is being requested (resolved by @resolve_target).

    Side Effects:
        - Sends a reply message with user details using a professional localized template.
    """
    if not message.chat:
        return

    # Localization helpers
    not_set = await at(message.chat.id, "common.not_set")
    yes = await at(message.chat.id, "common.yes")
    no = await at(message.chat.id, "common.no")

    # Data normalization
    username = f"@{target_user.username}" if target_user.username else not_set
    last_name = target_user.last_name or not_set
    is_bot = yes if target_user.is_bot else no
    dc_id = target_user.dc_id or not_set

    text = await at(
        message.chat.id,
        "admin.user_info",
        id=target_user.id,
        first_name=target_user.first_name,
        last_name=last_name,
        username=username,
        dc_id=dc_id,
        is_bot=is_bot,
    )
    await message.reply(text)


@bot.on_message(filters.command("chatinfo") & filters.group)
@safe_handler
async def chatinfo_handler(client: Client, message: Message) -> None:
    """
    Display detailed information about the current group.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Fetches the chat member count.
        - Sends a reply message with group details (title, ID, type, username, member count).
    """
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


# --- Admin Panel Input Handlers ---


@bot.on_message(filters.private & is_waiting_for_input("cleanerInactive"), group=-101)
@safe_handler
async def cleaner_inactive_input_handler(client: Client, message: Message) -> None:
    state = message.input_state
    chat_id = state["chat_id"]
    user_id = message.from_user.id
    ctx = get_context()
    value = message.text

    if not str(value).isdigit() or int(value) < 0:
        await message.reply(await at(user_id, "panel.input_invalid_number"))
        return

    from src.db.models import ChatCleaner

    async with ctx.db() as session:
        cleaner = await session.get(ChatCleaner, chat_id)
        if not cleaner:
            cleaner = ChatCleaner(chatId=chat_id)
        cleaner.cleanInactiveDays = int(value)
        session.add(cleaner)
        await session.commit()

    from src.plugins.admin_panel.handlers.keyboards import cleaner_menu_kb

    kb = await cleaner_menu_kb(ctx, chat_id)

    text = await at(user_id, "panel.cleaner_text")

    await finalize_input_capture(
        client,
        message,
        user_id,
        state["prompt_msg_id"],
        text,
        kb,
        success_text=await at(user_id, "panel.input_success"),
    )


register(AdminPlugin())
