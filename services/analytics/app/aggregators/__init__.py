"""Data aggregation logic for analytics."""

from app.aggregators.stats_aggregator import (
    StatsAggregator,
    get_aggregator,
    start_aggregator,
    stop_aggregator,
)

__all__ = [
    "StatsAggregator",
    "get_aggregator",
    "start_aggregator",
    "stop_aggregator",
]
