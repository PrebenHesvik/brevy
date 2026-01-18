"""Analytics business logic services."""

from app.services.click_storage import (
    ClickStorageService,
    get_storage_service,
    start_storage_service,
    stop_storage_service,
    store_click_handler,
)
from app.services.geoip import (
    GeoIPService,
    GeoLocation,
    close_geoip_service,
    get_geoip_service,
)

__all__ = [
    # Click storage
    "ClickStorageService",
    "get_storage_service",
    "start_storage_service",
    "stop_storage_service",
    "store_click_handler",
    # GeoIP
    "GeoIPService",
    "GeoLocation",
    "get_geoip_service",
    "close_geoip_service",
]
