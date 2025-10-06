"""
Performance benchmarks for KnowledgeBeast.

Benchmarks measure:
- Query latency (P50, P95, P99)
- Concurrent throughput
- Cache performance
- Lock contention impact
- Scalability characteristics
"""

import time
import statistics
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import pytest
from knowledgebeast.core.engine import KnowledgeBase
from knowledgebeast.core.config import KnowledgeBeastConfig
from knowledgebeast.core.cache import LRUCache


@pytest.fixture
def kb_instance_small(tmp_path):
    """Create small KB instance for benchmarking."""
    kb_dir = tmp_path / "knowledge"
    kb_dir.mkdir()

    # Create 10 test documents
    for i in range(10):
        content = f"""# Document {i}
This document covers topic_{i % 3} with various keywords.
Audio processing, video analysis, machine learning, data science, NLP.
Document {i} contains information about signal processing and computer vision.
"""
        (kb_dir / f"doc_{i}.md").write_text(content)

    config = KnowledgeBeastConfig(
        knowledge_dirs=[kb_dir],
        auto_warm=False,
        cache_file=str(tmp_path / "cache.json")
    )
    kb = KnowledgeBase(config)
    kb.ingest_all()
    return kb


@pytest.fixture
def kb_instance_warmed(kb_instance_small):
    """Create warmed KB instance with cache populated."""
    # Pre-populate cache with common queries
    common_queries = [
        "audio processing",
        "video analysis",
        "machine learning",
        "data science",
        "NLP natural language"
    ]

    for query in common_queries:
        kb_instance_small.query(query, use_cache=True)

    return kb_instance_small


class TestQueryLatency:
    """Test query latency characteristics."""

    def test_single_query_latency(self, kb_instance_warmed):
        """Measure single query latency (should be < 50ms for small KB)."""
        latencies = []

        for _ in range(100):
            start = time.time()
            kb_instance_warmed.query("audio processing", use_cache=False)
            latency = time.time() - start
            latencies.append(latency)

        p50 = statistics.median(latencies)
        p95 = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        p99 = statistics.quantiles(latencies, n=100)[98]  # 99th percentile

        print(f"\nQuery Latency (uncached):")
        print(f"  P50: {p50*1000:.2f}ms")
        print(f"  P95: {p95*1000:.2f}ms")
        print(f"  P99: {p99*1000:.2f}ms")

        assert p99 < 0.1, f"P99 latency too high: {p99*1000:.2f}ms"

    def test_cached_query_latency(self, kb_instance_warmed):
        """Measure cached query latency (should be < 10ms)."""
        latencies = []

        # First query to populate cache
        kb_instance_warmed.query("audio processing", use_cache=True)

        for _ in range(100):
            start = time.time()
            kb_instance_warmed.query("audio processing", use_cache=True)
            latency = time.time() - start
            latencies.append(latency)

        p50 = statistics.median(latencies)
        p99 = statistics.quantiles(latencies, n=100)[98]

        print(f"\nCached Query Latency:")
        print(f"  P50: {p50*1000:.2f}ms")
        print(f"  P99: {p99*1000:.2f}ms")

        assert p99 < 0.01, f"Cached P99 latency too high: {p99*1000:.2f}ms"

    def test_concurrent_query_latency(self, kb_instance_warmed):
        """Measure latency under concurrent load."""
        num_workers = 10
        queries_per_worker = 20
        all_latencies = []

        def worker(worker_id):
            """Worker performing queries."""
            latencies = []
            queries = ["audio", "video", "ml", "data", "NLP"]

            for i in range(queries_per_worker):
                query = queries[i % len(queries)]
                start = time.time()
                kb_instance_warmed.query(query, use_cache=True)
                latency = time.time() - start
                latencies.append(latency)

            return latencies

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(worker, i) for i in range(num_workers)]
            for future in as_completed(futures):
                all_latencies.extend(future.result())

        p50 = statistics.median(all_latencies)
        p95 = statistics.quantiles(all_latencies, n=20)[18]
        p99 = statistics.quantiles(all_latencies, n=100)[98]

        print(f"\nConcurrent Query Latency ({num_workers} workers):")
        print(f"  P50: {p50*1000:.2f}ms")
        print(f"  P95: {p95*1000:.2f}ms")
        print(f"  P99: {p99*1000:.2f}ms")

        # Under concurrent load, latency should still be reasonable
        assert p99 < 0.15, f"Concurrent P99 latency too high: {p99*1000:.2f}ms"


