"""Create stats tables.

Revision ID: 003
Revises: 002
Create Date: 2024-01-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the hourly and daily stats tables."""
    # Create link_stats_hourly table
    op.create_table(
        "link_stats_hourly",
        sa.Column(
            "link_id",
            UUID(as_uuid=True),
            nullable=False,
            comment="UUID of the link",
        ),
        sa.Column(
            "hour",
            sa.DateTime(),
            nullable=False,
            comment="Hour bucket (truncated to hour)",
        ),
        sa.Column(
            "click_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Total clicks in this hour",
        ),
        sa.Column(
            "unique_visitors",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Approximate unique visitors (distinct IPs)",
        ),
        sa.PrimaryKeyConstraint("link_id", "hour", name=op.f("pk_link_stats_hourly")),
        schema="analytics",
    )

    # Create link_stats_daily table
    op.create_table(
        "link_stats_daily",
        sa.Column(
            "link_id",
            UUID(as_uuid=True),
            nullable=False,
            comment="UUID of the link",
        ),
        sa.Column(
            "date",
            sa.Date(),
            nullable=False,
            comment="Date of the stats",
        ),
        sa.Column(
            "click_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Total clicks on this date",
        ),
        sa.Column(
            "unique_visitors",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Approximate unique visitors (distinct IPs)",
        ),
        sa.Column(
            "top_referrers",
            JSONB(),
            nullable=True,
            comment="Top referrers with counts: [{referrer: str, count: int}, ...]",
        ),
        sa.Column(
            "top_countries",
            JSONB(),
            nullable=True,
            comment="Top countries with counts: [{country: str, count: int}, ...]",
        ),
        sa.PrimaryKeyConstraint("link_id", "date", name=op.f("pk_link_stats_daily")),
        schema="analytics",
    )

    # Create indexes for efficient time-range queries
    op.create_index(
        "ix_link_stats_hourly_hour",
        "link_stats_hourly",
        ["hour"],
        schema="analytics",
    )
    op.create_index(
        "ix_link_stats_daily_date",
        "link_stats_daily",
        ["date"],
        schema="analytics",
    )


def downgrade() -> None:
    """Drop the stats tables."""
    op.drop_index(
        "ix_link_stats_daily_date",
        table_name="link_stats_daily",
        schema="analytics",
    )
    op.drop_index(
        "ix_link_stats_hourly_hour",
        table_name="link_stats_hourly",
        schema="analytics",
    )
    op.drop_table("link_stats_daily", schema="analytics")
    op.drop_table("link_stats_hourly", schema="analytics")
