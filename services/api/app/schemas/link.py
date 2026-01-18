"""Link Pydantic schemas."""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class LinkBase(BaseModel):
    """Base schema for link data."""

    original_url: HttpUrl = Field(description="The URL to shorten")
    title: str | None = Field(default=None, max_length=255, description="Optional title")
    expires_at: datetime | None = Field(default=None, description="Optional expiration time")


class LinkCreate(LinkBase):
    """Schema for creating a new link."""

    custom_code: str | None = Field(
        default=None,
        min_length=3,
        max_length=20,
        description="Optional custom short code",
    )

    @field_validator("custom_code")
    @classmethod
    def validate_custom_code(cls, v: str | None) -> str | None:
        """Validate custom code format."""
        if v is None:
            return v
        # Only allow alphanumeric characters and hyphens
        if not re.match(r"^[a-zA-Z0-9-]+$", v):
            raise ValueError("Custom code can only contain letters, numbers, and hyphens")
        # Cannot start or end with hyphen
        if v.startswith("-") or v.endswith("-"):
            raise ValueError("Custom code cannot start or end with a hyphen")
        return v.lower()


class LinkUpdate(BaseModel):
    """Schema for updating a link."""

    title: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    expires_at: datetime | None = None


class LinkResponse(BaseModel):
    """Schema for link response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    short_code: str
    original_url: str
    title: str | None
    is_custom: bool
    is_active: bool
    click_count: int
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None

    @property
    def short_url(self) -> str:
        """Generate the full short URL."""
        # This would be configured based on environment
        return f"http://localhost:8000/{self.short_code}"


class LinkListResponse(BaseModel):
    """Schema for paginated link list response."""

    items: list[LinkResponse]
    total: int
    page: int
    page_size: int
    pages: int


class LinkStats(BaseModel):
    """Schema for basic link statistics."""

    total_clicks: int
    unique_visitors: int | None = None
    last_clicked_at: datetime | None = None
