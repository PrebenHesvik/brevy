"""Create clicks table.

Revision ID: 002
Revises: 001
Create Date: 2024-01-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import INET, UUID

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the clicks table."""
    op.create_table(
        "clicks",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "link_id",
            UUID(as_uuid=True),
            nullable=False,
            comment="UUID of the shortened link (references api.links.id)",
        ),
        sa.Column(
            "short_code",
            sa.String(20),
            nullable=False,
            comment="Short code that was accessed (denormalized for queries)",
        ),
        sa.Column(
            "clicked_at",
            sa.DateTime(),
            nullable=False,
            comment="Timestamp when the click occurred",
        ),
        sa.Column(
            "referrer",
            sa.Text(),
            nullable=True,
            comment="HTTP Referer header",
        ),
        sa.Column(
            "user_agent",
            sa.Text(),
            nullable=True,
            comment="HTTP User-Agent header",
        ),
        sa.Column(
            "ip_address",
            INET(),
            nullable=True,
            comment="Client IP address",
        ),
        sa.Column(
            "country",
            sa.String(2),
            nullable=True,
            comment="ISO 3166-1 alpha-2 country code (from GeoIP)",
        ),
        sa.Column(
            "city",
            sa.String(255),
            nullable=True,
            comment="City name (from GeoIP)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When this record was created",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clicks")),
        schema="analytics",
    )

    # Create indexes
    op.create_index(
        op.f("ix_clicks_link_id"),
        "clicks",
        ["link_id"],
        schema="analytics",
    )
    op.create_index(
        op.f("ix_clicks_clicked_at"),
        "clicks",
        ["clicked_at"],
        schema="analytics",
    )
    op.create_index(
        "ix_clicks_link_id_clicked_at",
        "clicks",
        ["link_id", "clicked_at"],
        schema="analytics",
    )


def downgrade() -> None:
    """Drop the clicks table."""
    op.drop_index(
        "ix_clicks_link_id_clicked_at",
        table_name="clicks",
        schema="analytics",
    )
    op.drop_index(
        op.f("ix_clicks_clicked_at"),
        table_name="clicks",
        schema="analytics",
    )
    op.drop_index(
        op.f("ix_clicks_link_id"),
        table_name="clicks",
        schema="analytics",
    )
    op.drop_table("clicks", schema="analytics")
