from pyrogram.types import CallbackQuery

from src.config import config
from src.plugins.admin_panel.handlers.ai_kbs import ai_menu_kb
from src.plugins.admin_panel.handlers.keyboards import ai_security_kb, channel_watermark_kb
from src.plugins.admin_panel.repository import get_chat_settings
from src.plugins.ai_assistant.repository import AIRepository
from src.utils.i18n import at
from src.utils.media import parse_watermark_config

AI_PROVIDERS = ["openai", "gemini", "deepseek", "groq", "qwen", "anthropic"]
AI_PROVIDER_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-3.5-flash",
    "deepseek": "deepseek-chat",
    "groq": "llama3-8b-8192",
    "qwen": "qwen-plus",
    "anthropic": "claude-3-haiku-20240307",
}


def _panel_lang_id(is_pm: bool, user_id: int, chat_id: int) -> int:
    return user_id if is_pm else chat_id


def _plain(text: str) -> str:
    """Remove markdown-style markers for callback answers."""
    return (
        text.replace("**", "")
        .replace("__", "")
        .replace("`", "")
        .replace("||", "")
        .replace("[", "")
        .replace("]", "")
    )


def _next_ai_provider(current_provider: str) -> str:
    try:
        return AI_PROVIDERS[(AI_PROVIDERS.index(current_provider.lower()) + 1) % len(AI_PROVIDERS)]
    except ValueError:
        return AI_PROVIDERS[0]


async def _render_ai_panel(
    callback: CallbackQuery, ctx, chat_id: int, at_id: int, user_id: int
) -> None:
    s = await AIRepository.get_settings(ctx, chat_id)
    provider = (s.provider if s else "openai").upper()
    is_enabled = s.isEnabled if s else False
    model = (s.modelId if s else "N/A") or "N/A"
    api_key = "****" if (s and s.apiKey) else await at(at_id, "panel.not_set")
    status_text = await at(at_id, f"panel.status_{'enabled' if is_enabled else 'disabled'}")
    kb = await ai_menu_kb(chat_id, user_id=user_id)
    await callback.message.edit_text(
        await at(
            at_id,
            "panel.ai_text",
            status=status_text,
            provider=provider,
            model=model,
            api_key=api_key,
        ),
        reply_markup=kb,
    )


async def _render_ai_guard_panel(
    callback: CallbackQuery, ctx, chat_id: int, at_id: int, user_id: int
) -> str:
    from src.db.repositories.ai_guard import get_ai_guard_settings

    s = await get_ai_guard_settings(ctx, chat_id)
    status_label = await at(at_id, f"panel.status_{'enabled' if s.isEnabled else 'disabled'}")
    action_label = await at(at_id, f"action.{s.action}")
    await callback.message.edit_text(
        await at(
            at_id,
            "panel.ai_guard_text",
            status=status_label,
            action=action_label,
        ),
        reply_markup=await ai_security_kb(ctx, chat_id, user_id),
    )
    return action_label


async def _render_channel_watermark_panel(
    callback: CallbackQuery,
    ctx,
    channel_id: int,
    user_id: int,
    ui_id: int,
) -> None:
    settings = await get_chat_settings(ctx, channel_id)
    cfg = parse_watermark_config(settings.watermarkText)
    video_limit_note = (
        await at(ui_id, "panel.wm_video_limit_note", size_mb=config.VIDEO_WATERMARK_MAX_SIZE_MB)
        if config.ENABLE_VIDEO_WATERMARK
        else ""
    )
    await callback.message.edit_text(
        await at(
            ui_id,
            "panel.channel_watermark_text",
            image_status=await at(
                ui_id, "panel.status_enabled" if cfg.image_enabled else "panel.status_disabled"
            ),
            text=cfg.text or "-",
            color=await at(ui_id, f"panel.wm_color_{cfg.color}"),
            style=await at(ui_id, f"panel.wm_style_{cfg.style}"),
            video_status=await at(
                ui_id, "panel.status_enabled" if cfg.video_enabled else "panel.status_disabled"
            ),
            video_quality=await at(ui_id, f"panel.wm_quality_{cfg.video_quality}"),
            video_motion=await at(ui_id, f"panel.wm_motion_{cfg.video_motion}"),
            video_available=await at(
                ui_id,
                "panel.wm_video_available_yes"
                if config.ENABLE_VIDEO_WATERMARK
                else "panel.wm_video_available_no",
            ),
            video_limit_note=video_limit_note,
        ),
        reply_markup=await channel_watermark_kb(ctx, channel_id, user_id),
    )
