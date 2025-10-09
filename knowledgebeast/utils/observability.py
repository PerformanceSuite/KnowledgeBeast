"""Observability infrastructure for KnowledgeBeast.

This module provides OpenTelemetry tracing, Prometheus metrics, and structured logging
for comprehensive production monitoring and debugging.

Features:
- OpenTelemetry distributed tracing with automatic context propagation
- Prometheus metrics with custom application metrics
- Structured logging with correlation IDs
- Performance monitoring with minimal overhead
"""

import logging
import os
import time
from contextvars import ContextVar
from typing import Any, Dict, Optional

import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry

# Service information
SERVICE_NAME = "knowledgebeast"
SERVICE_VERSION = os.getenv("KB_VERSION", "0.1.0")

# Context variables for correlation IDs
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

# Global tracer instance
_tracer: Optional[trace.Tracer] = None

# Global Prometheus registry
metrics_registry = CollectorRegistry()

# Custom Prometheus metrics
query_duration = Histogram(
    "kb_query_duration_seconds",
    "Duration of knowledge base queries in seconds",
    ["operation", "status"],
    registry=metrics_registry,
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

embedding_cache_hits = Counter(
    "kb_embedding_cache_hits_total",
    "Total number of embedding cache hits",
    registry=metrics_registry
)

embedding_cache_misses = Counter(
    "kb_embedding_cache_misses_total",
    "Total number of embedding cache misses",
    registry=metrics_registry
)

vector_search_duration = Histogram(
    "kb_vector_search_duration_seconds",
    "Duration of vector search operations in seconds",
    ["search_type"],
    registry=metrics_registry,
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
)

active_projects = Gauge(
    "kb_active_projects_total",
    "Total number of active projects",
    registry=metrics_registry
)

chromadb_collection_size = Gauge(
    "kb_chromadb_collection_size",
    "Number of documents in ChromaDB collection",
    ["project_id"],
    registry=metrics_registry
)

# Additional observability metrics
api_requests_total = Counter(
    "kb_api_requests_total",
    "Total number of API requests",
    ["method", "endpoint", "status_code"],
    registry=metrics_registry
)

api_request_duration = Histogram(
    "kb_api_request_duration_seconds",
    "API request duration in seconds",
    ["method", "endpoint"],
    registry=metrics_registry,
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
)

cache_operations_total = Counter(
    "kb_cache_operations_total",
    "Total number of cache operations",
    ["operation", "cache_type"],
    registry=metrics_registry
)

cache_operation_duration = Histogram(
    "kb_cache_operation_duration_seconds",
    "Cache operation duration in seconds",
    ["operation", "cache_type"],
    registry=metrics_registry,
    buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1)
)

# Re-ranking metrics
reranking_duration = Histogram(
    "kb_reranking_duration_seconds",
    "Duration of re-ranking operations in seconds",
    ["reranker_type", "status"],
    registry=metrics_registry,
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
)

reranking_requests_total = Counter(
    "kb_reranking_requests_total",
    "Total number of re-ranking requests",
    ["reranker_type", "status"],
    registry=metrics_registry
)

reranking_model_loads_total = Counter(
    "kb_reranking_model_loads_total",
    "Total number of re-ranking model loads",
    ["model_name"],
    registry=metrics_registry
)

reranking_score_improvement = Histogram(
    "kb_reranking_score_improvement",
    "Score improvement delta between vector and rerank scores",
    ["reranker_type"],
    registry=metrics_registry,
    buckets=(-0.5, -0.25, -0.1, 0.0, 0.1, 0.25, 0.5, 0.75, 1.0)
)

# Chunking metrics
chunking_duration = Histogram(
    "kb_chunking_duration_seconds",
    "Duration of chunking operations in seconds",
    ["strategy"],
    registry=metrics_registry,
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
)

chunks_created_total = Counter(
    "kb_chunks_created_total",
    "Total number of chunks created",
    ["strategy"],
    registry=metrics_registry
)

chunk_size_bytes = Histogram(
    "kb_chunk_size_bytes",
    "Size of chunks in bytes",
    ["strategy"],
    registry=metrics_registry,
    buckets=(100, 250, 500, 1000, 2000, 5000, 10000, 20000, 50000)
)

