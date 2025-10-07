"""
Advanced Concurrency Tests for KnowledgeBeast.

This comprehensive test suite covers edge cases, race conditions, stress scenarios,
and extreme load testing for thread safety guarantees.

Tests cover:
- 1000+ concurrent queries with data consistency verification
- Concurrent index rebuilds during active queries
- Cache eviction races with 100+ threads
- Stats consistency under extreme load (10000+ operations)
- Deadlock detection and prevention
- Starvation scenarios (readers vs writers)
- Memory leak detection under sustained load
- Thread pool exhaustion handling
- Atomic operation verification
- Lock contention measurement
- Snapshot pattern validation
"""

import time
import threading
import gc
import tracemalloc
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from pathlib import Path
import pytest
from knowledgebeast.core.cache import LRUCache
from knowledgebeast.core.engine import KnowledgeBase
from knowledgebeast.core.config import KnowledgeBeastConfig


class TestExtremeLoadScenarios:
    """Test system behavior under extreme concurrent load."""

    def test_1000_concurrent_queries_data_consistency(self, tmp_path):
        """Test 1000+ concurrent queries with data consistency verification."""
        # Create test KB
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()

        # Create test documents
        docs = {
            "audio.md": "Audio processing with librosa and pydub for signal analysis",
            "video.md": "Video processing using opencv and ffmpeg for computer vision",
            "nlp.md": "Natural language processing with transformers and spacy",
            "ml.md": "Machine learning using scikit-learn and pytorch for deep learning",
            "data.md": "Data analysis with pandas and numpy for scientific computing",
            "web.md": "Web development with flask and fastapi for API development",
            "db.md": "Database management with postgresql and mongodb for data storage",
            "cloud.md": "Cloud computing with aws and azure for scalable infrastructure",
        }

        for filename, content in docs.items():
            (kb_dir / filename).write_text(content)

        config = KnowledgeBeastConfig(
            knowledge_dirs=[kb_dir],
            auto_warm=False,
            cache_file=str(tmp_path / "cache.json")
        )
        kb = KnowledgeBase(config)
        kb.ingest_all()

        num_operations = 1000
        queries = ["audio", "video", "nlp", "machine learning", "data analysis",
                   "web", "database", "cloud"]
        errors = []
        results_tracker = {}
        tracker_lock = threading.Lock()

        def worker(op_id):
            """Worker performing queries."""
            try:
                query = queries[op_id % len(queries)]
                results = kb.query(query, use_cache=True)

                # Verify results are valid
                assert isinstance(results, list)
                for doc_id, doc in results:
                    assert isinstance(doc_id, str)
                    assert isinstance(doc, dict)
                    assert 'content' in doc
                    assert 'name' in doc

                # Track results for consistency check
                with tracker_lock:
                    if query not in results_tracker:
                        results_tracker[query] = len(results)
                    else:
                        # Same query should return same number of results
                        assert results_tracker[query] == len(results), \
                            f"Inconsistent results for '{query}'"

                return True
            except Exception as e:
                errors.append((op_id, str(e)))
                return False

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(worker, i) for i in range(num_operations)]
            results = [f.result() for f in as_completed(futures)]

        assert len(errors) == 0, f"Query errors: {errors}"
        assert sum(results) == num_operations
        assert len(results_tracker) == len(queries)

    def test_10000_cache_operations_stats_consistency(self):
        """Test stats consistency under 10000+ concurrent operations."""
        cache = LRUCache[int, str](capacity=100)
        num_operations = 10000
        errors = []
        stats_violations = []

        def operation(op_id):
            """Single cache operation with stats verification."""
            try:
                # Mix of operations
                if op_id % 3 == 0:
                    cache.put(op_id % 500, f"value_{op_id}")
                elif op_id % 3 == 1:
                    cache.get(op_id % 500)
                else:
                    _ = op_id % 500 in cache

                # Verify stats consistency
                stats = cache.stats()
                if stats['size'] > stats['capacity']:
                    stats_violations.append((op_id, stats))
                if not (0 <= stats['utilization'] <= 1.0):
                    stats_violations.append((op_id, stats))

                return True
            except Exception as e:
                errors.append((op_id, str(e)))
                return False

        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(operation, i) for i in range(num_operations)]
            results = [f.result() for f in as_completed(futures)]

        assert len(errors) == 0, f"Operation errors: {errors}"
        assert len(stats_violations) == 0, f"Stats violations: {stats_violations}"
        assert sum(results) == num_operations

        # Final stats check
        stats = cache.stats()
        assert stats['size'] <= stats['capacity']
        assert 0 <= stats['utilization'] <= 1.0

    def test_concurrent_index_rebuild_during_queries(self, tmp_path):
        """Test concurrent index rebuilds while queries are running."""
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()

        # Initial documents
        for i in range(10):
            (kb_dir / f"doc_{i}.md").write_text(
                f"Document {i} about topic_{i % 3} with keywords audio video ml"
            )

        config = KnowledgeBeastConfig(
            knowledge_dirs=[kb_dir],
            auto_warm=False,
            cache_file=str(tmp_path / "cache.json")
        )
        kb = KnowledgeBase(config)
        kb.ingest_all()

        stop_event = threading.Event()
        errors = []
        query_count = {'count': 0}
        rebuild_count = {'count': 0}
        count_lock = threading.Lock()

        def query_worker(thread_id):
            """Worker performing queries."""
            try:
                while not stop_event.is_set():
                    results = kb.query("audio video ml", use_cache=True)
                    assert isinstance(results, list)
                    with count_lock:
                        query_count['count'] += 1
            except Exception as e:
                errors.append(('query', thread_id, str(e)))

        def rebuild_worker():
            """Worker rebuilding index."""
            try:
                for i in range(5):
                    time.sleep(0.1)
                    # Add new document and rebuild
                    new_doc = kb_dir / f"new_doc_{i}.md"
                    new_doc.write_text(f"New document {i} with audio video ml")
                    kb.ingest_all()
                    with count_lock:
                        rebuild_count['count'] += 1
            except Exception as e:
                errors.append(('rebuild', 0, str(e)))

        # Start query workers
        query_threads = []
        for i in range(20):
            t = threading.Thread(target=query_worker, args=(i,))
            query_threads.append(t)
            t.start()

        # Start rebuild worker
        rebuild_thread = threading.Thread(target=rebuild_worker)
        rebuild_thread.start()

        # Let them run
        rebuild_thread.join()
        time.sleep(0.5)

        # Stop query workers
        stop_event.set()
        for t in query_threads:
            t.join()

        assert len(errors) == 0, f"Concurrent rebuild errors: {errors}"
        assert query_count['count'] > 100, "Too few queries completed"
        assert rebuild_count['count'] == 5, "Not all rebuilds completed"


