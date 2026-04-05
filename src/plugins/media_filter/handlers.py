import contextlib

from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at

from . import get_ctx
from .repository import get_media_filter, set_media_filter


@bot.on_message(filters.command("mediafilter") & filters.group)
@safe_handler
@admin_only
async def mediafilter_handler(client: Client, message: Message) -> None:
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

    await set_media_filter(get_ctx(), message.chat.id, **{field: mode})
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
    mf = await get_media_filter(get_ctx(), message.chat.id)
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
