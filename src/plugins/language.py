import emoji
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.cache.local_cache import get_cache
from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.models import GroupSettings
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at, list_locales

_CACHE_TTL = 3600

LANG_METADATA = {
    "en": ("English", ":United_States:"),
    "he": ("עברית", ":Israel:"),
    "ru": ("Русский", ":Russia:"),
    "es": ("Español", ":Spain:"),
    "fr": ("Français", ":France:"),
    "de": ("Deutsch", ":Germany:"),
    "ar": ("العربية", ":Saudi_Arabia:"),
    "it": ("Italiano", ":Italy:"),
    "pt": ("Português", ":Portugal:"),
    "tr": ("Türkçe", ":Turkey:"),
    "id": ("Indonesia", ":Indonesia:"),
    "fa": ("فارسی", ":sun: :lion: :crossed_swords:"),
    "hi": ("हिन्दी", ":India:"),
    "uk": ("Українська", ":Ukraine:"),
    "pl": ("Polski", ":Poland:"),
    "nl": ("Nederlands", ":Netherlands:"),
    "zh": ("中文", ":China:"),
    "ja": ("日本語", ":Japan:"),
    "ko": ("한국어", ":South_Korea:"),
}


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
        settings = await session.get(GroupSettings, chat_id)
        lang = settings.language if settings else "en"
    await r.set(cache_key, lang, ttl=_CACHE_TTL)
    return lang


async def set_chat_lang(ctx, chat_id: int, lang: str) -> None:
    """Change the bot's language configuration for a specific chat."""
    async with ctx.db() as session:
        settings = await session.get(GroupSettings, chat_id)
        if settings:
            settings.language = lang
            session.add(settings)
        else:
            settings = GroupSettings(id=chat_id, language=lang)
            session.add(settings)
        await session.commit()
    r = get_cache()
    await r.delete(f"lang:{chat_id}")


@bot.on_message(filters.command(["setlang", "language"]))
@safe_handler
@admin_only
async def set_lang_handler(client: Client, message: Message) -> None:
    """Command to apply a new language to the current chat context."""
    if len(message.command) < 2:
        return
    ctx = get_context()
    lang = message.command[1].lower()
    if lang not in list_locales():
        await message.reply(await at(message.chat.id, "language.not_found", lang=lang))
        return
    await set_chat_lang(ctx, message.chat.id, lang)
    await message.reply(await at(message.chat.id, "language.set", lang=lang))


@bot.on_message(filters.command("langs") & filters.group)
@safe_handler
async def langs_list_handler(client: Client, message: Message) -> None:
    """Display all available and loaded languages."""
    langs = list_locales()
    text = await at(message.chat.id, "language.list_header")
    for lang_code in langs:
        text += f"\n• `{lang_code}`"
    await message.reply(text)


async def language_picker_kb(ctx, target_id: int, is_pm: bool = False) -> InlineKeyboardMarkup:
    """Generate an inline keyboard layout for the language selection interface."""
    langs = sorted(list_locales())
    current_lang = await get_chat_lang(ctx, target_id)
    buttons = []
    row = []
    for lang in langs:
        name, emoji_code = LANG_METADATA.get(lang, (lang.upper(), ":globe_with_meridians:"))
        flag = emoji.emojize(emoji_code, language="alias")
        data = f"panel:set_lang:{lang}" if is_pm else f"panel:set_lang:{lang}:{target_id}"
        prefix = "✅ " if lang == current_lang else ""
        btn_text = f"{prefix}{flag} {name}"
        row.append(InlineKeyboardButton(btn_text, callback_data=data))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    back_data = "panel:my_groups" if is_pm else "panel:main"
    buttons.append(
        [InlineKeyboardButton(await at(target_id, "panel.btn_back"), callback_data=back_data)]
    )
    return InlineKeyboardMarkup(buttons)


register(LanguagePlugin())
