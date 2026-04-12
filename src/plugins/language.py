import contextlib

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.models import ChatSettings, UserSettings
from src.utils.decorators import admin_permission_required, safe_handler
from src.utils.i18n import at, list_locales
from src.utils.input import finalize_input_capture, is_waiting_for_input
from src.utils.local_cache import get_cache
from src.utils.permissions import Permission

_CACHE_TTL = 1200  # 20 minutes
LANG_PAGE_SIZE = 6


class LanguagePlugin(Plugin):
    """Plugin to manage bot localization and language settings."""

    name = "language"
    priority = 2

    async def setup(self, client: Client, ctx) -> None:
        pass


async def get_chat_lang(ctx, chat_id: int) -> str:
    """Retrieve the current language applied to a chat configuration."""
    r = get_cache()
    cache_key = f"lang:{chat_id}"
    cached = await r.get(cache_key)
    if cached:
        return cached
    async with ctx.db() as session:
        settings = await session.get(ChatSettings, chat_id)
        lang = settings.language if settings else "en"
    await r.set(cache_key, lang, ttl=_CACHE_TTL)
    return lang


async def set_chat_lang(ctx, chat_id: int, lang: str) -> None:
    """Change the bot's language configuration for a specific chat."""
    async with ctx.db() as session:
        settings = await session.get(ChatSettings, chat_id)
        if settings:
            settings.language = lang
            session.add(settings)
        else:
            settings = ChatSettings(id=chat_id, language=lang)
            session.add(settings)
        await session.commit()
    r = get_cache()
    await r.delete(f"lang:{chat_id}")


async def get_user_lang(ctx, user_id: int) -> str:
    """Retrieve the current personal language preference for a user."""
    r = get_cache()
    cache_key = f"user_lang:{user_id}"
    cached = await r.get(cache_key)
    if cached:
        return cached
    async with ctx.db() as session:
        settings = await session.get(UserSettings, user_id)
        lang = settings.language if settings else "en"
    await r.set(cache_key, lang, ttl=_CACHE_TTL)
    return lang


async def set_user_lang(ctx, user_id: int, lang: str) -> None:
    """Update a user's personal language preference."""
    async with ctx.db() as session:
        settings = await session.get(UserSettings, user_id)
        if settings:
            settings.language = lang
            session.add(settings)
        else:
            settings = UserSettings(userId=user_id, language=lang)
            session.add(settings)
        await session.commit()
    r = get_cache()
    await r.delete(f"user_lang:{user_id}")


@bot.on_message(filters.command(["setlang", "language"]))
@safe_handler
@admin_permission_required(Permission.CAN_CHANGE_INFO)
async def set_lang_handler(client: Client, message: Message) -> None:
    """Command to apply a new language to the current chat context."""
    if len(message.command) < 2:
        return
    ctx = get_context()
    lang = message.command[1].lower()
    if lang not in list_locales():
        await message.reply(await at(message.chat.id, "language.not_found", lang=lang))
        return

    from src.utils.lang_utils import get_lang_info

    name, flag = await get_lang_info(ctx, lang, target_chat_id=message.chat.id)
    display_lang = f"{name} {flag}"

    await set_chat_lang(ctx, message.chat.id, lang)
    await message.reply(await at(message.chat.id, "language.set", lang=display_lang))


@bot.on_message(filters.command("langs") & filters.group)
@safe_handler
async def langs_list_handler(client: Client, message: Message) -> None:
    """Display all available and loaded languages."""
    langs = list_locales()
    text = await at(message.chat.id, "language.list_header")
    for lang_code in langs:
        text += f"\n• `{lang_code}`"
    await message.reply(text)


