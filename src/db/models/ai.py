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
)
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base


class AISettings(Base):
    __tablename__ = "aisettings"

    chatId: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("groupsettings.id"), primary_key=True
    )
    provider: Mapped[str] = mapped_column(
        String(50), default="openai", server_default=sa_text("'openai'")
    )
    apiKey: Mapped[str | None] = mapped_column(Text, nullable=True)
    modelId: Mapped[str | None] = mapped_column(String(100), nullable=True)
    systemPrompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    customInstruction: Mapped[str | None] = mapped_column(Text, nullable=True)
    isEnabled: Mapped[bool] = mapped_column(default=False, server_default=sa_text("false"))

    group: Mapped["GroupSettings"] = relationship(
        back_populates="aiSettings", uselist=False, lazy="selectin"
    )


class AIGuardSettings(Base):
    __tablename__ = "aiguardsettings"

    chatId: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("groupsettings.id"), primary_key=True
    )
    isEnabled: Mapped[bool] = mapped_column(default=False, server_default=sa_text("false"))
    apiKey: Mapped[str | None] = mapped_column(Text, nullable=True)
    modelId: Mapped[str] = mapped_column(
        String(100), default="llama-3.1-8b-instant", server_default=sa_text("'llama-3.1-8b-instant'")
    )
    action: Mapped[str] = mapped_column(
        String(50), default="delete", server_default=sa_text("'delete'")
    )

    group: Mapped["GroupSettings"] = relationship(
        back_populates="aiGuardSettings", uselist=False, lazy="selectin"
    )


class AIChatContext(Base):
    __tablename__ = "aichatcontext"

    id: Mapped[int] = mapped_column(primary_key=True)
    chatId: Mapped[int] = mapped_column(BigInteger, ForeignKey("groupsettings.id"), index=True)
    messageId: Mapped[int] = mapped_column(BigInteger)
    userId: Mapped[int] = mapped_column(BigInteger)
    userName: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=sa_text("now()"),
        nullable=False,
    )
