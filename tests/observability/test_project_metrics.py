"""Tests for project-scoped metrics and observability.

This module tests that Prometheus metrics are properly recorded for
project operations including queries, ingestion, cache hits/misses, and errors.
"""

import pytest
import tempfile
from pathlib import Path
from prometheus_client import REGISTRY

from knowledgebeast.utils.metrics import (
    measure_project_query,
    record_project_cache_hit,
    record_project_cache_miss,
    record_project_error,
    record_project_ingest,
)
from knowledgebeast.utils.observability import (
    project_queries_total,
    project_query_duration,
    project_cache_hits_total,
    project_cache_misses_total,
    project_ingests_total,
    project_errors_total,
)


@pytest.fixture
def sample_project_id():
    """Sample project ID for testing."""
    return "proj_metrics_test"


def get_metric_value(metric, labels=None):
    """Helper to get current value of a Prometheus metric.

    Args:
        metric: Prometheus metric object
        labels: Dict of label values

    Returns:
        Current metric value
    """
    if labels:
        return metric.labels(**labels)._value.get()
    else:
        # For counters without labels
        samples = list(metric.collect())[0].samples
        if samples:
            return samples[0].value
        return 0


def test_project_query_metrics_recorded(sample_project_id):
    """Test that project query metrics are recorded."""
    # Get initial counts
    initial_count = get_metric_value(
        project_queries_total,
        {"project_id": sample_project_id, "status": "success"}
    )

    # Record a successful query
    with measure_project_query(sample_project_id):
        pass  # Simulate query

    # Verify counter incremented
    new_count = get_metric_value(
        project_queries_total,
        {"project_id": sample_project_id, "status": "success"}
    )
    assert new_count == initial_count + 1

    # Verify duration was recorded (histogram count should increase)
    duration_metric = project_query_duration.labels(project_id=sample_project_id)
    # Access the histogram's sample count
    samples = list(duration_metric.collect())[0].samples
    count_sample = [s for s in samples if s.name.endswith('_count')][0]
    assert count_sample.value > 0


def test_project_ingest_metrics_recorded(sample_project_id):
    """Test that project ingest metrics are recorded."""
    # Get initial success count
    initial_success = get_metric_value(
        project_ingests_total,
        {"project_id": sample_project_id, "status": "success"}
    )

    # Get initial error count
    initial_error = get_metric_value(
        project_ingests_total,
        {"project_id": sample_project_id, "status": "error"}
    )

    # Record successful ingestion
    record_project_ingest(sample_project_id, "success")

    # Verify success counter incremented
    new_success = get_metric_value(
        project_ingests_total,
        {"project_id": sample_project_id, "status": "success"}
    )
    assert new_success == initial_success + 1

    # Record failed ingestion
    record_project_ingest(sample_project_id, "error")

    # Verify error counter incremented
    new_error = get_metric_value(
        project_ingests_total,
        {"project_id": sample_project_id, "status": "error"}
    )
    assert new_error == initial_error + 1


def test_project_metrics_isolation(sample_project_id):
    """Test that metrics for project A don't affect project B."""
    project_a = "proj_a"
    project_b = "proj_b"

    # Get initial counts for both projects
    initial_a = get_metric_value(
        project_cache_hits_total,
        {"project_id": project_a}
    )
    initial_b = get_metric_value(
        project_cache_hits_total,
        {"project_id": project_b}
    )

    # Record cache hit for project A
    record_project_cache_hit(project_a)

    # Verify only project A's metric changed
    new_a = get_metric_value(
        project_cache_hits_total,
        {"project_id": project_a}
    )
    new_b = get_metric_value(
        project_cache_hits_total,
        {"project_id": project_b}
    )

    assert new_a == initial_a + 1
    assert new_b == initial_b  # Should not change


def test_project_error_metrics(sample_project_id):
    """Test that project error metrics are recorded with error types."""
    error_types = ["QueryError", "IngestError", "ValidationError"]

    for error_type in error_types:
        # Get initial count
        initial_count = get_metric_value(
            project_errors_total,
            {"project_id": sample_project_id, "error_type": error_type}
        )

        # Record error
        record_project_error(sample_project_id, error_type)

        # Verify counter incremented
        new_count = get_metric_value(
            project_errors_total,
            {"project_id": sample_project_id, "error_type": error_type}
        )
        assert new_count == initial_count + 1


def test_project_cache_hit_metrics(sample_project_id):
    """Test that cache hit metrics are recorded."""
    # Get initial count
    initial_hits = get_metric_value(
        project_cache_hits_total,
        {"project_id": sample_project_id}
    )

    # Record multiple cache hits
    for _ in range(5):
        record_project_cache_hit(sample_project_id)

    # Verify counter incremented by 5
    new_hits = get_metric_value(
        project_cache_hits_total,
        {"project_id": sample_project_id}
    )
    assert new_hits == initial_hits + 5


def test_project_cache_miss_metrics(sample_project_id):
    """Test that cache miss metrics are recorded."""
    # Get initial count
    initial_misses = get_metric_value(
        project_cache_misses_total,
        {"project_id": sample_project_id}
    )

    # Record multiple cache misses
    for _ in range(3):
        record_project_cache_miss(sample_project_id)

    # Verify counter incremented by 3
    new_misses = get_metric_value(
        project_cache_misses_total,
        {"project_id": sample_project_id}
    )
    assert new_misses == initial_misses + 3


def test_project_metrics_labels(sample_project_id):
    """Test that all project metrics have project_id label."""
    # Record various metrics
    record_project_cache_hit(sample_project_id)
    record_project_cache_miss(sample_project_id)
    record_project_ingest(sample_project_id, "success")
    record_project_error(sample_project_id, "TestError")
    with measure_project_query(sample_project_id):
        pass

    # Verify all metrics can be retrieved with project_id label
    metrics_with_project_id = [
        (project_queries_total, {"project_id": sample_project_id, "status": "success"}),
        (project_cache_hits_total, {"project_id": sample_project_id}),
        (project_cache_misses_total, {"project_id": sample_project_id}),
        (project_ingests_total, {"project_id": sample_project_id, "status": "success"}),
        (project_errors_total, {"project_id": sample_project_id, "error_type": "TestError"}),
    ]

    for metric, labels in metrics_with_project_id:
        # Should not raise exception and should have a value
        value = get_metric_value(metric, labels)
        assert value >= 0  # All counters should be non-negative


def test_metrics_endpoint_accessible():
    """Test that metrics can be collected and formatted for /metrics endpoint."""
    from prometheus_client import generate_latest
    from knowledgebeast.utils.observability import metrics_registry

    # Record some test metrics
    test_project = "proj_metrics_endpoint_test"
    record_project_cache_hit(test_project)
    record_project_cache_miss(test_project)
    record_project_ingest(test_project, "success")

    # Generate metrics output (as would be served by /metrics)
    metrics_output = generate_latest(metrics_registry)

    # Verify output is bytes (Prometheus format)
    assert isinstance(metrics_output, bytes)

    # Decode and verify it contains our project metrics
    metrics_text = metrics_output.decode('utf-8')

    # Check for our project metrics
    assert "kb_project_cache_hits_total" in metrics_text
    assert "kb_project_cache_misses_total" in metrics_text
    assert "kb_project_ingests_total" in metrics_text

    # Check for project_id label
    assert f'project_id="{test_project}"' in metrics_text
