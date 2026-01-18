"""SQLAlchemy models.

All models should be imported here for Alembic to detect them.
"""

from app.core.database import Base
from app.models.user import User
from app.models.link import Link

__all__ = ["Base", "User", "Link"]
