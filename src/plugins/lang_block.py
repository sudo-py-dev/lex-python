import json

from langdetect import detect_langs
from loguru import logger
from pyrogram import Client, filters
from pyrogram.types import Message
from sqlalchemy import select

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.models import BlockedLanguage, GroupSettings
from src.utils.decorators import safe_handler
from src.utils.i18n import at
from src.utils.moderation import execute_moderation_action, resolve_sender

CACHE_KEY_PREFIX = "lex:lang_block:"

SUPPORTED_LANGS = {
    "af",
    "ar",
    "bg",
    "bn",
    "ca",
    "cs",
    "cy",
    "da",
    "de",
    "el",
    "en",
    "es",
    "et",
    "fa",
    "fi",
    "fr",
    "gu",
    "he",
    "hi",
    "hr",
    "hu",
    "id",
    "it",
    "ja",
    "kn",
    "ko",
    "lt",
    "lv",
    "mk",
    "ml",
    "mr",
    "ne",
    "nl",
    "no",
    "pa",
    "pl",
    "pt",
    "ro",
    "ru",
    "sk",
    "sl",
    "so",
    "sq",
    "sv",
    "sw",
    "ta",
    "te",
    "th",
    "tl",
    "tr",
    "uk",
    "ur",
    "vi",
    "zh-cn",
    "zh-tw",
}


class LangBlockPlugin(Plugin):
    """Plugin to restrict and moderate messages based on detected language."""

    name = "lang_block"
    priority = 50

    async def setup(self, client: Client, ctx) -> None:
        pass


def is_supported(lang_code: str) -> bool:
    """Check if a specific ISO language code is supported by the engine."""
    return lang_code.lower() in SUPPORTED_LANGS


def detect_language_with_confidence(text: str) -> list[tuple[str, float]]:
    """Detect language from string and return confidence scores."""
    try:
        langs = detect_langs(text)
        return [(lang_obj.lang, lang_obj.prob) for lang_obj in langs]
    except Exception:
        return []


async def get_lang_blocks(ctx, chat_id: int) -> list[BlockedLanguage]:
    """Retrieve all blocked languages for a specific chat."""
    key = f"{CACHE_KEY_PREFIX}{chat_id}"
    cached = await ctx.cache.get(key)
    if cached:
        try:
            data = json.loads(cached)
            return [
                BlockedLanguage(
                    id=b["id"],
                    chatId=b["chatId"],
                    langCode=b["langCode"],
                    action=b["action"],
                )
                for b in data
            ]
        except Exception as e:
            logger.error(f"Failed to parse LangBlock cache for {chat_id}: {e}")
            await ctx.cache.delete(key)
    async with ctx.db() as session:
        stmt = select(BlockedLanguage).where(BlockedLanguage.chatId == chat_id)
        result = await session.execute(stmt)
        blocks = list(result.scalars().all())
    try:
        data = [
            {
                "id": b.id,
                "chatId": b.chatId,
                "langCode": b.langCode,
                "action": b.action,
            }
            for b in blocks
        ]
        await ctx.cache.setex(key, 86400, json.dumps(data))
    except Exception as e:
        logger.error(f"Failed to cache LangBlocks for {chat_id}: {e}")
    return blocks


async def add_lang_block(
    ctx, chat_id: int, lang_code: str, action: str = "delete"
) -> BlockedLanguage:
    """Add a new blocked language configuration to a chat."""
    lang_code = lang_code.lower().strip()
    if not is_supported(lang_code):
        raise ValueError(f"Language code '{lang_code}' is not supported by the detector.")
    async with ctx.db() as session:
        settings = await session.get(GroupSettings, chat_id)
        if not settings:
            settings = GroupSettings(id=chat_id)
            session.add(settings)
            await session.commit()
            await session.refresh(settings)
        stmt = select(BlockedLanguage).where(
            BlockedLanguage.chatId == chat_id, BlockedLanguage.langCode == lang_code
        )
        result = await session.execute(stmt)
        res = result.scalars().first()
        if res:
            res.action = action
            session.add(res)
        else:
            res = BlockedLanguage(chatId=chat_id, langCode=lang_code, action=action)
            session.add(res)
        await session.commit()
        await session.refresh(res)
        await ctx.cache.delete(f"{CACHE_KEY_PREFIX}{chat_id}")
        return res


async def remove_lang_block(ctx, chat_id: int, lang_code: str) -> None:
    """Remove a blocked language configuration from a chat."""
    async with ctx.db() as session:
        stmt = select(BlockedLanguage).where(
            BlockedLanguage.chatId == chat_id, BlockedLanguage.langCode == lang_code
        )
        result = await session.execute(stmt)
        objs = result.scalars().all()
        for obj in objs:
            await session.delete(obj)
        await session.commit()
    await ctx.cache.delete(f"{CACHE_KEY_PREFIX}{chat_id}")


@bot.on_message(filters.group & (filters.text | filters.caption), group=-105)
@safe_handler
async def lang_block_interceptor(client: Client, message: Message) -> None:
    """Interceptor to analyze incoming text against language blocks."""
    if not message.from_user or message.from_user.is_bot or getattr(message, "command", None):
        return

    text = message.text or message.caption
    if not text or len(text) < 2:
        return
    user_id, _, is_adm = await resolve_sender(client, message)
    if not user_id or is_adm:
        return
    ctx = get_context()
    blocks = await get_lang_blocks(ctx, message.chat.id)
    if not blocks:
        return
    detections = detect_language_with_confidence(text)
    if not detections:
        return
    blocked_codes = {b.langCode: b for b in blocks}
    violated_block = None
    for code, prob in detections:
        if prob > 0.5 and code in blocked_codes:
            violated_block = blocked_codes[code]
            break
    if not violated_block:
        return
    reason = await at(message.chat.id, "reason.blocked_language", lang=violated_block.langCode)
    await execute_moderation_action(
        client=client,
        message=message,
        action=violated_block.action,
        reason=reason,
        log_tag="LangBlock",
        violation_key="langblock.violation",
        lang=violated_block.langCode.upper(),
    )



register(LangBlockPlugin())
