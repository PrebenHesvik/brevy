"""Create links table.

Revision ID: 003
Revises: 002
Create Date: 2024-01-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the links table."""
    op.create_table(
        "links",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "short_code",
            sa.String(20),
            nullable=False,
            comment="Short code for the URL (e.g., 'abc123' or 'my-custom-slug')",
        ),
        sa.Column(
            "original_url",
            sa.Text(),
            nullable=False,
            comment="The original URL to redirect to",
        ),
        sa.Column(
            "title",
            sa.String(255),
            nullable=True,
            comment="Optional title for the link",
        ),
        sa.Column(
            "is_custom",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether the short code was custom (user-provided)",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Whether the link is active (soft delete)",
        ),
        sa.Column(
            "click_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Total click count (denormalized for quick access)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(),
            nullable=True,
            comment="Optional expiration timestamp",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_links")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["api.users.id"],
            name=op.f("fk_links_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("short_code", name=op.f("uq_links_short_code")),
        schema="api",
    )
    op.create_index(
        op.f("ix_links_short_code"),
        "links",
        ["short_code"],
        schema="api",
    )
    op.create_index(
        op.f("ix_links_user_id"),
        "links",
        ["user_id"],
        schema="api",
    )


def downgrade() -> None:
    """Drop the links table."""
    op.drop_index(op.f("ix_links_user_id"), table_name="links", schema="api")
    op.drop_index(op.f("ix_links_short_code"), table_name="links", schema="api")
    op.drop_table("links", schema="api")
