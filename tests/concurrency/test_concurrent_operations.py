"""
Comprehensive Concurrent Operations Tests for Phase 2 Architecture.

This test suite validates thread safety under extreme concurrent load:
- 1000+ concurrent operations
- Multi-component concurrent access
- Stress testing with sustained load
- Zero data corruption validation
"""

import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import pytest
import numpy as np

from knowledgebeast.core.repository import DocumentRepository
from knowledgebeast.core.query_engine import QueryEngine
from knowledgebeast.core.cache import LRUCache
from knowledgebeast.core.query.semantic_cache import SemanticCache


class TestMassiveConcurrentOperations:
    """Test thread safety with 1000+ concurrent operations."""

    def test_1000_concurrent_queries(self):
        """Test 1000 concurrent queries maintain consistency."""
        # Create repository with test data
        repository = DocumentRepository()

        for i in range(50):
            doc_id = f"doc_{i}"
            content = f"Document {i} about machine learning and data science with topics audio video nlp"
            doc_data = {"name": f"{doc_id}.md", "content": content, "path": f"/test/{doc_id}"}
            repository.add_document(doc_id, doc_data)

            terms = content.lower().split()
            for term in terms:
                repository.index_term(term, doc_id)

        engine = QueryEngine(repository)

        queries = ["machine learning", "data science", "audio video", "nlp topics"]
        errors = []
        results_count = []

        def execute_query(query_id):
            """Execute single query."""
            try:
                query = queries[query_id % len(queries)]
                results = engine.execute_query(query)
                results_count.append(len(results))
                return True
            except Exception as e:
                errors.append((query_id, str(e)))
                return False

        # Execute 1000 concurrent queries
        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(execute_query, i) for i in range(1000)]
            completed = sum(f.result() for f in as_completed(futures))

        # Verify
        assert len(errors) == 0, f"Errors occurred: {errors[:10]}"
        assert completed == 1000, f"Not all queries completed: {completed}/1000"
        assert len(results_count) == 1000, "Missing query results"

        print(f"\n1000 concurrent queries completed successfully")
        print(f"Average results per query: {sum(results_count)/len(results_count):.1f}")

    def test_1000_concurrent_repository_operations(self):
        """Test 1000 concurrent repository add/read operations."""
        repository = DocumentRepository()

        # Pre-populate with some data
        for i in range(100):
            doc_id = f"base_{i}"
            repository.add_document(doc_id, {"name": f"{doc_id}.md", "content": "base content", "path": f"/test/{doc_id}"})

        errors = []

        def repository_operation(op_id):
            """Perform repository operation."""
            try:
                if op_id % 2 == 0:
                    # Add document
                    doc_id = f"doc_{op_id}"
                    repository.add_document(doc_id, {
                        "name": f"{doc_id}.md",
                        "content": f"Content {op_id}",
                        "path": f"/test/{doc_id}"
                    })
                else:
                    # Read document
                    doc_id = f"base_{op_id % 100}"
                    doc = repository.get_document(doc_id)
                    assert doc is not None, f"Document {doc_id} not found"

                return True
            except Exception as e:
                errors.append((op_id, str(e)))
                return False

        # Execute 1000 concurrent operations
        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(repository_operation, i) for i in range(1000)]
            completed = sum(f.result() for f in as_completed(futures))

        # Verify
        assert len(errors) == 0, f"Errors occurred: {errors[:10]}"
        assert completed == 1000, f"Not all operations completed: {completed}/1000"

        # Verify repository stats are consistent
        stats = repository.get_stats()
        assert stats['documents'] >= 100, "Lost documents during concurrent operations"

        print(f"\n1000 concurrent repository operations completed")
        print(f"Final document count: {stats['documents']}")

    def test_1000_concurrent_cache_operations(self):
        """Test 1000 concurrent cache operations maintain integrity."""
        cache = LRUCache[int, str](capacity=500)
        errors = []

        def cache_operation(op_id):
            """Perform cache operation."""
            try:
                key = op_id % 1000
                value = f"value_{op_id}"

                # Mix of operations
                if op_id % 3 == 0:
                    cache.put(key, value)
                elif op_id % 3 == 1:
                    result = cache.get(key)
                else:
                    _ = key in cache
                    _ = len(cache)
                    stats = cache.stats()
                    assert stats['size'] <= stats['capacity'], "Capacity violated"

                return True
            except Exception as e:
                errors.append((op_id, str(e)))
                return False

        # Execute 1000 concurrent cache operations
        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(cache_operation, i) for i in range(1000)]
            completed = sum(f.result() for f in as_completed(futures))

        # Verify
        assert len(errors) == 0, f"Errors occurred: {errors[:10]}"
        assert completed == 1000, f"Not all operations completed: {completed}/1000"

        # Verify cache integrity
        stats = cache.stats()
        assert stats['size'] <= stats['capacity'], "Cache exceeded capacity"
        assert 0 <= stats['utilization'] <= 1.0, "Invalid utilization"

        print(f"\n1000 concurrent cache operations completed")
        print(f"Final cache size: {stats['size']}/{stats['capacity']}")

    def test_sustained_concurrent_load(self):
        """Test sustained concurrent load for 5 seconds."""
        repository = DocumentRepository()

        # Setup repository
        for i in range(50):
            doc_id = f"doc_{i}"
            content = f"Document {i} with content about data science and machine learning"
            repository.add_document(doc_id, {"name": f"{doc_id}.md", "content": content, "path": f"/test/{doc_id}"})

            terms = content.lower().split()
            for term in terms:
                repository.index_term(term, doc_id)

        engine = QueryEngine(repository)

        stop_event = threading.Event()
        operation_counts = {'queries': 0, 'reads': 0, 'stats': 0}
        errors = []
        lock = threading.Lock()

        def sustained_worker(worker_id):
            """Worker performing sustained operations."""
            try:
                local_counts = {'queries': 0, 'reads': 0, 'stats': 0}
                queries = ["data science", "machine learning", "content"]

                while not stop_event.is_set():
                    op = worker_id % 3

                    if op == 0:
                        engine.execute_query(queries[worker_id % len(queries)])
                        local_counts['queries'] += 1
                    elif op == 1:
                        repository.get_document(f"doc_{worker_id % 50}")
                        local_counts['reads'] += 1
                    else:
                        repository.get_stats()
                        local_counts['stats'] += 1

                # Update global counts
                with lock:
                    for key in local_counts:
                        operation_counts[key] += local_counts[key]

            except Exception as e:
                errors.append((worker_id, str(e)))

        # Start 50 workers
        workers = []
        for i in range(50):
            t = threading.Thread(target=sustained_worker, args=(i,))
            workers.append(t)
            t.start()

        # Run for 5 seconds
        time.sleep(5)
        stop_event.set()

        # Wait for all workers
        for t in workers:
            t.join(timeout=2.0)

        # Verify
        assert len(errors) == 0, f"Errors occurred: {errors[:10]}"

        total_ops = sum(operation_counts.values())
        print(f"\nSustained load test (5 seconds):")
        print(f"  Total operations: {total_ops}")
        print(f"  Queries: {operation_counts['queries']}")
        print(f"  Reads: {operation_counts['reads']}")
        print(f"  Stats: {operation_counts['stats']}")
        print(f"  Throughput: {total_ops/5:.0f} ops/sec")

        # Should complete many operations
        assert total_ops > 1000, f"Too few operations: {total_ops}"


