from __future__ import annotations

import emoji

from src.core.context import AppContext
from src.utils.i18n import at, t

LANG_EMOJIS = {
    "af": ":South_Africa:",
    "ar": ":Saudi_Arabia:",
    "bg": ":Bulgaria:",
    "bn": ":Bangladesh:",
    "ca": ":Spain:",
    "cs": ":Czechia:",
    "cy": ":Wales:",
    "da": ":Denmark:",
    "de": ":Germany:",
    "el": ":Greece:",
    "en": ":United_States:",
    "es": ":Spain:",
    "et": ":Estonia:",
    "fa": ":Iran:",
    "fi": ":Finland:",
    "fr": ":France:",
    "gu": ":India:",
    "he": ":Israel:",
    "hi": ":India:",
    "hr": ":Croatia:",
    "hu": ":Hungary:",
    "id": ":Indonesia:",
    "it": ":Italy:",
    "ja": ":Japan:",
    "kn": ":India:",
    "ko": ":South_Korea:",
    "lt": ":Lithuania:",
    "lv": ":Latvia:",
    "mk": ":North_Macedonia:",
    "ml": ":India:",
    "mr": ":India:",
    "ne": ":Nepal:",
    "nl": ":Netherlands:",
    "no": ":Norway:",
    "pa": ":India:",
    "pl": ":Poland:",
    "pt": ":Portugal:",
    "ro": ":Romania:",
    "ru": ":Russia:",
    "sk": ":Slovakia:",
    "sl": ":Slovenia:",
    "so": ":Somalia:",
    "sq": ":Albania:",
    "sv": ":Sweden:",
    "sw": ":Tanzania:",
    "ta": ":India:",
    "te": ":India:",
    "th": ":Thailand:",
    "tl": ":Philippines:",
    "tr": ":Turkey:",
    "uk": ":Ukraine:",
    "ur": ":Pakistan:",
    "vi": ":Vietnam:",
    "zh": ":China:",
    "zh-cn": ":China:",
    "zh-tw": ":Taiwan:",
}


async def get_lang_info(
    ctx: AppContext,
    code: str,
    target_chat_id: int | None = None,
    target_user_id: int | None = None,
    native: bool = False,
) -> tuple[str, str]:
    """
    Get localized language name and emoji for a given language code.

    Args:
        ctx: App context.
        code: The language code to get info for (e.g., 'en', 'zh-cn').
        target_chat_id: Chat ID for localization context.
        target_user_id: User ID for localization context.
        native: If True, returns the name in its native language.

    Returns:
        tuple[str, str]: (localized_name, emoji_character)
    """
    key_code = code.replace("-", "_")

    shortcode = LANG_EMOJIS.get(code, ":globe_with_meridians:")
    emoji_char = emoji.emojize(shortcode, language="alias")

    key = f"lang.{key_code}"

    if native:
        name = t(code, key)
    else:
        name = await at(target_chat_id, key, user_id=target_user_id)

    if name == key:
        name = code.upper()

    return name, emoji_char


async def get_all_langs_info(
    ctx: AppContext,
    codes: list[str] | None = None,
    target_chat_id: int | None = None,
    target_user_id: int | None = None,
    native: bool = False,
) -> dict[str, tuple[str, str]]:
    """Batch version of get_lang_info."""
    if codes is None:
        codes = list(LANG_EMOJIS.keys())

    results = {}
    for code in codes:
        results[code] = await get_lang_info(ctx, code, target_chat_id, target_user_id, native)

    return results