class TestThroughput:
    """Test system throughput characteristics."""

    def test_sequential_throughput(self, kb_instance_warmed):
        """Measure sequential query throughput."""
        num_queries = 100
        queries = ["audio", "video", "ml", "data", "NLP"] * 20

        start = time.time()
        for query in queries[:num_queries]:
            kb_instance_warmed.query(query, use_cache=True)
        elapsed = time.time() - start

        throughput = num_queries / elapsed

        print(f"\nSequential Throughput: {throughput:.2f} queries/sec")

        assert throughput > 500, f"Sequential throughput too low: {throughput:.2f} q/s"

    def test_concurrent_throughput_10_workers(self, kb_instance_warmed):
        """Measure throughput with 10 concurrent workers."""
        num_workers = 10
        queries_per_worker = 100
        queries = ["audio processing", "video analysis", "machine learning",
                   "data science", "NLP", "signal processing", "computer vision"]

        def worker(worker_id):
            """Worker performing queries."""
            for i in range(queries_per_worker):
                query = queries[i % len(queries)]
                kb_instance_warmed.query(query, use_cache=True)
            return queries_per_worker

        start = time.time()
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(worker, i) for i in range(num_workers)]
            results = [f.result() for f in as_completed(futures)]
        elapsed = time.time() - start

        total_queries = sum(results)
        throughput = total_queries / elapsed

        print(f"\nConcurrent Throughput (10 workers): {throughput:.2f} queries/sec")
        print(f"  Total queries: {total_queries}")
        print(f"  Time: {elapsed:.2f}s")

        # With lock optimization, throughput should be high
        assert throughput > 500, f"Concurrent throughput too low: {throughput:.2f} q/s"

    def test_concurrent_throughput_50_workers(self, kb_instance_warmed):
        """Measure throughput with 50 concurrent workers (stress test)."""
        num_workers = 50
        queries_per_worker = 20
        queries = ["audio", "video", "ml", "data", "NLP"]

        def worker(worker_id):
            """Worker performing queries."""
            for i in range(queries_per_worker):
                query = queries[i % len(queries)]
                kb_instance_warmed.query(query, use_cache=True)
            return queries_per_worker

        start = time.time()
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(worker, i) for i in range(num_workers)]
            results = [f.result() for f in as_completed(futures)]
        elapsed = time.time() - start

        total_queries = sum(results)
        throughput = total_queries / elapsed

        print(f"\nConcurrent Throughput (50 workers): {throughput:.2f} queries/sec")
        print(f"  Total queries: {total_queries}")
        print(f"  Time: {elapsed:.2f}s")

        # Even under heavy load, throughput should be decent
        assert throughput > 300, f"Heavy load throughput too low: {throughput:.2f} q/s"


class TestCachePerformance:
    """Test cache performance characteristics."""

    def test_cache_hit_performance(self):
        """Measure cache hit vs miss performance."""
        cache = LRUCache[str, list](capacity=100)

        # Populate cache
        for i in range(100):
            cache.put(f"key_{i}", [f"value_{j}" for j in range(10)])

        # Measure hit latency
        hit_latencies = []
        for _ in range(1000):
            start = time.time()
            cache.get("key_50")
            hit_latencies.append(time.time() - start)

        # Measure miss latency
        miss_latencies = []
        for _ in range(1000):
            start = time.time()
            cache.get("nonexistent_key")
            miss_latencies.append(time.time() - start)

        avg_hit = statistics.mean(hit_latencies)
        avg_miss = statistics.mean(miss_latencies)

        print(f"\nCache Performance:")
        print(f"  Hit latency: {avg_hit*1000000:.2f}μs")
        print(f"  Miss latency: {avg_miss*1000000:.2f}μs")

        # Both should be very fast (< 100μs)
        assert avg_hit < 0.0001, f"Cache hit too slow: {avg_hit*1000000:.2f}μs"
        assert avg_miss < 0.0001, f"Cache miss too slow: {avg_miss*1000000:.2f}μs"

    def test_cache_hit_ratio_improvement(self, kb_instance_small):
        """Measure cache hit ratio improvement over time."""
        queries = ["audio processing", "video analysis", "machine learning"] * 50

        # Run queries
        for query in queries:
            kb_instance_small.query(query, use_cache=True)

        stats = kb_instance_small.get_stats()

        # With repeated queries, hit rate should be high
        hit_rate = stats['cache_hits'] / (stats['cache_hits'] + stats['cache_misses'])

        print(f"\nCache Hit Ratio: {hit_rate*100:.1f}%")
        print(f"  Hits: {stats['cache_hits']}")
        print(f"  Misses: {stats['cache_misses']}")

        assert hit_rate > 0.90, f"Cache hit ratio too low: {hit_rate*100:.1f}%"

    def test_lru_eviction_performance(self):
        """Measure LRU eviction performance."""
        cache = LRUCache[int, str](capacity=100)

        # Fill cache
        for i in range(100):
            cache.put(i, f"value_{i}")

        # Measure eviction overhead
        start = time.time()
        for i in range(1000):
            cache.put(100 + i, f"value_{100+i}")
        elapsed = time.time() - start

        ops_per_sec = 1000 / elapsed

        print(f"\nLRU Eviction Performance: {ops_per_sec:.2f} ops/sec")

        assert ops_per_sec > 10000, f"Eviction too slow: {ops_per_sec:.2f} ops/sec"


