"""Performance benchmarks for hybrid search modes.

Benchmarks:
- Vector search latency (P50, P95, P99)
- Keyword search latency
- Hybrid search latency
- MMR re-ranking latency
- Concurrent throughput
- Cache performance
"""

import pytest
import time
import statistics
from pathlib import Path
import tempfile

from knowledgebeast.core.repository import DocumentRepository
from knowledgebeast.core.query_engine import HybridQueryEngine, QueryEngine


@pytest.fixture
def large_repository():
    """Create a repository with many documents for benchmarking."""
    repo = DocumentRepository()

    # Generate 100 documents
    topics = [
        "audio processing and signal analysis",
        "machine learning algorithms and models",
        "web development frameworks and tools",
        "database management and optimization",
        "cloud computing and distributed systems",
        "cybersecurity and encryption methods",
        "mobile app development and design",
        "data visualization and analytics",
        "natural language processing techniques",
        "computer vision and image recognition"
    ]

    for i in range(100):
        topic = topics[i % len(topics)]
        doc_id = f"doc_{i:03d}"
        doc_data = {
            'name': f'Document {i}: {topic}',
            'content': f'This is document {i} about {topic}. It contains detailed information about various aspects of {topic}. ' * 10,
            'path': f'docs/doc_{i}.md'
        }

        repo.add_document(doc_id, doc_data)

        # Build index
        terms = doc_data['content'].lower().split()
        for term in set(terms):  # Use set to avoid duplicates
            repo.index_term(term, doc_id)

    return repo


@pytest.fixture
def benchmark_engine(large_repository):
    """Create HybridQueryEngine for benchmarking."""
    return HybridQueryEngine(
        large_repository,
        model_name="all-MiniLM-L6-v2",
        alpha=0.7,
        cache_size=1000
    )


class TestVectorSearchPerformance:
    """Benchmark vector search performance."""

    def test_vector_search_latency(self, benchmark_engine):
        """Test vector search latency meets P99 < 150ms target."""
        latencies = []
        queries = [
            "audio signal processing",
            "machine learning models",
            "web development",
            "database optimization",
            "cloud computing"
        ]

        # Warm-up
        for query in queries:
            benchmark_engine.search_vector(query, top_k=10)

        # Measure latencies
        for _ in range(50):
            query = queries[_ % len(queries)]
            start = time.perf_counter()
            results = benchmark_engine.search_vector(query, top_k=10)
            latency = (time.perf_counter() - start) * 1000  # Convert to ms

            latencies.append(latency)
            assert len(results) > 0

        # Calculate percentiles
        p50 = statistics.median(latencies)
        p95 = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        p99 = statistics.quantiles(latencies, n=100)[98]  # 99th percentile

        print(f"\nVector Search Latency:")
        print(f"  P50: {p50:.2f}ms")
        print(f"  P95: {p95:.2f}ms")
        print(f"  P99: {p99:.2f}ms")

        # Performance target: P99 < 150ms
        assert p99 < 150, f"P99 latency {p99:.2f}ms exceeds 150ms target"

    def test_vector_search_throughput(self, benchmark_engine):
        """Test vector search throughput."""
        queries = [
            "audio processing",
            "machine learning",
            "web development"
        ]

        start = time.perf_counter()
        total_queries = 100

        for i in range(total_queries):
            query = queries[i % len(queries)]
            benchmark_engine.search_vector(query, top_k=10)

        elapsed = time.perf_counter() - start
        throughput = total_queries / elapsed

        print(f"\nVector Search Throughput: {throughput:.1f} queries/sec")

        # Should process at least 10 queries per second
        assert throughput > 10


class TestKeywordSearchPerformance:
    """Benchmark keyword search performance."""

    def test_keyword_search_latency(self, benchmark_engine):
        """Test keyword search latency."""
        latencies = []
        queries = [
            "audio processing",
            "machine learning",
            "database",
            "cloud",
            "security"
        ]

        # Measure latencies
        for _ in range(50):
            query = queries[_ % len(queries)]
            start = time.perf_counter()
            results = benchmark_engine.search_keyword(query)
            latency = (time.perf_counter() - start) * 1000

            latencies.append(latency)

        p50 = statistics.median(latencies)
        p95 = statistics.quantiles(latencies, n=20)[18]
        p99 = statistics.quantiles(latencies, n=100)[98]

        print(f"\nKeyword Search Latency:")
        print(f"  P50: {p50:.2f}ms")
        print(f"  P95: {p95:.2f}ms")
        print(f"  P99: {p99:.2f}ms")

        # Keyword search should be very fast
        assert p99 < 50, f"Keyword search P99 {p99:.2f}ms too slow"


