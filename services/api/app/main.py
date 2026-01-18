"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from app.api.redirect import router as redirect_router
from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.database import close_db
from app.core.middleware import SecurityHeadersMiddleware
from app.core.observability import (
    RequestIDMiddleware,
    RequestLoggingMiddleware,
    setup_observability,
)
from app.core.rate_limit import limiter
from app.core.redis import close_redis

settings = get_settings()

# Get logger (will be configured by setup_observability)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    logger.info("Starting Brevy API", version=settings.app_version)
    yield
    # Shutdown
    logger.info("Shutting down Brevy API")
    await close_redis()
    logger.info("Redis connection closed")
    await close_db()
    logger.info("Database connections closed")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="URL Shortener with Analytics",
    lifespan=lifespan,
)

# Set up observability (logging, tracing, metrics, Sentry)
setup_observability(app)

# Rate limiter state and exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Middleware stack (order matters - first added = outermost = runs last on request, first on response)

# Request logging middleware (logs all requests with timing)
app.add_middleware(RequestLoggingMiddleware)

# Request ID middleware (adds unique ID to each request)
app.add_middleware(RequestIDMiddleware)

# Security headers middleware
app.add_middleware(
    SecurityHeadersMiddleware,
    enable_hsts=not settings.debug,  # Enable HSTS in production
)

# Session middleware (required for OAuth state storage)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="brevy_session",
    max_age=3600,  # 1 hour for OAuth flow
    same_site="lax",
    https_only=not settings.debug,  # Enable secure cookies in production
)

# CORS middleware (innermost - runs first on request)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset", "X-Request-ID"],
)

# Include routers
app.include_router(v1_router)

# Redirect router - must be after v1_router so /api/v1/* routes take precedence
# The redirect endpoint handles /{short_code} for URL redirects
app.include_router(redirect_router)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "Welcome to Brevy API", "version": settings.app_version}
