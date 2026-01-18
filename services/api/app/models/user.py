"""User SQLAlchemy model."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    """User model for OAuth-authenticated users."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="OAuth provider: 'github' or 'google'",
    )
    provider_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="User ID from the OAuth provider",
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships (will be populated when Link model is created)
    # links: Mapped[list["Link"]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<User {self.email}>"
