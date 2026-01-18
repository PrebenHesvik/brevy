"""Database configuration with SQLAlchemy 2.0 async support for analytics schema."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

# Naming convention for constraints (helps with migrations)
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Create async engine with connection pooling
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,  # Log SQL statements in debug mode
    pool_size=5,  # Number of connections to keep in the pool
    max_overflow=10,  # Additional connections beyond pool_size
    pool_timeout=30,  # Seconds to wait for a connection
    pool_recycle=1800,  # Recycle connections after 30 minutes
    pool_pre_ping=True,  # Verify connections before use
)

# Session factory for creating database sessions
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models in analytics schema."""

    metadata = MetaData(naming_convention=convention, schema="analytics")


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides an async database session.

    Usage:
        @router.get("/items")
        async def get_items(session: AsyncSession = Depends(get_async_session)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Type alias for dependency injection
AsyncSessionDep = Annotated[AsyncSession, Depends(get_async_session)]


async def init_db() -> None:
    """Initialize database tables.

    Note: In production, use Alembic migrations instead.
    This is useful for testing or initial development.
    """
    async with engine.begin() as conn:
        # Create schema if not exists
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS analytics"))
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
