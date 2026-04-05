import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base


class Federation(Base):
    __tablename__ = "federation"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    ownerId: Mapped[int] = mapped_column(BigInteger)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )

    chats: Mapped[list["FedChat"]] = relationship(back_populates="fed", lazy="raise")
    bans: Mapped[list["FedBan"]] = relationship(back_populates="fed", lazy="raise")
    admins: Mapped[list["FedAdmin"]] = relationship(back_populates="fed", lazy="raise")


class FedChat(Base):
    __tablename__ = "fedchat"

    id: Mapped[int] = mapped_column(primary_key=True)
    fedId: Mapped[str] = mapped_column(String(36), ForeignKey("federation.id"))
    chatId: Mapped[int] = mapped_column(BigInteger, unique=True)

    fed: Mapped["Federation"] = relationship(back_populates="chats", lazy="raise")


class FedAdmin(Base):
    __tablename__ = "fedadmin"

    id: Mapped[int] = mapped_column(primary_key=True)
    fedId: Mapped[str] = mapped_column(String(36), ForeignKey("federation.id"))
    userId: Mapped[int] = mapped_column(BigInteger)

    fed: Mapped["Federation"] = relationship(back_populates="admins", lazy="raise")


class FedBan(Base):
    __tablename__ = "fedban"

    id: Mapped[int] = mapped_column(primary_key=True)
    fedId: Mapped[str] = mapped_column(String(36), ForeignKey("federation.id"))
    userId: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    bannedBy: Mapped[int] = mapped_column(BigInteger)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )

    fed: Mapped["Federation"] = relationship(back_populates="bans", lazy="raise")


class FedSubscription(Base):
    __tablename__ = "fedsubscription"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscriberId: Mapped[str] = mapped_column(String(36), ForeignKey("federation.id"))
    publisherId: Mapped[str] = mapped_column(String(36), ForeignKey("federation.id"))
