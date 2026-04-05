from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.core.context import AppContext
from src.core.plugin import Plugin, register
from src.db.repositories.rules import (
    clear_rules,
    get_rules,
    set_rules,
    toggle_private_rules,
)
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at

_ctx: AppContext | None = None


def get_ctx() -> AppContext:
    if _ctx is None:
        raise RuntimeError("Rules plugin not initialized")
    return _ctx


class RulesPlugin(Plugin):
    name = "rules"
    priority = 100

    async def setup(self, client: Client, ctx: AppContext) -> None:
        global _ctx
        _ctx = ctx


@bot.on_message(filters.command("setrules") & filters.group)
@safe_handler
@admin_only
async def set_rules_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        return
    content = message.text.split(None, 1)[1]
    await set_rules(get_ctx(), message.chat.id, content)
    await message.reply(await at(message.chat.id, "rules.set"))


@bot.on_message(filters.command("rules") & filters.group)
@safe_handler
async def rules_handler(client: Client, message: Message) -> None:
    rules = await get_rules(get_ctx(), message.chat.id)
    if not rules or not rules.content:
        await message.reply(await at(message.chat.id, "rules.not_set"))
        return

    text = (await at(message.chat.id, "rules.header")) + rules.content
    if rules.privateMode:
        try:
            await client.send_message(message.from_user.id, text)
            await message.reply(await at(message.chat.id, "rules.sent_dm"))
        except Exception:
            await message.reply(await at(message.chat.id, "rules.start_private"))
    else:
        await message.reply(text)


@bot.on_message(filters.command("resetrules") & filters.group)
@safe_handler
@admin_only
async def reset_rules_handler(client: Client, message: Message) -> None:
    await clear_rules(get_ctx(), message.chat.id)
    await message.reply(await at(message.chat.id, "rules.reset"))


@bot.on_message(filters.command("privaterules") & filters.group)
@safe_handler
@admin_only
async def private_rules_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        return
    mode = message.command[1].lower() in ("on", "yes", "true")
    await toggle_private_rules(get_ctx(), message.chat.id, mode)
    if mode:
        await message.reply(await at(message.chat.id, "rules.private_on"))
    else:
        await message.reply(await at(message.chat.id, "rules.private_off"))


register(RulesPlugin())
