"""Create api schema.

Revision ID: 001
Revises:
Create Date: 2024-01-18

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the api schema."""
    op.execute("CREATE SCHEMA IF NOT EXISTS api")


def downgrade() -> None:
    """Drop the api schema."""
    op.execute("DROP SCHEMA IF EXISTS api CASCADE")
