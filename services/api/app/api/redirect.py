"""Redirect endpoint for short links."""

import asyncio
from datetime import datetime
from typing import Annotated
from uuid import UUID

import structlog
from brevy_shared import ClickEvent
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.observability import record_redirect
from app.core.rate_limit import RATE_LIMIT_REDIRECT, limiter
from app.core.redis import cache_link, get_cached_link, publish_click_event
from app.services import link_service

logger = structlog.get_logger()

router = APIRouter(tags=["redirect"])

# Redis Pub/Sub channel for click events
CLICK_EVENTS_CHANNEL = "brevy:clicks"


def get_client_ip(request: Request) -> str | None:
    """Extract client IP address from request.

    Handles X-Forwarded-For header for requests behind proxies/load balancers.
    """
    # Check X-Forwarded-For header first (set by proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs: client, proxy1, proxy2
        # The first one is the original client
        return forwarded_for.split(",")[0].strip()

    # Check X-Real-IP header (common in nginx setups)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct client IP
    if request.client:
        return request.client.host

    return None


async def publish_click_event_async(
    link_id: UUID,
    short_code: str,
    request: Request,
) -> None:
    """Publish a click event to Redis Pub/Sub (fire-and-forget)."""
    try:
        event = ClickEvent(
            link_id=link_id,
            short_code=short_code,
            referrer=request.headers.get("Referer"),
            user_agent=request.headers.get("User-Agent"),
            ip_address=get_client_ip(request),
        )
        await publish_click_event(CLICK_EVENTS_CHANNEL, event.model_dump(mode="json"))
        logger.debug(
            "Click event published",
            link_id=str(link_id),
            short_code=short_code,
        )
    except Exception as e:
        # Log but don't fail the redirect if event publishing fails
        logger.warning(
            "Failed to publish click event",
            link_id=str(link_id),
            short_code=short_code,
            error=str(e),
        )


@router.get("/{short_code}")
@limiter.limit(RATE_LIMIT_REDIRECT)
async def redirect_to_original(
    request: Request,
    short_code: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> RedirectResponse:
    """Redirect a short code to its original URL.

    Flow:
    1. Check Redis cache for the link
    2. If cache miss, query database
    3. If found in DB, cache the result
    4. Handle expired/inactive links appropriately
    5. Redirect to original URL
    """
    # Try cache first
    cached = await get_cached_link(short_code)

    if cached:
        # Check if cached link is inactive
        if not cached.get("is_active", True):
            logger.info("Redirect blocked - link inactive (cached)", short_code=short_code)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Link not found",
            )

        # Check if cached link is expired
        expires_at = cached.get("expires_at")
        if expires_at:
            expires_dt = datetime.fromisoformat(expires_at)
            if datetime.utcnow() > expires_dt:
                logger.info("Redirect blocked - link expired (cached)", short_code=short_code)
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail="Link has expired",
                )

        original_url = cached["original_url"]
        link_id = UUID(cached["link_id"])

        logger.info(
            "Redirect from cache",
            short_code=short_code,
            link_id=str(link_id),
        )

        # Publish click event (non-blocking, fire-and-forget)
        asyncio.create_task(publish_click_event_async(link_id, short_code, request))

        # Increment click count in background (non-blocking)
        await link_service.increment_click_count(session, link_id)
        await session.commit()

        # Record metric
        record_redirect(307)

        return RedirectResponse(
            url=original_url,
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    # Cache miss - query database
    link = await link_service.get_link_by_short_code(session, short_code)

    if not link:
        logger.info("Redirect failed - link not found", short_code=short_code)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found",
        )

    # Check if link is inactive (soft deleted)
    if not link.is_active:
        logger.info("Redirect blocked - link inactive", short_code=short_code)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found",
        )

    # Check if link is expired
    if link.is_expired:
        logger.info("Redirect blocked - link expired", short_code=short_code)
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Link has expired",
        )

    # Cache the link for future requests
    await cache_link(
        short_code=short_code,
        link_data={
            "link_id": str(link.id),
            "original_url": link.original_url,
            "is_active": link.is_active,
            "expires_at": link.expires_at.isoformat() if link.expires_at else None,
        },
    )

    logger.info(
        "Redirect from database",
        short_code=short_code,
        link_id=str(link.id),
    )

    # Publish click event (non-blocking, fire-and-forget)
    asyncio.create_task(publish_click_event_async(link.id, short_code, request))

    # Increment click count
    await link_service.increment_click_count(session, link.id)
    await session.commit()

    # Record metric
    record_redirect(307)

    return RedirectResponse(
        url=link.original_url,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
