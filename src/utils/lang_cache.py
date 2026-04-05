from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.context import get_context

if TYPE_CHECKING:
    from src.core.context import AppContext


async def resolve_lang(chat_id: int, ctx: AppContext | None = None) -> str:
    """Resolve the current language for a chat, with caching."""
    from src.plugins.language import get_chat_lang

    if ctx is None:
        try:
            ctx = get_context()
        except RuntimeError:
            return "en"

    return await get_chat_lang(ctx, chat_id)
