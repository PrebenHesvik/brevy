"""Authentication endpoints for OAuth login/logout."""

from typing import Annotated

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_async_session
from app.core.deps import AUTH_COOKIE_NAME, CurrentUser, CurrentUserOptional
from app.core.oauth import oauth
from app.core.rate_limit import RATE_LIMIT_AUTH, limiter
from app.core.security import create_cookie_token
from app.schemas.user import UserResponse
from app.services import user_service

settings = get_settings()
logger = structlog.get_logger()

router = APIRouter(prefix="/auth", tags=["auth"])

# Frontend URL to redirect after OAuth
FRONTEND_URL = "http://localhost:5173"


@router.get("/github")
@limiter.limit(RATE_LIMIT_AUTH)
async def github_login(request: Request) -> Response:
    """Initiate GitHub OAuth login flow.

    Redirects to GitHub's authorization page.
    """
    if not settings.github_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub OAuth is not configured",
        )

    redirect_uri = request.url_for("github_callback")
    return await oauth.github.authorize_redirect(request, redirect_uri)


@router.get("/github/callback")
@limiter.limit(RATE_LIMIT_AUTH)
async def github_callback(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Response:
    """Handle GitHub OAuth callback.

    Exchanges code for token, fetches user info, creates/updates user,
    and sets auth cookie.
    """
    try:
        token = await oauth.github.authorize_access_token(request)
    except Exception as e:
        logger.error("GitHub OAuth token exchange failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to authenticate with GitHub",
        )

    # Fetch user info from GitHub
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token['access_token']}"}

        # Get user profile
        user_resp = await client.get(
            "https://api.github.com/user",
            headers=headers,
        )
        if user_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch GitHub user info",
            )
        github_user = user_resp.json()

        # Get user emails (in case email is private)
        emails_resp = await client.get(
            "https://api.github.com/user/emails",
            headers=headers,
        )
        emails = emails_resp.json() if emails_resp.status_code == 200 else []

    # Extract email (prefer primary verified email)
    email = github_user.get("email")
    if not email and emails:
        for e in emails:
            if e.get("primary") and e.get("verified"):
                email = e.get("email")
                break
        if not email and emails:
            email = emails[0].get("email")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not get email from GitHub",
        )

    # Create or update user
    try:
        user, created = await user_service.get_or_create_user_from_oauth(
            session=session,
            provider="github",
            provider_id=str(github_user["id"]),
            email=email,
            name=github_user.get("name") or github_user.get("login"),
            avatar_url=github_user.get("avatar_url"),
        )
        await session.commit()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    logger.info(
        "GitHub OAuth successful",
        user_id=str(user.id),
        email=user.email,
        created=created,
    )

    # Create token and set cookie
    token_value, max_age = create_cookie_token(user.id, user.email)

    response = Response(
        status_code=status.HTTP_302_FOUND,
        headers={"Location": f"{FRONTEND_URL}/dashboard"},
    )
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token_value,
        max_age=max_age,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        path="/",
    )
    return response


@router.get("/google")
@limiter.limit(RATE_LIMIT_AUTH)
async def google_login(request: Request) -> Response:
    """Initiate Google OAuth login flow.

    Redirects to Google's authorization page.
    """
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        )

    redirect_uri = request.url_for("google_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
@limiter.limit(RATE_LIMIT_AUTH)
async def google_callback(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Response:
    """Handle Google OAuth callback.

    Exchanges code for token, fetches user info, creates/updates user,
    and sets auth cookie.
    """
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        logger.error("Google OAuth token exchange failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to authenticate with Google",
        )

    # Get user info from ID token
    user_info = token.get("userinfo")
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to get user info from Google",
        )

    email = user_info.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not get email from Google",
        )

    # Create or update user
    try:
        user, created = await user_service.get_or_create_user_from_oauth(
            session=session,
            provider="google",
            provider_id=user_info["sub"],
            email=email,
            name=user_info.get("name"),
            avatar_url=user_info.get("picture"),
        )
        await session.commit()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    logger.info(
        "Google OAuth successful",
        user_id=str(user.id),
        email=user.email,
        created=created,
    )

    # Create token and set cookie
    token_value, max_age = create_cookie_token(user.id, user.email)

    response = Response(
        status_code=status.HTTP_302_FOUND,
        headers={"Location": f"{FRONTEND_URL}/dashboard"},
    )
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token_value,
        max_age=max_age,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        path="/",
    )
    return response


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    """Log out the current user by clearing the auth cookie."""
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
    )
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: CurrentUser) -> UserResponse:
    """Get the current authenticated user's information."""
    return UserResponse.model_validate(user)


@router.get("/status")
async def auth_status(user: CurrentUserOptional) -> dict:
    """Check authentication status.

    Returns user info if authenticated, otherwise returns authenticated: false.
    Useful for frontend to check login state without 401 errors.
    """
    if user:
        return {
            "authenticated": True,
            "user": UserResponse.model_validate(user).model_dump(),
        }
    return {"authenticated": False, "user": None}