class TestHybridSearchPerformance:
    """Benchmark hybrid search performance."""

    def test_hybrid_search_latency(self, benchmark_engine):
        """Test hybrid search latency."""
        latencies = []
        queries = [
            "audio signal analysis",
            "machine learning algorithms",
            "web development frameworks"
        ]

        # Warm-up
        for query in queries:
            benchmark_engine.search_hybrid(query, top_k=10)

        # Measure latencies
        for _ in range(50):
            query = queries[_ % len(queries)]
            start = time.perf_counter()
            results = benchmark_engine.search_hybrid(query, top_k=10)
            latency = (time.perf_counter() - start) * 1000

            latencies.append(latency)

        p50 = statistics.median(latencies)
        p95 = statistics.quantiles(latencies, n=20)[18]
        p99 = statistics.quantiles(latencies, n=100)[98]

        print(f"\nHybrid Search Latency:")
        print(f"  P50: {p50:.2f}ms")
        print(f"  P95: {p95:.2f}ms")
        print(f"  P99: {p99:.2f}ms")

        # Hybrid should be slightly slower than pure vector but still < 200ms
        assert p99 < 200, f"Hybrid search P99 {p99:.2f}ms too slow"

    def test_hybrid_search_different_alphas(self, benchmark_engine):
        """Test hybrid search performance with different alpha values."""
        alphas = [0.0, 0.3, 0.5, 0.7, 0.9, 1.0]
        query = "audio processing machine learning"

        for alpha in alphas:
            latencies = []

            for _ in range(20):
                start = time.perf_counter()
                results = benchmark_engine.search_hybrid(query, alpha=alpha, top_k=10)
                latency = (time.perf_counter() - start) * 1000
                latencies.append(latency)

            avg_latency = statistics.mean(latencies)
            print(f"\nHybrid Search (alpha={alpha}): {avg_latency:.2f}ms avg")

            # All alpha values should have reasonable performance
            assert avg_latency < 150


class TestMMRPerformance:
    """Benchmark MMR re-ranking performance."""

    def test_mmr_latency(self, benchmark_engine):
        """Test MMR re-ranking latency."""
        latencies = []
        queries = ["audio processing", "machine learning", "web development"]

        for _ in range(30):
            query = queries[_ % len(queries)]
            start = time.perf_counter()
            results = benchmark_engine.search_with_mmr(query, lambda_param=0.5, top_k=10)
            latency = (time.perf_counter() - start) * 1000

            latencies.append(latency)

        p50 = statistics.median(latencies)
        p99 = statistics.quantiles(latencies, n=100)[98]

        print(f"\nMMR Re-ranking Latency:")
        print(f"  P50: {p50:.2f}ms")
        print(f"  P99: {p99:.2f}ms")

        # MMR should complete in reasonable time
        assert p99 < 300, f"MMR P99 {p99:.2f}ms too slow"


class TestDiversityPerformance:
    """Benchmark diversity sampling performance."""

    def test_diversity_latency(self, benchmark_engine):
        """Test diversity sampling latency."""
        latencies = []
        queries = ["audio", "machine learning", "database"]

        for _ in range(30):
            query = queries[_ % len(queries)]
            start = time.perf_counter()
            results = benchmark_engine.search_with_diversity(
                query,
                diversity_threshold=0.8,
                top_k=10
            )
            latency = (time.perf_counter() - start) * 1000

            latencies.append(latency)

        p50 = statistics.median(latencies)
        p99 = statistics.quantiles(latencies, n=100)[98]

        print(f"\nDiversity Sampling Latency:")
        print(f"  P50: {p50:.2f}ms")
        print(f"  P99: {p99:.2f}ms")

        # Diversity should complete in reasonable time
        assert p99 < 300, f"Diversity P99 {p99:.2f}ms too slow"


