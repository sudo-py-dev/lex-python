from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .groups import GroupSettings


from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base


class Blacklist(Base):
    __tablename__ = "blacklist"

    id: Mapped[int] = mapped_column(primary_key=True)
    chatId: Mapped[int] = mapped_column(BigInteger, ForeignKey("groupsettings.id"), index=True)
    pattern: Mapped[str] = mapped_column(Text)
    isRegex: Mapped[bool] = mapped_column(default=False, server_default=sa_text("false"))
    isWildcard: Mapped[bool] = mapped_column(default=False, server_default=sa_text("false"))
    action: Mapped[str] = mapped_column(
        String(50), default="delete", server_default=sa_text("'delete'")
    )
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )

    group: Mapped["GroupSettings"] = relationship(back_populates="blacklist", lazy="raise")


class BlockedEntity(Base):
    __tablename__ = "blockedentity"

    id: Mapped[int] = mapped_column(primary_key=True)
    chatId: Mapped[int] = mapped_column(BigInteger, ForeignKey("groupsettings.id"), index=True)
    entityType: Mapped[str] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(
        String(50), default="delete", server_default=sa_text("'delete'")
    )
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )

    group: Mapped["GroupSettings"] = relationship(back_populates="blockedEntities", lazy="raise")


class BlockedLanguage(Base):
    __tablename__ = "blockedlanguage"

    id: Mapped[int] = mapped_column(primary_key=True)
    chatId: Mapped[int] = mapped_column(BigInteger, ForeignKey("groupsettings.id"), index=True)
    langCode: Mapped[str] = mapped_column(String(10))
    action: Mapped[str] = mapped_column(
        String(50), default="delete", server_default=sa_text("'delete'")
    )
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )

    group: Mapped["GroupSettings"] = relationship(back_populates="langBlocks", lazy="raise")


class UserWarn(Base):
    __tablename__ = "userwarn"

    id: Mapped[int] = mapped_column(primary_key=True)
    chatId: Mapped[int] = mapped_column(BigInteger, ForeignKey("groupsettings.id"), index=True)
    userId: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actorId: Mapped[int] = mapped_column(BigInteger)
    expiresAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )

    group: Mapped["GroupSettings"] = relationship(back_populates="warns", lazy="raise")


class GlobalBan(Base):
    __tablename__ = "globalban"

    id: Mapped[int] = mapped_column(primary_key=True)
    userId: Mapped[int] = mapped_column(BigInteger, unique=True)
    reason: Mapped[str] = mapped_column(Text)
    bannedBy: Mapped[int] = mapped_column(BigInteger)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )


class ChannelProtect(Base):
    __tablename__ = "channelprotect"

    chatId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    antiChannel: Mapped[bool] = mapped_column(default=False, server_default=sa_text("false"))
    antiAnon: Mapped[bool] = mapped_column(default=False, server_default=sa_text("false"))
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=sa_text("now()"),
        nullable=False,
    )


class SlowmodeSetting(Base):
    __tablename__ = "slowmodesetting"

    chatId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    interval: Mapped[int] = mapped_column(default=0, server_default=sa_text("0"))
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=sa_text("now()"),
        nullable=False,
    )


class ReportSetting(Base):
    __tablename__ = "reportsetting"

    chatId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=True, server_default=sa_text("true"))
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=sa_text("now()"),
        nullable=False,
    )


class Approval(Base):
    __tablename__ = "approval"

    id: Mapped[int] = mapped_column(primary_key=True)
    chatId: Mapped[int] = mapped_column(BigInteger, index=True)
    userId: Mapped[int] = mapped_column(BigInteger)
    grantedBy: Mapped[int] = mapped_column(BigInteger)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
