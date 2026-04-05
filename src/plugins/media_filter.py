import contextlib

from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.models import MediaFilter
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at


class MediaFilterPlugin(Plugin):
    """Plugin to block specific types of media (photos, videos, etc.) in groups."""

    name = "media_filter"
    priority = 100

    async def setup(self, client: Client, ctx) -> None:
        pass


async def set_media_filter(chat_id: int, **kwargs) -> MediaFilter:
    """Update or create media filter settings for a chat."""
    ctx = get_context()
    async with ctx.db() as session:
        obj = await session.get(MediaFilter, chat_id)
        if obj:
            for key, value in kwargs.items():
                setattr(obj, key, value)
            session.add(obj)
        else:
            obj = MediaFilter(chatId=chat_id, **kwargs)
            session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return obj


async def get_media_filter(chat_id: int) -> MediaFilter | None:
    """Retrieve media filter settings for a chat."""
    ctx = get_context()
    async with ctx.db() as session:
        return await session.get(MediaFilter, chat_id)


@bot.on_message(filters.command("mediafilter") & filters.group)
@safe_handler
@admin_only
async def mediafilter_handler(client: Client, message: Message) -> None:
    """Configure which media types are blocked in the current group."""
    if len(message.command) < 3:
        await message.reply(await at(message.chat.id, "media_filter.usage"))
        return

    media_type = message.command[1].lower()
    mode = message.command[2].lower() in ("on", "yes", "true")

    field_map = {
        "photo": "blockPhoto",
        "video": "blockVideo",
        "document": "blockDocument",
        "audio": "blockAudio",
        "voice": "blockVoice",
        "sticker": "blockSticker",
        "gif": "blockGif",
        "antinsfw": "antiNsfw",
    }

    field = field_map.get(media_type)
    if not field:
        return

    await set_media_filter(message.chat.id, **{field: mode})
    await message.reply(
        await at(
            message.chat.id,
            "media_filter.set",
            type=media_type,
            mode="ON" if mode else "OFF",
        )
    )


@bot.on_message(filters.group, group=14)
@safe_handler
async def media_filter_interceptor(client: Client, message: Message) -> None:
    """Intercept and delete messages containing blocked media types."""
    mf = await get_media_filter(message.chat.id)
    if not mf:
        return

    should_delete = any(
        [
            message.photo and mf.blockPhoto,
            message.video and mf.blockVideo,
            message.document and mf.blockDocument,
            message.audio and mf.blockAudio,
            message.voice and mf.blockVoice,
            message.sticker and mf.blockSticker,
            message.animation and mf.blockGif,
        ]
    )

    if should_delete:
        with contextlib.suppress(Exception):
            await message.delete()


register(MediaFilterPlugin())
