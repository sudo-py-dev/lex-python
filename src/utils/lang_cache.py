from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.context import get_context

if TYPE_CHECKING:
    from src.core.context import AppContext


async def resolve_lang(
    chat_id: int | None = None, user_id: int | None = None, ctx: AppContext | None = None
) -> str:
    """
    Resolve the current language for a context, prioritizing individual user
    preference before falling back to chat/group configuration.
    """
    from src.plugins.language import get_chat_lang, get_user_lang

    if ctx is None:
        try:
            ctx = get_context()
        except RuntimeError:
            return "en"

    # 1. Try personal user preference (explicit "en" is valid too)
    if user_id:
        user_lang = await get_user_lang(ctx, user_id)
        if user_lang:
            return user_lang

    # 2. Fallback to chat/group level
    if chat_id:
        return await get_chat_lang(ctx, chat_id)

    # 3. Last fallback
    return "en"
