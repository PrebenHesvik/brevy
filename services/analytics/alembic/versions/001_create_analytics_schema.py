"""Create analytics schema.

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
    """Create the analytics schema."""
    op.execute("CREATE SCHEMA IF NOT EXISTS analytics")


def downgrade() -> None:
    """Drop the analytics schema."""
    # WARNING: This will delete all data in the analytics schema!
    op.execute("DROP SCHEMA IF EXISTS analytics CASCADE")