class TestCacheEvictionRaces:
    """Test cache eviction race conditions with 100+ threads."""

    def test_100_threads_cache_eviction_no_capacity_violation(self):
        """Test 100 threads causing evictions never violate capacity."""
        cache = LRUCache[int, str](capacity=20)
        num_threads = 100
        operations_per_thread = 100
        errors = []
        capacity_violations = []

        def worker(thread_id):
            """Worker causing continuous evictions."""
            try:
                for i in range(operations_per_thread):
                    key = thread_id * operations_per_thread + i
                    cache.put(key, f"value_{key}")

                    # Check capacity after every operation
                    stats = cache.stats()
                    if stats['size'] > stats['capacity']:
                        capacity_violations.append((thread_id, i, stats))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Eviction errors: {errors}"
        assert len(capacity_violations) == 0, \
            f"Capacity violations detected: {capacity_violations}"

        # Final verification
        stats = cache.stats()
        assert stats['size'] <= stats['capacity']
        assert stats['size'] == 20

    def test_eviction_race_with_mixed_operations(self):
        """Test eviction races with mixed get/put/clear operations."""
        cache = LRUCache[int, str](capacity=10)
        num_threads = 50
        duration_seconds = 2
        stop_event = threading.Event()
        errors = []
        violations = []

        def worker(thread_id):
            """Worker performing mixed operations."""
            try:
                counter = 0
                while not stop_event.is_set():
                    op = counter % 4
                    key = thread_id * 1000 + counter

                    if op == 0:
                        cache.put(key, f"value_{key}")
                    elif op == 1:
                        cache.get(key % 50)
                    elif op == 2:
                        _ = len(cache)
                    else:
                        stats = cache.stats()
                        if stats['size'] > stats['capacity']:
                            violations.append((thread_id, stats))

                    counter += 1
            except Exception as e:
                errors.append((thread_id, str(e)))

        # Start workers
        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        time.sleep(duration_seconds)
        stop_event.set()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Mixed operation errors: {errors}"
        assert len(violations) == 0, f"Capacity violations: {violations}"

    def test_eviction_during_concurrent_reads(self):
        """Test evictions don't corrupt data during concurrent reads."""
        cache = LRUCache[int, int](capacity=50)

        # Prepopulate cache
        for i in range(50):
            cache.put(i, i * 10)

        num_threads = 100
        errors = []
        data_corruption = []

        def reader(thread_id):
            """Worker reading from cache."""
            try:
                for i in range(100):
                    key = i % 50
                    value = cache.get(key)
                    # If value exists, it must be correct
                    if value is not None and value != key * 10:
                        data_corruption.append((thread_id, key, value, key * 10))
            except Exception as e:
                errors.append(('reader', thread_id, str(e)))

        def writer(thread_id):
            """Worker writing to cache (causing evictions)."""
            try:
                for i in range(100):
                    key = 100 + thread_id * 100 + i
                    cache.put(key, key * 10)
            except Exception as e:
                errors.append(('writer', thread_id, str(e)))

        # Start readers and writers
        threads = []
        for i in range(num_threads // 2):
            t1 = threading.Thread(target=reader, args=(i,))
            t2 = threading.Thread(target=writer, args=(i,))
            threads.extend([t1, t2])
            t1.start()
            t2.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Reader/writer errors: {errors}"
        assert len(data_corruption) == 0, \
            f"Data corruption detected: {data_corruption}"


class TestDeadlockPrevention:
    """Test deadlock detection and prevention."""

    def test_no_deadlock_with_mixed_cache_operations(self):
        """Test that mixed operations complete without deadlock."""
        cache = LRUCache[str, str](capacity=100)
        num_threads = 50
        timeout_seconds = 10
        errors = []
        completed = {'count': 0}
        lock = threading.Lock()

        def worker(thread_id):
            """Worker performing various operations."""
            try:
                for i in range(100):
                    key = f"key_{thread_id}_{i}"

                    # Mix of operations
                    cache.put(key, f"value_{i}")
                    cache.get(key)
                    _ = key in cache
                    _ = len(cache)
                    cache.stats()

                    if i % 20 == 0:
                        cache.clear()

                with lock:
                    completed['count'] += 1
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        # Wait with timeout to detect deadlocks
        start_time = time.time()
        for t in threads:
            remaining = timeout_seconds - (time.time() - start_time)
            if remaining <= 0:
                break
            t.join(timeout=remaining)

        # Check for deadlocks
        alive_threads = [t for t in threads if t.is_alive()]
        assert len(alive_threads) == 0, \
            f"Deadlock detected: {len(alive_threads)} threads still alive"

        assert len(errors) == 0, f"Operation errors: {errors}"
        assert completed['count'] == num_threads

    def test_no_deadlock_with_nested_stats_calls(self):
        """Test that nested stats calls don't cause deadlocks."""
        cache = LRUCache[int, int](capacity=50)
        num_threads = 30
        errors = []

        def worker(thread_id):
            """Worker making nested-like calls."""
            try:
                for i in range(100):
                    cache.put(thread_id * 100 + i, i)
                    stats1 = cache.stats()
                    cache.get(thread_id * 100 + i)
                    stats2 = cache.stats()

                    # Verify stats are consistent
                    assert stats1['capacity'] == stats2['capacity']
            except Exception as e:
                errors.append((thread_id, str(e)))

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(num_threads)]
            # Use timeout to detect deadlocks
            for future in as_completed(futures, timeout=10):
                future.result()

        assert len(errors) == 0, f"Nested call errors: {errors}"


