"""Performance tests for ChromaDB connection pooling.

Tests verify that connection pooling provides measurable performance improvements
by reducing connection overhead and caching collections.
"""

import pytest
import time
import tempfile
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from knowledgebeast.core.project_manager import ProjectManager


@pytest.fixture
def temp_storage():
    """Create temporary storage for tests."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def pm(temp_storage):
    """Create ProjectManager instance."""
    pm = ProjectManager(
        storage_path=str(temp_storage / "test_projects.db"),
        chroma_path=str(temp_storage / "test_chroma"),
        cache_capacity=100
    )
    yield pm
    pm.close()


def test_connection_pooling_basic(pm):
    """Test basic connection pooling functionality."""
    # Create a project
    project = pm.create_project("test_project")

    # Get collection multiple times
    start = time.time()
    for _ in range(10):
        collection = pm.get_collection(project.project_id)
        assert collection is not None
    pooled_time = time.time() - start

    # Should be very fast due to caching (< 100ms for 10 accesses)
    assert pooled_time < 0.1, f"Pooled access too slow: {pooled_time:.3f}s"

    # Verify collection is cached
    assert project.project_id in pm._collection_cache


def test_connection_pooling_performance(pm):
    """Test that connection pooling improves performance."""
    # Create a project
    project = pm.create_project("test_perf")

    # Warm up - first access will create connection
    pm.get_collection(project.project_id)

    # Measure cached access
    iterations = 100
    start = time.time()
    for _ in range(iterations):
        collection = pm.get_collection(project.project_id)
        assert collection is not None
    cached_time = time.time() - start

    avg_cached_time_ms = (cached_time / iterations) * 1000

    # Cached access should be very fast (< 1ms per access)
    assert avg_cached_time_ms < 1.0, f"Average cached access too slow: {avg_cached_time_ms:.2f}ms"

    print(f"\n✓ Connection pooling performance:")
    print(f"  - {iterations} collection accesses: {cached_time:.3f}s")
    print(f"  - Average per access: {avg_cached_time_ms:.3f}ms")


def test_concurrent_collection_access(pm):
    """Test concurrent access to collections with connection pooling."""
    # Create multiple projects
    project_ids = []
    for i in range(5):
        project = pm.create_project(f"concurrent_test_{i}")
        project_ids.append(project.project_id)

    # Concurrent access to collections
    def access_collection(project_id: str) -> float:
        start = time.time()
        for _ in range(10):
            collection = pm.get_collection(project_id)
            assert collection is not None
        return time.time() - start

    # Execute concurrently
    start = time.time()
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(access_collection, pid)
            for pid in project_ids
        ]

        times = [future.result() for future in as_completed(futures)]

    total_time = time.time() - start

    # All threads should complete quickly due to connection pooling
    assert total_time < 1.0, f"Concurrent access too slow: {total_time:.3f}s"

    # Individual thread times should be fast
    max_thread_time = max(times)
    assert max_thread_time < 0.5, f"Slowest thread too slow: {max_thread_time:.3f}s"

    print(f"\n✓ Concurrent collection access:")
    print(f"  - 5 threads × 10 accesses: {total_time:.3f}s")
    print(f"  - Slowest thread: {max_thread_time:.3f}s")


def test_cache_invalidation(pm):
    """Test that cache invalidation works correctly."""
    # Create project
    project = pm.create_project("cache_test")

    # Access collection (should be cached)
    collection1 = pm.get_collection(project.project_id)
    assert project.project_id in pm._collection_cache

    # Invalidate cache
    pm.invalidate_collection_cache(project.project_id)
    assert project.project_id not in pm._collection_cache

    # Access again (should re-cache)
    collection2 = pm.get_collection(project.project_id)
    assert project.project_id in pm._collection_cache

    # Collections should still work
    assert collection1 is not None
    assert collection2 is not None


def test_singleton_chroma_client(pm):
    """Test that ChromaDB client is a singleton."""
    # Access client multiple times
    client1 = pm.chroma_client
    client2 = pm.chroma_client
    client3 = pm.chroma_client

    # Should be same instance
    assert client1 is client2
    assert client2 is client3

    # Should only be created once
    assert pm._chroma_client is not None


def test_concurrent_client_initialization(temp_storage):
    """Test thread-safe client initialization with concurrent access."""
    pm = ProjectManager(
        storage_path=str(temp_storage / "concurrent_init.db"),
        chroma_path=str(temp_storage / "concurrent_chroma"),
        cache_capacity=100
    )

    clients = []

    def get_client():
        return pm.chroma_client

    # Multiple threads trying to get client simultaneously
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(get_client) for _ in range(10)]
        clients = [future.result() for future in as_completed(futures)]

    # All should be same instance
    first_client = clients[0]
    for client in clients[1:]:
        assert client is first_client

    pm.close()


def test_collection_cache_under_load(pm):
    """Test collection cache performance under concurrent load."""
    # Create projects
    num_projects = 10
    project_ids = []
    for i in range(num_projects):
        project = pm.create_project(f"load_test_{i}")
        project_ids.append(project.project_id)

    # Access collections from multiple threads
    def access_collections(iterations: int):
        for _ in range(iterations):
            # Randomly access different projects
            for pid in project_ids[:5]:  # Access subset
                collection = pm.get_collection(pid)
                assert collection is not None

    start = time.time()
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(access_collections, 10)
            for _ in range(5)
        ]

        for future in as_completed(futures):
            future.result()

    total_time = time.time() - start

    # Should complete quickly (5 threads × 10 iterations × 5 projects = 250 accesses)
    total_accesses = 5 * 10 * 5
    avg_access_time_ms = (total_time / total_accesses) * 1000

    assert avg_access_time_ms < 5.0, f"Average access too slow: {avg_access_time_ms:.2f}ms"

    print(f"\n✓ Collection cache under load:")
    print(f"  - {total_accesses} total accesses: {total_time:.3f}s")
    print(f"  - Average per access: {avg_access_time_ms:.2f}ms")


def test_connection_reuse_across_operations(pm):
    """Test that connection is reused across different operations."""
    # Create project
    project = pm.create_project("reuse_test")

    # Get client reference
    client_before = pm.chroma_client

    # Perform various operations
    for i in range(5):
        collection = pm.get_collection(project.project_id)
        assert collection is not None

    # Invalidate and re-access
    pm.invalidate_collection_cache(project.project_id)
    collection = pm.get_collection(project.project_id)

    # Client should still be same instance
    client_after = pm.chroma_client
    assert client_before is client_after


def test_close_cleanup(pm):
    """Test that close() properly cleans up resources."""
    # Create projects and access collections
    for i in range(3):
        project = pm.create_project(f"close_test_{i}")
        pm.get_collection(project.project_id)

    # Verify caches are populated
    assert len(pm._collection_cache) > 0
    assert pm._chroma_client is not None

    # Close
    pm.close()

    # Verify cleanup
    assert len(pm._collection_cache) == 0
    assert pm._chroma_client is None
    assert len(pm._project_caches) == 0


@pytest.mark.benchmark
def test_pooling_vs_no_pooling_simulation(temp_storage):
    """Simulate performance difference between pooling and no pooling.

    This test demonstrates the performance benefit of connection pooling.
    """
    # Setup
    pm = ProjectManager(
        storage_path=str(temp_storage / "bench.db"),
        chroma_path=str(temp_storage / "bench_chroma"),
    )

    project = pm.create_project("benchmark_project")

    # Warm up
    pm.get_collection(project.project_id)

    # Measure with pooling (cached)
    iterations = 50
    start = time.time()
    for _ in range(iterations):
        collection = pm.get_collection(project.project_id)
    pooled_time = time.time() - start

    # Measure with cache invalidation (simulating no pooling)
    start = time.time()
    for _ in range(iterations):
        pm.invalidate_collection_cache(project.project_id)
        collection = pm.get_collection(project.project_id)
    non_pooled_time = time.time() - start

    # Calculate improvement
    improvement = (non_pooled_time / pooled_time)

    print(f"\n✓ Connection pooling benchmark:")
    print(f"  - With pooling: {pooled_time:.3f}s ({iterations} accesses)")
    print(f"  - Without pooling: {non_pooled_time:.3f}s ({iterations} accesses)")
    print(f"  - Performance improvement: {improvement:.1f}x")

    # Should show measurable improvement (at least 2x)
    assert improvement >= 2.0, f"Insufficient improvement: {improvement:.1f}x"

    pm.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
