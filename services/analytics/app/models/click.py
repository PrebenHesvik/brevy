"""Click SQLAlchemy model for storing raw click events."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import INET, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Click(Base):
    """Click model for storing raw click/redirect events.

    Each row represents a single click on a shortened URL.
    This table stores raw event data for later aggregation.
    """

    __tablename__ = "clicks"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    link_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="UUID of the shortened link (references api.links.id)",
    )
    short_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Short code that was accessed (denormalized for queries)",
    )
    clicked_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        comment="Timestamp when the click occurred",
    )
    referrer: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="HTTP Referer header",
    )
    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="HTTP User-Agent header",
    )
    ip_address: Mapped[str | None] = mapped_column(
        INET,
        nullable=True,
        comment="Client IP address",
    )
    country: Mapped[str | None] = mapped_column(
        String(2),
        nullable=True,
        comment="ISO 3166-1 alpha-2 country code (from GeoIP)",
    )
    city: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="City name (from GeoIP)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        comment="When this record was created",
    )

    # Composite index for common queries
    __table_args__ = (
        Index("ix_clicks_link_id_clicked_at", "link_id", "clicked_at"),
        {"schema": "analytics"},
    )

    def __repr__(self) -> str:
        return f"<Click {self.id} link={self.link_id} at={self.clicked_at}>"
