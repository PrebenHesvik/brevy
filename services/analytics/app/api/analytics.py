"""Analytics API endpoints."""

from datetime import date, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.models.click import Click
from app.models.stats import LinkStatsDaily, LinkStatsHourly
from app.schemas import (
    AnalyticsSummary,
    CountriesResponse,
    CountryStats,
    ReferrersResponse,
    ReferrerStats,
    TimeseriesPoint,
    TimeseriesResponse,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/analytics", tags=["analytics"])


def get_default_date_range() -> tuple[date, date]:
    """Get default date range (last 30 days)."""
    today = date.today()
    start = today - timedelta(days=30)
    return start, today


@router.get("/{link_id}/summary", response_model=AnalyticsSummary)
async def get_link_summary(
    link_id: UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> AnalyticsSummary:
    """Get summary statistics for a link.

    Returns total clicks, unique visitors, and recent activity.
    """
    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Total clicks and unique visitors (all time from daily stats)
    total_query = select(
        func.coalesce(func.sum(LinkStatsDaily.click_count), 0).label("total_clicks"),
        func.coalesce(func.sum(LinkStatsDaily.unique_visitors), 0).label("unique_visitors"),
    ).where(LinkStatsDaily.link_id == link_id)

    total_result = await session.execute(total_query)
    total_row = total_result.one()

    # If no aggregated data, fall back to raw clicks
    if total_row.total_clicks == 0:
        raw_query = select(
            func.count().label("total_clicks"),
            func.count(func.distinct(Click.ip_address)).label("unique_visitors"),
        ).where(Click.link_id == link_id)

        raw_result = await session.execute(raw_query)
        raw_row = raw_result.one()
        total_clicks = raw_row.total_clicks
        unique_visitors = raw_row.unique_visitors
    else:
        total_clicks = total_row.total_clicks
        unique_visitors = total_row.unique_visitors

    # Clicks today
    today_query = select(
        func.coalesce(func.sum(LinkStatsDaily.click_count), 0)
    ).where(
        LinkStatsDaily.link_id == link_id,
        LinkStatsDaily.date == today,
    )
    today_result = await session.execute(today_query)
    clicks_today = today_result.scalar() or 0

    # If no daily stats for today, check raw clicks
    if clicks_today == 0:
        raw_today_query = select(func.count()).where(
            Click.link_id == link_id,
            func.date(Click.clicked_at) == today,
        )
        raw_today_result = await session.execute(raw_today_query)
        clicks_today = raw_today_result.scalar() or 0

    # Clicks this week
    week_query = select(
        func.coalesce(func.sum(LinkStatsDaily.click_count), 0)
    ).where(
        LinkStatsDaily.link_id == link_id,
        LinkStatsDaily.date >= week_ago,
    )
    week_result = await session.execute(week_query)
    clicks_this_week = week_result.scalar() or 0

    # Clicks this month
    month_query = select(
        func.coalesce(func.sum(LinkStatsDaily.click_count), 0)
    ).where(
        LinkStatsDaily.link_id == link_id,
        LinkStatsDaily.date >= month_ago,
    )
    month_result = await session.execute(month_query)
    clicks_this_month = month_result.scalar() or 0

    logger.debug(
        "Summary fetched",
        link_id=str(link_id),
        total_clicks=total_clicks,
    )

    return AnalyticsSummary(
        link_id=link_id,
        total_clicks=total_clicks,
        unique_visitors=unique_visitors,
        clicks_today=clicks_today,
        clicks_this_week=clicks_this_week,
        clicks_this_month=clicks_this_month,
    )


@router.get("/{link_id}/timeseries", response_model=TimeseriesResponse)
async def get_link_timeseries(
    link_id: UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    start_date: Annotated[date | None, Query(description="Start date (default: 30 days ago)")] = None,
    end_date: Annotated[date | None, Query(description="End date (default: today)")] = None,
    granularity: Annotated[
        Literal["hourly", "daily"],
        Query(description="Time granularity")
    ] = "daily",
) -> TimeseriesResponse:
    """Get timeseries data for clicks over time.

    Returns click counts and unique visitors at hourly or daily granularity.
    """
    # Set default date range
    if start_date is None or end_date is None:
        default_start, default_end = get_default_date_range()
        start_date = start_date or default_start
        end_date = end_date or default_end

    # Validate date range
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date",
        )

    data: list[TimeseriesPoint] = []

    if granularity == "hourly":
        # Query hourly stats
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        query = (
            select(
                LinkStatsHourly.hour,
                LinkStatsHourly.click_count,
                LinkStatsHourly.unique_visitors,
            )
            .where(LinkStatsHourly.link_id == link_id)
            .where(LinkStatsHourly.hour >= start_dt)
            .where(LinkStatsHourly.hour <= end_dt)
            .order_by(LinkStatsHourly.hour)
        )

        result = await session.execute(query)
        for row in result.all():
            data.append(TimeseriesPoint(
                timestamp=row.hour,
                clicks=row.click_count,
                unique_visitors=row.unique_visitors,
            ))
    else:
        # Query daily stats
        query = (
            select(
                LinkStatsDaily.date,
                LinkStatsDaily.click_count,
                LinkStatsDaily.unique_visitors,
            )
            .where(LinkStatsDaily.link_id == link_id)
            .where(LinkStatsDaily.date >= start_date)
            .where(LinkStatsDaily.date <= end_date)
            .order_by(LinkStatsDaily.date)
        )

        result = await session.execute(query)
        for row in result.all():
            data.append(TimeseriesPoint(
                timestamp=row.date,
                clicks=row.click_count,
                unique_visitors=row.unique_visitors,
            ))

    logger.debug(
        "Timeseries fetched",
        link_id=str(link_id),
        granularity=granularity,
        points=len(data),
    )

    return TimeseriesResponse(
        link_id=link_id,
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
        data=data,
    )


@router.get("/{link_id}/referrers", response_model=ReferrersResponse)
async def get_link_referrers(
    link_id: UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    start_date: Annotated[date | None, Query(description="Start date (default: 30 days ago)")] = None,
    end_date: Annotated[date | None, Query(description="End date (default: today)")] = None,
    limit: Annotated[int, Query(ge=1, le=50, description="Max referrers to return")] = 10,
) -> ReferrersResponse:
    """Get top referrers for a link.

    Returns the most common referrers with click counts and percentages.
    """
    # Set default date range
    if start_date is None or end_date is None:
        default_start, default_end = get_default_date_range()
        start_date = start_date or default_start
        end_date = end_date or default_end

    # Try to get from aggregated daily stats first
    # Aggregate top_referrers JSONB from daily stats
    daily_query = (
        select(LinkStatsDaily.top_referrers, LinkStatsDaily.click_count)
        .where(LinkStatsDaily.link_id == link_id)
        .where(LinkStatsDaily.date >= start_date)
        .where(LinkStatsDaily.date <= end_date)
        .where(LinkStatsDaily.top_referrers.isnot(None))
    )

    daily_result = await session.execute(daily_query)
    daily_rows = daily_result.all()

    # Aggregate referrers across days
    referrer_totals: dict[str, int] = {}
    total_clicks = 0

    for row in daily_rows:
        total_clicks += row.click_count
        if row.top_referrers:
            for item in row.top_referrers:
                ref = item.get("referrer", "")
                count = item.get("count", 0)
                referrer_totals[ref] = referrer_totals.get(ref, 0) + count

    # If no aggregated data, fall back to raw clicks
    if not referrer_totals:
        raw_query = (
            select(Click.referrer, func.count().label("count"))
            .where(Click.link_id == link_id)
            .where(func.date(Click.clicked_at) >= start_date)
            .where(func.date(Click.clicked_at) <= end_date)
            .where(Click.referrer.isnot(None))
            .where(Click.referrer != "")
            .group_by(Click.referrer)
            .order_by(func.count().desc())
            .limit(limit)
        )

        raw_result = await session.execute(raw_query)
        for row in raw_result.all():
            referrer_totals[row.referrer] = row.count

        # Get total clicks for percentage calculation
        total_query = (
            select(func.count())
            .where(Click.link_id == link_id)
            .where(func.date(Click.clicked_at) >= start_date)
            .where(func.date(Click.clicked_at) <= end_date)
        )
        total_result = await session.execute(total_query)
        total_clicks = total_result.scalar() or 0

    # Sort and limit
    sorted_referrers = sorted(
        referrer_totals.items(),
        key=lambda x: x[1],
        reverse=True,
    )[:limit]

    # Calculate percentages
    referrers = []
    for referrer, clicks in sorted_referrers:
        percentage = (clicks / total_clicks * 100) if total_clicks > 0 else 0
        referrers.append(ReferrerStats(
            referrer=referrer,
            clicks=clicks,
            percentage=round(percentage, 2),
        ))

    logger.debug(
        "Referrers fetched",
        link_id=str(link_id),
        count=len(referrers),
    )

    return ReferrersResponse(
        link_id=link_id,
        start_date=start_date,
        end_date=end_date,
        total_clicks=total_clicks,
        referrers=referrers,
    )


@router.get("/{link_id}/countries", response_model=CountriesResponse)
async def get_link_countries(
    link_id: UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    start_date: Annotated[date | None, Query(description="Start date (default: 30 days ago)")] = None,
    end_date: Annotated[date | None, Query(description="End date (default: today)")] = None,
    limit: Annotated[int, Query(ge=1, le=50, description="Max countries to return")] = 10,
) -> CountriesResponse:
    """Get geographic distribution of clicks.

    Returns top countries with click counts and percentages.
    """
    # Set default date range
    if start_date is None or end_date is None:
        default_start, default_end = get_default_date_range()
        start_date = start_date or default_start
        end_date = end_date or default_end

    # Try to get from aggregated daily stats first
    daily_query = (
        select(LinkStatsDaily.top_countries, LinkStatsDaily.click_count)
        .where(LinkStatsDaily.link_id == link_id)
        .where(LinkStatsDaily.date >= start_date)
        .where(LinkStatsDaily.date <= end_date)
        .where(LinkStatsDaily.top_countries.isnot(None))
    )

    daily_result = await session.execute(daily_query)
    daily_rows = daily_result.all()

    # Aggregate countries across days
    country_totals: dict[str, int] = {}
    total_clicks = 0

    for row in daily_rows:
        total_clicks += row.click_count
        if row.top_countries:
            for item in row.top_countries:
                country = item.get("country", "")
                count = item.get("count", 0)
                country_totals[country] = country_totals.get(country, 0) + count

    # If no aggregated data, fall back to raw clicks
    if not country_totals:
        raw_query = (
            select(Click.country, func.count().label("count"))
            .where(Click.link_id == link_id)
            .where(func.date(Click.clicked_at) >= start_date)
            .where(func.date(Click.clicked_at) <= end_date)
            .where(Click.country.isnot(None))
            .group_by(Click.country)
            .order_by(func.count().desc())
            .limit(limit)
        )

        raw_result = await session.execute(raw_query)
        for row in raw_result.all():
            country_totals[row.country] = row.count

        # Get total clicks for percentage calculation
        total_query = (
            select(func.count())
            .where(Click.link_id == link_id)
            .where(func.date(Click.clicked_at) >= start_date)
            .where(func.date(Click.clicked_at) <= end_date)
        )
        total_result = await session.execute(total_query)
        total_clicks = total_result.scalar() or 0

    # Sort and limit
    sorted_countries = sorted(
        country_totals.items(),
        key=lambda x: x[1],
        reverse=True,
    )[:limit]

    # Calculate percentages
    countries = []
    for country, clicks in sorted_countries:
        percentage = (clicks / total_clicks * 100) if total_clicks > 0 else 0
        countries.append(CountryStats(
            country=country,
            clicks=clicks,
            percentage=round(percentage, 2),
        ))

    logger.debug(
        "Countries fetched",
        link_id=str(link_id),
        count=len(countries),
    )

    return CountriesResponse(
        link_id=link_id,
        start_date=start_date,
        end_date=end_date,
        total_clicks=total_clicks,
        countries=countries,
    )
