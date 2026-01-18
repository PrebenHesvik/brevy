"""Dependency injection utilities for FastAPI routes."""

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.security import TokenData, decode_access_token
from app.models.user import User

# Cookie name for auth token
AUTH_COOKIE_NAME = "brevy_token"


async def get_token_from_cookie(
    brevy_token: Annotated[str | None, Cookie()] = None,
) -> str | None:
    """Extract auth token from httpOnly cookie."""
    return brevy_token


async def get_current_user_optional(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    token: Annotated[str | None, Depends(get_token_from_cookie)],
) -> User | None:
    """Get current user from token if present, otherwise return None.

    Use this for routes that work with or without authentication.
    """
    if token is None:
        return None

    token_data = decode_access_token(token)
    if token_data is None:
        return None

    result = await session.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalar_one_or_none()
    return user


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    token: Annotated[str | None, Depends(get_token_from_cookie)],
) -> User:
    """Get current authenticated user.

    Raises HTTPException 401 if not authenticated.
    Use this for protected routes.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token is None:
        raise credentials_exception

    token_data = decode_access_token(token)
    if token_data is None:
        raise credentials_exception

    result = await session.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


async def get_token_data(
    token: Annotated[str | None, Depends(get_token_from_cookie)],
) -> TokenData:
    """Get token data without fetching full user from database.

    Useful for lightweight auth checks.
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    token_data = decode_access_token(token)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    return token_data


# Type aliases for dependency injection
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentUserOptional = Annotated[User | None, Depends(get_current_user_optional)]
CurrentTokenData = Annotated[TokenData, Depends(get_token_data)]
