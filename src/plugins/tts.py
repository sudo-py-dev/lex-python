import os
import tempfile

import edge_tts
from langdetect import DetectorFactory, detect
from loguru import logger
from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.core.plugin import Plugin, register
from src.utils.decorators import safe_handler, user_rate_limit
from src.utils.i18n import at

DetectorFactory.seed = 0

TTS_LIMIT = 1000

VOICE_MAPPING = {
    "af": "af-ZA-AdriNeural",
    "am": "am-ET-AmehaNeural",
    "ar": "ar-SA-HamedNeural",
    "az": "az-AZ-BabekNeural",
    "bg": "bg-BG-BorislavNeural",
    "bn": "bn-BD-PradeepNeural",
    "bs": "bs-BA-GoranNeural",
    "ca": "ca-ES-EnricNeural",
    "cs": "cs-CZ-AntoninNeural",
    "cy": "cy-GB-AledNeural",
    "da": "da-DK-JeppeNeural",
    "de": "de-DE-KillianNeural",
    "el": "el-GR-NestorasNeural",
    "en": "en-US-AndrewMultilingualNeural",
    "es": "es-ES-AlvaroNeural",
    "et": "et-EE-KertNeural",
    "fa": "fa-IR-FaridNeural",
    "fi": "fi-FI-HarriNeural",
    "fil": "fil-PH-AngeloNeural",
    "fr": "fr-FR-VivienneMultilingualNeural",
    "ga": "ga-IE-ColmNeural",
    "gl": "gl-ES-RoiNeural",
    "gu": "gu-IN-NiranjanNeural",
    "he": "he-IL-AvriNeural",
    "hi": "hi-IN-MadhurNeural",
    "hr": "hr-HR-SreckoNeural",
    "hu": "hu-HU-TamasNeural",
    "hy": "hy-AM-AnahitNeural",
    "id": "id-ID-ArdiNeural",
    "is": "is-IS-GunnarNeural",
    "it": "it-IT-GiuseppeMultilingualNeural",
    "ja": "ja-JP-KeitaNeural",
    "jv": "jv-ID-DimasNeural",
    "ka": "ka-GE-GiorgiNeural",
    "kk": "kk-KZ-DauletNeural",
    "km": "km-KH-PisethNeural",
    "kn": "kn-IN-GaganNeural",
    "ko": "ko-KR-HyunsuMultilingualNeural",
    "lo": "lo-LA-ChanthavongNeural",
    "lt": "lt-LT-LeonasNeural",
    "lv": "lv-LV-NilsNeural",
    "mk": "mk-MK-AleksandarNeural",
    "ml": "ml-IN-MidhunNeural",
    "mn": "mn-MN-BataaNeural",
    "mr": "mr-IN-ManoharNeural",
    "ms": "ms-MY-OsmanNeural",
    "mt": "mt-MT-JosephNeural",
    "my": "my-MM-ThihaNeural",
    "nb": "nb-NO-FinnNeural",
    "ne": "ne-NP-SagarNeural",
    "nl": "nl-NL-MaartenNeural",
    "pl": "pl-PL-MarekNeural",
    "ps": "ps-AF-GulNawazNeural",
    "pt": "pt-BR-ThalitaMultilingualNeural",
    "ro": "ro-RO-EmilNeural",
    "ru": "ru-RU-DmitryNeural",
    "si": "si-LK-SameeraNeural",
    "sk": "sk-SK-LukasNeural",
    "sl": "sl-SI-RokNeural",
    "so": "so-SO-MuuseNeural",
    "sq": "sq-AL-IlirNeural",
    "sr": "sr-RS-NicholasNeural",
    "su": "su-ID-JajangNeural",
    "sv": "sv-SE-MattiasNeural",
    "sw": "sw-KE-RafikiNeural",
    "ta": "ta-IN-ValluvarNeural",
    "te": "te-IN-MohanNeural",
    "th": "th-TH-NiwatNeural",
    "tr": "tr-TR-AhmetNeural",
    "uk": "uk-UA-OstapNeural",
    "ur": "ur-PK-AsadNeural",
    "uz": "uz-UZ-SardorNeural",
    "vi": "vi-VN-NamMinhNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "zu": "zu-ZA-ThembaNeural",
}


class TTSPlugin(Plugin):
    name = "tts"
    priority = 100

    async def setup(self, client: Client, ctx) -> None:
        logger.debug("[tts] Plugin initialized")


@bot.on_message(filters.command("tts") & (filters.group | filters.private))
@user_rate_limit(seconds=60.0)
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

        tmp_dir = os.getenv("TMPDIR", "/app/tmp")
        if not os.path.exists(tmp_dir):
            tmp_dir = None

        with tempfile.NamedTemporaryFile(dir=tmp_dir, suffix=".mp3", delete=True) as temp_file:
            communicate = edge_tts.Communicate(text, voice)

            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    temp_file.write(chunk["data"])

            temp_file.flush()

            await message.reply_voice(temp_file.name)
            await status_msg.delete()

    except Exception:
        logger.exception(
            f"[tts] Generation failed for lang {lang if 'lang' in locals() else 'unknown'}"
        )
        await status_msg.edit_text(await at(message.chat.id, "tts.error_generic"))


register(TTSPlugin())
