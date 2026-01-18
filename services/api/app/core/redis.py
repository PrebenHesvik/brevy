"""Redis client for caching and pub/sub."""

import json
from typing import Any

import redis.asyncio as redis
import structlog

from app.core.config import get_settings

settings = get_settings()
logger = structlog.get_logger()

# Global Redis client instance
_redis_client: redis.Redis | None = None

# Cache key prefixes
LINK_CACHE_PREFIX = "link:"
LINK_CACHE_TTL = 3600  # 1 hour


async def get_redis() -> redis.Redis:
    """Get the Redis client instance, creating it if necessary."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        logger.info("Redis client initialized", url=settings.redis_url)
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis connection closed")


def _link_cache_key(short_code: str) -> str:
    """Generate cache key for a link."""
    return f"{LINK_CACHE_PREFIX}{short_code}"


async def get_cached_link(short_code: str) -> dict[str, Any] | None:
    """Get a link from cache by short code.

    Returns None if not found in cache.
    """
    client = await get_redis()
    try:
        data = await client.get(_link_cache_key(short_code))
        if data:
            logger.debug("Cache hit", short_code=short_code)
            return json.loads(data)
        logger.debug("Cache miss", short_code=short_code)
        return None
    except redis.RedisError as e:
        logger.warning("Redis get error", short_code=short_code, error=str(e))
        return None


async def cache_link(
    short_code: str,
    link_data: dict[str, Any],
    ttl: int = LINK_CACHE_TTL,
) -> None:
    """Cache a link by short code.

    Args:
        short_code: The short code for the link
        link_data: Dictionary with link data (original_url, is_active, expires_at)
        ttl: Time to live in seconds (default 1 hour)
    """
    client = await get_redis()
    try:
        await client.setex(
            _link_cache_key(short_code),
            ttl,
            json.dumps(link_data),
        )
        logger.debug("Link cached", short_code=short_code, ttl=ttl)
    except redis.RedisError as e:
        logger.warning("Redis set error", short_code=short_code, error=str(e))


async def invalidate_link_cache(short_code: str) -> None:
    """Invalidate (delete) a link from cache."""
    client = await get_redis()
    try:
        await client.delete(_link_cache_key(short_code))
        logger.debug("Cache invalidated", short_code=short_code)
    except redis.RedisError as e:
        logger.warning("Redis delete error", short_code=short_code, error=str(e))


async def publish_click_event(channel: str, event_data: dict[str, Any]) -> None:
    """Publish a click event to Redis Pub/Sub.

    This will be used in step 2.7 for click event publishing.
    """
    client = await get_redis()
    try:
        await client.publish(channel, json.dumps(event_data))
        logger.debug("Click event published", channel=channel)
    except redis.RedisError as e:
        logger.warning("Redis publish error", channel=channel, error=str(e))
