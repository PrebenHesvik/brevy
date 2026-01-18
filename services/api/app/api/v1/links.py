"""Link CRUD endpoints."""

import math
from typing import Annotated
from uuid import UUID

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_async_session
from app.core.deps import CurrentUser
from app.core.observability import record_link_operation
from app.core.rate_limit import RATE_LIMIT_API, RATE_LIMIT_CREATE_LINK, limiter
from app.schemas.link import LinkCreate, LinkListResponse, LinkResponse, LinkUpdate
from app.services import link_service

settings = get_settings()
logger = structlog.get_logger()

router = APIRouter(prefix="/links", tags=["links"])


@router.post("", response_model=LinkResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_LIMIT_CREATE_LINK)
async def create_link(
    request: Request,
    link_data: LinkCreate,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> LinkResponse:
    """Create a new shortened link.

    If `custom_code` is provided, it will be used as the short code.
    Otherwise, a random short code will be generated.
    """
    try:
        link = await link_service.create_link(
            session=session,
            user_id=user.id,
            link_data=link_data,
        )
        await session.commit()
        logger.info(
            "Link created",
            link_id=str(link.id),
            short_code=link.short_code,
            user_id=str(user.id),
        )
        record_link_operation("create")
        return LinkResponse.model_validate(link)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("", response_model=LinkListResponse)
@limiter.limit(RATE_LIMIT_API)
async def list_links(
    request: Request,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    include_inactive: bool = False,
) -> LinkListResponse:
    """List all links for the current user (paginated)."""
    links, total = await link_service.get_user_links(
        session=session,
        user_id=user.id,
        page=page,
        page_size=page_size,
        include_inactive=include_inactive,
    )

    return LinkListResponse(
        items=[LinkResponse.model_validate(link) for link in links],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{link_id}", response_model=LinkResponse)
@limiter.limit(RATE_LIMIT_API)
async def get_link(
    request: Request,
    link_id: UUID,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> LinkResponse:
    """Get a specific link by ID."""
    link = await link_service.get_link_by_id(
        session=session,
        link_id=link_id,
        user_id=user.id,
    )
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found",
        )
    return LinkResponse.model_validate(link)


@router.patch("/{link_id}", response_model=LinkResponse)
@limiter.limit(RATE_LIMIT_API)
async def update_link(
    request: Request,
    link_id: UUID,
    link_data: LinkUpdate,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> LinkResponse:
    """Update a link's properties."""
    link = await link_service.get_link_by_id(
        session=session,
        link_id=link_id,
        user_id=user.id,
    )
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found",
        )

    updated_link = await link_service.update_link(
        session=session,
        link=link,
        link_data=link_data,
    )
    await session.commit()

    logger.info(
        "Link updated",
        link_id=str(link_id),
        user_id=str(user.id),
    )
    record_link_operation("update")
    return LinkResponse.model_validate(updated_link)


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(RATE_LIMIT_API)
async def delete_link(
    request: Request,
    link_id: UUID,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    hard: bool = False,
) -> None:
    """Delete a link (soft delete by default).

    Use `hard=true` to permanently delete the link.
    """
    link = await link_service.get_link_by_id(
        session=session,
        link_id=link_id,
        user_id=user.id,
    )
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found",
        )

    await link_service.delete_link(
        session=session,
        link=link,
        soft=not hard,
    )
    await session.commit()

    logger.info(
        "Link deleted",
        link_id=str(link_id),
        user_id=str(user.id),
        hard_delete=hard,
    )
    record_link_operation("delete")


@router.get("/{link_id}/analytics")
@limiter.limit(RATE_LIMIT_API)
async def get_link_analytics(
    request: Request,
    link_id: UUID,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict:
    """Get analytics for a specific link.

    Proxies request to the Analytics service.
    """
    # Verify user owns the link
    link = await link_service.get_link_by_id(
        session=session,
        link_id=link_id,
        user_id=user.id,
    )
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found",
        )

    # Proxy to analytics service
    analytics_url = f"http://localhost:8001/analytics/{link_id}/summary"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(analytics_url, timeout=10.0)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                # No analytics yet - return empty stats
                return {
                    "link_id": str(link_id),
                    "total_clicks": link.click_count,
                    "unique_visitors": None,
                    "message": "Detailed analytics not available yet",
                }
            else:
                logger.warning(
                    "Analytics service error",
                    status_code=response.status_code,
                    link_id=str(link_id),
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Analytics service unavailable",
                )
    except httpx.RequestError as e:
        logger.warning(
            "Analytics service connection error",
            error=str(e),
            link_id=str(link_id),
        )
        # Fallback to basic stats from link model
        return {
            "link_id": str(link_id),
            "total_clicks": link.click_count,
            "unique_visitors": None,
            "message": "Detailed analytics service unavailable",
        }
