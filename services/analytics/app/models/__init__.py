"""Analytics SQLAlchemy models."""

from app.core.database import Base
from app.models.click import Click
from app.models.stats import LinkStatsDaily, LinkStatsHourly

__all__ = ["Base", "Click", "LinkStatsHourly", "LinkStatsDaily"]
