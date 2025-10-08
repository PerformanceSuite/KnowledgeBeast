"""Integration tests for multi-project isolation.

Tests verify complete isolation between projects:
- Zero data leakage between project caches
- Zero data leakage between project collections
- Correct project metadata persistence
- End-to-end project lifecycle scenarios
"""

import pytest
import tempfile
import time
from pathlib import Path

from knowledgebeast.core.project_manager import ProjectManager


class TestProjectIsolation:
    """Test complete isolation between projects."""

    @pytest.fixture
    def manager(self):
        """Create a temporary ProjectManager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "projects.db"
            chroma_path = Path(tmpdir) / "chroma"
            manager = ProjectManager(
                storage_path=str(storage_path),
                chroma_path=str(chroma_path),
                cache_capacity=100
            )
            yield manager
            manager.cleanup_all()

    def test_cache_isolation_zero_leakage(self, manager):
        """Test zero data leakage between project caches."""
        # Create multiple projects
        projects = []
        for i in range(5):
            project = manager.create_project(
                name=f"Project {i}",
                description=f"Project {i} description"
            )
            projects.append(project)

        # Populate each cache with unique data
        cache_data = {}
        for i, project in enumerate(projects):
            cache = manager.get_project_cache(project.project_id)
            cache_data[project.project_id] = {}

            for j in range(50):
                key = f"p{i}_key_{j}"
                value = f"p{i}_value_{j}"
                cache.put(key, value)
                cache_data[project.project_id][key] = value

        # Verify complete isolation - each cache only contains its own data
        for i, project in enumerate(projects):
            cache = manager.get_project_cache(project.project_id)

            # Check our own keys are present
            our_keys = cache_data[project.project_id]
            for key, value in our_keys.items():
                retrieved = cache.get(key)
                # Might be evicted due to capacity, but if present must match
                if retrieved is not None:
                    assert retrieved == value, f"Data corruption in project {i}"

            # Check other projects' keys are NOT present
            for j, other_project in enumerate(projects):
                if i == j:
                    continue

                other_keys = cache_data[other_project.project_id]
                for key in other_keys.keys():
                    retrieved = cache.get(key)
                    assert retrieved is None, \
                        f"Data leakage: Project {i} contains data from Project {j}"

    def test_collection_isolation_zero_leakage(self, manager):
        """Test zero data leakage between ChromaDB collections."""
        # Create multiple projects
        projects = []
        for i in range(3):
            project = manager.create_project(name=f"Project {i}")
            projects.append(project)

        # Verify each project has its own collection
        collections = []
        for project in projects:
            collection = manager.get_project_collection(project.project_id)
            assert collection is not None
            collections.append(collection)

        # Verify collections have unique names
        collection_names = [c.name for c in collections]
        assert len(collection_names) == len(set(collection_names)), \
            "Collections must have unique names"

        # Verify each collection name matches project
        for i, project in enumerate(projects):
            expected_name = f"kb_project_{project.project_id}"
            assert collections[i].name == expected_name

    def test_metadata_persistence_isolation(self, manager):
        """Test metadata is correctly persisted and isolated."""
        # Create projects with different metadata
        p1 = manager.create_project(
            name="Project 1",
            metadata={"type": "audio", "version": "1.0"}
        )
        p2 = manager.create_project(
            name="Project 2",
            metadata={"type": "video", "version": "2.0"}
        )
        p3 = manager.create_project(
            name="Project 3",
            metadata={"type": "text", "version": "3.0"}
        )

        # Retrieve and verify metadata
        retrieved_p1 = manager.get_project(p1.project_id)
        assert retrieved_p1.metadata == {"type": "audio", "version": "1.0"}

        retrieved_p2 = manager.get_project(p2.project_id)
        assert retrieved_p2.metadata == {"type": "video", "version": "2.0"}

        retrieved_p3 = manager.get_project(p3.project_id)
        assert retrieved_p3.metadata == {"type": "text", "version": "3.0"}

    def test_project_deletion_cleanup_isolation(self, manager):
        """Test deleting one project doesn't affect others."""
        # Create multiple projects
        p1 = manager.create_project(name="Project 1")
        p2 = manager.create_project(name="Project 2")
        p3 = manager.create_project(name="Project 3")

        # Populate caches
        for project in [p1, p2, p3]:
            cache = manager.get_project_cache(project.project_id)
            for i in range(10):
                cache.put(f"key_{i}", f"value_{i}")

        # Delete p2
        result = manager.delete_project(p2.project_id)
        assert result is True

        # Verify p2 is gone
        assert manager.get_project(p2.project_id) is None
        assert manager.get_project_cache(p2.project_id) is None

        # Verify p1 and p3 are unaffected
        assert manager.get_project(p1.project_id) is not None
        assert manager.get_project(p3.project_id) is not None

        cache1 = manager.get_project_cache(p1.project_id)
        cache3 = manager.get_project_cache(p3.project_id)

        assert cache1.get("key_0") == "value_0"
        assert cache3.get("key_0") == "value_0"


