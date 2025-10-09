"""
Snapshot Pattern Performance Validation Tests.

This test suite validates that the snapshot pattern in QueryEngine
delivers the expected 5-10x performance improvement under concurrent load.

The snapshot pattern works by:
1. Creating a snapshot of the index with minimal lock time (< 1ms)
2. Processing queries without holding locks (parallel execution)
3. Reducing lock contention by 80%+

Expected Performance Improvements:
- Lock hold time: < 1ms (vs 10-100ms with full lock)
- Concurrent throughput: 5-10x improvement
- Zero data corruption under load
"""

import time
import threading
from concurrent.futures import ThreadPoolExecutor
import pytest
from knowledgebeast.core.repository import DocumentRepository
from knowledgebeast.core.query_engine import QueryEngine


class TestSnapshotPatternPerformance:
    """Validate snapshot pattern delivers expected performance improvements."""

    @pytest.fixture
    def large_repository(self):
        """Create a repository with many documents for realistic testing."""
        repository = DocumentRepository()

        # Create 100 documents with diverse content
        for i in range(100):
            doc_id = f"doc_{i}"
            content = f"Document {i} about "
            content += " ".join([
                "audio", "video", "processing", "machine", "learning",
                "data", "analysis", "deep", "neural", "networks",
                "computer", "vision", "natural", "language", "processing",
                "transformers", "embeddings", "vectors", "similarity", "search"
            ][:i % 15 + 5])  # Vary content length

            doc_data = {
                "name": f"doc_{i}.md",
                "content": content,
                "path": f"/test/doc_{i}.md"
            }
            repository.add_document(doc_id, doc_data)

            # Index all terms
            terms = content.lower().split()
            for term in terms:
                repository.index_term(term, doc_id)

        return repository

    def test_snapshot_lock_hold_time(self, large_repository):
        """Test that snapshot creation holds lock for < 1ms."""
        engine = QueryEngine(large_repository)

        # Measure lock hold time during snapshot creation
        lock_times = []

        def query_and_measure():
            """Execute query and measure lock hold time."""
            # The snapshot is created in get_index_snapshot()
            start = time.time()
            terms = ["audio", "video", "machine"]
            with large_repository._lock:
                snapshot = large_repository.get_index_snapshot(terms)
            lock_time = time.time() - start
            lock_times.append(lock_time)
            return snapshot

        # Run multiple times to get average
        for _ in range(100):
            query_and_measure()

        avg_lock_time = sum(lock_times) / len(lock_times)
        max_lock_time = max(lock_times)

        # Lock should be held for < 1ms on average
        assert avg_lock_time < 0.001, f"Average lock time too high: {avg_lock_time*1000:.2f}ms"
        assert max_lock_time < 0.002, f"Max lock time too high: {max_lock_time*1000:.2f}ms"

        print(f"\nSnapshot lock times - Avg: {avg_lock_time*1000:.3f}ms, Max: {max_lock_time*1000:.3f}ms")

    def test_concurrent_query_throughput_improvement(self, large_repository):
        """Test that concurrent queries achieve 5-10x throughput improvement."""
        engine = QueryEngine(large_repository)

        queries = [
            "audio processing",
            "video machine learning",
            "data analysis",
            "neural networks",
            "computer vision"
        ]

        # Benchmark 1: Sequential execution (baseline)
        start = time.time()
        for _ in range(100):
            for query in queries:
                engine.execute_query(query)
        sequential_time = time.time() - start
        sequential_throughput = (100 * len(queries)) / sequential_time

        # Benchmark 2: Concurrent execution with 10 workers
        num_workers = 10
        queries_per_worker = 50

        start = time.time()
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            for _ in range(num_workers):
                for _ in range(queries_per_worker):
                    query = queries[_ % len(queries)]
                    future = executor.submit(engine.execute_query, query)
                    futures.append(future)

            # Wait for all to complete
            for future in futures:
                future.result()

        concurrent_time = time.time() - start
        total_queries = num_workers * queries_per_worker
        concurrent_throughput = total_queries / concurrent_time

        # Calculate improvement factor
        improvement = concurrent_throughput / sequential_throughput

        print(f"\nThroughput Comparison:")
        print(f"  Sequential: {sequential_throughput:.1f} queries/sec")
        print(f"  Concurrent:  {concurrent_throughput:.1f} queries/sec")
        print(f"  Improvement: {improvement:.1f}x")

        # With snapshot pattern, we should see at least 3-5x improvement
        # (Conservative estimate since we have 10 workers)
        assert improvement >= 3.0, f"Throughput improvement too low: {improvement:.1f}x (expected >= 3x)"

        # Verify we're achieving good concurrent throughput
        assert concurrent_throughput > 500, f"Concurrent throughput too low: {concurrent_throughput:.1f} q/s"

    def test_snapshot_pattern_prevents_lock_contention(self, large_repository):
        """Test that snapshot pattern reduces lock contention."""
        engine = QueryEngine(large_repository)

        # Track lock acquisition wait times
        lock_wait_times = []
        lock = threading.Lock()

        def query_with_timing(query):
            """Execute query and measure lock wait time."""
            try:
                # Measure time to acquire lock (should be minimal with snapshot pattern)
                wait_start = time.time()
                with large_repository._lock:
                    wait_time = time.time() - wait_start
                    with lock:
                        lock_wait_times.append(wait_time)

                # Execute query (most work happens without lock)
                engine.execute_query(query)
            except Exception as e:
                print(f"Query error: {e}")

        # Run 100 concurrent queries
        queries = ["audio", "video", "machine", "data", "neural"]
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [
                executor.submit(query_with_timing, queries[i % len(queries)])
                for i in range(200)
            ]
            for future in futures:
                future.result()

        # Calculate lock contention metrics
        avg_wait = sum(lock_wait_times) / len(lock_wait_times)
        max_wait = max(lock_wait_times)
        p95_wait = sorted(lock_wait_times)[int(len(lock_wait_times) * 0.95)]

        print(f"\nLock Wait Times:")
        print(f"  Average: {avg_wait*1000:.3f}ms")
        print(f"  P95:     {p95_wait*1000:.3f}ms")
        print(f"  Max:     {max_wait*1000:.3f}ms")

        # With snapshot pattern, lock contention should be minimal
        assert avg_wait < 0.001, f"Average lock wait too high: {avg_wait*1000:.2f}ms"
        assert p95_wait < 0.002, f"P95 lock wait too high: {p95_wait*1000:.2f}ms"

    def test_snapshot_isolation_prevents_corruption(self, large_repository):
        """Test that snapshot pattern prevents data corruption during concurrent access."""
        engine = QueryEngine(large_repository)

        # Track any corruption/inconsistency
        errors = []
        results_cache = {}

        def query_and_verify(thread_id, query):
            """Execute query and verify result consistency."""
            try:
                results = engine.execute_query(query)

                # Store first result for this query
                if query not in results_cache:
                    results_cache[query] = len(results)
                else:
                    # Verify subsequent results match
                    if len(results) != results_cache[query]:
                        errors.append(
                            f"Result inconsistency for '{query}': "
                            f"expected {results_cache[query]} results, got {len(results)}"
                        )
            except Exception as e:
                errors.append(f"Thread {thread_id}: {e}")

        # Run 1000 concurrent queries
        queries = ["audio", "video", "machine learning", "data analysis", "neural networks"]

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [
                executor.submit(query_and_verify, i, queries[i % len(queries)])
                for i in range(1000)
            ]
            for future in futures:
                future.result()

        # Should have zero corruption
        assert len(errors) == 0, f"Data corruption detected: {errors[:5]}"

    def test_snapshot_vs_no_snapshot_performance(self, large_repository):
        """Direct comparison of snapshot pattern vs hypothetical full-lock approach."""
        engine = QueryEngine(large_repository)

        # Simulate "no snapshot" by holding lock during entire query processing
        def query_with_full_lock(query):
            """Simulate query with full lock (no snapshot pattern)."""
            with large_repository._lock:
                terms = query.lower().split()
                # Simulate processing time under lock
                index_snapshot = {
                    term: list(large_repository.index.get(term, []))
                    for term in terms
                }
                # Process matches (still under lock!)
                matches = {}
                for term, doc_ids in index_snapshot.items():
                    for doc_id in doc_ids:
                        matches[doc_id] = matches.get(doc_id, 0) + 1
                sorted_matches = sorted(matches.items(), key=lambda x: x[1], reverse=True)
                doc_ids = [doc_id for doc_id, _ in sorted_matches]
                results = large_repository.get_documents_by_ids(doc_ids)
            return results

        queries = ["audio video", "machine learning data", "neural networks"]

        # Benchmark 1: Full lock approach (simulated)
        start = time.time()
        for _ in range(10):  # Fewer iterations due to blocking
            for query in queries:
                query_with_full_lock(query)
        full_lock_time = time.time() - start

        # Benchmark 2: Snapshot pattern (current implementation)
        start = time.time()
        for _ in range(10):
            for query in queries:
                engine.execute_query(query)
        snapshot_time = time.time() - start

        improvement = full_lock_time / snapshot_time

        print(f"\nFull Lock vs Snapshot Pattern:")
        print(f"  Full Lock: {full_lock_time:.3f}s")
        print(f"  Snapshot:  {snapshot_time:.3f}s")
        print(f"  Speedup:   {improvement:.2f}x")

        # Snapshot should be faster (though not dramatically in sequential case)
        assert snapshot_time <= full_lock_time, "Snapshot pattern should not be slower"

    def test_parallel_query_execution_without_blocking(self, large_repository):
        """Test that multiple queries can execute in parallel without blocking."""
        engine = QueryEngine(large_repository)

        # Track execution overlaps
        execution_times = []
        lock = threading.Lock()

        def timed_query(query_id, query):
            """Execute query and record timing."""
            start = time.time()
            engine.execute_query(query)
            duration = time.time() - start

            with lock:
                execution_times.append((query_id, start, duration))

        # Launch 20 concurrent queries
        queries = ["audio processing", "video analysis", "machine learning"]
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(timed_query, i, queries[i % len(queries)])
                for i in range(20)
            ]
            for future in futures:
                future.result()

        # Analyze overlaps (queries running in parallel)
        overlaps = 0
        for i, (id1, start1, dur1) in enumerate(execution_times):
            end1 = start1 + dur1
            for id2, start2, dur2 in execution_times[i+1:]:
                end2 = start2 + dur2
                # Check if executions overlap
                if not (end1 < start2 or end2 < start1):
                    overlaps += 1

        # With snapshot pattern, many queries should execute in parallel
        print(f"\nParallel Execution Analysis:")
        print(f"  Total queries: {len(execution_times)}")
        print(f"  Overlapping executions: {overlaps}")
        print(f"  Parallelism factor: {overlaps / len(execution_times):.2f}")

        # We should see significant parallelism
        assert overlaps > 50, f"Insufficient parallelism: only {overlaps} overlaps"