chunk_overlap_ratio = Histogram(
    "kb_chunk_overlap_ratio",
    "Ratio of chunk overlap to chunk size",
    ["strategy"],
    registry=metrics_registry,
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
)

# Query expansion metrics (Phase 2)
query_expansions_total = Counter(
    "kb_query_expansions_total",
    "Total number of query expansions performed",
    registry=metrics_registry
)

query_expansion_duration = Histogram(
    "kb_query_expansion_duration_seconds",
    "Query expansion duration in seconds",
    registry=metrics_registry,
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5)
)

# Semantic cache metrics (Phase 2)
semantic_cache_hits_total = Counter(
    "kb_semantic_cache_hits_total",
    "Total number of semantic cache hits",
    registry=metrics_registry
)

semantic_cache_misses_total = Counter(
    "kb_semantic_cache_misses_total",
    "Total number of semantic cache misses",
    registry=metrics_registry
)

semantic_cache_similarity_scores = Histogram(
    "kb_semantic_cache_similarity_scores",
    "Histogram of semantic cache similarity scores",
    registry=metrics_registry,
    buckets=(0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.92, 0.94, 0.95, 0.96, 0.97, 0.98, 0.99, 1.0)
)

# ============================================================================
# Per-Project Metrics (v2.3.0 - Security & Observability)
# ============================================================================

project_queries_total = Counter(
    "kb_project_queries_total",
    "Total queries per project",
    ["project_id", "status"],
    registry=metrics_registry
)

project_query_duration = Histogram(
    "kb_project_query_duration_seconds",
    "Query latency per project in seconds",
    ["project_id"],
    registry=metrics_registry,
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

project_documents_total = Gauge(
    "kb_project_documents_total",
    "Total documents per project",
    ["project_id"],
    registry=metrics_registry
)

project_cache_hits_total = Counter(
    "kb_project_cache_hits_total",
    "Cache hits per project",
    ["project_id"],
    registry=metrics_registry
)

project_cache_misses_total = Counter(
    "kb_project_cache_misses_total",
    "Cache misses per project",
    ["project_id"],
    registry=metrics_registry
)

project_ingests_total = Counter(
    "kb_project_ingests_total",
    "Total documents ingested per project",
    ["project_id", "status"],
    registry=metrics_registry
)

project_errors_total = Counter(
    "kb_project_errors_total",
    "Total errors per project",
    ["project_id", "error_type"],
    registry=metrics_registry
)

project_api_key_validations_total = Counter(
    "kb_project_api_key_validations_total",
    "Total API key validation attempts per project",
    ["project_id", "result"],
    registry=metrics_registry
)

project_api_keys_active = Gauge(
    "kb_project_api_keys_active",
    "Number of active (non-revoked) API keys per project",
    ["project_id"],
    registry=metrics_registry
)

# Project management metrics
project_creations_total = Counter(
    "kb_project_creations_total",
    "Total number of projects created",
    registry=metrics_registry
)

project_deletions_total = Counter(
    "kb_project_deletions_total",
    "Total number of projects deleted",
    registry=metrics_registry
)

project_updates_total = Counter(
    "kb_project_updates_total",
    "Total number of project updates",
    registry=metrics_registry
)


def setup_opentelemetry(
    service_name: str = SERVICE_NAME,
    service_version: str = SERVICE_VERSION,
    otlp_endpoint: Optional[str] = None,
    console_export: bool = False
) -> trace.Tracer:
    """Initialize OpenTelemetry tracing infrastructure.

    Args:
        service_name: Name of the service
        service_version: Version of the service
        otlp_endpoint: OTLP collector endpoint (e.g., "http://localhost:4317")
        console_export: Whether to export spans to console (for debugging)

    Returns:
        Configured tracer instance
    """
    global _tracer

    # Create resource with service information
    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
        "deployment.environment": os.getenv("KB_ENVIRONMENT", "development"),
    })

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Add span processors
    if otlp_endpoint:
        # Export to OTLP collector (production)
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    if console_export:
        # Export to console (development/debugging)
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(console_exporter))

    # Set global tracer provider
    trace.set_tracer_provider(provider)

    # Get tracer instance
    _tracer = trace.get_tracer(__name__)

    logging.info(f"OpenTelemetry initialized for {service_name} v{service_version}")
    return _tracer