class TestConcurrentPerformance:
    """Benchmark concurrent search performance."""

    def test_concurrent_vector_search(self, benchmark_engine):
        """Test concurrent vector search throughput."""
        import threading
        import queue

        num_threads = 10
        queries_per_thread = 10
        query = "audio processing machine learning"

        results_queue = queue.Queue()

        def worker():
            start = time.perf_counter()
            for _ in range(queries_per_thread):
                benchmark_engine.search_vector(query, top_k=10)
            elapsed = time.perf_counter() - start
            results_queue.put(elapsed)

        # Run concurrent searches
        start_time = time.perf_counter()
        threads = [threading.Thread(target=worker) for _ in range(num_threads)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        total_elapsed = time.perf_counter() - start_time
        total_queries = num_threads * queries_per_thread
        throughput = total_queries / total_elapsed

        print(f"\nConcurrent Vector Search ({num_threads} threads):")
        print(f"  Total queries: {total_queries}")
        print(f"  Total time: {total_elapsed:.2f}s")
        print(f"  Throughput: {throughput:.1f} queries/sec")

        # Should handle concurrent load
        assert throughput > 5  # At least 5 queries/sec with concurrency


class TestEmbeddingCachePerformance:
    """Benchmark embedding cache performance."""

    def test_cache_hit_performance(self, benchmark_engine):
        """Test performance of cache hits."""
        # Pre-populate cache by searching
        query = "audio processing"
        benchmark_engine.search_vector(query, top_k=10)

        # Measure cache hit latency
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            # Access cached embeddings
            stats = benchmark_engine.get_embedding_stats()
            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)

        avg_latency = statistics.mean(latencies)
        print(f"\nCache Stats Access Latency: {avg_latency:.4f}ms")

        # Cache access should be very fast
        assert avg_latency < 1.0  # Sub-millisecond

    def test_cache_utilization(self, benchmark_engine):
        """Test embedding cache utilization."""
        stats = benchmark_engine.get_embedding_stats()

        print(f"\nEmbedding Cache Stats:")
        print(f"  Size: {stats['size']}")
        print(f"  Capacity: {stats['capacity']}")
        print(f"  Utilization: {stats['utilization']:.1%}")

        # All documents should be cached
        assert stats['size'] == 100
        assert stats['utilization'] <= 1.0


class TestScalability:
    """Test performance scalability."""

    def test_search_scales_with_top_k(self, benchmark_engine):
        """Test that search time scales appropriately with top_k."""
        query = "machine learning algorithms"
        top_k_values = [5, 10, 20, 50]

        for top_k in top_k_values:
            latencies = []

            for _ in range(20):
                start = time.perf_counter()
                results = benchmark_engine.search_vector(query, top_k=top_k)
                latency = (time.perf_counter() - start) * 1000
                latencies.append(latency)

            avg_latency = statistics.mean(latencies)
            print(f"\nVector Search (top_k={top_k}): {avg_latency:.2f}ms avg")

        # Latency should not explode with larger top_k
        # (since we're just sorting, not re-computing)

    def test_hybrid_search_scales_with_alpha(self, benchmark_engine):
        """Test hybrid search scaling with different alpha values."""
        query = "audio processing"
        test_cases = [
            (0.0, "pure keyword"),
            (0.5, "balanced"),
            (1.0, "pure vector")
        ]

        for alpha, description in test_cases:
            latencies = []

            for _ in range(20):
                start = time.perf_counter()
                results = benchmark_engine.search_hybrid(query, alpha=alpha, top_k=10)
                latency = (time.perf_counter() - start) * 1000
                latencies.append(latency)

            avg_latency = statistics.mean(latencies)
            print(f"\nHybrid Search ({description}, alpha={alpha}): {avg_latency:.2f}ms avg")


class TestMemoryUsage:
    """Test memory efficiency."""

    def test_embedding_cache_memory(self, benchmark_engine):
        """Test that embedding cache doesn't grow unbounded."""
        import sys

        # Get cache stats
        stats = benchmark_engine.get_embedding_stats()

        # Calculate approximate memory usage
        # Each embedding is ~384 floats for all-MiniLM-L6-v2
        embedding_size = 384 * 4  # 4 bytes per float32
        total_memory = stats['size'] * embedding_size

        print(f"\nEmbedding Cache Memory Usage:")
        print(f"  Documents cached: {stats['size']}")
        print(f"  Approx memory: {total_memory / 1024:.1f} KB")

        # Should be reasonable for 100 documents
        assert total_memory < 10 * 1024 * 1024  # < 10 MB
