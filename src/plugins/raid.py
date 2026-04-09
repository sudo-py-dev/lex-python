from datetime import datetime, timedelta

from pyrogram import Client, filters
from pyrogram.types import Message

from src.cache.local_cache import get_cache
from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.chats import get_chat_settings as get_settings
from src.db.repositories.chats import update_settings
from src.plugins.logging import log_event
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at
from src.utils.input import finalize_input_capture, is_waiting_for_input
from src.utils.permissions import RESTRICTED_PERMISSIONS
from src.utils.time_parser import parse_time


class RaidPlugin(Plugin):
    name = "raid"
    priority = 100

    async def setup(self, client: Client, ctx) -> None:
        pass


async def _enable_active_raid(client: Client, chat_id: int, duration_str: str) -> None:
    duration_secs = parse_time(duration_str) or 21600  # Default 6h fallback
    r = get_cache()
    await r.setex(f"raid_active:{chat_id}", duration_secs, "1")
    await client.set_chat_permissions(chat_id, RESTRICTED_PERMISSIONS)


async def _disable_active_raid(client: Client, chat_id: int) -> None:
    r = get_cache()
    await r.delete(f"raid_active:{chat_id}")
    # Note: Telegram will still respect base permissions, but restoring to previous state would require more logic.
    # Typically, bots don't unlock entirely if it wasn't them who locked. For simplicity we unlock normal permissions.
    from pyrogram.types import ChatPermissions

    await client.set_chat_permissions(
        chat_id,
        ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_send_polls=True,
        ),
    )


@bot.on_message(filters.command("antiraid") & filters.group)
@safe_handler
@admin_only
async def raid_handler(client: Client, message: Message) -> None:
    ctx = get_context()

    if not message.from_user:
        return

    args = message.command[1:] if len(message.command) > 1 else []

    if not args:
        settings = await get_settings(ctx, message.chat.id)
        # Default behavior: Toggle using configured standard raid time
        r = get_cache()
        is_active = await r.get(f"raid_active:{message.chat.id}")
        if is_active:
            await _disable_active_raid(client, message.chat.id)
            await message.reply(await at(message.chat.id, "raid.disabled"))
        else:
            await _enable_active_raid(client, message.chat.id, settings.raidTime)
            await message.reply(
                await at(message.chat.id, "raid.enabled", duration=settings.raidTime)
            )
        return

    mode = args[0].lower()

    if mode in ("off", "no", "false"):
        await _disable_active_raid(client, message.chat.id)
        await message.reply(await at(message.chat.id, "raid.disabled"))
    else:
        # Treat args[0] as a time string
        secs = parse_time(mode)
        if not secs:
            await message.reply(await at(message.chat.id, "error.invalid_time"))
            return

        await _enable_active_raid(client, message.chat.id, mode)
        await message.reply(await at(message.chat.id, "raid.enabled", duration=mode))


@bot.on_message(filters.command("autoantiraid") & filters.group)
@safe_handler
@admin_only
async def autoantiraid_handler(client: Client, message: Message) -> None:
    if not message.from_user or len(message.command) < 2:
        return

    val = message.command[1].lower()
    ctx = get_context()

    if val in ("off", "no", "false", "0"):
        await update_settings(ctx, message.chat.id, raidEnabled=False, raidThreshold=0)
        await message.reply(await at(message.chat.id, "raid.auto_disabled"))
    else:
        if not val.isdigit():
            await message.reply(await at(message.chat.id, "error.invalid_number"))
            return

        threshold = int(val)
        await update_settings(ctx, message.chat.id, raidEnabled=True, raidThreshold=threshold)
        await message.reply(await at(message.chat.id, "raid.auto_enabled", threshold=threshold))


@bot.on_message(filters.command("raidtime") & filters.group)
@safe_handler
@admin_only
async def raidtime_handler(client: Client, message: Message) -> None:
    ctx = get_context()
    if len(message.command) < 2:
        settings = await get_settings(ctx, message.chat.id)
        await message.reply(await at(message.chat.id, "raid.current_time", time=settings.raidTime))
        return

    time_str = message.command[1].lower()
    secs = parse_time(time_str)
    if not secs:
        await message.reply(await at(message.chat.id, "error.invalid_time"))
        return

    await update_settings(ctx, message.chat.id, raidTime=time_str)
    await message.reply(await at(message.chat.id, "raid.time_updated", time=time_str))