class TestLockContention:
    """Test lock contention impact on performance."""

    def test_lock_contention_with_snapshot_pattern(self, kb_instance_warmed):
        """Verify snapshot pattern reduces lock contention."""
        num_workers = 20
        queries_per_worker = 50

        def worker(worker_id):
            """Worker performing queries."""
            queries = ["audio", "video", "ml", "data", "NLP"]
            for i in range(queries_per_worker):
                kb_instance_warmed.query(queries[i % len(queries)], use_cache=False)
            return queries_per_worker

        # Measure with snapshot pattern (current implementation)
        start = time.time()
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(worker, i) for i in range(num_workers)]
            results = [f.result() for f in as_completed(futures)]
        elapsed = time.time() - start

        total_queries = sum(results)
        throughput = total_queries / elapsed

        print(f"\nLock Contention Test (Snapshot Pattern):")
        print(f"  Workers: {num_workers}")
        print(f"  Total queries: {total_queries}")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Throughput: {throughput:.2f} queries/sec")

        # With optimized locking, should handle concurrent load well
        assert throughput > 200, f"Throughput indicates high lock contention: {throughput:.2f} q/s"

    def test_concurrent_stat_updates(self, kb_instance_warmed):
        """Test that stat updates don't cause significant contention."""
        num_workers = 30
        operations_per_worker = 100

        def worker(worker_id):
            """Worker that causes stat updates."""
            for _ in range(operations_per_worker):
                kb_instance_warmed.query("test query", use_cache=True)
                kb_instance_warmed.get_stats()
            return operations_per_worker

        start = time.time()
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(worker, i) for i in range(num_workers)]
            results = [f.result() for f in as_completed(futures)]
        elapsed = time.time() - start

        total_ops = sum(results)
        ops_per_sec = total_ops / elapsed

        print(f"\nStat Update Performance:")
        print(f"  Operations: {total_ops}")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Ops/sec: {ops_per_sec:.2f}")

        # Stats access should be fast
        assert ops_per_sec > 1000, f"Stat updates causing contention: {ops_per_sec:.2f} ops/sec"


class TestScalability:
    """Test scalability characteristics."""

    def test_scalability_with_increasing_workers(self, kb_instance_warmed):
        """Measure how throughput scales with number of workers."""
        queries_per_worker = 50
        queries = ["audio", "video", "ml", "data", "NLP"]
        results = {}

        def worker(worker_id):
            """Worker performing queries."""
            for i in range(queries_per_worker):
                kb_instance_warmed.query(queries[i % len(queries)], use_cache=True)
            return queries_per_worker

        for num_workers in [1, 2, 5, 10, 20]:
            start = time.time()
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = [executor.submit(worker, i) for i in range(num_workers)]
                query_counts = [f.result() for f in as_completed(futures)]
            elapsed = time.time() - start

            total_queries = sum(query_counts)
            throughput = total_queries / elapsed
            results[num_workers] = throughput

        print(f"\nScalability Results:")
        for workers, throughput in results.items():
            print(f"  {workers:2d} workers: {throughput:7.2f} queries/sec")

        # Throughput should increase with workers (up to a point)
        assert results[5] > results[1], "No improvement with 5 workers vs 1"
        assert results[10] > results[5], "No improvement with 10 workers vs 5"

    def test_memory_efficiency_under_load(self):
        """Test memory efficiency of cache under load."""
        cache = LRUCache[int, str](capacity=1000)

        # Fill cache with varying data
        for i in range(5000):
            cache.put(i, f"value_{i}" * 10)

        stats = cache.stats()

        print(f"\nMemory Efficiency:")
        print(f"  Capacity: {stats['capacity']}")
        print(f"  Size: {stats['size']}")
        print(f"  Utilization: {stats['utilization']*100:.1f}%")

        # Cache should maintain size limit
        assert stats['size'] <= stats['capacity']
        assert stats['utilization'] <= 1.0


class TestRegressionBenchmarks:
    """Benchmark tests to detect performance regressions."""

    def test_baseline_query_performance(self, kb_instance_warmed):
        """Baseline benchmark for query performance."""
        num_queries = 100
        queries = ["audio processing"] * num_queries

        start = time.time()
        for query in queries:
            kb_instance_warmed.query(query, use_cache=True)
        elapsed = time.time() - start

        qps = num_queries / elapsed

        print(f"\nBaseline Performance: {qps:.2f} queries/sec")

        # Document baseline for regression detection
        # If this fails in future, we have a performance regression
        assert qps > 500, f"Performance regression detected: {qps:.2f} q/s"

    def test_baseline_concurrent_performance(self, kb_instance_warmed):
        """Baseline benchmark for concurrent performance."""
        num_workers = 10
        queries_per_worker = 50

        def worker(worker_id):
            """Worker."""
            for i in range(queries_per_worker):
                kb_instance_warmed.query("test query", use_cache=True)

        start = time.time()
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(worker, i) for i in range(num_workers)]
            for f in as_completed(futures):
                f.result()
        elapsed = time.time() - start

        total = num_workers * queries_per_worker
        qps = total / elapsed

        print(f"\nBaseline Concurrent Performance: {qps:.2f} queries/sec")

        # Baseline for regression detection
        assert qps > 300, f"Concurrent performance regression: {qps:.2f} q/s"
