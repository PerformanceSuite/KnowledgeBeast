"""Multi-Project Concurrency Tests.

Tests cover:
- Concurrent project CRUD operations
- 1000+ thread stress tests
- Multi-project cache isolation under load
- Concurrent collection access
- Thread-safe project manager operations
- Race condition detection
- Data corruption detection
"""

import pytest
import tempfile
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from knowledgebeast.core.project_manager import ProjectManager


class TestConcurrentProjectCRUD:
    """Test concurrent CRUD operations."""

    @pytest.fixture
    def manager(self):
        """Create a temporary ProjectManager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "projects.db"
            chroma_path = Path(tmpdir) / "chroma"
            manager = ProjectManager(
                storage_path=str(storage_path),
                chroma_path=str(chroma_path)
            )
            yield manager
            manager.cleanup_all()

    def test_concurrent_project_creation(self, manager):
        """Test creating projects concurrently."""
        num_threads = 50
        errors = []

        def create_project(thread_id):
            try:
                project = manager.create_project(
                    name=f"Project {thread_id}",
                    description=f"Description {thread_id}"
                )
                assert project is not None
                assert project.name == f"Project {thread_id}"
                return project.project_id
            except Exception as e:
                errors.append((thread_id, str(e)))
                return None

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(create_project, i) for i in range(num_threads)]
            results = [f.result() for f in as_completed(futures)]

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len([r for r in results if r is not None]) == num_threads

        # Verify all projects were created
        projects = manager.list_projects()
        assert len(projects) == num_threads

    def test_concurrent_project_read(self, manager):
        """Test reading projects concurrently."""
        # Create projects
        project_ids = []
        for i in range(10):
            project = manager.create_project(name=f"Project {i}")
            project_ids.append(project.project_id)

        num_threads = 100
        errors = []

        def read_project(thread_id):
            try:
                project_id = project_ids[thread_id % len(project_ids)]
                project = manager.get_project(project_id)
                assert project is not None
                assert project.project_id == project_id
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=read_project, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Read errors: {errors}"

    def test_concurrent_project_update(self, manager):
        """Test updating projects concurrently."""
        # Create projects
        project_ids = []
        for i in range(10):
            project = manager.create_project(name=f"Project {i}")
            project_ids.append(project.project_id)

        num_threads = 50
        errors = []

        def update_project(thread_id):
            try:
                project_id = project_ids[thread_id % len(project_ids)]
                updated = manager.update_project(
                    project_id,
                    description=f"Updated by thread {thread_id}"
                )
                assert updated is not None
            except Exception as e:
                errors.append((thread_id, str(e)))

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(update_project, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Update errors: {errors}"

    def test_concurrent_project_delete(self, manager):
        """Test deleting projects concurrently."""
        # Create projects
        project_ids = []
        for i in range(50):
            project = manager.create_project(name=f"Project {i}")
            project_ids.append(project.project_id)

        num_threads = 50
        errors = []
        deleted_count = [0]
        lock = threading.Lock()

        def delete_project(thread_id):
            try:
                project_id = project_ids[thread_id]
                result = manager.delete_project(project_id)
                if result:
                    with lock:
                        deleted_count[0] += 1
            except Exception as e:
                errors.append((thread_id, str(e)))

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(delete_project, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Delete errors: {errors}"
        assert deleted_count[0] == 50

        # Verify all projects are deleted
        projects = manager.list_projects()
        assert len(projects) == 0

    def test_concurrent_mixed_operations(self, manager):
        """Test mixed CRUD operations concurrently."""
        num_operations = 100
        errors = []

        def create_worker(op_id):
            try:
                manager.create_project(name=f"Create {op_id}")
            except Exception as e:
                errors.append(('create', op_id, str(e)))

        def read_worker(op_id):
            try:
                projects = manager.list_projects()
                if projects:
                    manager.get_project(projects[0].project_id)
            except Exception as e:
                errors.append(('read', op_id, str(e)))

        def update_worker(op_id):
            try:
                projects = manager.list_projects()
                if projects:
                    manager.update_project(
                        projects[0].project_id,
                        description=f"Updated {op_id}"
                    )
            except Exception as e:
                errors.append(('update', op_id, str(e)))

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = []
            for i in range(num_operations):
                if i % 3 == 0:
                    futures.append(executor.submit(create_worker, i))
                elif i % 3 == 1:
                    futures.append(executor.submit(read_worker, i))
                else:
                    futures.append(executor.submit(update_worker, i))

            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Mixed operation errors: {errors}"


class TestConcurrentCacheIsolation:
    """Test per-project cache isolation under concurrent load."""

    @pytest.fixture
    def manager(self):
        """Create a temporary ProjectManager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "projects.db"
            chroma_path = Path(tmpdir) / "chroma"
            manager = ProjectManager(
                storage_path=str(storage_path),
                chroma_path=str(chroma_path),
                cache_capacity=50
            )
            yield manager
            manager.cleanup_all()

    def test_concurrent_cache_access_isolated(self, manager):
        """Test concurrent cache access maintains isolation."""
        # Create projects
        projects = []
        for i in range(10):
            project = manager.create_project(name=f"Project {i}")
            projects.append(project)

        num_threads = 100
        errors = []

        def cache_worker(thread_id):
            try:
                project = projects[thread_id % len(projects)]
                cache = manager.get_project_cache(project.project_id)

                # Add entries
                for i in range(10):
                    key = f"thread_{thread_id}_key_{i}"
                    value = f"value_{i}"
                    cache.put(key, value)

                # Verify our entries are there
                for i in range(10):
                    key = f"thread_{thread_id}_key_{i}"
                    result = cache.get(key)
                    # Entry might have been evicted, but if present, must be correct
                    if result is not None:
                        assert result == f"value_{i}"

            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=cache_worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Cache isolation errors: {errors}"

    def test_concurrent_cache_clear(self, manager):
        """Test clearing caches concurrently."""
        # Create projects
        projects = []
        for i in range(10):
            project = manager.create_project(name=f"Project {i}")
            projects.append(project)

            # Populate cache
            cache = manager.get_project_cache(project.project_id)
            for j in range(20):
                cache.put(f"key_{j}", f"value_{j}")

        num_threads = 20
        errors = []

        def clear_worker(thread_id):
            try:
                project = projects[thread_id % len(projects)]
                manager.clear_project_cache(project.project_id)
            except Exception as e:
                errors.append((thread_id, str(e)))

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(clear_worker, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Cache clear errors: {errors}"

    def test_concurrent_cache_operations_no_cross_contamination(self, manager):
        """Test no data leakage between project caches under load."""
        # Create projects
        p1 = manager.create_project(name="Project 1")
        p2 = manager.create_project(name="Project 2")

        cache1 = manager.get_project_cache(p1.project_id)
        cache2 = manager.get_project_cache(p2.project_id)

        num_threads = 50
        errors = []
        cross_contamination = [False]

        def worker1(thread_id):
            try:
                for i in range(100):
                    cache1.put(f"p1_key_{i}", f"p1_value_{i}")

                    # Check for contamination
                    p2_data = cache1.get(f"p2_key_0")
                    if p2_data is not None:
                        cross_contamination[0] = True
            except Exception as e:
                errors.append(('w1', thread_id, str(e)))

        def worker2(thread_id):
            try:
                for i in range(100):
                    cache2.put(f"p2_key_{i}", f"p2_value_{i}")

                    # Check for contamination
                    p1_data = cache2.get(f"p1_key_0")
                    if p1_data is not None:
                        cross_contamination[0] = True
            except Exception as e:
                errors.append(('w2', thread_id, str(e)))

        threads = []
        for i in range(num_threads):
            t1 = threading.Thread(target=worker1, args=(i,))
            t2 = threading.Thread(target=worker2, args=(i,))
            threads.append(t1)
            threads.append(t2)
            t1.start()
            t2.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"
        assert not cross_contamination[0], "Cross-contamination detected!"


class TestStressTests:
    """Stress tests with 1000+ concurrent operations."""

    @pytest.fixture
    def manager(self):
        """Create a temporary ProjectManager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "projects.db"
            chroma_path = Path(tmpdir) / "chroma"
            manager = ProjectManager(
                storage_path=str(storage_path),
                chroma_path=str(chroma_path)
            )
            yield manager
            manager.cleanup_all()

    def test_stress_1000_concurrent_project_creates(self, manager):
        """Stress test: 1000 concurrent project creations."""
        num_operations = 1000
        errors = []

        def create_operation(op_id):
            try:
                project = manager.create_project(
                    name=f"StressProject_{op_id}",
                    description=f"Stress test project {op_id}"
                )
                assert project is not None
                return True
            except Exception as e:
                errors.append((op_id, str(e)))
                return False

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(create_operation, i) for i in range(num_operations)]
            results = [f.result() for f in as_completed(futures)]

        elapsed = time.time() - start_time

        assert len(errors) == 0, f"Stress test errors: {errors[:10]}"
        assert sum(results) == num_operations

        # Verify all projects exist
        projects = manager.list_projects()
        assert len(projects) == num_operations

        print(f"\n1000 concurrent creates: {elapsed:.2f}s ({num_operations/elapsed:.2f} ops/sec)")

    def test_stress_1000_concurrent_reads(self, manager):
        """Stress test: 1000 concurrent project reads."""
        # Create test projects
        project_ids = []
        for i in range(20):
            project = manager.create_project(name=f"Project {i}")
            project_ids.append(project.project_id)

        num_operations = 1000
        errors = []

        def read_operation(op_id):
            try:
                project_id = project_ids[op_id % len(project_ids)]
                project = manager.get_project(project_id)
                assert project is not None
                return True
            except Exception as e:
                errors.append((op_id, str(e)))
                return False

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(read_operation, i) for i in range(num_operations)]
            results = [f.result() for f in as_completed(futures)]

        elapsed = time.time() - start_time

        assert len(errors) == 0, f"Read stress errors: {errors}"
        assert sum(results) == num_operations

        print(f"\n1000 concurrent reads: {elapsed:.2f}s ({num_operations/elapsed:.2f} ops/sec)")

    def test_stress_1000_concurrent_cache_operations(self, manager):
        """Stress test: 1000 concurrent cache operations."""
        # Create projects
        projects = []
        for i in range(10):
            project = manager.create_project(name=f"Project {i}")
            projects.append(project)

        num_operations = 1000
        errors = []

        def cache_operation(op_id):
            try:
                project = projects[op_id % len(projects)]
                cache = manager.get_project_cache(project.project_id)

                # Perform cache operation
                cache.put(f"key_{op_id}", f"value_{op_id}")
                result = cache.get(f"key_{op_id}")

                # Might be evicted, but if present, must be correct
                if result is not None:
                    assert result == f"value_{op_id}"

                return True
            except Exception as e:
                errors.append((op_id, str(e)))
                return False

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(cache_operation, i) for i in range(num_operations)]
            results = [f.result() for f in as_completed(futures)]

        elapsed = time.time() - start_time

        assert len(errors) == 0, f"Cache stress errors: {errors}"
        assert sum(results) == num_operations

        print(f"\n1000 concurrent cache ops: {elapsed:.2f}s ({num_operations/elapsed:.2f} ops/sec)")

    def test_stress_1000_mixed_operations(self, manager):
        """Stress test: 1000 mixed operations (create, read, update, delete)."""
        num_operations = 1000
        errors = []
        lock = threading.Lock()
        created_projects = []

        def mixed_operation(op_id):
            try:
                op_type = op_id % 4

                if op_type == 0:  # Create
                    project = manager.create_project(name=f"Project_{op_id}")
                    with lock:
                        created_projects.append(project.project_id)

                elif op_type == 1:  # Read
                    projects = manager.list_projects()
                    if projects:
                        manager.get_project(projects[0].project_id)

                elif op_type == 2:  # Update
                    projects = manager.list_projects()
                    if projects:
                        manager.update_project(
                            projects[0].project_id,
                            description=f"Updated_{op_id}"
                        )

                elif op_type == 3:  # Cache operation
                    projects = manager.list_projects()
                    if projects:
                        cache = manager.get_project_cache(projects[0].project_id)
                        cache.put(f"key_{op_id}", f"value_{op_id}")

                return True
            except Exception as e:
                errors.append((op_id, str(e)))
                return False

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(mixed_operation, i) for i in range(num_operations)]
            results = [f.result() for f in as_completed(futures)]

        elapsed = time.time() - start_time

        assert len(errors) == 0, f"Mixed stress errors: {errors[:10]}"
        assert sum(results) == num_operations

        print(f"\n1000 mixed operations: {elapsed:.2f}s ({num_operations/elapsed:.2f} ops/sec)")

    def test_stress_concurrent_project_lifecycle(self, manager):
        """Stress test: Full lifecycle (create, use, delete) for many projects."""
        num_projects = 200
        errors = []

        def project_lifecycle(project_id):
            try:
                # Create
                project = manager.create_project(
                    name=f"Lifecycle_{project_id}",
                    description=f"Lifecycle test {project_id}"
                )

                # Use cache
                cache = manager.get_project_cache(project.project_id)
                for i in range(10):
                    cache.put(f"key_{i}", f"value_{i}")

                # Read
                retrieved = manager.get_project(project.project_id)
                assert retrieved is not None

                # Update
                manager.update_project(
                    project.project_id,
                    description="Updated"
                )

                # Delete
                result = manager.delete_project(project.project_id)
                assert result is True

                return True
            except Exception as e:
                errors.append((project_id, str(e)))
                return False

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(project_lifecycle, i) for i in range(num_projects)]
            results = [f.result() for f in as_completed(futures)]

        elapsed = time.time() - start_time

        assert len(errors) == 0, f"Lifecycle errors: {errors}"
        assert sum(results) == num_projects

        # Verify all projects are deleted
        projects = manager.list_projects()
        assert len(projects) == 0

        print(f"\n{num_projects} project lifecycles: {elapsed:.2f}s ({num_projects/elapsed:.2f} projects/sec)")


class TestRaceConditions:
    """Test for race conditions and data corruption."""

    @pytest.fixture
    def manager(self):
        """Create a temporary ProjectManager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "projects.db"
            chroma_path = Path(tmpdir) / "chroma"
            manager = ProjectManager(
                storage_path=str(storage_path),
                chroma_path=str(chroma_path)
            )
            yield manager
            manager.cleanup_all()

    def test_race_condition_duplicate_names(self, manager):
        """Test race condition: concurrent attempts to create same name."""
        num_threads = 50
        errors = []
        success_count = [0]
        lock = threading.Lock()

        def create_same_name(thread_id):
            try:
                manager.create_project(name="SameName")
                with lock:
                    success_count[0] += 1
            except ValueError:
                # Expected: duplicate name error
                pass
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=create_same_name, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Only one should succeed
        assert success_count[0] == 1, f"Expected 1 success, got {success_count[0]}"
        assert len(errors) == 0, f"Unexpected errors: {errors}"

    def test_race_condition_update_same_project(self, manager):
        """Test race condition: concurrent updates to same project."""
        project = manager.create_project(name="Test")

        num_threads = 100
        errors = []

        def update_worker(thread_id):
            try:
                manager.update_project(
                    project.project_id,
                    description=f"Update {thread_id}"
                )
            except Exception as e:
                errors.append((thread_id, str(e)))

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(update_worker, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Update race errors: {errors}"

        # Project should still be valid
        updated = manager.get_project(project.project_id)
        assert updated is not None

    def test_race_condition_delete_while_reading(self, manager):
        """Test race condition: deleting project while others read it."""
        project = manager.create_project(name="Test")

        num_readers = 50
        stop_event = threading.Event()
        errors = []

        def reader_worker(thread_id):
            try:
                while not stop_event.is_set():
                    manager.get_project(project.project_id)
                    time.sleep(0.001)
            except Exception as e:
                # Acceptable: project might be deleted
                pass

        def deleter_worker():
            try:
                time.sleep(0.05)
                manager.delete_project(project.project_id)
                stop_event.set()
            except Exception as e:
                errors.append(('deleter', str(e)))

        # Start readers
        threads = []
        for i in range(num_readers):
            t = threading.Thread(target=reader_worker, args=(i,))
            threads.append(t)
            t.start()

        # Start deleter
        deleter_thread = threading.Thread(target=deleter_worker)
        deleter_thread.start()

        # Wait for completion
        deleter_thread.join()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Delete race errors: {errors}"

        # Verify project is deleted
        result = manager.get_project(project.project_id)
        assert result is None

    def test_data_consistency_under_load(self, manager):
        """Test data consistency under heavy concurrent load."""
        num_operations = 500
        errors = []
        created_count = [0]
        deleted_count = [0]
        lock = threading.Lock()

        def create_worker(op_id):
            try:
                manager.create_project(name=f"Project_{op_id}")
                with lock:
                    created_count[0] += 1
            except Exception as e:
                errors.append(('create', op_id, str(e)))

        def delete_worker(op_id):
            try:
                projects = manager.list_projects()
                if projects:
                    result = manager.delete_project(projects[0].project_id)
                    if result:
                        with lock:
                            deleted_count[0] += 1
            except Exception as e:
                errors.append(('delete', op_id, str(e)))

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = []
            for i in range(num_operations):
                if i % 2 == 0:
                    futures.append(executor.submit(create_worker, i))
                else:
                    futures.append(executor.submit(delete_worker, i))

            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Consistency errors: {errors[:10]}"

        # Verify consistency: created - deleted = current count
        current_projects = manager.list_projects()
        expected_count = created_count[0] - deleted_count[0]
        assert len(current_projects) == expected_count, \
            f"Inconsistent state: created={created_count[0]}, deleted={deleted_count[0]}, current={len(current_projects)}"


class TestConcurrentCollectionAccess:
    """Test concurrent ChromaDB collection access."""

    @pytest.fixture
    def manager(self):
        """Create a temporary ProjectManager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "projects.db"
            chroma_path = Path(tmpdir) / "chroma"
            manager = ProjectManager(
                storage_path=str(storage_path),
                chroma_path=str(chroma_path)
            )
            yield manager
            manager.cleanup_all()

    def test_concurrent_collection_access(self, manager):
        """Test concurrent access to ChromaDB collections."""
        # Create projects
        projects = []
        for i in range(10):
            project = manager.create_project(name=f"Project {i}")
            projects.append(project)

        num_threads = 50
        errors = []

        def collection_worker(thread_id):
            try:
                project = projects[thread_id % len(projects)]
                collection = manager.get_project_collection(project.project_id)
                assert collection is not None
                assert collection.name == project.collection_name
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=collection_worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Collection access errors: {errors}"

    def test_concurrent_collection_creation_and_deletion(self, manager):
        """Test concurrent collection creation and deletion."""
        num_operations = 100
        errors = []

        def create_delete_worker(op_id):
            try:
                # Create project (creates collection)
                project = manager.create_project(name=f"TempProject_{op_id}")

                # Verify collection exists
                collection = manager.get_project_collection(project.project_id)
                assert collection is not None

                # Delete project (deletes collection)
                manager.delete_project(project.project_id)

            except Exception as e:
                errors.append((op_id, str(e)))

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(create_delete_worker, i) for i in range(num_operations)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Collection lifecycle errors: {errors}"
