"""Create users table.

Revision ID: 002
Revises: 001
Create Date: 2024-01-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the users table."""
    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column(
            "provider",
            sa.String(50),
            nullable=False,
            comment="OAuth provider: 'github' or 'google'",
        ),
        sa.Column(
            "provider_id",
            sa.String(255),
            nullable=False,
            comment="User ID from the OAuth provider",
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        schema="api",
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], schema="api")


def downgrade() -> None:
    """Drop the users table."""
    op.drop_index(op.f("ix_users_email"), table_name="users", schema="api")
    op.drop_table("users", schema="api")
