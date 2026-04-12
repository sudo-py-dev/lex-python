"""Lightweight i18n loader. Uses JSON locale files with English fallback."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.config import config
from src.utils.lang_cache import resolve_lang

_LOCALES_DIR = Path(__file__).parent.parent / "locales"


@lru_cache(maxsize=10)
def _load_locale(lang: str) -> dict[str, str]:
    """Load and parse JSON locale file with caching."""
    path = _LOCALES_DIR / f"{lang}.json"
    if not path.exists():
        path = _LOCALES_DIR / "en.json"

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def t(lang: str, key: str, /, **kwargs: Any) -> str:
    """Translate ``key`` for ``lang``, with optional keyword format args.

    Falls back to English if key is missing in the selected locale.
    Falls back to the raw key if missing in English too.
    """
    locale = _load_locale(lang)
    template = locale.get(key)

    if not template and lang != "en":
        template = _load_locale("en").get(key)

    if not template:
        template = key

    try:
        if "bot_name" not in kwargs:
            kwargs["bot_name"] = config.BOT_NAME

        return template.format(**kwargs) if kwargs else template
    except (KeyError, IndexError):
        return template


async def at(chat_id: int | None, key: str, /, user_id: int | None = None, **kwargs: Any) -> str:
    """Async translate helper that automatically resolves chat/user language."""
    if chat_id is None and user_id is None:
        return t("en", key, **kwargs)

    if user_id is None and chat_id is not None and chat_id > 0:
        user_id = chat_id

    lang = await resolve_lang(chat_id, user_id)

    if chat_id is not None and "chat_id" not in kwargs:
        kwargs["chat_id"] = chat_id
    if user_id is not None and "user_id" not in kwargs:
        kwargs["user_id"] = user_id

    return t(lang, key, **kwargs)


def list_locales() -> list[str]:
    """Get list of available locale codes."""
    return [f.stem for f in _LOCALES_DIR.glob("*.json")]
