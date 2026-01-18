"""Observability setup: logging, tracing, metrics, and error tracking."""

import logging
import time
import uuid
from contextvars import ContextVar

import sentry_sdk
import structlog
from fastapi import FastAPI, Request, Response
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import get_settings

settings = get_settings()

# Context variable for request ID (accessible throughout the request lifecycle)
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

# Prometheus metrics - HTTP requests
REQUEST_COUNT = Counter(
    "analytics_http_requests_total",
    "Total HTTP requests to analytics service",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "analytics_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Prometheus metrics - Click event processing
CLICK_EVENTS_RECEIVED = Counter(
    "analytics_click_events_received_total",
    "Total click events received from Redis Pub/Sub",
)

CLICK_EVENTS_PROCESSED = Counter(
    "analytics_click_events_processed_total",
    "Total click events successfully processed",
)

CLICK_EVENTS_FAILED = Counter(
    "analytics_click_events_failed_total",
    "Total click events that failed processing",
    ["reason"],
)

CLICK_PROCESSING_LATENCY = Histogram(
    "analytics_click_processing_duration_seconds",
    "Time to process a click event",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

# Prometheus metrics - Batch storage
BATCH_SIZE = Histogram(
    "analytics_batch_size",
    "Number of clicks per batch insert",
    buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000],
)

BATCH_INSERT_LATENCY = Histogram(
    "analytics_batch_insert_duration_seconds",
    "Time to perform batch insert",
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

# Prometheus metrics - Aggregation
AGGREGATION_RUNS = Counter(
    "analytics_aggregation_runs_total",
    "Total aggregation job runs",
    ["type"],  # hourly, daily
)

AGGREGATION_DURATION = Histogram(
    "analytics_aggregation_duration_seconds",
    "Time to complete aggregation job",
    ["type"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

LINKS_AGGREGATED = Counter(
    "analytics_links_aggregated_total",
    "Total links aggregated",
    ["type"],
)

# Prometheus metrics - Service state
CONSUMER_RUNNING = Gauge(
    "analytics_consumer_running",
    "Whether the click event consumer is running (1) or stopped (0)",
)

PENDING_CLICKS = Gauge(
    "analytics_pending_clicks",
    "Number of clicks pending batch insert",
)


def get_request_id() -> str | None:
    """Get the current request ID from context."""
    return request_id_ctx.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add a unique request ID to each request.

    The request ID is:
    - Generated if not provided in X-Request-ID header
    - Stored in context variable for access throughout the request
    - Added to response headers
    - Bound to structlog context for all log messages
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        # Get or generate request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Store in context variable
        token = request_id_ctx.set(request_id)

        # Bind to structlog context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_ctx.reset(token)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all requests with timing information."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        logger = structlog.get_logger()
        start_time = time.perf_counter()

        # Log request start
        logger.info(
            "Request started",
            client_ip=request.client.host if request.client else None,
        )

        response = await call_next(request)

        # Calculate duration
        duration = time.perf_counter() - start_time

        # Log request completion
        logger.info(
            "Request completed",
            status_code=response.status_code,
            duration_ms=round(duration * 1000, 2),
        )

        # Update Prometheus metrics
        endpoint = request.url.path
        # Normalize path parameters to avoid high cardinality
        if endpoint.startswith("/analytics/"):
            endpoint = "/analytics/{link_id}"

        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=endpoint,
            status_code=response.status_code,
        ).inc()

        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=endpoint,
        ).observe(duration)

        return response


def configure_structlog() -> None:
    """Configure structlog for JSON logging with context variables."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO if not settings.debug else logging.DEBUG,
    )


def setup_opentelemetry(app: FastAPI) -> None:
    """Set up OpenTelemetry tracing."""
    if not settings.otlp_endpoint:
        structlog.get_logger().info("OpenTelemetry disabled (no OTLP endpoint configured)")
        return

    # Create tracer provider
    resource = Resource(attributes={
        SERVICE_NAME: "brevy-analytics",
    })
    provider = TracerProvider(resource=resource)

    # Configure OTLP exporter
    otlp_exporter = OTLPSpanExporter(
        endpoint=settings.otlp_endpoint,
        insecure=True,  # Set to False in production with TLS
    )
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    # Set global tracer provider
    trace.set_tracer_provider(provider)

    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)

    structlog.get_logger().info(
        "OpenTelemetry configured",
        otlp_endpoint=settings.otlp_endpoint,
    )


def setup_sentry() -> None:
    """Set up Sentry for error tracking."""
    if not settings.sentry_dsn:
        structlog.get_logger().info("Sentry disabled (no DSN configured)")
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment="development" if settings.debug else "production",
        traces_sample_rate=0.1,  # Sample 10% of transactions
        profiles_sample_rate=0.1,  # Sample 10% of profiles
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
        ],
        # Don't send PII
        send_default_pii=False,
        # Attach request data
        request_bodies="small",
    )

    structlog.get_logger().info("Sentry configured")


def get_prometheus_metrics() -> bytes:
    """Generate Prometheus metrics output."""
    return generate_latest()


def setup_observability(app: FastAPI) -> None:
    """Set up all observability components.

    Call this function during app initialization to configure:
    - Structured logging with request context
    - Request ID middleware
    - Request logging middleware
    - OpenTelemetry tracing
    - Sentry error tracking
    - Prometheus metrics endpoint
    """
    # Configure structlog first
    configure_structlog()

    # Set up external integrations
    setup_sentry()
    setup_opentelemetry(app)

    # Add metrics endpoint
    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        """Prometheus metrics endpoint."""
        return Response(
            content=get_prometheus_metrics(),
            media_type="text/plain; charset=utf-8",
        )

    structlog.get_logger().info("Observability setup complete")


# Helper functions to record custom metrics
def record_click_received() -> None:
    """Record a click event received."""
    CLICK_EVENTS_RECEIVED.inc()


def record_click_processed() -> None:
    """Record a click event successfully processed."""
    CLICK_EVENTS_PROCESSED.inc()


def record_click_failed(reason: str) -> None:
    """Record a click event that failed processing."""
    CLICK_EVENTS_FAILED.labels(reason=reason).inc()


def record_click_processing_time(duration: float) -> None:
    """Record the time to process a click event."""
    CLICK_PROCESSING_LATENCY.observe(duration)


def record_batch_insert(batch_size: int, duration: float) -> None:
    """Record a batch insert operation."""
    BATCH_SIZE.observe(batch_size)
    BATCH_INSERT_LATENCY.observe(duration)


def record_aggregation(agg_type: str, duration: float, links_count: int) -> None:
    """Record an aggregation job run."""
    AGGREGATION_RUNS.labels(type=agg_type).inc()
    AGGREGATION_DURATION.labels(type=agg_type).observe(duration)
    LINKS_AGGREGATED.labels(type=agg_type).inc(links_count)


def set_consumer_running(running: bool) -> None:
    """Set the consumer running state."""
    CONSUMER_RUNNING.set(1 if running else 0)


def set_pending_clicks(count: int) -> None:
    """Set the number of pending clicks."""
    PENDING_CLICKS.set(count)
