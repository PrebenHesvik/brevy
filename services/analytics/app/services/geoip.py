"""GeoIP service for IP to location lookup."""

from dataclasses import dataclass
from pathlib import Path

import httpx
import structlog

from app.core.config import get_settings

settings = get_settings()
logger = structlog.get_logger()


@dataclass
class GeoLocation:
    """Geographic location data from IP lookup."""

    country: str | None = None  # ISO 3166-1 alpha-2 country code
    city: str | None = None


class GeoIPService:
    """Service for looking up geographic location from IP addresses.

    Supports two backends:
    1. GeoIP2 database (MaxMind) - for production use
    2. IP-API.com - free API fallback for development

    Usage:
        service = GeoIPService()
        location = await service.lookup("8.8.8.8")
        print(location.country, location.city)
    """

    def __init__(self, geoip_database_path: str | None = None):
        """Initialize the GeoIP service.

        Args:
            geoip_database_path: Path to GeoIP2 database file.
                If not provided, falls back to IP-API.com.
        """
        self._geoip_reader = None
        self._database_path = geoip_database_path or settings.geoip_database_path

        if self._database_path:
            self._init_geoip2()

    def _init_geoip2(self) -> None:
        """Initialize GeoIP2 database reader."""
        try:
            import geoip2.database

            path = Path(self._database_path)
            if path.exists():
                self._geoip_reader = geoip2.database.Reader(str(path))
                logger.info("GeoIP2 database loaded", path=str(path))
            else:
                logger.warning("GeoIP2 database not found", path=str(path))
        except ImportError:
            logger.warning("geoip2 package not installed")
        except Exception as e:
            logger.error("Failed to load GeoIP2 database", error=str(e))

    async def lookup(self, ip_address: str | None) -> GeoLocation:
        """Look up geographic location for an IP address.

        Args:
            ip_address: IP address to look up.

        Returns:
            GeoLocation with country and city if found.
        """
        if not ip_address:
            return GeoLocation()

        # Skip private/local IP addresses
        if self._is_private_ip(ip_address):
            return GeoLocation()

        # Try GeoIP2 database first
        if self._geoip_reader:
            return self._lookup_geoip2(ip_address)

        # Fall back to IP-API
        return await self._lookup_ip_api(ip_address)

    def _is_private_ip(self, ip_address: str) -> bool:
        """Check if an IP address is private/local."""
        # Simple check for common private ranges
        private_prefixes = (
            "10.",
            "172.16.",
            "172.17.",
            "172.18.",
            "172.19.",
            "172.20.",
            "172.21.",
            "172.22.",
            "172.23.",
            "172.24.",
            "172.25.",
            "172.26.",
            "172.27.",
            "172.28.",
            "172.29.",
            "172.30.",
            "172.31.",
            "192.168.",
            "127.",
            "::1",
            "fe80:",
        )
        return ip_address.startswith(private_prefixes)

    def _lookup_geoip2(self, ip_address: str) -> GeoLocation:
        """Look up location using GeoIP2 database."""
        try:
            response = self._geoip_reader.city(ip_address)
            return GeoLocation(
                country=response.country.iso_code,
                city=response.city.name,
            )
        except Exception as e:
            logger.debug("GeoIP2 lookup failed", ip=ip_address, error=str(e))
            return GeoLocation()

    async def _lookup_ip_api(self, ip_address: str) -> GeoLocation:
        """Look up location using IP-API.com (free tier).

        Note: IP-API has rate limits (45 requests/minute for free tier).
        Use GeoIP2 database for production.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://ip-api.com/json/{ip_address}",
                    params={"fields": "status,countryCode,city"},
                    timeout=2.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success":
                        return GeoLocation(
                            country=data.get("countryCode"),
                            city=data.get("city"),
                        )
        except Exception as e:
            logger.debug("IP-API lookup failed", ip=ip_address, error=str(e))

        return GeoLocation()

    def close(self) -> None:
        """Close the GeoIP2 database reader."""
        if self._geoip_reader:
            self._geoip_reader.close()
            self._geoip_reader = None


# Global service instance
_geoip_service: GeoIPService | None = None


def get_geoip_service() -> GeoIPService:
    """Get the global GeoIP service instance."""
    global _geoip_service
    if _geoip_service is None:
        _geoip_service = GeoIPService()
    return _geoip_service


def close_geoip_service() -> None:
    """Close the global GeoIP service."""
    global _geoip_service
    if _geoip_service:
        _geoip_service.close()
        _geoip_service = None
