"""Tests for Prometheus metrics integration.

This module tests Prometheus metrics recording and exposure for all
instrumented components of KnowledgeBeast.
"""

import pytest
import time
import numpy as np
from prometheus_client import REGISTRY, CollectorRegistry

from knowledgebeast.core.cache import LRUCache
from knowledgebeast.core.embeddings import EmbeddingEngine
from knowledgebeast.core.vector_store import VectorStore
from knowledgebeast.core.query_engine import HybridQueryEngine
from knowledgebeast.core.repository import DocumentRepository
from knowledgebeast.utils.observability import (
    embedding_cache_hits,
    embedding_cache_misses,
    query_duration,
    vector_search_duration,
    cache_operations_total,
    cache_operation_duration,
    chromadb_collection_size,
    metrics_registry,
)
from knowledgebeast.utils.metrics import (
    record_cache_hit,
    record_cache_miss,
    record_query_metrics,
    record_vector_search,
    record_cache_operation,
    update_collection_size,
    measure_cache_operation,
    measure_vector_search,
)


@pytest.fixture
def embedding_engine():
    """Create embedding engine for testing."""
    return EmbeddingEngine(model_name="all-MiniLM-L6-v2", cache_size=10)


@pytest.fixture
def vector_store(tmp_path):
    """Create vector store for testing."""
    return VectorStore(persist_directory=tmp_path / "chroma_test", collection_name="test")


@pytest.fixture
def hybrid_engine(tmp_path):
    """Create hybrid query engine for testing."""
    repo = DocumentRepository()
    repo.add_document("doc1", {"name": "Test Doc 1", "content": "Machine learning is awesome"})
    repo.add_document("doc2", {"name": "Test Doc 2", "content": "Python programming tutorial"})
    return HybridQueryEngine(repo, cache_size=10)


