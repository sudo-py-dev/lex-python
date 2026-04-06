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
    """
    Reply with a random 'running away' action string.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Sends a random 'run' message from the localization file.
    """
    index = random.randint(1, 5)
    await message.reply(await at(message.chat.id, f"misc.run_{index}"))
    await message.stop_propagation()


@bot.on_message(filters.command("slap") & filters.group)
@safe_handler
async def slap_handler(client: Client, message: Message) -> None:
    """
    Slap the replied-to user with a random object.

    Requires a reply to identify the target user.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Sends a random 'slap' message mentioning the target user.
    """
    if not message.reply_to_message:
        await message.reply(await at(message.chat.id, "error.no_reply"))
        await message.stop_propagation()
        return
    target = (
        message.reply_to_message.from_user.first_name
        if message.reply_to_message.from_user
        else await at(message.chat.id, "common.unknown")
    )
    index = random.randint(1, 4)
    await message.reply(await at(message.chat.id, f"misc.slap_{index}", target=target))
    await message.stop_propagation()


@bot.on_message(filters.command("shrug") & filters.group)
@safe_handler
async def shrug_handler(client: Client, message: Message) -> None:
    """
    Reply with a classic shrug emoticon: ¯\\_(ツ)_/¯.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Sends a text message with the shrug emoticon.
    """
    await message.reply("¯\\_(ツ)_/¯")
    await message.stop_propagation()


@bot.on_message(filters.command("about"))
@safe_handler
async def about_handler(client: Client, message: Message) -> None:
    """
    Display information regarding the bot's technology stack, version, and developer.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Compiles the tech stack from project configuration.
        - Sends an informational message with tech stack details, version, and developer links.
        - Disables link previews for the response message.
    """
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
            dev_name=config.DEV_NAME,
            dev_url=config.DEV_URL,
            repo_url=config.GITHUB_URL,
            tech_stack=tech_stack,
        ),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
    await message.stop_propagation()


register(MiscPlugin())
