"""Click storage service for persisting click events to the database."""

import asyncio
import time
from collections.abc import Sequence

import structlog
from brevy_shared import ClickEvent
from sqlalchemy import insert

from app.core.database import async_session_factory
from app.core.observability import record_batch_insert, set_pending_clicks
from app.models.click import Click
from app.services.geoip import get_geoip_service

logger = structlog.get_logger()


class ClickStorageService:
    """Service for storing click events in the database.

    Supports both single insert and batch insert modes for high throughput.

    Usage:
        # Single insert mode
        service = ClickStorageService()
        await service.store_click(event)

        # Batch insert mode (for high throughput)
        service = ClickStorageService(batch_size=100, flush_interval=5.0)
        await service.start()
        await service.store_click(event)  # Buffered
        await service.stop()  # Flushes remaining
    """

    def __init__(
        self,
        batch_size: int = 100,
        flush_interval: float = 5.0,
        enable_batching: bool = True,
    ):
        """Initialize the click storage service.

        Args:
            batch_size: Number of events to batch before flushing.
            flush_interval: Maximum seconds between flushes.
            enable_batching: Whether to enable batch mode.
        """
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._enable_batching = enable_batching
        self._buffer: list[dict] = []
        self._buffer_lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None
        self._running = False
        self._clicks_stored = 0
        self._batches_flushed = 0

    async def start(self) -> None:
        """Start the batch flush timer."""
        if not self._enable_batching:
            return

        if self._running:
            return

        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info(
            "Click storage service started",
            batch_size=self._batch_size,
            flush_interval=self._flush_interval,
        )

    async def stop(self) -> None:
        """Stop the service and flush any remaining events."""
        if not self._running:
            return

        self._running = False

        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None

        # Flush any remaining events
        await self._flush_buffer()

        logger.info(
            "Click storage service stopped",
            clicks_stored=self._clicks_stored,
            batches_flushed=self._batches_flushed,
        )

    async def store_click(self, event: ClickEvent) -> None:
        """Store a click event.

        In batch mode, events are buffered and flushed periodically.
        In single mode, events are stored immediately.
        """
        # Look up geo location
        geoip = get_geoip_service()
        location = await geoip.lookup(event.ip_address)

        # Prepare click data
        click_data = {
            "link_id": event.link_id,
            "short_code": event.short_code,
            "clicked_at": event.clicked_at,
            "referrer": event.referrer,
            "user_agent": event.user_agent,
            "ip_address": event.ip_address,
            "country": location.country,
            "city": location.city,
        }

        if self._enable_batching:
            await self._add_to_buffer(click_data)
        else:
            await self._store_single(click_data)

    async def _add_to_buffer(self, click_data: dict) -> None:
        """Add a click to the buffer and flush if needed."""
        async with self._buffer_lock:
            self._buffer.append(click_data)
            set_pending_clicks(len(self._buffer))

            if len(self._buffer) >= self._batch_size:
                await self._flush_buffer_locked()

    async def _flush_loop(self) -> None:
        """Periodic flush loop for batch mode."""
        try:
            while self._running:
                await asyncio.sleep(self._flush_interval)
                await self._flush_buffer()
        except asyncio.CancelledError:
            pass

    async def _flush_buffer(self) -> None:
        """Flush the buffer to the database."""
        async with self._buffer_lock:
            await self._flush_buffer_locked()

    async def _flush_buffer_locked(self) -> None:
        """Flush the buffer (must be called with lock held)."""
        if not self._buffer:
            return

        events_to_flush = self._buffer.copy()
        self._buffer.clear()
        set_pending_clicks(0)

        try:
            start_time = time.perf_counter()
            await self._batch_insert(events_to_flush)
            duration = time.perf_counter() - start_time

            self._clicks_stored += len(events_to_flush)
            self._batches_flushed += 1

            # Record metrics
            record_batch_insert(len(events_to_flush), duration)

            logger.debug(
                "Batch flushed",
                count=len(events_to_flush),
                total_stored=self._clicks_stored,
                duration_ms=round(duration * 1000, 2),
            )
        except Exception as e:
            logger.error(
                "Failed to flush batch",
                count=len(events_to_flush),
                error=str(e),
            )
            # Re-add to buffer for retry
            self._buffer.extend(events_to_flush)
            set_pending_clicks(len(self._buffer))

    async def _store_single(self, click_data: dict) -> None:
        """Store a single click immediately."""
        async with async_session_factory() as session:
            try:
                click = Click(**click_data)
                session.add(click)
                await session.commit()
                self._clicks_stored += 1
                logger.debug(
                    "Click stored",
                    link_id=str(click_data["link_id"]),
                )
            except Exception as e:
                await session.rollback()
                logger.error(
                    "Failed to store click",
                    link_id=str(click_data["link_id"]),
                    error=str(e),
                )
                raise

    async def _batch_insert(self, clicks: Sequence[dict]) -> None:
        """Batch insert multiple clicks."""
        async with async_session_factory() as session:
            try:
                # Use bulk insert for better performance
                await session.execute(insert(Click), clicks)
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error("Batch insert failed", count=len(clicks), error=str(e))
                raise

    @property
    def stats(self) -> dict:
        """Get storage statistics."""
        return {
            "clicks_stored": self._clicks_stored,
            "batches_flushed": self._batches_flushed,
            "buffer_size": len(self._buffer),
            "batching_enabled": self._enable_batching,
        }


# Global service instance
_storage_service: ClickStorageService | None = None


def get_storage_service() -> ClickStorageService:
    """Get the global storage service instance."""
    global _storage_service
    if _storage_service is None:
        _storage_service = ClickStorageService()
    return _storage_service


async def start_storage_service() -> None:
    """Start the global storage service."""
    service = get_storage_service()
    await service.start()


async def stop_storage_service() -> None:
    """Stop the global storage service."""
    service = get_storage_service()
    await service.stop()


async def store_click_handler(event: ClickEvent) -> None:
    """Handler function for the click consumer.

    This function is registered with the ClickEventConsumer
    to process incoming click events.
    """
    service = get_storage_service()
    await service.store_click(event)
