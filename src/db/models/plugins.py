from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .chats import ChatSettings


from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    Text,
    false,
    func,
    true,
)
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base


class Filter(Base):
    __tablename__ = "filter"

    id: Mapped[int] = mapped_column(primary_key=True)
    chatId: Mapped[int] = mapped_column(BigInteger, ForeignKey("chatsettings.id"), index=True)
    keyword: Mapped[str] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text)
    responseType: Mapped[str] = mapped_column(
        String(50), default="text", server_default=sa_text("'text'")
    )
    fileId: Mapped[str | None] = mapped_column(String(255), nullable=True)
    settings: Mapped[dict] = mapped_column(JSON, default=dict, server_default=sa_text("'{}'"))
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )

    chat: Mapped["ChatSettings"] = relationship(back_populates="filters", lazy="raise")


class Note(Base):
    __tablename__ = "note"

    id: Mapped[int] = mapped_column(primary_key=True)
    chatId: Mapped[int] = mapped_column(BigInteger, ForeignKey("chatsettings.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    isPrivate: Mapped[bool] = mapped_column(default=False, server_default=false())
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )

    chat: Mapped["ChatSettings"] = relationship(back_populates="notes", lazy="raise")


class Reminder(Base):
    __tablename__ = "reminder"

    id: Mapped[int] = mapped_column(primary_key=True)
    chatId: Mapped[int] = mapped_column(BigInteger, ForeignKey("chatsettings.id"), index=True)
    messageType: Mapped[str] = mapped_column(
        String(50), default="text", server_default=sa_text("'text'")
    )
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    fileId: Mapped[str | None] = mapped_column(String(255), nullable=True)
    additionalData: Mapped[str | None] = mapped_column(Text, nullable=True)
    sendTime: Mapped[str] = mapped_column(
        String(5), default="12:00", server_default=sa_text("'12:00'")
    )
    isActive: Mapped[bool] = mapped_column(default=True, server_default=true())
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )

    chat: Mapped["ChatSettings"] = relationship(back_populates="reminders", lazy="raise")


class ScheduledMessage(Base):
    __tablename__ = "scheduledmessage"

    id: Mapped[int] = mapped_column(primary_key=True)
    chatId: Mapped[int] = mapped_column(BigInteger, index=True)
    content: Mapped[str] = mapped_column(Text)
    sendAt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    cronExpr: Mapped[str | None] = mapped_column(String(100), nullable=True)
    jobId: Mapped[str] = mapped_column(String(100), unique=True)
    createdBy: Mapped[int] = mapped_column(BigInteger)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
