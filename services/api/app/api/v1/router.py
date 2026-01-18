"""API v1 router - aggregates all v1 endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
