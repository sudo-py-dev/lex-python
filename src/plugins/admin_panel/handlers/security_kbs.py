from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.utils.i18n import at

from ..repository import get_chat_settings


async def raid_kb(ctx, chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    settings = await get_chat_settings(ctx, chat_id)
    status = await at(
        chat_id, "panel.status_enabled" if settings.raidEnabled else "panel.status_disabled"
    )
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_raid_toggle", status=status),
                    callback_data="panel:tgs:raidEnabled",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_raid_threshold", threshold=settings.raidThreshold),
                    callback_data="panel:input:raidThreshold",
                ),
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_raid_window", window=settings.raidWindow),
                    callback_data="panel:input:raidWindow",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(
                        chat_id,
                        "panel.btn_raid_action",
                        action=await at(chat_id, f"action.{settings.raidAction.lower()}"),
                    ),
                    callback_data="panel:cycle:raidAction",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_back"), callback_data="panel:category:security"
                )
            ],
        ]
    )


async def captcha_kb(ctx, chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    settings = await get_chat_settings(ctx, chat_id)
    status = await at(
        chat_id, "panel.status_enabled" if settings.captchaEnabled else "panel.status_disabled"
    )
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_captcha_toggle", status=status),
                    callback_data="panel:tgs:captchaEnabled",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(
                        chat_id,
                        "panel.btn_captcha_mode",
                        mode=await at(chat_id, f"mode.{settings.captchaMode.lower()}"),
                    ),
                    callback_data="panel:cycle:captchaMode",
                ),
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_captcha_timeout", timeout=settings.captchaTimeout),
                    callback_data="panel:input:captchaTimeout",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_back"), callback_data="panel:category:security"
                )
            ],
        ]
    )
