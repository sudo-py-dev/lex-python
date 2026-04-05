"""Centralised string constants — no magic strings in handlers."""


class CacheKeys:
    """Cache key templates for all features."""

    @staticmethod
    def flood(chat_id: int, user_id: int) -> str:
        return f"flood:{chat_id}:{user_id}"

    @staticmethod
    def raid(chat_id: int) -> str:
        return f"raid:{chat_id}"

    @staticmethod
    def admins(chat_id: int) -> str:
        return f"admins:{chat_id}"

    @staticmethod
    def captcha(chat_id: int, user_id: int) -> str:
        return f"captcha:{chat_id}:{user_id}"

    @staticmethod
    def dupes(chat_id: int, user_id: int) -> str:
        return f"dupes:{chat_id}:{user_id}"

    @staticmethod
    def afk(user_id: int) -> str:
        return f"afk:{user_id}"

    @staticmethod
    def afk_username(username: str) -> str:
        return f"afk_un:{username.lower()}"

    @staticmethod
    def slowmode(chat_id: int, user_id: int) -> str:
        return f"slowmode:{chat_id}:{user_id}"

    @staticmethod
    def report_cooldown(chat_id: int, user_id: int) -> str:
        return f"report_cd:{chat_id}:{user_id}"

    @staticmethod
    def fsub_grace(chat_id: int, user_id: int) -> str:
        return f"fsub_grace:{chat_id}:{user_id}"


class Actions:
    """Action name constants."""

    MUTE = "mute"
    KICK = "kick"
    BAN = "ban"
    TBAN = "tban"
    TMUTE = "tmute"
    DELETE = "delete"
    WARN = "warn"
    LOCK = "lock"


class LockTypes:
    """Valid lock type names."""

    ALL = {"text", "media", "sticker", "gif", "url", "forward", "command", "rtl", "poll"}


class WarnExpiry:
    NEVER = "never"
    H24 = "24h"
    D7 = "7d"
    D30 = "30d"
