from pyrogram import Client
from pyrogram.types import Message

from src.core.context import AppContext
from src.plugins.admin_panel.handlers.ai_kbs import ai_menu_kb
from src.plugins.ai_assistant.repository import AIRepository
from src.utils.i18n import at

from .dispatch_logic import finalize_input_capture, input_registry


@input_registry.register(["aiApiKey", "aiModelId", "aiSystemPrompt", "aiInstruction"])
async def ai_settings_processor(
    client: Client,
    message: Message,
    ctx: AppContext,
    chat_id: int,
    field: str,
    value: str,
    prompt_msg_id: int | None,
    page: int,
) -> None:
    user_id = message.from_user.id

    mapping = {
        "aiApiKey": "apiKey",
        "aiModelId": "modelId",
        "aiSystemPrompt": "systemPrompt",
        "aiInstruction": "customInstruction",
    }
    db_field = mapping.get(field, field)

    update_data = {db_field: str(value)}
    await AIRepository.update_settings(ctx, chat_id, **update_data)

    kb = await ai_menu_kb(chat_id, user_id=user_id)
    s = await AIRepository.get_settings(ctx, chat_id)
    is_enabled = s.isEnabled if s else False
    provider = (s.provider if s else "openai").upper()
    model = (s.modelId if s else "N/A") or "N/A"

    status_text = await at(user_id, f"panel.status_{'enabled' if is_enabled else 'disabled'}")
    main_text = await at(
        user_id, "panel.ai_text", status=status_text, provider=provider, model=model
    )

    success_text = await at(user_id, "panel.input_success")
    await finalize_input_capture(
        client,
        message,
        user_id,
        prompt_msg_id,
        f"**{success_text}**\n\n{main_text}",
        kb,
    )
