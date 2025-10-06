"""
Dedicated thread safety tests for LRU Cache.

This test suite focuses exclusively on the LRUCache implementation's
thread safety guarantees under various concurrent load scenarios.

Tests cover:
- 100+ concurrent get/put operations
- Cache eviction race conditions
- Capacity invariant (size <= capacity always)
- Stats consistency under load
- Stress testing with 1000+ concurrent operations
"""

import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import pytest
from knowledgebeast.core.cache import LRUCache


class TestLRUCacheThreadSafety:
    """Test LRU cache thread safety with concurrent operations."""

    def test_lru_cache_concurrent_get_put(self):
        """Test LRU cache handles 100 threads doing concurrent get/put operations."""
        cache = LRUCache[int, str](capacity=50)
        num_threads = 100
        operations_per_thread = 100
        errors = []

        def worker(thread_id):
            """Worker function performing cache operations."""
            try:
                for i in range(operations_per_thread):
                    key = (thread_id * operations_per_thread + i) % 200
                    value = f"thread_{thread_id}_value_{i}"

                    # Put operation
                    cache.put(key, value)

                    # Get operation
                    result = cache.get(key)

                    # Verify we get a valid result (might be evicted due to LRU)
                    if result is not None:
                        assert isinstance(result, str)
            except Exception as e:
                errors.append((thread_id, str(e)))

        # Run concurrent operations
        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Verify no errors occurred
        assert len(errors) == 0, f"Thread safety errors: {errors}"

        # Verify cache is in valid state
        stats = cache.stats()
        assert stats['size'] <= stats['capacity']
        assert stats['utilization'] <= 1.0

    def test_lru_cache_concurrent_eviction(self):
        """Test LRU eviction is thread-safe during concurrent access."""
        cache = LRUCache[int, str](capacity=10)
        num_threads = 50
        num_operations = 100
        errors = []

        def worker(thread_id):
            """Worker that causes evictions."""
            try:
                for i in range(num_operations):
                    # This will cause continuous evictions
                    cache.put(thread_id * num_operations + i, f"value_{i}")
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

        # Cache should never exceed capacity
        stats = cache.stats()
        assert stats['size'] <= stats['capacity']
        assert stats['size'] == 10  # Should be at capacity

    def test_lru_cache_concurrent_clear(self):
        """Test clearing cache while concurrent operations are happening."""
        cache = LRUCache[int, str](capacity=100)
        num_threads = 20
        stop_event = threading.Event()
        errors = []

        def worker(thread_id):
            """Worker performing operations."""
            try:
                counter = 0
                while not stop_event.is_set():
                    cache.put(thread_id * 1000 + counter, f"value_{counter}")
                    cache.get(thread_id * 1000 + counter)
                    counter += 1
            except Exception as e:
                errors.append((thread_id, str(e)))

        # Start workers
        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        # Clear cache multiple times while workers are running
        for _ in range(10):
            time.sleep(0.01)
            cache.clear()

        # Stop workers
        stop_event.set()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Clear operation errors: {errors}"

    def test_lru_cache_stats_thread_safe(self):
        """Test stats() method is thread-safe."""
        cache = LRUCache[int, str](capacity=100)
        num_threads = 50
        errors = []

        def worker(thread_id):
            """Worker that calls stats repeatedly."""
            try:
                for i in range(100):
                    cache.put(thread_id * 100 + i, f"value_{i}")
                    stats = cache.stats()
                    assert stats['size'] <= stats['capacity']
                    assert 0 <= stats['utilization'] <= 1.0
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Stats errors: {errors}"

    def test_cache_eviction_race_condition(self):
        """Test for race conditions during cache eviction."""
        cache = LRUCache[int, str](capacity=5)
        num_threads = 20
        errors = []
        eviction_tracker = []

        def worker(thread_id):
            """Worker causing evictions."""
            try:
                for i in range(50):
                    cache.put(thread_id * 100 + i, f"value_{i}")
                    stats = cache.stats()
                    eviction_tracker.append(stats['size'])
                    # Cache should NEVER exceed capacity
                    assert stats['size'] <= 5, f"Cache exceeded capacity: {stats['size']}"
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert max(eviction_tracker) <= 5, "Cache exceeded capacity during race condition"

    def test_concurrent_contains_check(self):
        """Test __contains__ is thread-safe."""
        cache = LRUCache[int, str](capacity=100)
        num_threads = 50
        errors = []

        def worker(thread_id):
            """Worker checking contains."""
            try:
                for i in range(100):
                    key = thread_id * 100 + i
                    cache.put(key, f"value_{i}")

                    # Check contains
                    if key in cache:
                        result = cache.get(key)
                        # If key was in cache, get should work (unless evicted)
                        # Just verify no exception
                        pass
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Contains check errors: {errors}"

    def test_concurrent_len_operations(self):
        """Test __len__ is thread-safe."""
        cache = LRUCache[int, str](capacity=50)
        num_threads = 30
        errors = []
        len_tracker = []

        def worker(thread_id):
            """Worker checking length."""
            try:
                for i in range(100):
                    cache.put(thread_id * 100 + i, f"value_{i}")
                    length = len(cache)
                    len_tracker.append(length)
                    assert 0 <= length <= 50
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Length check errors: {errors}"
        assert max(len_tracker) <= 50, "Cache length exceeded capacity"

    def test_stress_test_1000_concurrent_operations(self):
        """Stress test with 1000 concurrent cache operations."""
        cache = LRUCache[int, str](capacity=100)
        num_operations = 1000
        errors = []

        def operation(op_id):
            """Single cache operation."""
            try:
                cache.put(op_id, f"value_{op_id}")
                cache.get(op_id % 500)

                # Also test other methods
                _ = len(cache)
                _ = op_id % 500 in cache
                stats = cache.stats()

                # Verify capacity invariant
                assert stats['size'] <= stats['capacity'], \
                    f"Capacity violated: {stats['size']} > {stats['capacity']}"
                assert 0 <= stats['utilization'] <= 1.0, \
                    f"Invalid utilization: {stats['utilization']}"

                return True
            except Exception as e:
                errors.append((op_id, str(e)))
                return False

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(operation, i) for i in range(num_operations)]
            results = [f.result() for f in as_completed(futures)]

        assert len(errors) == 0, f"Stress test errors: {errors}"
        assert sum(results) == num_operations

        # Verify cache is still valid
        stats = cache.stats()
        assert stats['size'] <= stats['capacity']

    def test_capacity_invariant_under_load(self):
        """Test that capacity invariant (size <= capacity) is never violated under heavy load."""
        cache = LRUCache[int, str](capacity=20)
        num_threads = 100
        operations_per_thread = 200
        errors = []
        violations = []

        def worker(thread_id):
            """Worker that stresses the cache."""
            try:
                for i in range(operations_per_thread):
                    # Mix of operations
                    key = (thread_id * operations_per_thread + i) % 500

                    if i % 3 == 0:
                        cache.put(key, f"value_{key}")
                    elif i % 3 == 1:
                        cache.get(key)
                    else:
                        stats = cache.stats()
                        if stats['size'] > stats['capacity']:
                            violations.append((thread_id, i, stats))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert len(violations) == 0, f"Capacity invariant violations: {violations}"

        # Final verification
        stats = cache.stats()
        assert stats['size'] <= stats['capacity']
        assert stats['size'] == 20  # Should be at capacity

    def test_sequential_consistency(self):
        """Test that operations appear to occur in some sequential order."""
        cache = LRUCache[int, int](capacity=10)
        num_threads = 20
        errors = []

        # Initialize cache with known values
        for i in range(10):
            cache.put(i, i * 10)

        def worker(thread_id):
            """Worker performing read-modify-write operations."""
            try:
                for i in range(50):
                    key = i % 10

                    # Get current value
                    current = cache.get(key)

                    # If we got a value, increment and put back
                    if current is not None:
                        cache.put(key, current + 1)
                    else:
                        # Key was evicted, reinitialize
                        cache.put(key, key * 10)
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Sequential consistency errors: {errors}"

        # Verify cache is in valid state
        stats = cache.stats()
        assert stats['size'] <= stats['capacity']

    def test_mixed_operations_no_deadlock(self):
        """Test that mixed operations don't cause deadlocks."""
        cache = LRUCache[str, str](capacity=50)
        num_threads = 30
        duration_seconds = 2
        start_time = time.time()
        stop_event = threading.Event()
        operation_counts = {'get': 0, 'put': 0, 'clear': 0, 'stats': 0, 'len': 0, 'contains': 0}
        lock = threading.Lock()
        errors = []

        def worker(thread_id):
            """Worker performing mixed operations."""
            try:
                local_ops = {'get': 0, 'put': 0, 'clear': 0, 'stats': 0, 'len': 0, 'contains': 0}
                counter = 0

                while not stop_event.is_set():
                    op = counter % 6
                    key = f"key_{thread_id}_{counter % 20}"

                    if op == 0:
                        cache.put(key, f"value_{counter}")
                        local_ops['put'] += 1
                    elif op == 1:
                        cache.get(key)
                        local_ops['get'] += 1
                    elif op == 2:
                        _ = len(cache)
                        local_ops['len'] += 1
                    elif op == 3:
                        _ = key in cache
                        local_ops['contains'] += 1
                    elif op == 4:
                        cache.stats()
                        local_ops['stats'] += 1
                    elif op == 5 and thread_id % 10 == 0:  # Only some threads clear
                        cache.clear()
                        local_ops['clear'] += 1

                    counter += 1

                # Update global counts
                with lock:
                    for key in local_ops:
                        operation_counts[key] += local_ops[key]

            except Exception as e:
                errors.append((thread_id, str(e)))

        # Start workers
        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        # Let them run for specified duration
        time.sleep(duration_seconds)
        stop_event.set()

        # Wait for all threads with timeout
        for t in threads:
            t.join(timeout=5.0)
            if t.is_alive():
                errors.append(('main', 'Thread failed to terminate - possible deadlock'))

        assert len(errors) == 0, f"Deadlock or error detected: {errors}"

        # Verify operations actually ran
        total_ops = sum(operation_counts.values())
        assert total_ops > 1000, f"Too few operations completed: {total_ops}"

        # Verify cache is in valid state
        stats = cache.stats()
        assert stats['size'] <= stats['capacity']

        print(f"\nCompleted {total_ops} operations in {duration_seconds}s: {operation_counts}")