class TestEndToEndScenarios:
    """Test end-to-end multi-project scenarios."""

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

    def test_multi_tenant_scenario(self, manager):
        """Test multi-tenant scenario with isolated projects."""
        # Simulate 3 tenants with multiple projects each
        tenants = {
            "tenant_a": [],
            "tenant_b": [],
            "tenant_c": []
        }

        # Create projects for each tenant
        for tenant, project_list in tenants.items():
            for i in range(3):
                project = manager.create_project(
                    name=f"{tenant}_project_{i}",
                    description=f"Project {i} for {tenant}",
                    metadata={"tenant": tenant, "project_num": i}
                )
                project_list.append(project)

        # Verify total project count
        all_projects = manager.list_projects()
        assert len(all_projects) == 9

        # Verify each tenant's projects are isolated
        for tenant, project_list in tenants.items():
            for project in project_list:
                retrieved = manager.get_project(project.project_id)
                assert retrieved.metadata["tenant"] == tenant

    def test_project_migration_scenario(self, manager):
        """Test migrating project data (update metadata)."""
        # Create original project
        project = manager.create_project(
            name="Original Project",
            description="Original description",
            metadata={"version": "1.0", "status": "active"}
        )

        # Simulate migration - update metadata
        updated = manager.update_project(
            project.project_id,
            description="Migrated description",
            metadata={"version": "2.0", "status": "migrated", "migration_date": "2025-10-07"}
        )

        assert updated.description == "Migrated description"
        assert updated.metadata["version"] == "2.0"
        assert updated.metadata["status"] == "migrated"
        assert "migration_date" in updated.metadata

    def test_project_archival_scenario(self, manager):
        """Test archiving projects (mark as archived in metadata)."""
        # Create active projects
        active_projects = []
        for i in range(5):
            project = manager.create_project(
                name=f"Project {i}",
                metadata={"status": "active"}
            )
            active_projects.append(project)

        # Archive some projects
        for i in [0, 2, 4]:
            manager.update_project(
                active_projects[i].project_id,
                metadata={"status": "archived"}
            )

        # List and filter archived projects
        all_projects = manager.list_projects()
        archived = [p for p in all_projects if p.metadata.get("status") == "archived"]
        active = [p for p in all_projects if p.metadata.get("status") == "active"]

        assert len(archived) == 3
        assert len(active) == 2

    def test_batch_project_creation_and_cleanup(self, manager):
        """Test batch creation and cleanup of projects."""
        # Create batch of projects
        batch_size = 50
        project_ids = []

        for i in range(batch_size):
            project = manager.create_project(
                name=f"Batch_Project_{i}",
                description=f"Batch project {i}",
                metadata={"batch": "test_batch_001"}
            )
            project_ids.append(project.project_id)

        # Verify all created
        assert len(manager.list_projects()) == batch_size

        # Batch cleanup - delete all projects with specific metadata
        all_projects = manager.list_projects()
        batch_projects = [p for p in all_projects if p.metadata.get("batch") == "test_batch_001"]

        for project in batch_projects:
            manager.delete_project(project.project_id)

        # Verify all deleted
        assert len(manager.list_projects()) == 0

    def test_high_volume_project_rotation(self, manager):
        """Test high-volume project creation and rotation."""
        # Simulate rolling window of projects
        max_projects = 20
        total_iterations = 100

        for i in range(total_iterations):
            # Create new project
            project = manager.create_project(
                name=f"Rotating_Project_{i}",
                metadata={"iteration": i}
            )

            # If over limit, delete oldest
            projects = manager.list_projects()
            if len(projects) > max_projects:
                # Delete oldest (last in list since ordered by created_at DESC)
                oldest = projects[-1]
                manager.delete_project(oldest.project_id)

            # Verify constraint maintained
            assert len(manager.list_projects()) <= max_projects

        # Final verification
        final_projects = manager.list_projects()
        assert len(final_projects) == max_projects

        # Verify only recent projects remain
        for project in final_projects:
            assert project.metadata["iteration"] >= total_iterations - max_projects


