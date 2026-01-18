"""Rate limiting configuration using slowapi."""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.config import get_settings

settings = get_settings()


def get_real_client_ip(request: Request) -> str:
    """Get the real client IP address, handling proxies.

    Checks X-Forwarded-For and X-Real-IP headers before falling back
    to the direct client address.
    """
    # Check X-Forwarded-For header first (set by proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs: client, proxy1, proxy2
        # The first one is the original client
        return forwarded_for.split(",")[0].strip()

    # Check X-Real-IP header (common in nginx setups)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to default behavior
    return get_remote_address(request)


# Create the limiter instance with custom key function
limiter = Limiter(
    key_func=get_real_client_ip,
    default_limits=["1000/hour"],  # Default limit for all endpoints
    storage_uri=settings.redis_url,  # Use Redis for distributed rate limiting
    strategy="fixed-window",  # Simple fixed window strategy
)

# Rate limit constants for different endpoint types
# These can be used as decorators: @limiter.limit(RATE_LIMIT_REDIRECT)

# High limit for redirect endpoint - this is the hot path
# 1000 requests per minute per IP should handle most legitimate use cases
RATE_LIMIT_REDIRECT = "1000/minute"

# Lower limit for link creation - prevent spam/abuse
# 60 per hour = 1 per minute average, with burst capacity
RATE_LIMIT_CREATE_LINK = "60/hour"

# Auth endpoints - prevent brute force
RATE_LIMIT_AUTH = "20/minute"

# General API endpoints - moderate limit
RATE_LIMIT_API = "100/minute"
