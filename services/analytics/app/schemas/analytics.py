"""Pydantic schemas for analytics API responses."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AnalyticsSummary(BaseModel):
    """Summary statistics for a link."""

    link_id: UUID
    total_clicks: int = Field(description="Total number of clicks")
    unique_visitors: int = Field(description="Approximate unique visitors (by IP)")
    clicks_today: int = Field(default=0, description="Clicks today")
    clicks_this_week: int = Field(default=0, description="Clicks in the last 7 days")
    clicks_this_month: int = Field(default=0, description="Clicks in the last 30 days")


class TimeseriesPoint(BaseModel):
    """A single point in a timeseries."""

    timestamp: datetime | date
    clicks: int
    unique_visitors: int


class TimeseriesResponse(BaseModel):
    """Timeseries data for clicks over time."""

    link_id: UUID
    granularity: str = Field(description="Time granularity: 'hourly' or 'daily'")
    start_date: date
    end_date: date
    data: list[TimeseriesPoint]


class ReferrerStats(BaseModel):
    """Statistics for a single referrer."""

    referrer: str
    clicks: int
    percentage: float = Field(description="Percentage of total clicks")


class ReferrersResponse(BaseModel):
    """Top referrers for a link."""

    link_id: UUID
    start_date: date
    end_date: date
    total_clicks: int
    referrers: list[ReferrerStats]


class CountryStats(BaseModel):
    """Statistics for a single country."""

    country: str = Field(description="ISO 3166-1 alpha-2 country code")
    clicks: int
    percentage: float = Field(description="Percentage of total clicks")


class CountriesResponse(BaseModel):
    """Geographic distribution of clicks."""

    link_id: UUID
    start_date: date
    end_date: date
    total_clicks: int
    countries: list[CountryStats]