class TestPersistence:
    """Test project persistence across manager instances."""

    def test_projects_persist_across_instances(self):
        """Test projects persist when recreating manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "projects.db"
            chroma_path = Path(tmpdir) / "chroma"

            # Create manager and projects
            manager1 = ProjectManager(
                storage_path=str(storage_path),
                chroma_path=str(chroma_path)
            )

            p1 = manager1.create_project(
                name="Project 1",
                description="Description 1",
                metadata={"key": "value1"}
            )
            p2 = manager1.create_project(
                name="Project 2",
                description="Description 2",
                metadata={"key": "value2"}
            )

            project_ids = [p1.project_id, p2.project_id]

            # Close manager
            manager1.cleanup_all()
            del manager1

            # Create new manager instance
            manager2 = ProjectManager(
                storage_path=str(storage_path),
                chroma_path=str(chroma_path)
            )

            # Verify projects persisted
            retrieved_p1 = manager2.get_project(project_ids[0])
            retrieved_p2 = manager2.get_project(project_ids[1])

            assert retrieved_p1 is not None
            assert retrieved_p1.name == "Project 1"
            assert retrieved_p1.description == "Description 1"
            assert retrieved_p1.metadata == {"key": "value1"}

            assert retrieved_p2 is not None
            assert retrieved_p2.name == "Project 2"
            assert retrieved_p2.metadata == {"key": "value2"}

            manager2.cleanup_all()

    def test_collections_persist_across_instances(self):
        """Test ChromaDB collections persist across manager instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "projects.db"
            chroma_path = Path(tmpdir) / "chroma"

            # Create manager and project
            manager1 = ProjectManager(
                storage_path=str(storage_path),
                chroma_path=str(chroma_path)
            )

            project = manager1.create_project(name="Test Project")
            project_id = project.project_id
            collection_name = project.collection_name

            # Verify collection exists
            collection1 = manager1.get_project_collection(project_id)
            assert collection1 is not None

            # Don't cleanup - we want to test persistence
            # Just delete the manager instance
            del manager1

            # Create new manager instance
            manager2 = ProjectManager(
                storage_path=str(storage_path),
                chroma_path=str(chroma_path)
            )

            # Verify collection still exists
            collection2 = manager2.get_project_collection(project_id)
            assert collection2 is not None
            assert collection2.name == collection_name

            # Cleanup at the end
            manager2.cleanup_all()


class TestScalability:
    """Test scalability with large numbers of projects."""

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

    def test_100_projects_creation_and_access(self, manager):
        """Test creating and accessing 100 projects."""
        num_projects = 100
        project_ids = []

        # Create 100 projects
        start_time = time.time()
        for i in range(num_projects):
            project = manager.create_project(
                name=f"Project_{i:03d}",
                description=f"Project number {i}",
                metadata={"index": i}
            )
            project_ids.append(project.project_id)

        creation_time = time.time() - start_time

        # Verify all created
        all_projects = manager.list_projects()
        assert len(all_projects) == num_projects

        # Access all projects
        start_time = time.time()
        for project_id in project_ids:
            project = manager.get_project(project_id)
            assert project is not None

        access_time = time.time() - start_time

        # Access caches
        start_time = time.time()
        for project_id in project_ids:
            cache = manager.get_project_cache(project_id)
            assert cache is not None

        cache_time = time.time() - start_time

        print(f"\n100 projects performance:")
        print(f"  Creation: {creation_time:.2f}s ({num_projects/creation_time:.2f} projects/sec)")
        print(f"  Access: {access_time:.2f}s ({num_projects/access_time:.2f} projects/sec)")
        print(f"  Cache init: {cache_time:.2f}s ({num_projects/cache_time:.2f} caches/sec)")

        # Verify stats
        stats = manager.get_stats()
        assert stats['total_projects'] == num_projects

    def test_project_isolation_at_scale(self, manager):
        """Test isolation is maintained with many projects."""
        num_projects = 50

        # Create projects
        projects = []
        for i in range(num_projects):
            project = manager.create_project(name=f"Project_{i}")
            projects.append(project)

        # Populate each cache with unique data
        for i, project in enumerate(projects):
            cache = manager.get_project_cache(project.project_id)
            for j in range(20):
                cache.put(f"p{i}_key_{j}", f"p{i}_value_{j}")

        # Verify isolation for random sample
        import random
        sample_size = 10
        sample = random.sample(projects, sample_size)

        for i, project in enumerate(sample):
            cache = manager.get_project_cache(project.project_id)

            # Find original index
            original_index = projects.index(project)

            # Verify own data
            for j in range(20):
                key = f"p{original_index}_key_{j}"
                value = cache.get(key)
                if value is not None:  # Might be evicted
                    assert value == f"p{original_index}_value_{j}"

            # Sample check: verify no data from other random project
            other_project = random.choice([p for p in projects if p != project])
            other_index = projects.index(other_project)
            other_key = f"p{other_index}_key_0"
            assert cache.get(other_key) is None, "Data leakage detected!"
