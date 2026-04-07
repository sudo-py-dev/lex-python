from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .ai import AIGuardSettings, AISettings
    from .moderation import Blacklist, BlockedEntity, BlockedLanguage, UserWarn
    from .plugins import Filter, Note, Reminder

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base
from .core import TimestampMixin


class ChatSettings(TimestampMixin, Base):
    __tablename__ = "chatsettings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    chatType: Mapped[str] = mapped_column(
        String(50), default="supergroup", server_default=sa_text("'supergroup'")
    )

    floodThreshold: Mapped[int] = mapped_column(default=5, server_default=sa_text("5"))
    floodWindow: Mapped[int] = mapped_column(default=5, server_default=sa_text("5"))
    floodAction: Mapped[str] = mapped_column(
        String(50), default="mute", server_default=sa_text("'mute'")
    )
    raidEnabled: Mapped[bool] = mapped_column(default=False, server_default=sa_text("false"))
    raidThreshold: Mapped[int] = mapped_column(default=10, server_default=sa_text("10"))
    raidWindow: Mapped[int] = mapped_column(default=60, server_default=sa_text("60"))
    raidAction: Mapped[str] = mapped_column(
        String(50), default="lock", server_default=sa_text("'lock'")
    )
    warnLimit: Mapped[int] = mapped_column(default=3, server_default=sa_text("3"))
    warnAction: Mapped[str] = mapped_column(
        String(50), default="kick", server_default=sa_text("'kick'")
    )
    warnExpiry: Mapped[str] = mapped_column(
        String(50), default="never", server_default=sa_text("'never'")
    )
    captchaEnabled: Mapped[bool] = mapped_column(default=False, server_default=sa_text("false"))
    captchaMode: Mapped[str] = mapped_column(
        String(50), default="button", server_default=sa_text("'button'")
    )
    captchaTimeout: Mapped[int] = mapped_column(default=120, server_default=sa_text("120"))
    logChannelId: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en", server_default=sa_text("'en'"))
    welcomeEnabled: Mapped[bool] = mapped_column(default=True, server_default=sa_text("true"))
    welcomeText: Mapped[str | None] = mapped_column(Text, nullable=True)
    goodbyeEnabled: Mapped[bool] = mapped_column(default=False, server_default=sa_text("false"))
    goodbyeText: Mapped[str | None] = mapped_column(Text, nullable=True)
    cleanJoin: Mapped[bool] = mapped_column(default=False, server_default=sa_text("false"))
    cleanLeave: Mapped[bool] = mapped_column(default=False, server_default=sa_text("false"))
    cleanPinned: Mapped[bool] = mapped_column(default=False, server_default=sa_text("false"))
    cleanAllServices: Mapped[bool] = mapped_column(default=False, server_default=sa_text("false"))
    cleanServiceTypes: Mapped[str] = mapped_column(
        Text, default="[]", server_default=sa_text("'[]'")
    )
    blacklistAction: Mapped[str] = mapped_column(
        String(50), default="delete", server_default=sa_text("'delete'")
    )
    timezone: Mapped[str] = mapped_column(
        String(50), default="UTC", server_default=sa_text("'UTC'")
    )
    urlScannerEnabled: Mapped[bool] = mapped_column(default=False, server_default=sa_text("false"))
    gsbKey: Mapped[str | None] = mapped_column(Text, nullable=True)
    urlScannerAction: Mapped[str] = mapped_column(
        String(50), default="delete", server_default=sa_text("'delete'")
    )
    isActive: Mapped[bool] = mapped_column(default=True, server_default=sa_text("true"))

    reactionsEnabled: Mapped[bool] = mapped_column(default=False, server_default=sa_text("false"))
    reactions: Mapped[str] = mapped_column(Text, default="👍", server_default=sa_text("'👍'"))
    reactionMode: Mapped[str] = mapped_column(Text, default="all", server_default=sa_text("'all'"))
    watermarkEnabled: Mapped[bool] = mapped_column(default=False, server_default=sa_text("false"))
    watermarkText: Mapped[str | None] = mapped_column(Text, nullable=True)
    signatureEnabled: Mapped[bool] = mapped_column(default=False, server_default=sa_text("false"))
    signatureText: Mapped[str | None] = mapped_column(Text, nullable=True)

    warns: Mapped[list["UserWarn"]] = relationship(back_populates="chat", lazy="raise")
    filters: Mapped[list["Filter"]] = relationship(back_populates="chat", lazy="raise")
    notes: Mapped[list["Note"]] = relationship(back_populates="chat", lazy="raise")
    blacklist: Mapped[list["Blacklist"]] = relationship(back_populates="chat", lazy="raise")
    langBlocks: Mapped[list["BlockedLanguage"]] = relationship(back_populates="chat", lazy="raise")
    blockedEntities: Mapped[list["BlockedEntity"]] = relationship(
        back_populates="chat", lazy="raise"
    )
    reminders: Mapped[list["Reminder"]] = relationship(back_populates="chat", lazy="raise")
    nightLock: Mapped[Optional["ChatNightLock"]] = relationship(
        back_populates="chat", uselist=False, lazy="selectin"
    )
    ChatCleaner: Mapped[Optional["ChatCleaner"]] = relationship(
        back_populates="chat", uselist=False, lazy="selectin"
    )
    aiSettings: Mapped[Optional["AISettings"]] = relationship(
        back_populates="chat", uselist=False, lazy="selectin"
    )
    aiGuardSettings: Mapped[Optional["AIGuardSettings"]] = relationship(
        back_populates="chat", uselist=False, lazy="selectin"
    )


