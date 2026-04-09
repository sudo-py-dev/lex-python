import json

from langdetect import detect_langs
from loguru import logger
from pyrogram import Client, filters
from pyrogram.types import Message
from sqlalchemy import select

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.models import BlockedLanguage, ChatSettings
from src.utils.decorators import safe_handler
from src.utils.i18n import at
from src.utils.input import finalize_input_capture, is_waiting_for_input
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
    """
    Check if a specific ISO 639-1 language code is supported by the language detector.

    Args:
        lang_code (str): The language code to check.

    Returns:
        bool: True if the language is supported, False otherwise.
    """
    return lang_code.lower() in SUPPORTED_LANGS


def detect_language_with_confidence(text: str) -> list[tuple[str, float]]:
    """
    Detect the potential languages of a given text string.

    Uses `langdetect` to analyze the text and returns a list of detected
    languages with their associated probability scores.

    Args:
        text (str): The text to analyze.

    Returns:
        list[tuple[str, float]]: A list of tuples containing (language_code, probability).
    """
    try:
        langs = detect_langs(text)
        return [(lang_obj.lang, lang_obj.prob) for lang_obj in langs]
    except Exception:
        return []


async def get_lang_blocks(ctx, chat_id: int) -> list[BlockedLanguage]:
    """
    Retrieve all blocked languages for a specific chat, with caching.

    Caches the results in Cache for 24 hours to reduce database load.

    Args:
        ctx (Context): The application context.
        chat_id (int): The ID of the chat.

    Returns:
        list[BlockedLanguage]: A list of blocked language database objects.
    """
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
    """
    Block a new language in a specific chat.

    Validates that the language code is supported by the detector.
    Invalidates the chat's language block cache upon success.

    Args:
        ctx (Context): The application context.
        chat_id (int): The ID of the chat.
        lang_code (str): The ISO 639-1 language code to block.
        action (str, optional): The moderation action to take on violation. Defaults to "delete".

    Returns:
        BlockedLanguage: The created or updated blocked language entry.

    Raises:
        ValueError: If the language code is not supported.
    """
    lang_code = lang_code.lower().strip()
    if not is_supported(lang_code):
        raise ValueError(f"Language code '{lang_code}' is not supported by the detector.")
    async with ctx.db() as session:
        settings = await session.get(ChatSettings, chat_id)
        if not settings:
            settings = ChatSettings(id=chat_id)
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
    """
    Remove a blocked language configuration from a chat.

    Invalidates the chat's language block cache.

    Args:
        ctx (Context): The application context.
        chat_id (int): The ID of the chat.
        lang_code (str): The ISO 639-1 language code to unblock.
    """
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


@bot.on_message(filters.group & (filters.text | filters.caption), group=-50)
@safe_handler
async def lang_block_interceptor(client: Client, message: Message) -> None:
    """
    Analyze incoming group messages and enforce language restrictions.

    Uses language detection with a confidence threshold (>0.5). If any
    detected language is in the chat's block list, a moderation action
     is executed.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object to analyze.

    Side Effects:
        - Deletes the message if a violation is found.
        - May mute, kick, or ban the sender based on settings.
        - Logs the action in the database and audit log channel.
        - Stops message propagation on violation.
    """
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
    acted = await execute_moderation_action(
        client=client,
        message=message,
        action=violated_block.action,
        reason=reason,
        log_tag="LangBlock",
        violation_key="langblock.violation",
        lang=violated_block.langCode.upper(),
    )
    if acted:
        await message.stop_propagation()


# --- Admin Panel Input Handlers ---


@bot.on_message(filters.private & is_waiting_for_input("langblockInput"), group=-50)
@safe_handler
async def langblock_input_handler(client: Client, message: Message) -> None:
    state = message.input_state
    chat_id = state["chat_id"]
    user_id = message.from_user.id
    ctx = get_context()
    value = message.text

    parsed_iso = str(value).lower().strip()
    if not parsed_iso or not is_supported(parsed_iso):
        await message.reply(await at(user_id, "panel.langblock_invalid_input"))
        return

    await add_lang_block(ctx, chat_id, parsed_iso)

    from src.plugins.admin_panel.handlers.moderation_kbs import langblock_kb

    kb = await langblock_kb(ctx, chat_id, state["page"])

    text = await at(user_id, "panel.langblock_text")

    await finalize_input_capture(
        client,
        message,
        user_id,
        state["prompt_msg_id"],
        text,
        kb,
        success_text=await at(user_id, "panel.input_success"),
    )


register(LangBlockPlugin())