class TestMultiComponentConcurrency:
    """Test concurrent access across multiple Phase 2 components."""

    def test_concurrent_repository_and_cache_access(self):
        """Test concurrent access to repository and cache simultaneously."""
        repository = DocumentRepository()
        cache = LRUCache[str, list](capacity=100)

        # Setup repository
        for i in range(50):
            doc_id = f"doc_{i}"
            repository.add_document(doc_id, {"name": f"{doc_id}.md", "content": f"Content {i}", "path": f"/test/{doc_id}"})

        errors = []

        def mixed_operation(op_id):
            """Perform operation on both repository and cache."""
            try:
                # Repository operation
                doc_id = f"doc_{op_id % 50}"
                doc = repository.get_document(doc_id)

                # Cache operation
                cache_key = f"key_{op_id}"
                if op_id % 2 == 0:
                    cache.put(cache_key, [doc_id])
                else:
                    cache.get(cache_key)

                return True
            except Exception as e:
                errors.append((op_id, str(e)))
                return False

        # Execute 500 concurrent mixed operations
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(mixed_operation, i) for i in range(500)]
            completed = sum(f.result() for f in as_completed(futures))

        # Verify
        assert len(errors) == 0, f"Errors occurred: {errors[:10]}"
        assert completed == 500, f"Not all operations completed: {completed}/500"

        print(f"\n500 mixed repository+cache operations completed")

    def test_concurrent_semantic_cache_operations(self):
        """Test concurrent semantic cache operations."""
        cache = SemanticCache(similarity_threshold=0.95, ttl_seconds=3600, max_entries=100)

        errors = []

        def semantic_cache_op(op_id):
            """Perform semantic cache operation."""
            try:
                query = f"query about topic {op_id % 10}"
                embedding = np.random.rand(384).astype(np.float32)

                if op_id % 2 == 0:
                    # Put operation
                    results = [{"doc": f"doc_{op_id}"}]
                    cache.put(query, embedding, results)
                else:
                    # Get operation
                    result = cache.get(query, embedding)

                return True
            except Exception as e:
                errors.append((op_id, str(e)))
                return False

        # Execute 200 concurrent semantic cache operations
        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = [executor.submit(semantic_cache_op, i) for i in range(200)]
            completed = sum(f.result() for f in as_completed(futures))

        # Verify
        assert len(errors) == 0, f"Errors occurred: {errors[:10]}"
        assert completed == 200, f"Not all operations completed: {completed}/200"

        stats = cache.get_stats()
        assert stats['total_queries'] > 0, "No queries recorded"

        print(f"\n200 semantic cache operations completed")
        print(f"Cache stats: {stats['hits']} hits, {stats['misses']} misses")


