"""User service for database operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    """Get a user by their ID."""
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    """Get a user by their email address."""
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_provider(
    session: AsyncSession,
    provider: str,
    provider_id: str,
) -> User | None:
    """Get a user by their OAuth provider and provider ID."""
    result = await session.execute(
        select(User).where(
            User.provider == provider,
            User.provider_id == provider_id,
        )
    )
    return result.scalar_one_or_none()


async def create_user(session: AsyncSession, user_data: UserCreate) -> User:
    """Create a new user."""
    user = User(
        email=user_data.email,
        name=user_data.name,
        avatar_url=user_data.avatar_url,
        provider=user_data.provider,
        provider_id=user_data.provider_id,
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def update_user(
    session: AsyncSession,
    user: User,
    user_data: UserUpdate,
) -> User:
    """Update an existing user."""
    update_data = user_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    await session.flush()
    await session.refresh(user)
    return user


async def get_or_create_user_from_oauth(
    session: AsyncSession,
    provider: str,
    provider_id: str,
    email: str,
    name: str | None = None,
    avatar_url: str | None = None,
) -> tuple[User, bool]:
    """Get existing user or create new one from OAuth data.

    Returns:
        Tuple of (user, created) where created is True if new user was created
    """
    # First try to find by provider ID
    user = await get_user_by_provider(session, provider, provider_id)
    if user:
        # Update profile info if changed
        if user.name != name or user.avatar_url != avatar_url:
            user.name = name
            user.avatar_url = avatar_url
            await session.flush()
        return user, False

    # Check if email already exists (user switching providers)
    existing_user = await get_user_by_email(session, email)
    if existing_user:
        # For now, don't allow switching providers
        # Could implement account linking in the future
        raise ValueError(
            f"Email {email} is already registered with {existing_user.provider}"
        )

    # Create new user
    user_data = UserCreate(
        email=email,
        name=name,
        avatar_url=avatar_url,
        provider=provider,
        provider_id=provider_id,
    )
    user = await create_user(session, user_data)
    return user, True
