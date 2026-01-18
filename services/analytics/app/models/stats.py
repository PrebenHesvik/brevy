"""Aggregated statistics SQLAlchemy models."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LinkStatsHourly(Base):
    """Hourly aggregated statistics for links.

    Primary key is (link_id, hour) to allow efficient upserts
    and range queries by time.
    """

    __tablename__ = "link_stats_hourly"

    link_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        comment="UUID of the link",
    )
    hour: Mapped[datetime] = mapped_column(
        DateTime,
        primary_key=True,
        comment="Hour bucket (truncated to hour)",
    )
    click_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Total clicks in this hour",
    )
    unique_visitors: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Approximate unique visitors (distinct IPs)",
    )

    __table_args__ = ({"schema": "analytics"},)

    def __repr__(self) -> str:
        return f"<LinkStatsHourly {self.link_id} hour={self.hour} clicks={self.click_count}>"


class LinkStatsDaily(Base):
    """Daily aggregated statistics for links.

    Includes additional aggregations like top referrers and countries.
    """

    __tablename__ = "link_stats_daily"

    link_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        comment="UUID of the link",
    )
    date: Mapped[date] = mapped_column(
        Date,
        primary_key=True,
        comment="Date of the stats",
    )
    click_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Total clicks on this date",
    )
    unique_visitors: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Approximate unique visitors (distinct IPs)",
    )
    top_referrers: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Top referrers with counts: [{referrer: str, count: int}, ...]",
    )
    top_countries: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Top countries with counts: [{country: str, count: int}, ...]",
    )

    __table_args__ = ({"schema": "analytics"},)

    def __repr__(self) -> str:
        return f"<LinkStatsDaily {self.link_id} date={self.date} clicks={self.click_count}>"
