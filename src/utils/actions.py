import contextlib
from enum import Enum, StrEnum
from typing import TypeVar

from pyrogram.enums import ButtonStyle

T = TypeVar("T", bound=str | Enum)


class ModerationAction(StrEnum):
    DELETE = "delete"
    MUTE = "mute"
    KICK = "kick"
    BAN = "ban"
    WARN = "warn"
    LOCK = "lock"
    OFF = "off"


class CaptchaMode(StrEnum):
    BUTTON = "button"
    MATH = "math"
    POLL = "poll"
    IMAGE = "image"


class ReactionMode(StrEnum):
    ALL = "all"
    RANDOM = "random"


class AIProvider(StrEnum):
    OPENAI = "openai"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    GROQ = "groq"
    QWEN = "qwen"
    ANTHROPIC = "anthropic"


class WarnExpiry(StrEnum):
    NEVER = "never"
    H24 = "24h"
    D7 = "7d"
    D30 = "30d"


class WatermarkColor(StrEnum):
    WHITE = "white"
    BLACK = "black"
    RED = "red"
    BLUE = "blue"
    GOLD = "gold"


class WatermarkStyle(StrEnum):
    SOFT_SHADOW = "soft_shadow"
    OUTLINE = "outline"
    CLEAN = "clean"
    PATTERN_GRID = "pattern_grid"
    PATTERN_DIAGONAL = "pattern_diagonal"


class VideoQuality(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class VideoMotion(StrEnum):
    STATIC = "static"
    FLOAT = "float"
    SCROLL_LR = "scroll_lr"
    SCROLL_RL = "scroll_rl"


def cycle_action[T: str | Enum](
    current_action: T | None,
    allowed_actions: list[T],
    default_action: T | None = None,
) -> str:
    """
    Returns the next action string in a cyclic list of allowed_actions.
    Handles both strings and Enum members.
    """
    if not allowed_actions:
        raise ValueError("allowed_actions cannot be empty")

    def _to_str(val: T | None) -> str | None:
        if val is None:
            return None
        return val.value if isinstance(val, Enum) else str(val)

    normalized_allowed = [_to_str(x).lower() for x in allowed_actions]
    fallback_idx = 0
    if default_action is not None:
        with contextlib.suppress(ValueError):
            fallback_idx = normalized_allowed.index(_to_str(default_action).lower())

    fallback = _to_str(allowed_actions[fallback_idx])

    if not current_action:
        if default_action is not None:
            return _to_str(default_action)
        return fallback

    current_str = _to_str(current_action).lower()

    if current_str in normalized_allowed:
        idx = normalized_allowed.index(current_str)
        next_val = allowed_actions[(idx + 1) % len(allowed_actions)]
        return _to_str(next_val)

    if default_action is not None:
        return _to_str(default_action)

    return fallback


MODERATION_ACTIONS = [
    ModerationAction.DELETE,
    ModerationAction.MUTE,
    ModerationAction.KICK,
    ModerationAction.BAN,
    ModerationAction.WARN,
]

PUNISHMENT_ACTIONS = [
    ModerationAction.MUTE,
    ModerationAction.KICK,
    ModerationAction.BAN,
]

LANG_BLOCK_ACTIONS = [
    ModerationAction.DELETE,
    ModerationAction.MUTE,
    ModerationAction.KICK,
    ModerationAction.BAN,
]

EXTENDED_MODERATION_ACTIONS = [
    ModerationAction.DELETE,
    ModerationAction.WARN,
    ModerationAction.MUTE,
    ModerationAction.KICK,
    ModerationAction.BAN,
    ModerationAction.OFF,
]

AI_GUARD_ACTIONS = [
    ModerationAction.DELETE,
    ModerationAction.WARN,
    ModerationAction.MUTE,
    ModerationAction.BAN,
]

SECURITY_ACTIONS = [
    ModerationAction.DELETE,
    ModerationAction.WARN,
    ModerationAction.MUTE,
    ModerationAction.KICK,
    ModerationAction.BAN,
]

RAID_ACTIONS = [
    ModerationAction.LOCK,
    ModerationAction.KICK,
    ModerationAction.BAN,
]


CAPTCHA_MODES = [
    CaptchaMode.BUTTON,
    CaptchaMode.MATH,
    CaptchaMode.POLL,
    CaptchaMode.IMAGE,
]

FLOOD_ACTIONS = PUNISHMENT_ACTIONS

REACTION_MODES = [
    ReactionMode.ALL,
    ReactionMode.RANDOM,
]

AI_PROVIDERS = [
    AIProvider.OPENAI,
    AIProvider.GEMINI,
    AIProvider.DEEPSEEK,
    AIProvider.GROQ,
    AIProvider.QWEN,
    AIProvider.ANTHROPIC,
]

WARN_EXPIRY_OPTIONS = [
    WarnExpiry.NEVER,
    WarnExpiry.H24,
    WarnExpiry.D7,
    WarnExpiry.D30,
]

REACTION_MODES = [
    ReactionMode.ALL,
    ReactionMode.RANDOM,
]

WATERMARK_COLORS = [
    WatermarkColor.WHITE,
    WatermarkColor.BLACK,
    WatermarkColor.RED,
    WatermarkColor.BLUE,
    WatermarkColor.GOLD,
]

WATERMARK_STYLES = [
    WatermarkStyle.SOFT_SHADOW,
    WatermarkStyle.OUTLINE,
    WatermarkStyle.CLEAN,
    WatermarkStyle.PATTERN_GRID,
    WatermarkStyle.PATTERN_DIAGONAL,
]

VIDEO_QUALITIES = [
    VideoQuality.HIGH,
    VideoQuality.MEDIUM,
    VideoQuality.LOW,
]

VIDEO_MOTIONS = [
    VideoMotion.STATIC,
    VideoMotion.FLOAT,
    VideoMotion.SCROLL_LR,
    VideoMotion.SCROLL_RL,
]

BUTTON_STYLES = list(ButtonStyle)