def get_tracer() -> trace.Tracer:
    """Get the global tracer instance.

    Returns:
        Tracer instance

    Raises:
        RuntimeError: If OpenTelemetry is not initialized
    """
    global _tracer

    if _tracer is None:
        # Auto-initialize with defaults if not already initialized
        _tracer = setup_opentelemetry()

    return _tracer


def setup_structured_logging(
    log_level: str = "INFO",
    json_logs: bool = True,
    include_trace_context: bool = True
) -> None:
    """Configure structured logging with correlation IDs and trace context.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: Whether to output logs in JSON format
        include_trace_context: Whether to include OpenTelemetry trace context
    """
    # Configure processors for structured logging
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    # Add trace context processor if enabled
    if include_trace_context:
        processors.append(add_trace_context)

    # Add rendering processor
    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper()),
    )

    logging.info(f"Structured logging configured (level={log_level}, json={json_logs})")


def add_trace_context(
    logger: Any,
    method_name: str,
    event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Add OpenTelemetry trace context to log entries.

    Args:
        logger: Logger instance
        method_name: Name of log method
        event_dict: Event dictionary

    Returns:
        Updated event dictionary with trace context
    """
    # Get current span context
    span = trace.get_current_span()
    if span.is_recording():
        span_context = span.get_span_context()
        if span_context.is_valid:
            event_dict["trace_id"] = format(span_context.trace_id, "032x")
            event_dict["span_id"] = format(span_context.span_id, "016x")
            event_dict["trace_flags"] = span_context.trace_flags

    # Add request ID from context variable
    request_id = request_id_var.get()
    if request_id:
        event_dict["request_id"] = request_id

    return event_dict


def set_request_id(request_id: str) -> None:
    """Set request ID in context for correlation.

    Args:
        request_id: Unique request identifier
    """
    request_id_var.set(request_id)


def get_request_id() -> Optional[str]:
    """Get current request ID from context.

    Returns:
        Request ID if set, None otherwise
    """
    return request_id_var.get()


def trace_operation(operation_name: str):
    """Decorator to trace an operation with OpenTelemetry.

    Args:
        operation_name: Name of the operation

    Example:
        @trace_operation("embedding.generate")
        def generate_embedding(text: str) -> np.ndarray:
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(operation_name) as span:
                # Add function attributes
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)

                # Execute function
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("status", "success")
                    return result
                except Exception as e:
                    span.set_attribute("status", "error")
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    span.record_exception(e)
                    raise
                finally:
                    duration = time.time() - start_time
                    span.set_attribute("duration_seconds", duration)

        return wrapper
    return decorator


def record_metric(
    metric_name: str,
    value: float,
    labels: Optional[Dict[str, str]] = None
) -> None:
    """Record a custom metric value.

    Args:
        metric_name: Name of the metric
        value: Metric value
        labels: Optional metric labels
    """
    # This is a placeholder for custom metric recording
    # In production, this would interact with the metrics backend
    logger = structlog.get_logger()
    logger.debug(
        "metric_recorded",
        metric_name=metric_name,
        value=value,
        labels=labels or {}
    )


# Initialize observability on module import
def initialize_observability(
    enable_tracing: bool = True,
    enable_metrics: bool = True,
    enable_logging: bool = True,
    otlp_endpoint: Optional[str] = None
) -> None:
    """Initialize all observability components.

    Args:
        enable_tracing: Whether to enable OpenTelemetry tracing
        enable_metrics: Whether to enable Prometheus metrics
        enable_logging: Whether to enable structured logging
        otlp_endpoint: OTLP collector endpoint for tracing
    """
    if enable_tracing:
        setup_opentelemetry(
            otlp_endpoint=otlp_endpoint,
            console_export=os.getenv("KB_TRACE_CONSOLE", "false").lower() == "true"
        )

    if enable_logging:
        setup_structured_logging(
            log_level=os.getenv("KB_LOG_LEVEL", "INFO"),
            json_logs=os.getenv("KB_JSON_LOGS", "true").lower() == "true"
        )

    if enable_metrics:
        # Metrics are registered globally via prometheus_client
        logging.info("Prometheus metrics registered")


# Don't auto-initialize to avoid test conflicts
# Users should call initialize_observability() explicitly or set KB_AUTO_INIT_OBSERVABILITY=true
if os.getenv("KB_AUTO_INIT_OBSERVABILITY", "false").lower() == "true":
    initialize_observability()
