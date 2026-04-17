import contextlib

from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Message,
)

from src.core.bot import bot
from src.core.plugin import Plugin, register
from src.utils.about import get_about_text
from src.utils.decorators import safe_handler
from src.utils.i18n import at


class HelpPlugin(Plugin):
    """Plugin for the grid-based help system."""

    name = "help"
    priority = 200

    async def setup(self, client: Client, ctx) -> None:
        pass


HELP_CATEGORIES = [
    ("about", "help.btn_about"),
    ("admin", "help.btn_admin"),
    ("antiflood", "help.btn_antiflood"),
    ("antiraid", "help.btn_antiraid"),
    ("approval", "help.btn_approval"),
    ("bans", "help.btn_bans"),
    ("blacklist", "help.btn_blacklist"),
    ("captcha", "help.btn_captcha"),
    ("cleancmd", "help.btn_cleancmd"),
    ("cleansvc", "help.btn_cleansvc"),
    ("connections", "help.btn_connections"),
    ("disabling", "help.btn_disabling"),
    ("federations", "help.btn_federations"),
    ("filters", "help.btn_filters"),
    ("formatting", "help.btn_formatting"),
    ("greetings", "help.btn_greetings"),
    ("impexp", "help.btn_impexp"),
    ("languages", "help.btn_languages"),
    ("locks", "help.btn_locks"),
    ("logging", "help.btn_logging"),
    ("misc", "help.btn_misc"),
    ("notes", "help.btn_notes"),
    ("pin", "help.btn_pin"),
    ("privacy", "help.btn_privacy"),
    ("purges", "help.btn_purges"),
    ("reports", "help.btn_reports"),
    ("rules", "help.btn_rules"),
    ("topics", "help.btn_topics"),
]


async def get_help_kb(chat_id: int) -> InlineKeyboardMarkup:
    """Generate the 3-column grid of help categories."""
    buttons = []
    row = []
    for cat_id, label_key in HELP_CATEGORIES:
        row.append(
            InlineKeyboardButton(await at(chat_id, label_key), callback_data=f"help:cat:{cat_id}")
        )
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append(
        [InlineKeyboardButton(await at(chat_id, "help.back_btn"), callback_data="help:start")]
    )
    return InlineKeyboardMarkup(buttons)


@bot.on_message(filters.command("help") & filters.private)
@safe_handler
async def help_handler(client: Client, message: Message) -> None:
    """Display the main help menu with the 3-column grid."""
    chat_id = message.chat.id
    await message.reply(
        await at(chat_id, "help.main_text"), reply_markup=await get_help_kb(chat_id)
    )


@bot.on_callback_query(filters.regex(r"^help:"))
@safe_handler
async def help_callback_handler(client: Client, callback_query: CallbackQuery) -> None:
    """Handle navigation within the help menu."""
    data = callback_query.data
    chat_id = callback_query.message.chat.id

    if data == "help:start":
        from src.plugins.admin import send_start_message

        await send_start_message(client, callback_query.message, edit=True)
        return

    if data == "help:main":
        with contextlib.suppress(Exception):
            await callback_query.message.edit_text(
                await at(chat_id, "help.main_text"), reply_markup=await get_help_kb(chat_id)
            )
        return

    if data.startswith("help:cat:"):
        cat_id = data.replace("help:cat:", "")

        if cat_id.startswith("about"):
            text = await get_about_text(chat_id)
            options = LinkPreviewOptions(is_disabled=True)
            back_target = "help:start" if cat_id.endswith(":start") else "help:main"
        else:
            text = await at(chat_id, f"help.{cat_id}_text")
            options = None
            back_target = "help:main"

        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(await at(chat_id, "help.back_btn"), callback_data=back_target)]]
        )
        with contextlib.suppress(Exception):
            await callback_query.message.edit_text(
                text, reply_markup=kb, link_preview_options=options
            )


register(HelpPlugin())
