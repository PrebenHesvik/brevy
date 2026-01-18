"""Link SQLAlchemy model."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Link(Base):
    """Link model for shortened URLs."""

    __tablename__ = "links"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("api.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    short_code: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
        comment="Short code for the URL (e.g., 'abc123' or 'my-custom-slug')",
    )
    original_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="The original URL to redirect to",
    )
    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Optional title for the link",
    )
    is_custom: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether the short code was custom (user-provided)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether the link is active (soft delete)",
    )
    click_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="Total click count (denormalized for quick access)",
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
    expires_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="Optional expiration timestamp",
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="links")

    def __repr__(self) -> str:
        return f"<Link {self.short_code} -> {self.original_url[:50]}>"

    @property
    def is_expired(self) -> bool:
        """Check if the link has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at


# Import User for type hints (avoid circular import)
from app.models.user import User  # noqa: E402

# Update User model to include links relationship
User.links = relationship("Link", back_populates="user", lazy="selectin")
