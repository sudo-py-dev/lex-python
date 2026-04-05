from langdetect import detect, detect_langs

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

_LANG_NAMES = {
    "en": "English",
    "he": "Hebrew",
    "ru": "Russian",
    "id": "Indonesian",
    "ar": "Arabic",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "it": "Italian",
    "hi": "Hindi",
    "tr": "Turkish",
    "fa": "Persian",
    "uk": "Ukrainian",
    "uz": "Uzbek",
    "zh": "Chinese",
    "zh-cn": "Chinese (Simplified)",
    "zh-tw": "Chinese (Traditional)",
}


def is_supported(lang_code: str) -> bool:
    """Check if the language code is supported by langdetect."""
    return lang_code.lower() in SUPPORTED_LANGS


def detect_language(text: str) -> str | None:
    """Detect the language of a given text using langdetect."""
    try:
        return detect(text)
    except Exception:
        return None


def detect_language_with_confidence(text: str) -> list[tuple[str, float]]:
    """
    Returns a list of (iso_code, confidence) tuples for all detected languages.
    """
    try:
        langs = detect_langs(text)
        return [(lang_obj.lang, lang_obj.prob) for lang_obj in langs]
    except Exception:
        return []


def get_language_name(iso_code: str) -> str:
    """Returns the English name of a language code."""
    return _LANG_NAMES.get(iso_code.lower(), iso_code.upper())


def parse_iso_code(input_str: str) -> str | None:
    """
    Parses a string input (like 'en' or 'English') into its ISO 639-1 code.
    Fallback logic for full names based on our _LANG_NAMES map.
    """
    input_str = input_str.strip().lower()
    if len(input_str) == 2:
        return input_str

    for code, name in _LANG_NAMES.items():
        if name.lower() == input_str:
            return code

    return None