class TestZeroDataCorruption:
    """Validate zero data corruption under all concurrent scenarios."""

    def test_data_integrity_under_heavy_load(self):
        """Test data remains consistent under heavy concurrent load."""
        repository = DocumentRepository()

        # Add initial documents with known content
        initial_docs = {}
        for i in range(100):
            doc_id = f"doc_{i}"
            content = f"Document {i} content checksum_{i}"
            doc_data = {"name": f"{doc_id}.md", "content": content, "path": f"/test/{doc_id}"}
            repository.add_document(doc_id, doc_data)
            initial_docs[doc_id] = content

        engine = QueryEngine(repository)
        errors = []

        def verify_operation(op_id):
            """Perform operation and verify data integrity."""
            try:
                # Random read
                doc_id = f"doc_{op_id % 100}"
                doc = repository.get_document(doc_id)

                # Verify content hasn't been corrupted
                if doc:
                    expected_content = initial_docs[doc_id]
                    if doc['content'] != expected_content:
                        errors.append(f"Data corruption in {doc_id}: {doc['content']} != {expected_content}")

                # Concurrent query
                engine.execute_query("content checksum")

                return True
            except Exception as e:
                errors.append(str(e))
                return False

        # Execute 2000 concurrent operations
        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(verify_operation, i) for i in range(2000)]
            for future in as_completed(futures):
                future.result()

        # Verify zero corruption
        assert len(errors) == 0, f"Data corruption detected: {errors[:10]}"

        # Final integrity check
        for doc_id, expected_content in initial_docs.items():
            doc = repository.get_document(doc_id)
            assert doc is not None, f"Document {doc_id} lost"
            assert doc['content'] == expected_content, f"Content corrupted for {doc_id}"

        print(f"\n2000 concurrent operations completed with zero data corruption")

    def test_repository_stats_accuracy(self):
        """Test repository stats remain accurate under concurrent load."""
        repository = DocumentRepository()

        # Add 100 documents
        for i in range(100):
            doc_id = f"doc_{i}"
            repository.add_document(doc_id, {"name": f"{doc_id}.md", "content": f"Content {i}", "path": f"/test/{doc_id}"})

        errors = []
        stats_snapshots = []

        def concurrent_operation(op_id):
            """Perform operation and check stats."""
            try:
                # Get stats
                stats = repository.get_stats()
                stats_snapshots.append(stats['documents'])

                # Verify stats consistency
                assert stats['documents'] == stats['total_documents'], "Stats inconsistency"
                assert stats['documents'] >= 100, "Lost documents"

                # Read operation
                repository.get_document(f"doc_{op_id % 100}")

                return True
            except Exception as e:
                errors.append(str(e))
                return False

        # Execute 500 concurrent operations
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(concurrent_operation, i) for i in range(500)]
            for future in as_completed(futures):
                future.result()

        # Verify
        assert len(errors) == 0, f"Errors occurred: {errors[:10]}"

        # All stats snapshots should show consistent document count
        assert all(count == 100 for count in stats_snapshots), "Inconsistent stats"

        print(f"\n500 operations with consistent stats (all showed {stats_snapshots[0]} documents)")