class ChatRules(Base):
    __tablename__ = "chatrules"

    chatId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    content: Mapped[str] = mapped_column(Text)
    privateMode: Mapped[bool] = mapped_column(default=False, server_default=sa_text("false"))
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=sa_text("now()"),
        nullable=False,
    )


class ChatCleaner(Base):
    __tablename__ = "chatcleaner"

    chatId: Mapped[int] = mapped_column(BigInteger, ForeignKey("chatsettings.id"), primary_key=True)
    cleanDeleted: Mapped[bool] = mapped_column(default=False, server_default=sa_text("false"))
    cleanFake: Mapped[bool] = mapped_column(default=False, server_default=sa_text("false"))
    cleanInactiveDays: Mapped[int] = mapped_column(default=0, server_default=sa_text("0"))
    lastRunDate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=sa_text("now()"),
        nullable=False,
    )

    chat: Mapped["ChatSettings"] = relationship(back_populates="ChatCleaner", lazy="raise")


class ChatNightLock(Base):
    __tablename__ = "chatnightlock"

    chatId: Mapped[int] = mapped_column(BigInteger, ForeignKey("chatsettings.id"), primary_key=True)
    isEnabled: Mapped[bool] = mapped_column(default=False, server_default=sa_text("false"))
    startTime: Mapped[str] = mapped_column(
        String(5), default="23:00", server_default=sa_text("'23:00'")
    )
    endTime: Mapped[str] = mapped_column(
        String(5), default="07:00", server_default=sa_text("'07:00'")
    )
    lastPermissions: Mapped[str | None] = mapped_column(Text, nullable=True)
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=sa_text("now()"),
        nullable=False,
    )

    chat: Mapped["ChatSettings"] = relationship(back_populates="nightLock", lazy="raise")


class AllowedChannel(Base):
    __tablename__ = "allowedchannel"

    id: Mapped[int] = mapped_column(primary_key=True)
    chatId: Mapped[int] = mapped_column(BigInteger, index=True)
    channelId: Mapped[int] = mapped_column(BigInteger)


class DisabledCommand(Base):
    __tablename__ = "disabledcommand"

    id: Mapped[int] = mapped_column(primary_key=True)
    chatId: Mapped[int] = mapped_column(BigInteger, index=True)
    command: Mapped[str] = mapped_column(String(100))