@bot.on_message(filters.command("raidactiontime") & filters.group)
@safe_handler
@admin_only
async def raidactiontime_handler(client: Client, message: Message) -> None:
    ctx = get_context()
    if len(message.command) < 2:
        settings = await get_settings(ctx, message.chat.id)
        await message.reply(
            await at(message.chat.id, "raid.current_action_time", time=settings.raidActionTime)
        )
        return

    time_str = message.command[1].lower()
    secs = parse_time(time_str)
    if not secs:
        await message.reply(await at(message.chat.id, "error.invalid_time"))
        return

    await update_settings(ctx, message.chat.id, raidActionTime=time_str)
    await message.reply(await at(message.chat.id, "raid.action_time_updated", time=time_str))


@bot.on_message(filters.group & filters.new_chat_members, group=-70)
@safe_handler
async def raid_interceptor(client: Client, message: Message) -> None:
    if not message.from_user or message.from_user.is_bot:
        return

    ctx = get_context()
    settings = await get_settings(ctx, message.chat.id)
    r = get_cache()

    is_active_raid = await r.exists(f"raid_active:{message.chat.id}")

    if is_active_raid:
        # Raid is currently locked down - penalize new users directly
        action_time_secs = parse_time(settings.raidActionTime) or 3600
        until_date = datetime.now() + timedelta(seconds=action_time_secs)

        for new_user in message.new_chat_members:
            if settings.raidAction == "ban":
                await client.ban_chat_member(message.chat.id, new_user.id, until_date=until_date)
            elif settings.raidAction == "kick":
                await client.ban_chat_member(message.chat.id, new_user.id)
                await client.unban_chat_member(message.chat.id, new_user.id)
            else:  # lock/mute
                from pyrogram.types import ChatPermissions

                await client.restrict_chat_member(
                    message.chat.id,
                    new_user.id,
                    ChatPermissions(can_send_messages=False),
                    until_date=until_date,
                )
        return

    if not settings.raidEnabled or settings.raidThreshold <= 0:
        return

    # Auto Anti-Raid detection logic
    key = f"raid_joins:{message.chat.id}"
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, settings.raidWindow)

    if count >= settings.raidThreshold:
        await _enable_active_raid(client, message.chat.id, settings.raidTime)
        await log_event(
            ctx,
            client,
            message.chat.id,
            "raid_lock",
            "Group",
            client.me,
            reason=await at(
                message.chat.id,
                "logging.raid_reason",
                threshold=settings.raidThreshold,
                window=settings.raidWindow,
            ),
            chat_title=message.chat.title,
        )
        await message.reply(await at(message.chat.id, "raid.detected"))


# --- Admin Panel Input Handlers ---


@bot.on_message(
    filters.private
    & is_waiting_for_input(["raidThreshold", "raidWindow", "raidTime", "raidActionTime"]),
    group=-50,
)
@safe_handler
async def raid_settings_input_handler(client: Client, message: Message) -> None:
    state = message.input_state
    chat_id = state["chat_id"]
    field = state["field"]
    user_id = message.from_user.id
    ctx = get_context()
    value_str = str(message.text or "")

    if field in ("raidThreshold", "raidWindow"):
        if not value_str.isdigit() or int(value_str) < 0:
            await message.reply(await at(user_id, "panel.input_invalid_number"))
            return
        await update_settings(
            ctx,
            chat_id,
            **{
                field: int(value_str),
                "raidEnabled": True if field == "raidThreshold" and int(value_str) > 0 else None,
            },
        )
    else:
        # Time string
        secs = parse_time(value_str)
        if not secs:
            await message.reply(await at(user_id, "error.invalid_time"))
            return
        await update_settings(ctx, chat_id, **{field: value_str})

    from src.plugins.admin_panel.handlers.security_kbs import raid_kb

    kb = await raid_kb(ctx, chat_id, user_id=user_id)

    s = await get_settings(ctx, chat_id)
    r = get_cache()
    is_active = await r.exists(f"raid_active:{chat_id}")
    status = await at(user_id, "panel.status_enabled" if is_active else "panel.status_disabled")

    text = await at(
        user_id,
        "panel.raid_text",
        status=status,
        threshold=s.raidThreshold,
        window=s.raidWindow,
        time=s.raidTime,
        actiontime=s.raidActionTime,
        action=s.raidAction.capitalize(),
    )

    await finalize_input_capture(
        client,
        message,
        user_id,
        state["prompt_msg_id"],
        text,
        kb,
        success_text=await at(user_id, "panel.input_success"),
    )


register(RaidPlugin())