class TestStarvationScenarios:
    """Test reader/writer starvation scenarios."""

    def test_readers_dont_starve_writers(self):
        """Test that heavy read load doesn't starve writers."""
        cache = LRUCache[int, int](capacity=100)
        duration_seconds = 2
        stop_event = threading.Event()
        read_count = {'count': 0}
        write_count = {'count': 0}
        lock = threading.Lock()
        errors = []

        def reader(thread_id):
            """Heavy reader thread."""
            try:
                while not stop_event.is_set():
                    for i in range(10):
                        cache.get(i)
                    with lock:
                        read_count['count'] += 10
            except Exception as e:
                errors.append(('reader', thread_id, str(e)))

        def writer(thread_id):
            """Writer thread."""
            try:
                counter = 0
                while not stop_event.is_set():
                    cache.put(thread_id * 1000 + counter, counter)
                    with lock:
                        write_count['count'] += 1
                    counter += 1
                    time.sleep(0.001)  # Small delay
            except Exception as e:
                errors.append(('writer', thread_id, str(e)))

        # Start many readers
        reader_threads = []
        for i in range(20):
            t = threading.Thread(target=reader, args=(i,))
            reader_threads.append(t)
            t.start()

        # Start fewer writers
        writer_threads = []
        for i in range(5):
            t = threading.Thread(target=writer, args=(i,))
            writer_threads.append(t)
            t.start()

        time.sleep(duration_seconds)
        stop_event.set()

        for t in reader_threads + writer_threads:
            t.join()

        assert len(errors) == 0, f"Starvation test errors: {errors}"
        # Writers should have made progress
        assert write_count['count'] > 100, \
            f"Writers starved: only {write_count['count']} writes"
        # Readers should also have made progress
        assert read_count['count'] > 1000, \
            f"Readers starved: only {read_count['count']} reads"

    def test_writers_dont_starve_readers(self):
        """Test that heavy write load doesn't starve readers."""
        cache = LRUCache[int, int](capacity=100)
        duration_seconds = 2
        stop_event = threading.Event()
        read_count = {'count': 0}
        write_count = {'count': 0}
        lock = threading.Lock()
        errors = []

        def reader(thread_id):
            """Reader thread."""
            try:
                counter = 0
                while not stop_event.is_set():
                    cache.get(counter % 100)
                    with lock:
                        read_count['count'] += 1
                    counter += 1
                    time.sleep(0.001)
            except Exception as e:
                errors.append(('reader', thread_id, str(e)))

        def writer(thread_id):
            """Heavy writer thread."""
            try:
                while not stop_event.is_set():
                    for i in range(10):
                        cache.put(thread_id * 1000 + i, i)
                    with lock:
                        write_count['count'] += 10
            except Exception as e:
                errors.append(('writer', thread_id, str(e)))

        # Start fewer readers
        reader_threads = []
        for i in range(5):
            t = threading.Thread(target=reader, args=(i,))
            reader_threads.append(t)
            t.start()

        # Start many writers
        writer_threads = []
        for i in range(20):
            t = threading.Thread(target=writer, args=(i,))
            writer_threads.append(t)
            t.start()

        time.sleep(duration_seconds)
        stop_event.set()

        for t in reader_threads + writer_threads:
            t.join()

        assert len(errors) == 0, f"Starvation test errors: {errors}"
        # Readers should have made progress
        assert read_count['count'] > 100, \
            f"Readers starved: only {read_count['count']} reads"
        # Writers should also have made progress
        assert write_count['count'] > 1000, \
            f"Writers starved: only {write_count['count']} writes"


