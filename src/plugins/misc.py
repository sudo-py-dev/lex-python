import random

from pyrogram import Client, filters
from pyrogram.types import LinkPreviewOptions, Message

from src.config import TECH_STACK, config
from src.core.bot import bot
from src.core.plugin import Plugin, register
from src.utils.decorators import safe_handler
from src.utils.i18n import at


class MiscPlugin(Plugin):
    """Plugin for miscellaneous, fun, and informational commands."""

    name = "misc"
    priority = 150

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.command("runs") & filters.group)
@safe_handler
async def runs_handler(client: Client, message: Message) -> None:
    """Reply with a random 'running away' action string."""
    runs = [
        "runs to the other side of the room.",
        "runs away from the group.",
        "runs to hide under the bed.",
        "runs to the store.",
        "runs out of the door.",
    ]
    await message.reply(random.choice(runs))


@bot.on_message(filters.command("slap") & filters.group)
@safe_handler
async def slap_handler(client: Client, message: Message) -> None:
    """Slap the replied-to user with a random object."""
    if not message.reply_to_message:
        return
    slaps = [
        "slaps {target} with a large trout.",
        "slaps {target} across the face.",
        "slaps {target} into the next room.",
        "slaps {target} with a wet noodle.",
    ]
    target = (
        message.reply_to_message.from_user.first_name
        if message.reply_to_message.from_user
        else "someone"
    )
    await message.reply(random.choice(slaps).format(target=target))


@bot.on_message(filters.command("shrug") & filters.group)
@safe_handler
async def shrug_handler(client: Client, message: Message) -> None:
    """Reply with a classic shrug emoticon."""
    await message.reply("¯\\_(ツ)_/¯")


@bot.on_message(filters.command("about"))
@safe_handler
async def about_handler(client: Client, message: Message) -> None:
    """Display information regarding the bot's stack, version, and developer."""
    chat_id = message.chat.id if message.chat else None
    labels = {
        "engine": await at(chat_id, "misc.tech_engine"),
        "database": await at(chat_id, "misc.tech_database"),
        "framework": await at(chat_id, "misc.tech_framework"),
        "performance": await at(chat_id, "misc.tech_performance"),
    }
    tech_stack = "\n".join(
        [
            f"• **{label}**: {value}"
            for key, label in labels.items()
            if (value := TECH_STACK.get(key))
        ]
    )
    await message.reply(
        await at(
            chat_id,
            "misc.about_text",
            version=config.VERSION,
            dev_name="sudopydev",
            dev_url="https://github.com/sudopydev/lex-tg",
            tech_stack=tech_stack,
        ),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


register(MiscPlugin())
