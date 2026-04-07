from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from src.utils.i18n import at

from ..repository import get_chat_settings


async def raid_kb(ctx, chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    at_id = user_id if user_id else chat_id
    settings = await get_chat_settings(ctx, chat_id)
    status = await at(
        at_id, "panel.status_enabled" if settings.raidEnabled else "panel.status_disabled"
    )
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(at_id, "common.btn_status", status=status),
                    callback_data="panel:tgs:raidEnabled",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_raid_threshold", threshold=settings.raidThreshold),
                    callback_data="panel:input:raidThreshold",
                ),
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_raid_window", window=settings.raidWindow),
                    callback_data="panel:input:raidWindow",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(
                        chat_id,
                        "common.btn_action",
                        action=await at(at_id, f"action.{settings.raidAction.lower()}"),
                    ),
                    callback_data="panel:cycle:raidAction",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_back"), callback_data="panel:category:security"
                )
            ],
        ]
    )


async def captcha_kb(ctx, chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    at_id = user_id if user_id else chat_id
    settings = await get_chat_settings(ctx, chat_id)
    status = await at(
        at_id, "panel.status_enabled" if settings.captchaEnabled else "panel.status_disabled"
    )
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(at_id, "common.btn_status", status=status),
                    callback_data="panel:tgs:captchaEnabled",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(
                        at_id,
                        "panel.btn_captcha_mode",
                        mode=await at(at_id, f"mode.{settings.captchaMode.lower()}"),
                    ),
                    callback_data="panel:cycle:captchaMode",
                ),
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_captcha_timeout", timeout=settings.captchaTimeout),
                    callback_data="panel:input:captchaTimeout",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_back"), callback_data="panel:category:security"
                )
            ],
        ]
    )


async def url_scanner_kb(ctx, chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    at_id = user_id if user_id else chat_id
    settings = await get_chat_settings(ctx, chat_id)
    status = await at(
        at_id, "panel.status_enabled" if settings.urlScannerEnabled else "panel.status_disabled"
    )
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(at_id, "common.btn_status", status=status),
                    callback_data="panel:tgs:urlScannerEnabled",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_set_gsb_key"),
                    callback_data="panel:input:gsbKey",
                ),
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_get_gsb_key"),
                    url="https://console.cloud.google.com/apis/library/safebrowsing.googleapis.com",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(
                        at_id,
                        "common.btn_action",
                        action=await at(at_id, f"action.{settings.urlScannerAction.lower()}"),
                    ),
                    callback_data="panel:cycle:urlScannerAction",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_back"), callback_data="panel:category:security"
                )
            ],
        ]
    )