class TestPrometheusMetrics:
    """Test suite for Prometheus metrics functionality."""

    def test_metrics_registry_exists(self):
        """Test that metrics registry is properly configured."""
        assert metrics_registry is not None
        assert isinstance(metrics_registry, CollectorRegistry)

    def test_cache_hit_counter_increment(self):
        """Test that cache hit counter increments correctly."""
        before = embedding_cache_hits._value._value

        # Record cache hits
        record_cache_hit()
        record_cache_hit()
        record_cache_hit()

        after = embedding_cache_hits._value._value
        assert after == before + 3

    def test_cache_miss_counter_increment(self):
        """Test that cache miss counter increments correctly."""
        before = embedding_cache_misses._value._value

        # Record cache misses
        record_cache_miss()
        record_cache_miss()

        after = embedding_cache_misses._value._value
        assert after == before + 2

    def test_query_duration_histogram(self):
        """Test that query duration histogram records values."""
        # Record query durations
        record_query_metrics("search", "success", 0.05)
        record_query_metrics("search", "success", 0.15)
        record_query_metrics("ingest", "success", 0.25)

        # Get histogram samples
        for metric_family in query_duration.collect():
            for sample in metric_family.samples:
                # Check that our metrics were recorded
                if sample.name.endswith('_count'):
                    if sample.labels.get('operation') == 'search':
                        assert sample.value >= 2
                        return  # Test passed

        pytest.fail("No query duration metrics found")

    def test_vector_search_duration_histogram(self):
        """Test that vector search duration histogram records values."""
        # Record different search types
        record_vector_search("vector", 0.1)
        record_vector_search("keyword", 0.05)
        record_vector_search("hybrid", 0.2)

        samples = vector_search_duration.collect()[0].samples
        count_samples = [s for s in samples if s.name.endswith('_count')]

        # Should have samples for each search type
        assert len(count_samples) >= 3

    def test_cache_operation_metrics(self):
        """Test that cache operation metrics are recorded."""
        before_count = cache_operations_total._metrics.get(("get", "lru"))
        if before_count is None:
            before_count = 0
        else:
            before_count = before_count._value._value

        # Record cache operations
        record_cache_operation("get", "lru", 0.001)
        record_cache_operation("get", "lru", 0.002)

        after_count = cache_operations_total._metrics[("get", "lru")]._value._value
        assert after_count == before_count + 2

    def test_collection_size_gauge(self):
        """Test that collection size gauge updates correctly."""
        project_id = "test_project_123"

        # Update collection size
        update_collection_size(project_id, 100)

        # Retrieve gauge value
        gauge_value = chromadb_collection_size.labels(project_id=project_id)._value._value
        assert gauge_value == 100

        # Update again
        update_collection_size(project_id, 250)
        gauge_value = chromadb_collection_size.labels(project_id=project_id)._value._value
        assert gauge_value == 250

    def test_embedding_cache_metrics_integration(self, embedding_engine):
        """Test that embedding operations record cache metrics."""
        text = "Test text for caching"

        before_misses = embedding_cache_misses._value._value

        # First call - should be cache miss
        _ = embedding_engine.embed(text)
        after_first = embedding_cache_misses._value._value
        assert after_first == before_misses + 1

        before_hits = embedding_cache_hits._value._value

        # Second call - should be cache hit
        _ = embedding_engine.embed(text)
        after_second = embedding_cache_hits._value._value
        assert after_second == before_hits + 1

    def test_lru_cache_metrics_integration(self):
        """Test that LRU cache operations record metrics."""
        cache = LRUCache[str, int](capacity=5)

        before_count = cache_operations_total._metrics.get(("put", "lru"))
        if before_count is None:
            before_value = 0
        else:
            before_value = before_count._value._value

        # Perform cache operations
        cache.put("key1", 100)
        cache.put("key2", 200)

        after_count = cache_operations_total._metrics[("put", "lru")]._value._value
        assert after_count >= before_value + 2

    def test_measure_cache_operation_context_manager(self):
        """Test cache operation measurement context manager."""
        before_count = cache_operations_total._metrics.get(("get", "lru"))
        if before_count is None:
            before_value = 0
        else:
            before_value = before_count._value._value

        with measure_cache_operation("get", "lru"):
            time.sleep(0.01)  # Simulate operation

        after_count = cache_operations_total._metrics[("get", "lru")]._value._value
        assert after_count == before_value + 1

    def test_measure_vector_search_context_manager(self):
        """Test vector search measurement context manager."""
        with measure_vector_search("hybrid"):
            time.sleep(0.01)  # Simulate search

        for metric_family in vector_search_duration.collect():
            for sample in metric_family.samples:
                if sample.labels.get('search_type') == 'hybrid':
                    return  # Test passed

        pytest.fail("No vector search metrics found for hybrid search")

    def test_metrics_labels_validation(self):
        """Test that metrics with labels are properly recorded."""
        # Record metrics with different label combinations
        record_query_metrics("search", "success", 0.1)
        record_query_metrics("search", "error", 0.05)
        record_query_metrics("ingest", "success", 0.2)

        found_labels = set()
        for metric_family in query_duration.collect():
            for sample in metric_family.samples:
                operation = sample.labels.get('operation')
                status = sample.labels.get('status')
                if operation and status:
                    found_labels.add((operation, status))

        # Should have all three label combinations
        assert ('search', 'success') in found_labels
        assert ('search', 'error') in found_labels
        assert ('ingest', 'success') in found_labels

    def test_histogram_buckets_configuration(self):
        """Test that histograms have proper bucket configuration."""
        # Query duration histogram
        query_samples = query_duration.collect()[0].samples
        bucket_samples = [s for s in query_samples if s.name.endswith('_bucket')]

        # Should have multiple buckets
        assert len(bucket_samples) > 5

        # Cache operation duration histogram (should have smaller buckets)
        cache_samples = cache_operation_duration.collect()[0].samples
        cache_buckets = [s for s in cache_samples if s.name.endswith('_bucket')]

        # Should have buckets for sub-millisecond measurements
        assert len(cache_buckets) > 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
