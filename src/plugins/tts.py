import os
import shutil
import tempfile
import asyncio
import edge_tts
from pyrogram import Client, filters
from pyrogram.types import Message
from langdetect import detect, DetectorFactory
from loguru import logger

from src.core.bot import bot
from src.core.plugin import Plugin, register
from src.utils.decorators import safe_handler
from src.utils.i18n import at

DetectorFactory.seed = 0

TTS_LIMIT = 1000

VOICE_MAPPING = {
    "he": "he-IL-AvriNeural",
    "en": "en-US-GuyNeural",
    "ru": "ru-RU-DmitryNeural",
    "ar": "ar-SA-HamedNeural",
    "es": "es-ES-AlvaroNeural",
    "fr": "fr-FR-HenriNeural",
    "de": "de-DE-KillianNeural",
    "it": "it-IT-DiegoNeural",
    "pt": "pt-PT-DuarteNeural",
    "ja": "ja-JP-KeitaNeural",
    "zh": "zh-CN-YunxiNeural",
    "tr": "tr-TR-AhmetNeural",
    "hi": "hi-IN-MadhurNeural",
    "ko": "ko-KR-InJoonNeural",
}


class TTSPlugin(Plugin):
    name = "tts"
    priority = 100

    async def setup(self, client: Client, ctx) -> None:
        logger.info("[tts] Plugin initialized with multi-language support and Docker-ready temp handling")


@bot.on_message(filters.command("tts") & (filters.group | filters.private))
@safe_handler
async def tts_handler(client: Client, message: Message):
    text = ""
    if len(message.command) > 1:
        text = message.text.split(None, 1)[1]
    elif message.reply_to_message:
        text = message.reply_to_message.text or message.reply_to_message.caption

    if not text:
        return await message.reply_text(await at(message.chat.id, "tts.no_text"))

    if len(text) > TTS_LIMIT:
        return await message.reply_text(
            await at(message.chat.id, "tts.error_too_long", limit=TTS_LIMIT)
        )

    status_msg = await message.reply_text(await at(message.chat.id, "tts.generating"))

    try:
        try:
            lang = detect(text)
        except Exception:
            lang = "en"

        voice = VOICE_MAPPING.get(lang, "en-US-GuyNeural")
        logger.debug(f"[tts] Text length: {len(text)}, Detected lang: {lang}, Using voice: {voice}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = os.path.join(tmp_dir, "input.mp3")
            output_path = os.path.join(tmp_dir, "voice.ogg")

            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(input_path)

            ffmpeg_bin = shutil.which("ffmpeg")
            if ffmpeg_bin:
                cmd = [
                    ffmpeg_bin,
                    "-y",
                    "-i",
                    input_path,
                    "-c:a",
                    "libopus",
                    "-b:a",
                    "32k",
                    "-application",
                    "voip",
                    output_path,
                ]
                proc = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()
            else:
                logger.warning("[tts] ffmpeg not found, sending raw MP3 (might not show as voice)")
                output_path = input_path

            await message.reply_voice(output_path)
            await status_msg.delete()

    except Exception as e:
        logger.exception(f"[tts] Generation failed for lang {lang if 'lang' in locals() else 'unknown'}")
        await status_msg.edit_text(await at(message.chat.id, "tts.error_generic"))


register(TTSPlugin())