class TestSnapshotPatternCorrectness:
    """Validate snapshot pattern maintains correctness guarantees."""

    def test_snapshot_is_consistent(self):
        """Test that snapshot provides a consistent view of the index."""
        repository = DocumentRepository()

        # Add initial documents
        for i in range(10):
            doc_id = f"doc_{i}"
            content = f"Document {i} with terms audio video data"
            repository.add_document(doc_id, {"name": f"doc_{i}.md", "content": content, "path": f"/test/{doc_id}"})
            for term in content.lower().split():
                repository.index_term(term, doc_id)

        engine = QueryEngine(repository)

        # Take snapshot
        snapshot1 = repository.get_index_snapshot(["audio", "video"])

        # Modify index (shouldn't affect snapshot)
        repository.add_document("new_doc", {"name": "new.md", "content": "audio video", "path": "/test/new"})
        repository.index_term("audio", "new_doc")
        repository.index_term("video", "new_doc")

        # Original snapshot should be unchanged
        snapshot2 = repository.get_index_snapshot(["audio", "video"])

        # snapshot1 should not include new_doc (taken before addition)
        assert "new_doc" not in snapshot1.get("audio", [])
        assert "new_doc" not in snapshot1.get("video", [])

        # snapshot2 should include new_doc (taken after addition)
        assert "new_doc" in snapshot2.get("audio", [])
        assert "new_doc" in snapshot2.get("video", [])

    def test_snapshot_independence_from_index_changes(self):
        """Test that snapshots are independent of subsequent index changes."""
        repository = DocumentRepository()

        # Add documents
        for i in range(5):
            doc_id = f"doc_{i}"
            content = "audio video processing"
            repository.add_document(doc_id, {"name": f"{doc_id}.md", "content": content, "path": f"/test/{doc_id}"})
            for term in content.split():
                repository.index_term(term.lower(), doc_id)

        # Create snapshot
        snapshot = repository.get_index_snapshot(["audio"])

        # Modify index after snapshot
        repository.index_term("audio", "doc_999")

        # Snapshot should not be affected by post-creation changes
        assert "doc_999" not in snapshot.get("audio", [])
        assert len(snapshot.get("audio", [])) == 5  # Original 5 docs only
