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
    project_api_key_validations_total,
    project_api_keys_active,
    project_cache_hits_total,
    project_cache_misses_total,
    project_documents_total,
    project_errors_total,
    project_ingests_total,
    project_queries_total,
    project_query_duration,
    query_duration,
    query_expansion_duration,
    query_expansions_total,
    reranking_duration,
    reranking_model_loads_total,
    reranking_requests_total,
    reranking_score_improvement,
    semantic_cache_hits_total,
    semantic_cache_misses_total,
    semantic_cache_similarity_scores,
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


# Query expansion metrics (Phase 2)
def record_query_expansion(duration: float) -> None:
    """Record query expansion metrics.

    Args:
        duration: Expansion duration in seconds
    """
    query_expansions_total.inc()
    query_expansion_duration.observe(duration)
    logger.debug(
        "query_expansion_metrics_recorded",
        duration_seconds=duration
    )


@contextmanager
def measure_query_expansion() -> Generator[None, None, None]:
    """Context manager to measure and record query expansion operations.

    Example:
        with measure_query_expansion():
            result = expander.expand(query)
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        record_query_expansion(duration)


# Semantic cache metrics (Phase 2)
def record_semantic_cache_hit(similarity: float) -> None:
    """Record semantic cache hit with similarity score.

    Args:
        similarity: Similarity score (0-1)
    """
    semantic_cache_hits_total.inc()
    semantic_cache_similarity_scores.observe(similarity)
    logger.debug(
        "semantic_cache_hit_recorded",
        similarity=similarity
    )


def record_semantic_cache_miss() -> None:
    """Record semantic cache miss."""
    semantic_cache_misses_total.inc()
    logger.debug("semantic_cache_miss_recorded")


# Re-ranking metrics (Phase 2)
def record_model_load(model_name: str) -> None:
    """Record re-ranking model load.

    Args:
        model_name: Name of the loaded model
    """
    reranking_model_loads_total.labels(model_name=model_name).inc()
    logger.debug(
        "reranking_model_loaded",
        model_name=model_name
    )


def record_score_improvement(
    reranker_type: str,
    vector_score: float,
    rerank_score: float
) -> None:
    """Record score improvement from re-ranking.

    Args:
        reranker_type: Type of reranker ("cross_encoder", "mmr")
        vector_score: Original vector search score
        rerank_score: Re-ranked score
    """
    improvement = rerank_score - vector_score
    reranking_score_improvement.labels(reranker_type=reranker_type).observe(improvement)
    logger.debug(
        "reranking_score_improvement_recorded",
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
            results = reranker.rerank(query, results)
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
        reranking_duration.labels(reranker_type=reranker_type, status=status).observe(duration)
        reranking_requests_total.labels(reranker_type=reranker_type, status=status).inc()
        logger.debug(
            "reranking_metrics_recorded",
            reranker_type=reranker_type,
            status=status,
            duration_seconds=duration
        )


# ============================================================================
# Per-Project Metrics Helpers (v2.3.0)
# ============================================================================


def record_project_query(project_id: str, status: str, duration: float) -> None:
    """Record project-scoped query metrics.

    Args:
        project_id: Project identifier
        status: Query status ("success" or "error")
        duration: Query duration in seconds

    Example:
        start = time.time()
        try:
            results = query_project(project_id, query)
            record_project_query(project_id, "success", time.time() - start)
        except Exception:
            record_project_query(project_id, "error", time.time() - start)
            raise
    """
    project_queries_total.labels(project_id=project_id, status=status).inc()
    project_query_duration.labels(project_id=project_id).observe(duration)
    logger.debug(
        "project_query_metrics_recorded",
        project_id=project_id,
        status=status,
        duration_seconds=duration
    )


@contextmanager
def measure_project_query(project_id: str) -> Generator[None, None, None]:
    """Context manager to measure and record project query operations.

    Args:
        project_id: Project identifier

    Example:
        with measure_project_query("proj_123"):
            results = collection.query(query_text=query)
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
        record_project_query(project_id, status, duration)


def record_project_cache_hit(project_id: str) -> None:
    """Record project cache hit.

    Args:
        project_id: Project identifier
    """
    project_cache_hits_total.labels(project_id=project_id).inc()
    logger.debug("project_cache_hit_recorded", project_id=project_id)


def record_project_cache_miss(project_id: str) -> None:
    """Record project cache miss.

    Args:
        project_id: Project identifier
    """
    project_cache_misses_total.labels(project_id=project_id).inc()
    logger.debug("project_cache_miss_recorded", project_id=project_id)


def record_project_ingest(project_id: str, status: str) -> None:
    """Record project document ingestion.

    Args:
        project_id: Project identifier
        status: Ingest status ("success" or "error")
    """
    project_ingests_total.labels(project_id=project_id, status=status).inc()
    logger.debug(
        "project_ingest_metrics_recorded",
        project_id=project_id,
        status=status
    )


def record_project_error(project_id: str, error_type: str) -> None:
    """Record project error.

    Args:
        project_id: Project identifier
        error_type: Type of error (e.g., "ValidationError", "NotFoundError")
    """
    project_errors_total.labels(project_id=project_id, error_type=error_type).inc()
    logger.debug(
        "project_error_recorded",
        project_id=project_id,
        error_type=error_type
    )


def update_project_document_count(project_id: str, count: int) -> None:
    """Update project document count gauge.

    Args:
        project_id: Project identifier
        count: Total number of documents in project
    """
    project_documents_total.labels(project_id=project_id).set(count)
    logger.debug(
        "project_document_count_updated",
        project_id=project_id,
        count=count
    )


def record_project_api_key_validation(project_id: str, result: str) -> None:
    """Record project API key validation attempt.

    Args:
        project_id: Project identifier
        result: Validation result ("success" or "failure")
    """
    project_api_key_validations_total.labels(
        project_id=project_id,
        result=result
    ).inc()
    logger.debug(
        "project_api_key_validation_recorded",
        project_id=project_id,
        result=result
    )


def update_project_active_api_keys(project_id: str, count: int) -> None:
    """Update number of active API keys for project.

    Args:
        project_id: Project identifier
        count: Number of active (non-revoked) API keys
    """
    project_api_keys_active.labels(project_id=project_id).set(count)
    logger.debug(
        "project_active_api_keys_updated",
        project_id=project_id,
        count=count
    )
