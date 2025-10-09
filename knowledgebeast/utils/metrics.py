"""Prometheus metrics utilities for KnowledgeBeast.

This module provides helper functions and context managers for recording
Prometheus metrics with minimal boilerplate.
"""

import time
from contextlib import contextmanager
from typing import Dict, Generator, Optional

import structlog
from prometheus_client import Counter, Gauge, Histogram

from knowledgebeast.utils.observability import (
    api_request_duration,
    api_requests_total,
    cache_operation_duration,
    cache_operations_total,
    chromadb_collection_size,
    embedding_cache_hits,
    embedding_cache_misses,
    query_duration,
    reranking_duration,
    reranking_model_loads_total,
    reranking_requests_total,
    reranking_score_improvement,
    vector_search_duration,
)

logger = structlog.get_logger()


@contextmanager
def timed_operation(
    histogram: Histogram,
    labels: Optional[Dict[str, str]] = None
) -> Generator[None, None, None]:
    """Context manager to time an operation and record it in a histogram.

    Args:
        histogram: Prometheus histogram to record duration
        labels: Optional labels for the metric

    Example:
        with timed_operation(query_duration, {"operation": "search", "status": "success"}):
            results = kb.query("search terms")
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        if labels:
            histogram.labels(**labels).observe(duration)
        else:
            histogram.observe(duration)


def record_query_metrics(operation: str, status: str, duration: float) -> None:
    """Record query metrics.

    Args:
        operation: Operation type (e.g., "search", "ingest")
        status: Operation status ("success" or "error")
        duration: Operation duration in seconds
    """
    query_duration.labels(operation=operation, status=status).observe(duration)
    logger.debug(
        "query_metrics_recorded",
        operation=operation,
        status=status,
        duration_seconds=duration
    )


def record_cache_hit() -> None:
    """Record an embedding cache hit."""
    embedding_cache_hits.inc()


def record_cache_miss() -> None:
    """Record an embedding cache miss."""
    embedding_cache_misses.inc()


def record_vector_search(search_type: str, duration: float) -> None:
    """Record vector search metrics.

    Args:
        search_type: Type of search ("vector", "keyword", "hybrid")
        duration: Search duration in seconds
    """
    vector_search_duration.labels(search_type=search_type).observe(duration)
    logger.debug(
        "vector_search_metrics_recorded",
        search_type=search_type,
        duration_seconds=duration
    )


def record_api_request(
    method: str,
    endpoint: str,
    status_code: int,
    duration: float
) -> None:
    """Record API request metrics.

    Args:
        method: HTTP method (GET, POST, etc.)
        endpoint: API endpoint path
        status_code: HTTP status code
        duration: Request duration in seconds
    """
    api_requests_total.labels(
        method=method,
        endpoint=endpoint,
        status_code=str(status_code)
    ).inc()
    api_request_duration.labels(method=method, endpoint=endpoint).observe(duration)
    logger.debug(
        "api_request_metrics_recorded",
        method=method,
        endpoint=endpoint,
        status_code=status_code,
        duration_seconds=duration
    )


def record_cache_operation(
    operation: str,
    cache_type: str,
    duration: float
) -> None:
    """Record cache operation metrics.

    Args:
        operation: Operation type ("get", "put", "clear")
        cache_type: Cache type ("lru", "embedding")
        duration: Operation duration in seconds
    """
    cache_operations_total.labels(operation=operation, cache_type=cache_type).inc()
    cache_operation_duration.labels(
        operation=operation,
        cache_type=cache_type
    ).observe(duration)
    logger.debug(
        "cache_operation_metrics_recorded",
        operation=operation,
        cache_type=cache_type,
        duration_seconds=duration
    )


def update_collection_size(project_id: str, size: int) -> None:
    """Update ChromaDB collection size metric.

    Args:
        project_id: Project identifier
        size: Number of documents in collection
    """
    chromadb_collection_size.labels(project_id=project_id).set(size)
    logger.debug(
        "collection_size_updated",
        project_id=project_id,
        size=size
    )


@contextmanager
def measure_cache_operation(
    operation: str,
    cache_type: str
) -> Generator[None, None, None]:
    """Context manager to measure and record cache operations.

    Args:
        operation: Operation type ("get", "put", "clear")
        cache_type: Cache type ("lru", "embedding")

    Example:
        with measure_cache_operation("get", "lru"):
            value = cache.get(key)
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        record_cache_operation(operation, cache_type, duration)


@contextmanager
def measure_vector_search(search_type: str) -> Generator[None, None, None]:
    """Context manager to measure and record vector search operations.

    Args:
        search_type: Type of search ("vector", "keyword", "hybrid")

    Example:
        with measure_vector_search("hybrid"):
            results = engine.search_hybrid(query)
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        record_vector_search(search_type, duration)


def record_reranking_metrics(
    reranker_type: str,
    status: str,
    duration: float
) -> None:
    """Record re-ranking metrics.

    Args:
        reranker_type: Type of reranker ("cross_encoder", "mmr")
        status: Operation status ("success" or "error")
        duration: Operation duration in seconds
    """
    reranking_requests_total.labels(reranker_type=reranker_type, status=status).inc()
    reranking_duration.labels(reranker_type=reranker_type, status=status).observe(duration)
    logger.debug(
        "reranking_metrics_recorded",
        reranker_type=reranker_type,
        status=status,
        duration_seconds=duration
    )


def record_model_load(model_name: str) -> None:
    """Record a model load event.

    Args:
        model_name: Name of the model that was loaded
    """
    reranking_model_loads_total.labels(model_name=model_name).inc()
    logger.debug("model_load_recorded", model_name=model_name)


def record_score_improvement(
    reranker_type: str,
    vector_score: float,
    rerank_score: float
) -> None:
    """Record score improvement from re-ranking.

    Args:
        reranker_type: Type of reranker ("cross_encoder", "mmr")
        vector_score: Original vector similarity score
        rerank_score: Re-ranking score
    """
    improvement = rerank_score - vector_score
    reranking_score_improvement.labels(reranker_type=reranker_type).observe(improvement)
    logger.debug(
        "score_improvement_recorded",
        reranker_type=reranker_type,
        improvement=improvement
    )


@contextmanager
def measure_reranking(reranker_type: str) -> Generator[None, None, None]:
    """Context manager to measure and record re-ranking operations.

    Args:
        reranker_type: Type of reranker ("cross_encoder", "mmr")

    Example:
        with measure_reranking("cross_encoder"):
            reranked_results = reranker.rerank(query, results)
    """
    start_time = time.time()
    status = "success"
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        duration = time.time() - start_time
        record_reranking_metrics(reranker_type, status, duration)
