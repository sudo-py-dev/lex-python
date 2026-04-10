# Fields that only apply to Groups/Supergroups
GROUP_ONLY_FIELDS: set[str] = {
    # DB Fields
    "floodThreshold",
    "floodWindow",
    "floodAction",
    "raidEnabled",
    "raidThreshold",
    "raidWindow",
    "raidTime",
    "raidActionTime",
    "raidAction",
    "captchaEnabled",
    "captchaTimeout",
    "captchaMode",
    "welcomeEnabled",
    "goodbyeEnabled",
    "welcomeText",
    "goodbyeText",
    "cleanJoin",
    "cleanLeave",
    "cleanPinned",
    "cleanAllServices",
    "cleanServiceTypes",
    "blacklistAction",
    "warnAction",
    "warnLimit",
    "warnExpiry",
    "rulesText",
    "blacklistInput",
    "reminderText",
    "reminderTime",
    "purgeMessagesCount",
    "slowmode",
    "chatnightlockStart",
    "chatnightlockEnd",
    "cleanerInactive",
    "cleanerRunTime",
    "timezoneSearch",
    # UI Slugs
    "flood",
    "captcha",
    "raid",
    "warns",
    "blacklist",
    "welcome",
    "rules",
    "filters",
    "chatnightlock",
    "cleaner",
    "reminders",
    "timezone",
    "svc",
    "entityblock",
    "langblock",
    "logging",
    "stickers",
    "stickerAction",
}

# Fields that only apply to Channels
CHANNEL_ONLY_FIELDS: set[str] = {
    # DB Fields
    "reactionsEnabled",
    "reactions",
    "reactionMode",
    "watermarkText",
    "signatureEnabled",
    "signatureText",
    # UI Slugs
    "channel_settings",
}


def is_setting_allowed(field: str, chat_type: str) -> bool:
    """
    Check if a setting field is allowed for a given chat type.
    chat_type: 'group', 'supergroup', or 'channel'
    """
    is_group = chat_type in ("group", "supergroup")
    is_channel = chat_type == "channel"

    # Normalize fields that might come from callbacks or inputs
    f = field.split(":")[0] if ":" in field else field

    if f in GROUP_ONLY_FIELDS:
        return is_group
    if f in CHANNEL_ONLY_FIELDS:
        return is_channel

    return True
