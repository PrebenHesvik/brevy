"""Statistics aggregation service for hourly and daily stats."""

import asyncio
import time
from datetime import datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.observability import record_aggregation
from app.models.click import Click
from app.models.stats import LinkStatsDaily, LinkStatsHourly

logger = structlog.get_logger()


class StatsAggregator:
    """Service for aggregating click statistics.

    Performs hourly and daily aggregations of raw click data into
    summary statistics tables for efficient querying.

    Usage:
        aggregator = StatsAggregator()
        await aggregator.start()  # Starts background scheduler
        # ... later ...
        await aggregator.stop()

        # Or run manually:
        await aggregator.aggregate_hourly()
        await aggregator.aggregate_daily()
    """

    def __init__(
        self,
        hourly_interval: float = 300.0,  # 5 minutes
        daily_interval: float = 3600.0,  # 1 hour
        top_n: int = 10,  # Number of top referrers/countries to keep
    ):
        """Initialize the aggregator.

        Args:
            hourly_interval: Seconds between hourly aggregation runs.
            daily_interval: Seconds between daily aggregation runs.
            top_n: Number of top items to keep in daily aggregations.
        """
        self._hourly_interval = hourly_interval
        self._daily_interval = daily_interval
        self._top_n = top_n
        self._running = False
        self._hourly_task: asyncio.Task | None = None
        self._daily_task: asyncio.Task | None = None
        self._hourly_runs = 0
        self._daily_runs = 0

    async def start(self) -> None:
        """Start the background aggregation scheduler."""
        if self._running:
            return

        self._running = True
        self._hourly_task = asyncio.create_task(self._hourly_loop())
        self._daily_task = asyncio.create_task(self._daily_loop())

        logger.info(
            "Stats aggregator started",
            hourly_interval=self._hourly_interval,
            daily_interval=self._daily_interval,
        )

    async def stop(self) -> None:
        """Stop the background aggregation scheduler."""
        if not self._running:
            return

        self._running = False

        for task in [self._hourly_task, self._daily_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._hourly_task = None
        self._daily_task = None

        logger.info(
            "Stats aggregator stopped",
            hourly_runs=self._hourly_runs,
            daily_runs=self._daily_runs,
        )

    async def _hourly_loop(self) -> None:
        """Background loop for hourly aggregation."""
        try:
            while self._running:
                await asyncio.sleep(self._hourly_interval)
                try:
                    await self.aggregate_hourly()
                    self._hourly_runs += 1
                except Exception as e:
                    logger.error("Hourly aggregation failed", error=str(e))
        except asyncio.CancelledError:
            pass

    async def _daily_loop(self) -> None:
        """Background loop for daily aggregation."""
        try:
            while self._running:
                await asyncio.sleep(self._daily_interval)
                try:
                    await self.aggregate_daily()
                    self._daily_runs += 1
                except Exception as e:
                    logger.error("Daily aggregation failed", error=str(e))
        except asyncio.CancelledError:
            pass

    async def aggregate_hourly(self, hours_back: int = 2) -> int:
        """Aggregate clicks into hourly statistics.

        Args:
            hours_back: Number of hours back to aggregate (for catching up).

        Returns:
            Number of rows upserted.
        """
        start_time_metric = time.perf_counter()

        async with async_session_factory() as session:
            # Calculate time range
            now = datetime.utcnow()
            start_time = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=hours_back)

            logger.debug("Running hourly aggregation", start_time=start_time.isoformat())

            # Aggregate clicks by link_id and hour
            query = (
                select(
                    Click.link_id,
                    func.date_trunc("hour", Click.clicked_at).label("hour"),
                    func.count().label("click_count"),
                    func.count(func.distinct(Click.ip_address)).label("unique_visitors"),
                )
                .where(Click.clicked_at >= start_time)
                .group_by(Click.link_id, func.date_trunc("hour", Click.clicked_at))
            )

            result = await session.execute(query)
            rows = result.all()

            if not rows:
                logger.debug("No clicks to aggregate for hourly stats")
                duration = time.perf_counter() - start_time_metric
                record_aggregation("hourly", duration, 0)
                return 0

            # Upsert aggregated data
            for row in rows:
                stmt = insert(LinkStatsHourly).values(
                    link_id=row.link_id,
                    hour=row.hour,
                    click_count=row.click_count,
                    unique_visitors=row.unique_visitors,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["link_id", "hour"],
                    set_={
                        "click_count": stmt.excluded.click_count,
                        "unique_visitors": stmt.excluded.unique_visitors,
                    },
                )
                await session.execute(stmt)

            await session.commit()

            duration = time.perf_counter() - start_time_metric
            record_aggregation("hourly", duration, len(rows))

            logger.info(
                "Hourly aggregation complete",
                rows_upserted=len(rows),
                hours_back=hours_back,
                duration_ms=round(duration * 1000, 2),
            )
            return len(rows)

    async def aggregate_daily(self, days_back: int = 2) -> int:
        """Aggregate clicks into daily statistics with top referrers/countries.

        Args:
            days_back: Number of days back to aggregate (for catching up).

        Returns:
            Number of rows upserted.
        """
        start_time_metric = time.perf_counter()

        async with async_session_factory() as session:
            # Calculate time range
            today = datetime.utcnow().date()
            start_date = today - timedelta(days=days_back)

            logger.debug("Running daily aggregation", start_date=start_date.isoformat())

            # Get distinct link_ids with clicks in the date range
            links_query = (
                select(func.distinct(Click.link_id))
                .where(func.date(Click.clicked_at) >= start_date)
            )
            links_result = await session.execute(links_query)
            link_ids = [row[0] for row in links_result.all()]

            if not link_ids:
                logger.debug("No clicks to aggregate for daily stats")
                duration = time.perf_counter() - start_time_metric
                record_aggregation("daily", duration, 0)
                return 0

            rows_upserted = 0

            for link_id in link_ids:
                # Aggregate for each day
                for day_offset in range(days_back + 1):
                    target_date = start_date + timedelta(days=day_offset)
                    await self._aggregate_daily_for_link(session, link_id, target_date)
                    rows_upserted += 1

            await session.commit()

            duration = time.perf_counter() - start_time_metric
            record_aggregation("daily", duration, rows_upserted)

            logger.info(
                "Daily aggregation complete",
                rows_upserted=rows_upserted,
                days_back=days_back,
                duration_ms=round(duration * 1000, 2),
            )
            return rows_upserted

    async def _aggregate_daily_for_link(
        self,
        session: AsyncSession,
        link_id: UUID,
        target_date: datetime,
    ) -> None:
        """Aggregate daily stats for a single link and date."""
        # Base stats query
        stats_query = (
            select(
                func.count().label("click_count"),
                func.count(func.distinct(Click.ip_address)).label("unique_visitors"),
            )
            .where(Click.link_id == link_id)
            .where(func.date(Click.clicked_at) == target_date)
        )
        stats_result = await session.execute(stats_query)
        stats = stats_result.one_or_none()

        if not stats or stats.click_count == 0:
            return

        # Top referrers
        referrers_query = (
            select(Click.referrer, func.count().label("count"))
            .where(Click.link_id == link_id)
            .where(func.date(Click.clicked_at) == target_date)
            .where(Click.referrer.isnot(None))
            .where(Click.referrer != "")
            .group_by(Click.referrer)
            .order_by(func.count().desc())
            .limit(self._top_n)
        )
        referrers_result = await session.execute(referrers_query)
        top_referrers = [
            {"referrer": row.referrer, "count": row.count}
            for row in referrers_result.all()
        ]

        # Top countries
        countries_query = (
            select(Click.country, func.count().label("count"))
            .where(Click.link_id == link_id)
            .where(func.date(Click.clicked_at) == target_date)
            .where(Click.country.isnot(None))
            .group_by(Click.country)
            .order_by(func.count().desc())
            .limit(self._top_n)
        )
        countries_result = await session.execute(countries_query)
        top_countries = [
            {"country": row.country, "count": row.count}
            for row in countries_result.all()
        ]

        # Upsert daily stats
        stmt = insert(LinkStatsDaily).values(
            link_id=link_id,
            date=target_date,
            click_count=stats.click_count,
            unique_visitors=stats.unique_visitors,
            top_referrers=top_referrers if top_referrers else None,
            top_countries=top_countries if top_countries else None,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["link_id", "date"],
            set_={
                "click_count": stmt.excluded.click_count,
                "unique_visitors": stmt.excluded.unique_visitors,
                "top_referrers": stmt.excluded.top_referrers,
                "top_countries": stmt.excluded.top_countries,
            },
        )
        await session.execute(stmt)

    @property
    def stats(self) -> dict:
        """Get aggregator statistics."""
        return {
            "running": self._running,
            "hourly_runs": self._hourly_runs,
            "daily_runs": self._daily_runs,
        }


# Global aggregator instance
_aggregator: StatsAggregator | None = None


def get_aggregator() -> StatsAggregator:
    """Get the global aggregator instance."""
    global _aggregator
    if _aggregator is None:
        _aggregator = StatsAggregator()
    return _aggregator


async def start_aggregator() -> None:
    """Start the global aggregator."""
    aggregator = get_aggregator()
    await aggregator.start()


async def stop_aggregator() -> None:
    """Stop the global aggregator."""
    aggregator = get_aggregator()
    await aggregator.stop()
