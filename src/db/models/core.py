from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class TimestampMixin:
    """Mixin for adding createdAt and updatedAt columns."""

    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )


class SudoUser(Base):
    __tablename__ = "sudouser"

    userId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    addedBy: Mapped[int] = mapped_column(BigInteger)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )


class UserConnection(TimestampMixin, Base):
    __tablename__ = "userconnection"

    id: Mapped[int] = mapped_column(primary_key=True)
    userId: Mapped[int] = mapped_column(BigInteger, unique=True)
    activeChatId: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class ActionLog(Base):
    __tablename__ = "actionlog"

    id: Mapped[int] = mapped_column(primary_key=True)
    chatId: Mapped[int] = mapped_column(BigInteger, index=True)
    actorId: Mapped[int] = mapped_column(BigInteger)
    targetId: Mapped[int] = mapped_column(BigInteger, index=True)
    action: Mapped[str] = mapped_column(String(50))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration: Mapped[int | None] = mapped_column(nullable=True)
    msgLink: Mapped[str | None] = mapped_column(Text, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )


class TimedAction(Base):
    __tablename__ = "timedaction"

    id: Mapped[int] = mapped_column(primary_key=True)
    chatId: Mapped[int] = mapped_column(BigInteger)
    userId: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(50))
    expiresAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
