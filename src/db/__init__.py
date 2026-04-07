"""
Database package.

Exposes all SQLAlchemy models so that:
  - Alembic autogenerate can discover the full schema via `from src.db.models import *`
  - Application code has a single, clean import path
"""

from .base import Base
from .engine import engine, make_engine
from .models import (
    ActionLog,
    AllowedChannel,
    Approval,
    Blacklist,
    BlockedEntity,
    BlockedLanguage,
    ChannelProtect,
    ChatCleaner,
    ChatNightLock,
    ChatRules,
    ChatSettings,
    DisabledCommand,
    FedAdmin,
    FedBan,
    FedChat,
    Federation,
    FedSubscription,
    Filter,
    GlobalBan,
    Note,
    Reminder,
    ReportSetting,
    ScheduledMessage,
    SlowmodeSetting,
    SudoUser,
    TimedAction,
    UserConnection,
    UserWarn,
)
from .session import AsyncSessionLocal, get_db

__all__ = [
    "Base",
    "engine",
    "make_engine",
    "AsyncSessionLocal",
    "get_db",
    "ActionLog",
    "AllowedChannel",
    "Approval",
    "Blacklist",
    "BlockedEntity",
    "BlockedLanguage",
    "ChannelProtect",
    "DisabledCommand",
    "FedAdmin",
    "FedBan",
    "FedChat",
    "Federation",
    "FedSubscription",
    "Filter",
    "GlobalBan",
    "ChatCleaner",
    "ChatRules",
    "ChatSettings",
    "ChatNightLock",
    "Note",
    "Reminder",
    "ReportSetting",
    "ScheduledMessage",
    "SlowmodeSetting",
    "SudoUser",
    "TimedAction",
    "UserConnection",
    "UserWarn",
]