async def language_picker_kb(
    ctx,
    target_id: int,
    scope: str = "chat",
    page: int = 0,
    query: str | None = None,
    mode: str = "set",
    display_id: int | None = None,
) -> InlineKeyboardMarkup:
    """Generate an inline keyboard layout for the language selection interface."""
    from src.utils.i18n import list_locales

    # Use display_id for localization (preferred for Admin Panel UI)
    at_id = display_id or target_id

    if mode == "block":
        from src.plugins.lang_block import SUPPORTED_LANGS

        langs = list(SUPPORTED_LANGS)
    else:
        langs = list_locales()

    langs.sort()

    from src.utils.lang_utils import get_lang_info

    if query:
        q = query.strip().lower()
        filtered_langs = []
        for lang in langs:
            name, _ = await get_lang_info(
                ctx,
                lang,
                target_chat_id=at_id if scope == "chat" else None,
                target_user_id=at_id if scope == "user" else None,
            )
            if q in lang.lower() or q in name.lower():
                filtered_langs.append(lang)
        langs = filtered_langs

    if mode == "block":
        from src.plugins.lang_block import get_lang_blocks

        blocks = await get_lang_blocks(ctx, target_id)
        current_blocked = set(blocks["blocked"])
    else:
        if scope == "user":
            current_lang = await get_user_lang(ctx, target_id)
        else:
            current_lang = await get_chat_lang(ctx, target_id)

    total = len(langs)
    total_pages = max(1, (total + LANG_PAGE_SIZE - 1) // LANG_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * LANG_PAGE_SIZE
    chunk = langs[start : start + LANG_PAGE_SIZE]

    buttons = []

    if mode == "block":
        from src.plugins.admin_panel.repository import get_chat_settings

        settings = await get_chat_settings(ctx, target_id)
        action_type = (settings.langBlockAction or "delete").lower()
        action_icon = {
            "delete": "🗑️",
            "mute": "🔇",
            "kick": "👢",
            "ban": "🔨",
            "warn": "⚠️",
        }.get(action_type, "🗑️")
        action_label = await at(at_id, f"action.{action_type}")

        buttons.append(
            [
                InlineKeyboardButton(
                    await at(
                        at_id,
                        "panel.btn_lang_block_global_action",
                        action=action_label,
                        icon=action_icon,
                    ),
                    callback_data=f"panel:cycle_lang_block_action:{page}",
                )
            ]
        )
    row = []
    for lang in chunk:
        name, flag = await get_lang_info(
            ctx,
            lang,
            target_chat_id=at_id if scope == "chat" else None,
            target_user_id=at_id if scope == "user" else None,
            native=False,
        )

        if mode == "block":
            is_active = lang in current_blocked
            prefix = "✅ " if is_active else "❌ "
            callback_data = f"panel:lang_toggle:{lang}:{page}"
        else:
            is_active = lang == current_lang
            prefix = "✅ " if is_active else ""
            callback_data = f"panel:set_lang:{scope}:{target_id}:{lang}"

        btn_text = f"{prefix}{flag} {name}"
        row.append(InlineKeyboardButton(btn_text, callback_data=callback_data))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    if total == 0 and query is not None:
        no_results = await at(at_id, "language.search_no_results", query=query)
        buttons.append([InlineKeyboardButton(no_results, callback_data="panel:noop")])
    elif total_pages > 1:
        nav_row = []
        if page > 0:
            nav_row.append(
                InlineKeyboardButton(
                    "⬅️",
                    callback_data=f"panel:language_page:{scope}:{target_id}:{page - 1}:{mode}",
                )
            )
        nav_row.append(
            InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="panel:noop")
        )
        if page < total_pages - 1:
            nav_row.append(
                InlineKeyboardButton(
                    "➡️",
                    callback_data=f"panel:language_page:{scope}:{target_id}:{page + 1}:{mode}",
                )
            )
        buttons.append(nav_row)

    buttons.append(
        [
            InlineKeyboardButton(
                await at(at_id, "common.btn_search"),
                callback_data=f"panel:language_search:{scope}:{target_id}:{mode}",
            )
        ]
    )

    if mode == "block":
        back_data = "panel:category:moderation"
    else:
        back_data = "panel:my_chats" if scope == "user" else "panel:category:settings"

    buttons.append(
        [InlineKeyboardButton(await at(at_id, "panel.btn_back"), callback_data=back_data)]
    )
    return InlineKeyboardMarkup(buttons)


async def begin_language_search(
    user_id: int, scope: str, target_id: int, prompt_msg_id: int | None = None, mode: str = "set"
) -> None:
    """Store pending language search state in cache for next private text input."""
    r = get_cache()
    msg_id = prompt_msg_id or 0
    await r.set(f"lang_search:{user_id}", f"{scope}:{target_id}:{msg_id}:{mode}", ttl=300)


@bot.on_message(filters.private & ~filters.regex(r"^/.*"))
@safe_handler
async def language_search_input_handler(client: Client, message: Message) -> None:
    """Consume private message as language search query when requested by the panel."""
    user_id = message.from_user.id
    r = get_cache()
    state = await r.get(f"lang_search:{user_id}")
    if not state:
        return
    await r.delete(f"lang_search:{user_id}")

    parts = state.split(":")
    if len(parts) < 2:
        return
    scope = parts[0]
    target_id = int(parts[1])
    prompt_msg_id = int(parts[2]) if len(parts) > 2 else 0
    mode = parts[3] if len(parts) > 3 else "set"
    query = (message.text or "").strip()

    ctx = get_context()
    kb = await language_picker_kb(
        ctx, target_id, scope=scope, page=0, query=query, mode=mode, display_id=user_id
    )
    if mode == "block":
        header_text = await at(user_id, "panel.langblock_picker_text")
    else:
        header_key = (
            "language.user_picker_header" if scope == "user" else "language.group_picker_header"
        )
        header_text = await at(user_id, header_key)

    search_label = await at(user_id, "common.btn_search")
    result_text = f"{header_text}\n\n{search_label}: `{query or '-'}`"

    with contextlib.suppress(Exception):
        await message.delete()
    if prompt_msg_id:
        with contextlib.suppress(Exception):
            await client.edit_message_text(user_id, prompt_msg_id, result_text, reply_markup=kb)
            return
    await client.send_message(user_id, result_text, reply_markup=kb)


# --- Admin Panel Input Handlers ---


@bot.on_message(filters.private & is_waiting_for_input("timezoneSearch"), group=-50)
@safe_handler
async def timezone_search_input_handler(client: Client, message: Message) -> None:
    state = message.input_state
    chat_id = state["chat_id"]
    user_id = message.from_user.id
    ctx = get_context()
    value = str(message.text or "").strip()

    from src.plugins.admin_panel.handlers.keyboards import timezone_picker_kb

    kb = await timezone_picker_kb(ctx, chat_id, user_id=user_id, filter_query=value)

    text = await at(user_id, "panel.timezone_search_results_text", query=value)

    await finalize_input_capture(
        client,
        message,
        user_id,
        state["prompt_msg_id"],
        text,
        kb,
        success_text=await at(user_id, "panel.input_success"),
    )


register(LanguagePlugin())