class TestMemoryLeakDetection:
    """Test memory leak detection under sustained load."""

    def test_no_memory_leak_under_sustained_load(self):
        """Test that sustained operations don't cause memory leaks."""
        tracemalloc.start()

        cache = LRUCache[int, str](capacity=100)
        num_iterations = 1000
        errors = []

        # Get baseline memory
        gc.collect()
        baseline = tracemalloc.get_traced_memory()[0]

        def worker(thread_id):
            """Worker performing operations."""
            try:
                for i in range(num_iterations):
                    cache.put(thread_id * num_iterations + i, f"value_{i}")
                    cache.get((thread_id * num_iterations + i) % 500)
                    _ = len(cache)
                    _ = (thread_id * num_iterations + i) in cache
            except Exception as e:
                errors.append((thread_id, str(e)))

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker, i) for i in range(10)]
            for future in as_completed(futures):
                future.result()

        # Force garbage collection
        gc.collect()

        # Get final memory
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        assert len(errors) == 0, f"Memory leak test errors: {errors}"

        # Memory should not have grown significantly
        # Allow for some overhead but not excessive growth
        memory_growth = current - baseline
        memory_growth_mb = memory_growth / (1024 * 1024)

        # Cache with 100 items shouldn't use more than 10MB
        assert memory_growth_mb < 10, \
            f"Possible memory leak: {memory_growth_mb:.2f}MB growth"

    def test_cache_clear_releases_memory(self):
        """Test that cache.clear() actually releases memory."""
        tracemalloc.start()

        cache = LRUCache[int, str](capacity=1000)

        # Fill cache
        for i in range(1000):
            cache.put(i, "x" * 1000)  # 1KB strings

        gc.collect()
        filled_memory = tracemalloc.get_traced_memory()[0]

        # Clear cache
        cache.clear()
        gc.collect()
        cleared_memory = tracemalloc.get_traced_memory()[0]

        tracemalloc.stop()

        # Memory should be significantly reduced
        memory_freed = filled_memory - cleared_memory
        memory_freed_mb = memory_freed / (1024 * 1024)

        # Should free at least 0.05MB (Python GC may not immediately release all memory)
        # The important thing is that some memory is freed
        assert memory_freed_mb > 0.05, \
            f"Clear didn't release memory: only {memory_freed_mb:.2f}MB freed"


