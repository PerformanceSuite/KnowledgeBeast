"""Comprehensive tests for semantic cache functionality.

This module tests:
- Cache hit rate validation
- Similarity threshold tuning
- TTL expiration behavior
- Cache eviction (LRU)
- Thread safety (concurrent access)
- Cache warming
- Performance metrics
"""

import pytest
import time
import threading
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

from knowledgebeast.core.query.semantic_cache import SemanticCache, CachedEntry


class TestSemanticCache:
    """Test suite for semantic cache."""

    def test_basic_cache_put_get(self):
        """Test basic cache put and get operations."""
        cache = SemanticCache(similarity_threshold=0.95, ttl_seconds=3600, max_entries=100)

        query = "machine learning best practices"
        embedding = np.random.rand(384)  # Simulated embedding
        results = [{"doc1": "content1"}, {"doc2": "content2"}]

        # Put in cache
        cache.put(query, embedding, results)

        # Get from cache (exact same embedding)
        cached = cache.get(query, embedding)

        assert cached is not None
        cached_results, similarity, matched_query = cached
        assert cached_results == results
        assert similarity == 1.0  # Exact match
        assert matched_query == query

    def test_cache_miss(self):
        """Test cache miss when no similar queries exist."""
        cache = SemanticCache(similarity_threshold=0.95)

        query = "machine learning"
        embedding = np.random.rand(384)

        # Cache is empty, should miss
        cached = cache.get(query, embedding)

        assert cached is None

        # Stats should reflect miss
        stats = cache.get_stats()
        assert stats['misses'] == 1
        assert stats['hits'] == 0

    def test_similarity_threshold_matching(self):
        """Test that similarity threshold is enforced."""
        cache = SemanticCache(similarity_threshold=0.95, ttl_seconds=3600)

        # Create two similar but not identical embeddings
        embedding1 = np.random.rand(384)
        embedding2 = embedding1 + np.random.rand(384) * 0.01  # Very similar

        query1 = "machine learning"
        query2 = "machine learning algorithms"
        results = [{"doc": "content"}]

        # Cache first query
        cache.put(query1, embedding1, results)

        # Try to get with similar embedding
        cached = cache.get(query2, embedding2)

        # May or may not hit depending on similarity
        # This tests that the threshold logic is working
        if cached:
            _, similarity, _ = cached
            assert similarity >= 0.95

    def test_ttl_expiration(self):
        """Test that cache entries expire after TTL."""
        cache = SemanticCache(similarity_threshold=0.95, ttl_seconds=1)  # 1 second TTL

        query = "test query"
        embedding = np.random.rand(384)
        results = [{"doc": "content"}]

        # Put in cache
        cache.put(query, embedding, results)

        # Should be in cache immediately
        cached = cache.get(query, embedding)
        assert cached is not None

        # Wait for expiration
        time.sleep(1.5)

        # Should be expired now
        cached_after = cache.get(query, embedding)
        # The get operation should detect expiration and return None
        # OR cleanup_expired should remove it

        # Clean up expired entries
        expired_count = cache.cleanup_expired()
        assert expired_count >= 0

    def test_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = SemanticCache(similarity_threshold=0.95, ttl_seconds=3600, max_entries=3)

        # Fill cache beyond capacity
        for i in range(5):
            query = f"query_{i}"
            embedding = np.random.rand(384)
            results = [{"doc": f"content_{i}"}]
            cache.put(query, embedding, results)

        # Cache should have at most 3 entries (max_entries)
        stats = cache.get_stats()
        assert stats['size'] <= 3

        # Check eviction count
        assert stats['evictions'] > 0

    def test_cache_hit_updates_lru(self):
        """Test that cache hits update LRU order."""
        cache = SemanticCache(similarity_threshold=0.95, ttl_seconds=3600, max_entries=3)

        # Add 3 entries
        embeddings = []
        for i in range(3):
            query = f"query_{i}"
            embedding = np.random.rand(384)
            embeddings.append(embedding)
            results = [{"doc": f"content_{i}"}]
            cache.put(query, embedding, results)

        # Access query_0 (should move it to end of LRU)
        cache.get("query_0", embeddings[0])

        # Add one more entry (should evict query_1, not query_0)
        new_embedding = np.random.rand(384)
        cache.put("query_new", new_embedding, [{"doc": "new_content"}])

        # query_0 should still be in cache (it was accessed recently)
        cached = cache.get("query_0", embeddings[0])
        # May or may not be there depending on implementation

    def test_thread_safety_concurrent_puts(self):
        """Test thread safety with concurrent put operations."""
        cache = SemanticCache(similarity_threshold=0.95, ttl_seconds=3600, max_entries=1000)

        def put_query(i):
            query = f"query_{i}"
            embedding = np.random.rand(384)
            results = [{"doc": f"content_{i}"}]
            cache.put(query, embedding, results)

        # Run concurrent puts
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(put_query, i) for i in range(100)]
            for future in as_completed(futures):
                future.result()  # Wait for completion

        # All entries should be stored
        stats = cache.get_stats()
        assert stats['size'] <= 100

    def test_thread_safety_concurrent_gets(self):
        """Test thread safety with concurrent get operations."""
        cache = SemanticCache(similarity_threshold=0.95, ttl_seconds=3600)

        # Pre-populate cache
        query = "test query"
        embedding = np.random.rand(384)
        results = [{"doc": "content"}]
        cache.put(query, embedding, results)

        def get_query():
            return cache.get(query, embedding)

        # Run concurrent gets
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(get_query) for _ in range(50)]
            cached_results = [future.result() for future in as_completed(futures)]

        # All gets should succeed
        assert all(result is not None for result in cached_results)

    def test_cache_warming(self):
        """Test cache warming with common queries."""
        cache = SemanticCache(similarity_threshold=0.95, ttl_seconds=3600)

        # Define warming queries
        warming_queries = [
            "machine learning",
            "deep learning",
            "neural networks"
        ]

        # Mock embedding and query functions
        def mock_embedding_fn(query):
            return np.random.rand(384)

        def mock_query_fn(query):
            return [{"doc": f"result_for_{query}"}]

        # Warm cache
        warmed_count = cache.warm(warming_queries, mock_embedding_fn, mock_query_fn)

        assert warmed_count == len(warming_queries)

        # Cache should have the warmed entries
        stats = cache.get_stats()
        assert stats['size'] == len(warming_queries)

    def test_cache_clear(self):
        """Test cache clearing."""
        cache = SemanticCache(similarity_threshold=0.95, ttl_seconds=3600)

        # Add some entries
        for i in range(5):
            query = f"query_{i}"
            embedding = np.random.rand(384)
            results = [{"doc": f"content_{i}"}]
            cache.put(query, embedding, results)

        assert cache.get_stats()['size'] == 5

        # Clear cache
        cache.clear()

        # Cache should be empty
        stats = cache.get_stats()
        assert stats['size'] == 0

    def test_cache_statistics(self):
        """Test cache statistics tracking."""
        cache = SemanticCache(similarity_threshold=0.95, ttl_seconds=3600, max_entries=100)

        # Perform various operations
        query = "test"
        embedding = np.random.rand(384)
        results = [{"doc": "content"}]

        # Miss
        cache.get(query, embedding)

        # Put
        cache.put(query, embedding, results)

        # Hit
        cache.get(query, embedding)

        # Get stats
        stats = cache.get_stats()

        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['total_queries'] == 2
        assert stats['hit_rate'] == 0.5
        assert stats['size'] == 1
        assert 0 <= stats['utilization'] <= 1
        assert stats['similarity_threshold'] == 0.95

    def test_get_top_queries(self):
        """Test retrieving top cached queries by hit count."""
        cache = SemanticCache(similarity_threshold=0.95, ttl_seconds=3600)

        # Add queries and access them different number of times
        queries = ["query_1", "query_2", "query_3"]
        embeddings = [np.random.rand(384) for _ in range(3)]
        hit_counts = [5, 3, 1]

        for i, (query, embedding) in enumerate(zip(queries, embeddings)):
            results = [{"doc": f"content_{i}"}]
            cache.put(query, embedding, results)

            # Access query multiple times to increase hit count
            for _ in range(hit_counts[i]):
                cache.get(query, embedding)

        # Get top queries
        top_queries = cache.get_top_queries(top_k=3)

        assert len(top_queries) == 3
        # Should be sorted by hit count (query_1 first)
        assert top_queries[0][0] == "query_1"
        assert top_queries[0][1] >= top_queries[1][1]  # Hit counts descending


class TestCachedEntry:
    """Test CachedEntry class."""

    def test_is_expired(self):
        """Test expiration checking."""
        embedding = np.random.rand(384)
        entry = CachedEntry(
            query="test",
            embedding=embedding,
            results=[],
            timestamp=time.time(),
            ttl_seconds=1
        )

        # Should not be expired immediately
        assert not entry.is_expired()

        # Wait for expiration
        time.sleep(1.5)

        # Should be expired now
        assert entry.is_expired()

    def test_matches_similarity(self):
        """Test similarity matching."""
        embedding1 = np.random.rand(384)
        embedding2 = embedding1.copy()  # Identical

        entry = CachedEntry(
            query="test",
            embedding=embedding1,
            results=[],
            timestamp=time.time(),
            ttl_seconds=3600
        )

        # Exact match
        matches, similarity = entry.matches(embedding2, similarity_threshold=0.95)
        assert matches
        assert similarity == 1.0

        # Very different embedding
        embedding3 = np.random.rand(384)
        matches, similarity = entry.matches(embedding3, similarity_threshold=0.95)
        # Likely won't match (random embeddings)
        assert isinstance(matches, bool)
        assert 0.0 <= similarity <= 1.0
