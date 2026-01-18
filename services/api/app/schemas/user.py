"""User Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    """Base schema for user data."""

    email: EmailStr
    name: str | None = None
    avatar_url: str | None = None


class UserCreate(UserBase):
    """Schema for creating a user (from OAuth)."""

    provider: str
    provider_id: str


class UserUpdate(BaseModel):
    """Schema for updating user data."""

    name: str | None = None
    avatar_url: str | None = None


class UserResponse(UserBase):
    """Schema for user response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider: str
    created_at: datetime
    updated_at: datetime


class UserInDB(UserResponse):
    """Schema for user stored in database (includes provider_id)."""

    provider_id: str