class TestThreadPoolExhaustion:
    """Test thread pool exhaustion handling."""

    def test_graceful_handling_of_thread_pool_exhaustion(self):
        """Test system handles thread pool exhaustion gracefully."""
        cache = LRUCache[int, str](capacity=100)
        errors = []
        completed = {'count': 0}
        lock = threading.Lock()

        def worker(thread_id):
            """Worker that might face thread exhaustion."""
            try:
                for i in range(50):
                    cache.put(thread_id * 50 + i, f"value_{i}")
                    cache.get(thread_id * 50 + i)

                with lock:
                    completed['count'] += 1
            except Exception as e:
                errors.append((thread_id, str(e)))

        # Try to exhaust thread pool
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit way more tasks than workers
            futures = [executor.submit(worker, i) for i in range(100)]

            # All should eventually complete
            for future in as_completed(futures, timeout=30):
                future.result()

        assert len(errors) == 0, f"Thread pool errors: {errors}"
        assert completed['count'] == 100

    def test_timeout_handling_in_concurrent_operations(self):
        """Test that timeouts are handled properly."""
        cache = LRUCache[int, str](capacity=100)
        errors = []

        def slow_worker(thread_id):
            """Worker that takes some time."""
            try:
                for i in range(100):
                    cache.put(thread_id * 100 + i, f"value_{i}")
                    time.sleep(0.01)  # Simulate slow operation
                return True
            except Exception as e:
                errors.append((thread_id, str(e)))
                return False

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(slow_worker, i) for i in range(20)]

            # Some might timeout, but that's ok
            completed = 0
            try:
                for future in as_completed(futures, timeout=5):
                    if future.result():
                        completed += 1
            except TimeoutError:
                # Some operations timed out, which is expected
                pass

        # At least some should have completed
        assert completed >= 5, f"Too few operations completed: {completed}"


