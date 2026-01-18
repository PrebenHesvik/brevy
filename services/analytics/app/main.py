"""FastAPI application entry point for Analytics service."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI

from app.aggregators import get_aggregator, start_aggregator, stop_aggregator
from app.api import analytics_router
from app.consumers import get_consumer, start_consumer, stop_consumer
from app.core.config import get_settings
from app.core.database import close_db
from app.core.observability import (
    RequestIDMiddleware,
    RequestLoggingMiddleware,
    setup_observability,
)
from app.services import (
    close_geoip_service,
    get_storage_service,
    start_storage_service,
    stop_storage_service,
    store_click_handler,
)

settings = get_settings()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    logger.info("Starting Brevy Analytics", version=settings.app_version)

    # Start click storage service (batch mode)
    await start_storage_service()
    logger.info("Click storage service started")

    # Register storage handler with consumer
    consumer = get_consumer()
    consumer.register_handler(store_click_handler)

    # Start Redis Pub/Sub consumer
    await start_consumer()
    logger.info("Click event consumer started")

    # Start stats aggregator (background scheduler)
    await start_aggregator()
    logger.info("Stats aggregator started")

    yield

    # Shutdown
    logger.info("Shutting down Brevy Analytics")

    # Stop stats aggregator
    await stop_aggregator()
    logger.info("Stats aggregator stopped")

    # Stop Redis Pub/Sub consumer
    await stop_consumer()
    logger.info("Click event consumer stopped")

    # Stop click storage service (flushes remaining events)
    await stop_storage_service()
    logger.info("Click storage service stopped")

    # Close GeoIP service
    close_geoip_service()

    await close_db()
    logger.info("Database connections closed")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Analytics service for URL click tracking",
    lifespan=lifespan,
)

# Set up observability (logging, tracing, metrics, error tracking)
setup_observability(app)

# Add request middleware (order matters: RequestID first, then logging)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RequestIDMiddleware)

# Include routers
app.include_router(analytics_router)


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    consumer = get_consumer()
    return {
        "status": "healthy" if consumer.is_running else "degraded",
        "service": "analytics",
        "consumer_running": consumer.is_running,
    }


@app.get("/stats")
async def service_stats() -> dict:
    """Get service statistics."""
    consumer = get_consumer()
    storage = get_storage_service()
    aggregator = get_aggregator()
    return {
        "service": "analytics",
        "version": settings.app_version,
        "consumer": consumer.stats,
        "storage": storage.stats,
        "aggregator": aggregator.stats,
    }


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "Welcome to Brevy Analytics", "version": settings.app_version}
