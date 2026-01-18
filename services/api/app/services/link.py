"""Link service for database operations and short code generation."""

import secrets
import string
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import invalidate_link_cache
from app.models.link import Link
from app.schemas.link import LinkCreate, LinkUpdate

# Characters for random short code generation (base62)
SHORT_CODE_CHARS = string.ascii_lowercase + string.ascii_uppercase + string.digits
SHORT_CODE_LENGTH = 6


def generate_short_code(length: int = SHORT_CODE_LENGTH) -> str:
    """Generate a random short code using base62 characters."""
    return "".join(secrets.choice(SHORT_CODE_CHARS) for _ in range(length))


async def is_short_code_available(session: AsyncSession, short_code: str) -> bool:
    """Check if a short code is available (not already used)."""
    result = await session.execute(
        select(Link.id).where(Link.short_code == short_code)
    )
    return result.scalar_one_or_none() is None


async def generate_unique_short_code(
    session: AsyncSession,
    max_attempts: int = 10,
) -> str:
    """Generate a unique short code with collision detection.

    Raises ValueError if unable to generate unique code after max_attempts.
    """
    for _ in range(max_attempts):
        code = generate_short_code()
        if await is_short_code_available(session, code):
            return code
    raise ValueError("Unable to generate unique short code")


async def get_link_by_id(
    session: AsyncSession,
    link_id: UUID,
    user_id: UUID | None = None,
) -> Link | None:
    """Get a link by its ID, optionally filtering by user."""
    query = select(Link).where(Link.id == link_id)
    if user_id:
        query = query.where(Link.user_id == user_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_link_by_short_code(
    session: AsyncSession,
    short_code: str,
) -> Link | None:
    """Get a link by its short code."""
    result = await session.execute(
        select(Link).where(Link.short_code == short_code)
    )
    return result.scalar_one_or_none()


async def get_active_link_by_short_code(
    session: AsyncSession,
    short_code: str,
) -> Link | None:
    """Get an active, non-expired link by its short code."""
    result = await session.execute(
        select(Link).where(
            Link.short_code == short_code,
            Link.is_active == True,  # noqa: E712
        )
    )
    link = result.scalar_one_or_none()
    if link and link.is_expired:
        return None
    return link


async def get_user_links(
    session: AsyncSession,
    user_id: UUID,
    page: int = 1,
    page_size: int = 20,
    include_inactive: bool = False,
) -> tuple[list[Link], int]:
    """Get paginated links for a user.

    Returns tuple of (links, total_count).
    """
    # Base query
    query = select(Link).where(Link.user_id == user_id)
    count_query = select(func.count(Link.id)).where(Link.user_id == user_id)

    if not include_inactive:
        query = query.where(Link.is_active == True)  # noqa: E712
        count_query = count_query.where(Link.is_active == True)  # noqa: E712

    # Get total count
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    offset = (page - 1) * page_size
    query = query.order_by(Link.created_at.desc()).offset(offset).limit(page_size)

    result = await session.execute(query)
    links = list(result.scalars().all())

    return links, total


async def create_link(
    session: AsyncSession,
    user_id: UUID,
    link_data: LinkCreate,
) -> Link:
    """Create a new shortened link."""
    # Handle custom vs generated short code
    if link_data.custom_code:
        if not await is_short_code_available(session, link_data.custom_code):
            raise ValueError(f"Short code '{link_data.custom_code}' is already taken")
        short_code = link_data.custom_code
        is_custom = True
    else:
        short_code = await generate_unique_short_code(session)
        is_custom = False

    link = Link(
        user_id=user_id,
        short_code=short_code,
        original_url=str(link_data.original_url),
        title=link_data.title,
        is_custom=is_custom,
        expires_at=link_data.expires_at,
    )
    session.add(link)
    await session.flush()
    await session.refresh(link)
    return link


async def update_link(
    session: AsyncSession,
    link: Link,
    link_data: LinkUpdate,
) -> Link:
    """Update an existing link."""
    update_data = link_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(link, field, value)
    await session.flush()
    await session.refresh(link)

    # Invalidate cache so next redirect gets fresh data
    await invalidate_link_cache(link.short_code)

    return link


async def delete_link(
    session: AsyncSession,
    link: Link,
    soft: bool = True,
) -> None:
    """Delete a link (soft delete by default)."""
    short_code = link.short_code  # Save before potential deletion

    if soft:
        link.is_active = False
        await session.flush()
    else:
        await session.delete(link)
        await session.flush()

    # Invalidate cache so redirect returns 404/410
    await invalidate_link_cache(short_code)


async def increment_click_count(
    session: AsyncSession,
    link_id: UUID,
) -> None:
    """Increment the click count for a link."""
    result = await session.execute(select(Link).where(Link.id == link_id))
    link = result.scalar_one_or_none()
    if link:
        link.click_count += 1
        await session.flush()