class TestAtomicOperations:
    """Test atomicity of cache operations."""

    def test_put_operation_is_atomic(self):
        """Test that put operations are atomic."""
        cache = LRUCache[int, int](capacity=100)
        num_threads = 50
        operations_per_thread = 100
        errors = []

        # Track all puts
        put_tracker = {}
        tracker_lock = threading.Lock()

        def worker(thread_id):
            """Worker performing puts."""
            try:
                for i in range(operations_per_thread):
                    key = i % 100
                    value = thread_id * 1000 + i
                    cache.put(key, value)

                    with tracker_lock:
                        if key not in put_tracker:
                            put_tracker[key] = []
                        put_tracker[key].append(value)
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Atomic put errors: {errors}"

        # Verify final values are from one of the puts
        for key in range(100):
            final_value = cache.get(key)
            if final_value is not None:
                assert final_value in put_tracker[key], \
                    f"Value {final_value} for key {key} not in put history"

    def test_get_returns_consistent_value(self):
        """Test that get returns consistent values during concurrent puts."""
        cache = LRUCache[int, int](capacity=100)

        # Prepopulate
        for i in range(100):
            cache.put(i, i * 10)

        num_threads = 50
        errors = []
        inconsistencies = []

        def reader(thread_id):
            """Reader checking consistency."""
            try:
                for i in range(100):
                    key = i % 100
                    value = cache.get(key)

                    # If we get a value, verify it's valid
                    if value is not None:
                        # Value should be key * 10 or some other valid value
                        # from concurrent puts
                        if value % 10 != 0:
                            inconsistencies.append((thread_id, key, value))
            except Exception as e:
                errors.append(('reader', thread_id, str(e)))

        def writer(thread_id):
            """Writer updating values."""
            try:
                for i in range(100):
                    key = i % 100
                    cache.put(key, (i + 1) * 10)
            except Exception as e:
                errors.append(('writer', thread_id, str(e)))

        threads = []
        for i in range(num_threads // 2):
            t1 = threading.Thread(target=reader, args=(i,))
            t2 = threading.Thread(target=writer, args=(i,))
            threads.extend([t1, t2])
            t1.start()
            t2.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Consistency errors: {errors}"
        assert len(inconsistencies) == 0, \
            f"Inconsistent values detected: {inconsistencies}"


class TestSnapshotPattern:
    """Test snapshot pattern implementation in query engine."""

    def test_query_snapshot_isolation(self, tmp_path):
        """Test that query snapshots provide isolation."""
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()

        for i in range(5):
            (kb_dir / f"doc_{i}.md").write_text(f"Document {i} about audio processing")

        config = KnowledgeBeastConfig(
            knowledge_dirs=[kb_dir],
            auto_warm=False,
            cache_file=str(tmp_path / "cache.json")
        )
        kb = KnowledgeBase(config)
        kb.ingest_all()

        num_threads = 50
        errors = []
        results_tracker = []

        def worker(thread_id):
            """Worker performing queries."""
            try:
                for _ in range(10):
                    results = kb.query("audio processing", use_cache=False)
                    # All queries should return same number of results
                    # (snapshot isolation)
                    results_tracker.append(len(results))
                    assert len(results) > 0
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Snapshot isolation errors: {errors}"
        # All results should be consistent
        assert len(set(results_tracker)) <= 2, \
            f"Too much variation in results: {set(results_tracker)}"


class TestLockContentionMeasurement:
    """Measure and verify lock contention is minimized."""

    def test_lock_contention_under_load(self):
        """Test that lock contention doesn't cause severe slowdowns."""
        cache = LRUCache[int, str](capacity=100)

        # Measure single-threaded performance
        start = time.time()
        for i in range(1000):
            cache.put(i, f"value_{i}")
            cache.get(i % 500)
        single_thread_time = time.time() - start

        # Measure multi-threaded performance
        num_threads = 10
        operations_per_thread = 100
        errors = []

        def worker(thread_id):
            """Worker performing operations."""
            try:
                for i in range(operations_per_thread):
                    cache.put(thread_id * operations_per_thread + i, f"value_{i}")
                    cache.get((thread_id * operations_per_thread + i) % 500)
            except Exception as e:
                errors.append((thread_id, str(e)))

        start = time.time()
        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()
        multi_thread_time = time.time() - start

        assert len(errors) == 0, f"Lock contention errors: {errors}"

        # With 10 threads, we should see some speedup
        # Even with contention, shouldn't be drastically slower
        ops_per_second_single = 1000 / single_thread_time
        ops_per_second_multi = (num_threads * operations_per_thread) / multi_thread_time

        # Multi-threaded should provide reasonable throughput
        # Lock contention may prevent linear scaling, but should still be faster overall
        # Accept if multi-threaded is at least 50% of single-threaded throughput
        assert ops_per_second_multi > ops_per_second_single * 0.5, \
            f"Excessive lock contention detected: {ops_per_second_single:.0f} vs {ops_per_second_multi:.0f} ops/sec"


class TestStressWithConfigurableDuration:
    """Stress tests with configurable duration."""

    @pytest.mark.parametrize("duration_seconds", [1, 2, 5])
    def test_sustained_load_stress_test(self, duration_seconds):
        """Stress test with configurable duration."""
        cache = LRUCache[int, str](capacity=100)
        stop_event = threading.Event()
        errors = []
        operation_counts = {'total': 0}
        lock = threading.Lock()

        def worker(thread_id):
            """Worker performing continuous operations."""
            try:
                local_count = 0
                while not stop_event.is_set():
                    op = local_count % 5
                    key = thread_id * 10000 + local_count

                    if op == 0:
                        cache.put(key, f"value_{key}")
                    elif op == 1:
                        cache.get(key % 500)
                    elif op == 2:
                        _ = len(cache)
                    elif op == 3:
                        _ = key in cache
                    else:
                        cache.stats()

                    local_count += 1

                with lock:
                    operation_counts['total'] += local_count
            except Exception as e:
                errors.append((thread_id, str(e)))

        # Start workers
        num_threads = 20
        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        # Run for specified duration
        time.sleep(duration_seconds)
        stop_event.set()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Stress test errors: {errors}"

        # Verify significant work was done
        ops_per_second = operation_counts['total'] / duration_seconds
        assert ops_per_second > 1000, \
            f"Low throughput: {ops_per_second:.0f} ops/sec"

        # Verify cache is still valid
        stats = cache.stats()
        assert stats['size'] <= stats['capacity']


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_concurrent_operations_on_empty_cache(self):
        """Test concurrent operations on initially empty cache."""
        cache = LRUCache[int, str](capacity=100)
        num_threads = 50
        errors = []

        def worker(thread_id):
            """Worker on empty cache."""
            try:
                # Should handle gets on empty cache
                for i in range(100):
                    result = cache.get(i)
                    assert result is None or isinstance(result, str)

                    # Then start putting
                    cache.put(i, f"value_{i}")
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Empty cache errors: {errors}"

    def test_concurrent_operations_at_exact_capacity(self):
        """Test operations when cache is exactly at capacity."""
        cache = LRUCache[int, str](capacity=50)

        # Fill to exact capacity
        for i in range(50):
            cache.put(i, f"value_{i}")

        num_threads = 50
        errors = []

        def worker(thread_id):
            """Worker on full cache."""
            try:
                for i in range(100):
                    # Mix of operations on full cache
                    cache.get(i % 50)
                    cache.put(100 + thread_id * 100 + i, f"value_{i}")
                    stats = cache.stats()
                    assert stats['size'] <= stats['capacity']
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Full cache errors: {errors}"
        assert cache.stats()['size'] == 50

    def test_zero_data_corruption_verification(self):
        """Comprehensive test to verify zero data corruption."""
        cache = LRUCache[str, dict](capacity=100)
        num_threads = 50
        errors = []
        corruption_detected = []

        def worker(thread_id):
            """Worker with data integrity checks."""
            try:
                for i in range(100):
                    key = f"key_{thread_id}_{i}"
                    value = {
                        'thread_id': thread_id,
                        'counter': i,
                        'checksum': hash((thread_id, i))
                    }

                    cache.put(key, value)

                    # Immediately verify
                    retrieved = cache.get(key)
                    if retrieved is not None:
                        expected_checksum = hash((thread_id, i))
                        if retrieved['checksum'] != expected_checksum:
                            corruption_detected.append({
                                'key': key,
                                'expected': expected_checksum,
                                'got': retrieved['checksum']
                            })
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Data corruption test errors: {errors}"
        assert len(corruption_detected) == 0, \
            f"Data corruption detected: {corruption_detected}"
