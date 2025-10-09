"""
Comprehensive thread safety tests for KnowledgeBeast Phase 2 Architecture.

Tests cover:
- LRU cache concurrent access
- QueryEngine concurrent operations
- DocumentRepository thread safety
- Semantic cache thread safety
- Index snapshot pattern validation
- Data corruption detection
- Race condition detection
"""

import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import pytest
from knowledgebeast.core.cache import LRUCache
from knowledgebeast.core.repository import DocumentRepository
from knowledgebeast.core.query_engine import QueryEngine
from knowledgebeast.core.query.semantic_cache import SemanticCache
import numpy as np


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


class TestQueryEngineThreadSafety:
    """Test QueryEngine thread safety with concurrent queries using Phase 2 architecture."""

    @pytest.fixture
    def query_engine(self):
        """Create a QueryEngine instance with test documents."""
        # Create repository with test documents
        repository = DocumentRepository()

        docs = {
            "doc1": {"name": "audio.md", "content": "Audio processing with librosa and pydub for signal analysis", "path": "/test/audio.md"},
            "doc2": {"name": "video.md", "content": "Video processing using opencv and ffmpeg for computer vision", "path": "/test/video.md"},
            "doc3": {"name": "nlp.md", "content": "Natural language processing with transformers and spacy", "path": "/test/nlp.md"},
            "doc4": {"name": "ml.md", "content": "Machine learning using scikit-learn and pytorch for deep learning", "path": "/test/ml.md"},
            "doc5": {"name": "data.md", "content": "Data analysis with pandas and numpy for scientific computing", "path": "/test/data.md"}
        }

        # Add documents to repository
        for doc_id, doc_data in docs.items():
            repository.add_document(doc_id, doc_data)

            # Index terms from content
            terms = doc_data['content'].lower().split()
            for term in terms:
                repository.index_term(term, doc_id)

        # Create query engine
        engine = QueryEngine(repository)
        return engine

    def test_concurrent_queries_no_corruption(self, query_engine):
        """Test 100 concurrent queries produce consistent results without corruption."""
        num_threads = 100
        queries = [
            "audio processing",
            "video opencv",
            "machine learning",
            "data analysis",
            "natural language"
        ]
        errors = []
        results_list = []

        def worker(thread_id):
            """Worker performing queries."""
            try:
                query = queries[thread_id % len(queries)]
                results = query_engine.execute_query(query)

                # Verify results are valid
                assert isinstance(results, list)
                for doc_id, doc in results:
                    assert isinstance(doc_id, str)
                    assert isinstance(doc, dict)
                    assert 'content' in doc
                    assert 'name' in doc

                results_list.append((thread_id, query, len(results)))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Query errors: {errors}"
        assert len(results_list) == num_threads

        # Verify same queries return same number of results
        query_results = {}
        for thread_id, query, num_results in results_list:
            if query not in query_results:
                query_results[query] = num_results
            else:
                assert query_results[query] == num_results, \
                    f"Inconsistent results for '{query}': {query_results[query]} vs {num_results}"

    def test_concurrent_queries_consistency(self, query_engine):
        """Test concurrent queries return consistent results."""
        num_threads = 50
        query = "audio processing"
        errors = []
        all_results = []

        def worker(thread_id):
            """Worker performing queries."""
            try:
                for _ in range(10):
                    results = query_engine.execute_query(query)
                    assert len(results) > 0
                    all_results.append(len(results))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Query errors: {errors}"

        # Verify all queries return same number of results
        assert len(set(all_results)) == 1, f"Inconsistent result counts: {set(all_results)}"

    def test_concurrent_repository_access(self, query_engine):
        """Test concurrent access to repository during queries."""
        num_threads = 100
        errors = []

        def worker(thread_id):
            """Worker performing queries."""
            try:
                queries = ["audio", "video", "ml", "data", "nlp", "processing"]
                for query in queries:
                    results = query_engine.execute_query(query)
                    assert isinstance(results, list)
                    # Verify we can access repository stats during queries
                    stats = query_engine.repository.get_stats()
                    assert stats['documents'] > 0
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent access errors: {errors}"

    def test_repository_stats_consistency(self, query_engine):
        """Test repository stats remain consistent under concurrent load."""
        num_threads = 50
        queries_per_thread = 20
        errors = []

        def worker(thread_id):
            """Worker performing queries and checking stats."""
            try:
                for i in range(queries_per_thread):
                    query_engine.execute_query(f"query audio {i % 5}")

                    # Stats should always be consistent
                    stats = query_engine.repository.get_stats()
                    assert stats['documents'] > 0
                    assert stats['terms'] > 0
                    assert stats['documents'] == stats['total_documents']
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Stats consistency errors: {errors}"


class TestRaceConditions:
    """Test for race conditions and edge cases."""

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


class TestPerformanceUnderLoad:
    """Test performance characteristics under concurrent load."""

    def test_throughput_with_concurrent_clients(self):
        """Test system throughput with 20 concurrent clients using Phase 2."""
        # Create test repository with documents
        repository = DocumentRepository()

        for i in range(10):
            doc_id = f"doc_{i}"
            content = f"Document {i} about topic_{i % 3} with keywords audio video ml data nlp processing"
            doc_data = {"name": f"doc_{i}.md", "content": content, "path": f"/test/doc_{i}.md"}
            repository.add_document(doc_id, doc_data)

            # Index terms
            terms = content.lower().split()
            for term in terms:
                repository.index_term(term, doc_id)

        # Create query engine
        engine = QueryEngine(repository)

        num_workers = 20
        queries_per_worker = 50
        start_time = time.time()
        errors = []

        def worker(thread_id):
            """Worker performing queries."""
            try:
                queries = ["audio", "video", "ml", "data", "nlp", "processing", "topic"]
                for i in range(queries_per_worker):
                    query = queries[i % len(queries)]
                    engine.execute_query(query)
            except Exception as e:
                errors.append((thread_id, str(e)))

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(worker, i) for i in range(num_workers)]
            for future in as_completed(futures):
                future.result()

        elapsed = time.time() - start_time
        total_queries = num_workers * queries_per_worker
        throughput = total_queries / elapsed

        assert len(errors) == 0, f"Throughput test errors: {errors}"
        assert throughput > 100, f"Throughput too low: {throughput:.2f} queries/sec"

        print(f"\nThroughput: {throughput:.2f} queries/sec ({total_queries} queries in {elapsed:.2f}s)")

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
