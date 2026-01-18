"""Shared Pydantic schemas for inter-service communication."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ClickEvent(BaseModel):
    """Click event published from API service to Analytics service via Redis Pub/Sub.

    This schema represents a single click/redirect event that occurs when
    a user accesses a shortened URL.
    """

    link_id: UUID = Field(description="UUID of the shortened link")
    short_code: str = Field(description="The short code that was accessed")
    clicked_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the click occurred",
    )
    referrer: str | None = Field(default=None, description="HTTP Referer header")
    user_agent: str | None = Field(default=None, description="HTTP User-Agent header")
    ip_address: str | None = Field(default=None, description="Client IP address")

    model_config = {"json_schema_extra": {"example": {
        "link_id": "550e8400-e29b-41d4-a716-446655440000",
        "short_code": "abc123",
        "clicked_at": "2024-01-15T10:30:00Z",
        "referrer": "https://google.com",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "ip_address": "192.168.1.1",
    }}}


class LinkCreatedEvent(BaseModel):
    """Event published when a new link is created (for cache warming, etc.)."""

    link_id: UUID = Field(description="UUID of the new link")
    short_code: str = Field(description="The short code for the link")
    original_url: str = Field(description="The original URL to redirect to")
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the link was created",
    )


class LinkUpdatedEvent(BaseModel):
    """Event published when a link is updated (for cache invalidation)."""

    link_id: UUID = Field(description="UUID of the updated link")
    short_code: str = Field(description="The short code for the link")
    is_active: bool = Field(description="Whether the link is active")
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the link was updated",
    )
