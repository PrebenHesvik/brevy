"""Redis Pub/Sub consumer for click events."""

import asyncio
import json
import time
from typing import Callable, Coroutine

import redis.asyncio as redis
import structlog
from brevy_shared import ClickEvent
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.observability import (
    record_click_failed,
    record_click_processing_time,
    record_click_processed,
    record_click_received,
    set_consumer_running,
)

settings = get_settings()
logger = structlog.get_logger()

# Type alias for click event handler
ClickEventHandler = Callable[[ClickEvent], Coroutine[None, None, None]]


class ClickEventConsumer:
    """Redis Pub/Sub consumer for click events.

    This consumer subscribes to the click events channel and processes
    incoming events asynchronously. It handles malformed events gracefully
    by logging errors and continuing to process new events.

    Usage:
        consumer = ClickEventConsumer()
        consumer.register_handler(my_handler)
        await consumer.start()
        # ... later ...
        await consumer.stop()
    """

    def __init__(self, redis_url: str | None = None, channel: str | None = None):
        """Initialize the consumer.

        Args:
            redis_url: Redis connection URL. Defaults to settings.redis_url.
            channel: Channel to subscribe to. Defaults to settings.redis_channel.
        """
        self.redis_url = redis_url or settings.redis_url
        self.channel = channel or settings.redis_channel
        self._client: redis.Redis | None = None
        self._pubsub: redis.client.PubSub | None = None
        self._task: asyncio.Task | None = None
        self._running = False
        self._handlers: list[ClickEventHandler] = []
        self._events_processed = 0
        self._events_failed = 0

    def register_handler(self, handler: ClickEventHandler) -> None:
        """Register a handler function to process click events.

        Handlers are called in order of registration for each event.

        Args:
            handler: Async function that takes a ClickEvent and processes it.
        """
        self._handlers.append(handler)
        logger.debug("Handler registered", handler=handler.__name__)

    async def start(self) -> None:
        """Start consuming click events from Redis Pub/Sub."""
        if self._running:
            logger.warning("Consumer already running")
            return

        logger.info("Starting click event consumer", channel=self.channel)

        # Create Redis client
        self._client = redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )

        # Create pubsub and subscribe
        self._pubsub = self._client.pubsub()
        await self._pubsub.subscribe(self.channel)

        # Start the consumer loop in a background task
        self._running = True
        set_consumer_running(True)
        self._task = asyncio.create_task(self._consume_loop())

        logger.info("Click event consumer started", channel=self.channel)

    async def stop(self) -> None:
        """Stop consuming click events."""
        if not self._running:
            return

        logger.info(
            "Stopping click event consumer",
            events_processed=self._events_processed,
            events_failed=self._events_failed,
        )

        self._running = False
        set_consumer_running(False)

        # Cancel the consumer task
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        # Unsubscribe and close connections
        if self._pubsub:
            await self._pubsub.unsubscribe(self.channel)
            await self._pubsub.close()
            self._pubsub = None

        if self._client:
            await self._client.close()
            self._client = None

        logger.info("Click event consumer stopped")

    async def _consume_loop(self) -> None:
        """Main consumer loop that processes incoming messages."""
        if not self._pubsub:
            return

        logger.debug("Consumer loop started")

        try:
            async for message in self._pubsub.listen():
                if not self._running:
                    break

                # Skip subscription confirmation messages
                if message["type"] != "message":
                    continue

                await self._process_message(message["data"])

        except asyncio.CancelledError:
            logger.debug("Consumer loop cancelled")
            raise
        except redis.RedisError as e:
            logger.error("Redis error in consumer loop", error=str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error in consumer loop", error=str(e))
            raise

    async def _process_message(self, data: str) -> None:
        """Process a single message from the channel.

        Args:
            data: Raw JSON string from Redis.
        """
        start_time = time.perf_counter()
        record_click_received()

        try:
            # Parse JSON
            try:
                event_dict = json.loads(data)
            except json.JSONDecodeError as e:
                logger.warning(
                    "Invalid JSON in click event",
                    error=str(e),
                    data=data[:100],  # Truncate for logging
                )
                self._events_failed += 1
                record_click_failed("invalid_json")
                return

            # Validate and parse into ClickEvent
            try:
                event = ClickEvent.model_validate(event_dict)
            except ValidationError as e:
                logger.warning(
                    "Invalid click event schema",
                    error=str(e),
                    data=event_dict,
                )
                self._events_failed += 1
                record_click_failed("invalid_schema")
                return

            # Call all registered handlers
            for handler in self._handlers:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(
                        "Handler error",
                        handler=handler.__name__,
                        error=str(e),
                        link_id=str(event.link_id),
                    )
                    # Continue with other handlers even if one fails

            self._events_processed += 1
            record_click_processed()

            # Record processing time
            duration = time.perf_counter() - start_time
            record_click_processing_time(duration)

            logger.debug(
                "Click event processed",
                link_id=str(event.link_id),
                short_code=event.short_code,
                duration_ms=round(duration * 1000, 2),
            )

        except Exception as e:
            logger.error("Unexpected error processing message", error=str(e))
            self._events_failed += 1
            record_click_failed("unexpected_error")

    @property
    def is_running(self) -> bool:
        """Check if the consumer is running."""
        return self._running

    @property
    def stats(self) -> dict:
        """Get consumer statistics."""
        return {
            "running": self._running,
            "events_processed": self._events_processed,
            "events_failed": self._events_failed,
            "handlers_count": len(self._handlers),
        }


# Global consumer instance
_consumer: ClickEventConsumer | None = None


def get_consumer() -> ClickEventConsumer:
    """Get the global consumer instance, creating it if necessary."""
    global _consumer
    if _consumer is None:
        _consumer = ClickEventConsumer()
    return _consumer


async def start_consumer() -> None:
    """Start the global consumer."""
    consumer = get_consumer()
    await consumer.start()


async def stop_consumer() -> None:
    """Stop the global consumer."""
    consumer = get_consumer()
    await consumer.stop()
