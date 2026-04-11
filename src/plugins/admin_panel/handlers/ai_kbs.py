import itertools

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.core.context import get_context
from src.plugins.ai_assistant.repository import AIRepository
from src.utils.i18n import at


async def ai_menu_kb(chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    at_id = user_id or chat_id
    ctx = get_context()
    settings = await AIRepository.get_settings(ctx, chat_id)

    is_enabled = settings.isAssistantEnabled if settings else False
    provider = settings.provider if settings else "openai"

    status_text = await at(at_id, f"panel.status_{'enabled' if is_enabled else 'disabled'}")

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_ai_toggle", status=status_text),
                    callback_data="panel:ai:toggle",
                )
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_ai_provider", provider=provider.upper()),
                    callback_data="panel:ai:cycle_provider",
                )
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_ai_set_key"),
                    callback_data="panel:input:aiApiKey",
                ),
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_ai_select_model"),
                    callback_data="panel:ai:model_list",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_ai_set_prompt"),
                    callback_data="panel:input:aiSystemPrompt",
                ),
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_ai_set_instruction"),
                    callback_data="panel:input:aiInstruction",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_ai_clear_ctx"), callback_data="panel:ai:clear_ctx"
                )
            ],
            [InlineKeyboardButton(await at(at_id, "panel.btn_back"), callback_data="panel:main")],
        ]
    )


async def model_selection_kb(
    provider: str, chat_id: int, user_id: int | None = None
) -> InlineKeyboardMarkup:
    at_id = user_id or chat_id
    models = {
        "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        "gemini": ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-pro"],
        "deepseek": ["deepseek-chat", "deepseek-coder"],
        "anthropic": [
            "claude-3-5-sonnet-20240620",
            "claude-3-opus-20240229",
            "claude-3-haiku-20240307",
        ],
        "groq": ["llama3-70b-8192", "llama3-8b-8192", "mixtral-8x7b-32768"],
        "qwen": ["qwen-plus", "qwen-turbo", "qwen-max"],
    }

    links = {
        "openai": "https://platform.openai.com/docs/models",
        "gemini": "https://ai.google.dev/gemini-api/docs/models/gemini",
        "deepseek": "https://api-docs.deepseek.com/quick_start/pricing",
        "anthropic": "https://docs.anthropic.com/en/docs/about-claude/models",
        "groq": "https://console.groq.com/docs/models",
        "qwen": "https://help.aliyun.com/zh/dashscope/developer-reference/model-introduction",
    }

    provider_models = models.get(provider.lower(), [])

    buttons = [
        [InlineKeyboardButton(m, callback_data=f"panel:ai:set_model:{m}") for m in row]
        for row in itertools.batched(provider_models, 2)
    ]

    if provider.lower() in links:
        buttons.append(
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_ai_view_all_models"),
                    url=links[provider.lower()],
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                await at(at_id, "panel.btn_ai_custom_model"),
                callback_data="panel:input:aiModelId",
            )
        ]
    )

    buttons.append(
        [InlineKeyboardButton(await at(at_id, "panel.btn_back"), callback_data="panel:category:ai")]
    )

    return InlineKeyboardMarkup(buttons)
