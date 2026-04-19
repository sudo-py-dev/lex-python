import json

from pyrogram import Client, StopPropagation, filters
from pyrogram.types import InlineKeyboardMarkup, Message
from sqlalchemy import select

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.models import BlockedEntity, ChatSettings
from src.db.repositories.chats import get_chat_settings as get_settings
from src.utils.decorators import safe_handler
from src.utils.i18n import at
from src.utils.moderation import execute_moderation_action, resolve_sender

CACHE_KEY_PREFIX = "lex:entity_block:"


class EntityBlockPlugin(Plugin):
    """Plugin to block specific message entities (links, stickers, media, etc.) in groups."""

    name = "entity_block"
    priority = 50

    async def setup(self, client: Client, ctx) -> None:
        pass


async def get_blocked_entities(ctx, cid: int) -> list[BlockedEntity]:
    k = f"{CACHE_KEY_PREFIX}{cid}"
    if cached := await ctx.cache.get(k):
        try:
            return [BlockedEntity(**b) for b in json.loads(cached)]
        except Exception:
            await ctx.cache.delete(k)
    async with ctx.db() as s:
        blocks = (
            (await s.execute(select(BlockedEntity).where(BlockedEntity.chatId == cid)))
            .scalars()
            .all()
        )
        await ctx.cache.setex(
            k,
            86400,
            json.dumps(
                [
                    {"id": b.id, "chatId": b.chatId, "entityType": b.entityType, "action": b.action}
                    for b in blocks
                ]
            ),
        )
        return blocks


async def add_blocked_entity(ctx, cid: int, etype: str, act: str = "delete") -> BlockedEntity:
    async with ctx.db() as s:
        if not (setts := await s.get(ChatSettings, cid)):
            setts = ChatSettings(id=cid)
            s.add(setts)
            await s.commit()
        b = (
            (
                await s.execute(
                    select(BlockedEntity).where(
                        BlockedEntity.chatId == cid, BlockedEntity.entityType == etype
                    )
                )
            )
            .scalars()
            .first()
        )
        if b:
            b.action = act
        else:
            b = BlockedEntity(chatId=cid, entityType=etype, action=act)
        s.add(b)
        await s.commit()
        await s.refresh(b)
        await ctx.cache.delete(f"{CACHE_KEY_PREFIX}{cid}")
        return b


async def remove_blocked_entity(ctx, cid: int, etype: str) -> None:
    async with ctx.db() as s:
        for b in (
            (
                await s.execute(
                    select(BlockedEntity).where(
                        BlockedEntity.chatId == cid, BlockedEntity.entityType == etype
                    )
                )
            )
            .scalars()
            .all()
        ):
            await s.delete(b)
        await s.commit()
    await ctx.cache.delete(f"{CACHE_KEY_PREFIX}{cid}")


@bot.on_message(filters.group, group=-70)
@safe_handler
async def entity_block_interceptor(client: Client, message: Message) -> None:
    if not message.from_user or message.from_user.is_bot or getattr(message, "command", None):
        return
    uid, _, admin = await resolve_sender(client, message)
    if not uid or admin:
        return
    ctx = get_context()
    if not (bl := await get_blocked_entities(ctx, message.chat.id)):
        return
    bt, ents = (
        {b.entityType: b for b in bl},
        (message.entities or []) + (message.caption_entities or []),
    )
    match = None
    for e in ents:
        if (et := str(e.type).split(".")[-1].lower()) in bt:
            match = bt[et]
            break
    if not match and "url" in bt:
        s = await get_settings(ctx, message.chat.id)
        if (
            getattr(s, "blacklistScanButtons", False)
            and message.reply_markup
            and isinstance(message.reply_markup, InlineKeyboardMarkup)
        ):
            for row in message.reply_markup.inline_keyboard:
                if any(b.url for b in row):
                    match = bt["url"]
                    break
    if not match:
        m_map = {
            "poll": "poll",
            "contact": "contact",
            "location": "location",
            "venue": "location",
            "sticker": "sticker",
            "animation": "gif",
            "forward_origin": "forward",
        }
        for k, v in m_map.items():
            if getattr(message, k, None) and v in bt:
                match = bt[v]
                break
        if (
            not match
            and "media" in bt
            and (
                message.photo
                or message.video
                or message.audio
                or message.voice
                or message.document
                or message.video_note
            )
        ):
            match = bt["media"]
        if not match and "command" in bt and message.text and message.text.startswith("/"):
            match = bt["command"]
        if not match and "message" in bt and message.text and not message.text.startswith("/"):
            match = bt["message"]
    if match:
        lbl = await at(message.chat.id, f"lock.{match.entityType}")
        if await execute_moderation_action(
            client,
            message,
            match.action,
            await at(message.chat.id, "reason.blocked_entity", type=lbl),
            "EntityBlock",
            "entityblock.violation",
            type=lbl,
        ):
            raise StopPropagation


register(EntityBlockPlugin())
