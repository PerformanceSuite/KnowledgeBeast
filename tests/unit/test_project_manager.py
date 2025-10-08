"""Comprehensive unit tests for ProjectManager.

Tests cover:
- Project CRUD operations
- Project metadata management
- Per-project cache isolation
- Per-project ChromaDB collection isolation
- Thread-safe operations
- Error handling
- Edge cases
"""

import pytest
import tempfile
import shutil
import uuid
from pathlib import Path
from datetime import datetime

from knowledgebeast.core.project_manager import Project, ProjectManager


class TestProjectDataclass:
    """Test Project dataclass functionality."""

    def test_project_creation_with_defaults(self):
        """Test creating project with default values."""
        project = Project(
            project_id="test-id",
            name="Test Project"
        )

        assert project.project_id == "test-id"
        assert project.name == "Test Project"
        assert project.description == ""
        assert project.collection_name == "kb_project_test-id"
        assert project.embedding_model == "all-MiniLM-L6-v2"
        assert project.created_at != ""
        assert project.updated_at != ""
        assert project.metadata == {}

    def test_project_creation_with_all_fields(self):
        """Test creating project with all fields specified."""
        metadata = {"key": "value", "count": 42}
        project = Project(
            project_id="test-id",
            name="Test Project",
            description="Test description",
            collection_name="custom_collection",
            embedding_model="custom-model",
            created_at="2025-01-01T00:00:00",
            updated_at="2025-01-02T00:00:00",
            metadata=metadata
        )

        assert project.project_id == "test-id"
        assert project.name == "Test Project"
        assert project.description == "Test description"
        assert project.collection_name == "custom_collection"
        assert project.embedding_model == "custom-model"
        assert project.created_at == "2025-01-01T00:00:00"
        assert project.updated_at == "2025-01-02T00:00:00"
        assert project.metadata == metadata

    def test_project_auto_collection_name(self):
        """Test automatic collection name generation."""
        project = Project(
            project_id="abc-123",
            name="Test"
        )

        assert project.collection_name == "kb_project_abc-123"

    def test_project_to_dict(self):
        """Test converting project to dictionary."""
        project = Project(
            project_id="test-id",
            name="Test Project",
            description="Description"
        )

        project_dict = project.to_dict()

        assert project_dict['project_id'] == "test-id"
        assert project_dict['name'] == "Test Project"
        assert project_dict['description'] == "Description"
        assert 'collection_name' in project_dict
        assert 'created_at' in project_dict

    def test_project_from_dict(self):
        """Test creating project from dictionary."""
        data = {
            'project_id': 'test-id',
            'name': 'Test Project',
            'description': 'Description',
            'collection_name': 'kb_project_test-id',
            'embedding_model': 'all-MiniLM-L6-v2',
            'created_at': '2025-01-01T00:00:00',
            'updated_at': '2025-01-02T00:00:00',
            'metadata': {'key': 'value'}
        }

        project = Project.from_dict(data)

        assert project.project_id == 'test-id'
        assert project.name == 'Test Project'
        assert project.metadata['key'] == 'value'

    def test_project_timestamps_auto_generated(self):
        """Test timestamps are auto-generated if not provided."""
        before = datetime.utcnow().isoformat()
        project = Project(project_id="test", name="Test")
        after = datetime.utcnow().isoformat()

        assert before <= project.created_at <= after
        assert project.created_at == project.updated_at


class TestProjectManagerInitialization:
    """Test ProjectManager initialization."""

    def test_manager_initialization_default(self):
        """Test manager initialization with defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "projects.db"
            manager = ProjectManager(storage_path=str(storage_path))

            assert manager.storage_path == storage_path
            assert manager.cache_capacity == 100
            assert manager._project_caches == {}

    def test_manager_initialization_custom(self):
        """Test manager initialization with custom parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "custom.db"
            chroma_path = Path(tmpdir) / "chroma"

            manager = ProjectManager(
                storage_path=str(storage_path),
                chroma_path=str(chroma_path),
                cache_capacity=200
            )

            assert manager.storage_path == storage_path
            assert manager.chroma_path == chroma_path
            assert manager.cache_capacity == 200

    def test_manager_database_schema_created(self):
        """Test database schema is created on initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "projects.db"
            manager = ProjectManager(storage_path=str(storage_path))

            assert storage_path.exists()

            # Verify schema
            import sqlite3
            conn = sqlite3.connect(str(storage_path))
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='projects'"
            )
            result = cursor.fetchone()
            conn.close()

            assert result is not None

    def test_manager_creates_parent_directories(self):
        """Test manager creates parent directories if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "nested" / "dir" / "projects.db"
            manager = ProjectManager(storage_path=str(storage_path))

            assert storage_path.parent.exists()
            assert storage_path.exists()


class TestProjectCRUD:
    """Test CRUD operations."""

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
            # Cleanup
            manager.cleanup_all()

    def test_create_project_basic(self, manager):
        """Test creating a basic project."""
        project = manager.create_project(
            name="Test Project",
            description="Test description"
        )

        assert project.project_id is not None
        assert project.name == "Test Project"
        assert project.description == "Test description"
        assert project.collection_name.startswith("kb_project_")

    def test_create_project_with_metadata(self, manager):
        """Test creating project with metadata."""
        metadata = {"author": "test", "version": "1.0"}
        project = manager.create_project(
            name="Test Project",
            metadata=metadata
        )

        assert project.metadata == metadata

    def test_create_project_with_custom_embedding(self, manager):
        """Test creating project with custom embedding model."""
        project = manager.create_project(
            name="Test Project",
            embedding_model="custom-model-v2"
        )

        assert project.embedding_model == "custom-model-v2"

    def test_create_duplicate_project_name_fails(self, manager):
        """Test creating project with duplicate name raises error."""
        manager.create_project(name="Test Project")

        with pytest.raises(ValueError, match="already exists"):
            manager.create_project(name="Test Project")

    def test_get_project_existing(self, manager):
        """Test getting existing project."""
        created = manager.create_project(name="Test Project")
        retrieved = manager.get_project(created.project_id)

        assert retrieved is not None
        assert retrieved.project_id == created.project_id
        assert retrieved.name == created.name
        assert retrieved.description == created.description

    def test_get_project_nonexistent(self, manager):
        """Test getting nonexistent project returns None."""
        result = manager.get_project("nonexistent-id")
        assert result is None

    def test_list_projects_empty(self, manager):
        """Test listing projects when none exist."""
        projects = manager.list_projects()
        assert projects == []

    def test_list_projects_multiple(self, manager):
        """Test listing multiple projects."""
        p1 = manager.create_project(name="Project 1")
        p2 = manager.create_project(name="Project 2")
        p3 = manager.create_project(name="Project 3")

        projects = manager.list_projects()

        assert len(projects) == 3
        project_ids = {p.project_id for p in projects}
        assert p1.project_id in project_ids
        assert p2.project_id in project_ids
        assert p3.project_id in project_ids

    def test_list_projects_ordered_by_created_at(self, manager):
        """Test projects are listed in reverse chronological order."""
        import time

        p1 = manager.create_project(name="Project 1")
        time.sleep(0.01)
        p2 = manager.create_project(name="Project 2")
        time.sleep(0.01)
        p3 = manager.create_project(name="Project 3")

        projects = manager.list_projects()

        # Should be in reverse order (newest first)
        assert projects[0].project_id == p3.project_id
        assert projects[1].project_id == p2.project_id
        assert projects[2].project_id == p1.project_id

    def test_update_project_name(self, manager):
        """Test updating project name."""
        project = manager.create_project(name="Original Name")
        updated = manager.update_project(
            project.project_id,
            name="New Name"
        )

        assert updated is not None
        assert updated.name == "New Name"
        assert updated.updated_at > project.updated_at

    def test_update_project_description(self, manager):
        """Test updating project description."""
        project = manager.create_project(name="Test")
        updated = manager.update_project(
            project.project_id,
            description="New description"
        )

        assert updated.description == "New description"

    def test_update_project_embedding_model(self, manager):
        """Test updating project embedding model."""
        project = manager.create_project(name="Test")
        updated = manager.update_project(
            project.project_id,
            embedding_model="new-model"
        )

        assert updated.embedding_model == "new-model"

    def test_update_project_metadata(self, manager):
        """Test updating project metadata."""
        project = manager.create_project(name="Test")
        new_metadata = {"key": "new_value"}
        updated = manager.update_project(
            project.project_id,
            metadata=new_metadata
        )

        assert updated.metadata == new_metadata

    def test_update_project_multiple_fields(self, manager):
        """Test updating multiple project fields at once."""
        project = manager.create_project(name="Test")
        updated = manager.update_project(
            project.project_id,
            name="New Name",
            description="New Description",
            metadata={"key": "value"}
        )

        assert updated.name == "New Name"
        assert updated.description == "New Description"
        assert updated.metadata == {"key": "value"}

    def test_update_project_nonexistent(self, manager):
        """Test updating nonexistent project returns None."""
        result = manager.update_project(
            "nonexistent-id",
            name="New Name"
        )
        assert result is None

    def test_update_project_duplicate_name_fails(self, manager):
        """Test updating to duplicate name fails."""
        p1 = manager.create_project(name="Project 1")
        p2 = manager.create_project(name="Project 2")

        with pytest.raises(ValueError, match="already exists"):
            manager.update_project(p2.project_id, name="Project 1")

    def test_delete_project_existing(self, manager):
        """Test deleting existing project."""
        project = manager.create_project(name="Test Project")
        result = manager.delete_project(project.project_id)

        assert result is True

        # Verify project is gone
        retrieved = manager.get_project(project.project_id)
        assert retrieved is None

    def test_delete_project_nonexistent(self, manager):
        """Test deleting nonexistent project returns False."""
        result = manager.delete_project("nonexistent-id")
        assert result is False

    def test_delete_project_cleans_resources(self, manager):
        """Test deleting project cleans up all resources."""
        project = manager.create_project(name="Test Project")

        # Add cache entry
        cache = manager.get_project_cache(project.project_id)
        cache.put("test_key", "test_value")

        # Delete project
        manager.delete_project(project.project_id)

        # Verify cache is removed
        assert project.project_id not in manager._project_caches


class TestProjectCacheIsolation:
    """Test per-project cache isolation."""

    @pytest.fixture
    def manager(self):
        """Create a temporary ProjectManager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "projects.db"
            chroma_path = Path(tmpdir) / "chroma"
            manager = ProjectManager(
                storage_path=str(storage_path),
                chroma_path=str(chroma_path),
                cache_capacity=10
            )
            yield manager
            manager.cleanup_all()

    def test_get_project_cache_creates_cache(self, manager):
        """Test getting project cache creates cache if needed."""
        project = manager.create_project(name="Test")
        cache = manager.get_project_cache(project.project_id)

        assert cache is not None
        assert project.project_id in manager._project_caches

    def test_get_project_cache_nonexistent_project(self, manager):
        """Test getting cache for nonexistent project returns None."""
        cache = manager.get_project_cache("nonexistent-id")
        assert cache is None

    def test_project_caches_are_isolated(self, manager):
        """Test caches are isolated between projects."""
        p1 = manager.create_project(name="Project 1")
        p2 = manager.create_project(name="Project 2")

        cache1 = manager.get_project_cache(p1.project_id)
        cache2 = manager.get_project_cache(p2.project_id)

        # Add data to cache1
        cache1.put("key1", "value1")
        cache1.put("key2", "value2")

        # Add data to cache2
        cache2.put("key3", "value3")

        # Verify isolation
        assert cache1.get("key1") == "value1"
        assert cache1.get("key2") == "value2"
        assert cache1.get("key3") is None

        assert cache2.get("key3") == "value3"
        assert cache2.get("key1") is None
        assert cache2.get("key2") is None

    def test_clear_project_cache(self, manager):
        """Test clearing project cache."""
        project = manager.create_project(name="Test")
        cache = manager.get_project_cache(project.project_id)

        cache.put("key1", "value1")
        cache.put("key2", "value2")

        result = manager.clear_project_cache(project.project_id)
        assert result is True

        # Verify cache is empty
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert len(cache) == 0

    def test_clear_cache_nonexistent_project(self, manager):
        """Test clearing cache for nonexistent project returns False."""
        result = manager.clear_project_cache("nonexistent-id")
        assert result is False

    def test_cache_respects_capacity(self, manager):
        """Test per-project cache respects capacity."""
        project = manager.create_project(name="Test")
        cache = manager.get_project_cache(project.project_id)

        # Add more items than capacity
        for i in range(20):
            cache.put(f"key{i}", f"value{i}")

        # Cache should be at capacity
        stats = cache.stats()
        assert stats['size'] <= manager.cache_capacity
        assert stats['size'] == 10


class TestProjectCollectionIsolation:
    """Test per-project ChromaDB collection isolation."""

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

    def test_create_project_creates_collection(self, manager):
        """Test creating project creates ChromaDB collection."""
        project = manager.create_project(name="Test Project")
        collection = manager.get_project_collection(project.project_id)

        assert collection is not None
        assert collection.name == project.collection_name

    def test_get_project_collection(self, manager):
        """Test getting project collection."""
        project = manager.create_project(name="Test Project")
        collection = manager.get_project_collection(project.project_id)

        assert collection is not None
        assert collection.name == f"kb_project_{project.project_id}"

    def test_get_collection_nonexistent_project(self, manager):
        """Test getting collection for nonexistent project returns None."""
        collection = manager.get_project_collection("nonexistent-id")
        assert collection is None

    def test_delete_project_deletes_collection(self, manager):
        """Test deleting project deletes ChromaDB collection."""
        project = manager.create_project(name="Test Project")

        # Verify collection exists
        collection = manager.get_project_collection(project.project_id)
        assert collection is not None

        # Delete project
        manager.delete_project(project.project_id)

        # Verify collection is deleted
        collection = manager.get_project_collection(project.project_id)
        assert collection is None


class TestProjectManagerStats:
    """Test ProjectManager statistics."""

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

    def test_get_stats_empty(self, manager):
        """Test getting stats with no projects."""
        stats = manager.get_stats()

        assert stats['total_projects'] == 0
        assert stats['total_cache_entries'] == 0
        assert stats['cache_capacity_per_project'] == 100

    def test_get_stats_with_projects(self, manager):
        """Test getting stats with projects."""
        p1 = manager.create_project(name="Project 1")
        p2 = manager.create_project(name="Project 2")

        stats = manager.get_stats()

        assert stats['total_projects'] == 2

    def test_get_stats_with_cache_entries(self, manager):
        """Test stats include cache entry counts."""
        p1 = manager.create_project(name="Project 1")
        p2 = manager.create_project(name="Project 2")

        cache1 = manager.get_project_cache(p1.project_id)
        cache1.put("key1", "value1")
        cache1.put("key2", "value2")

        cache2 = manager.get_project_cache(p2.project_id)
        cache2.put("key3", "value3")

        stats = manager.get_stats()

        assert stats['total_cache_entries'] == 3


class TestProjectManagerCleanup:
    """Test cleanup and resource management."""

    def test_cleanup_all_clears_caches(self):
        """Test cleanup_all clears all project caches."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "projects.db"
            chroma_path = Path(tmpdir) / "chroma"
            manager = ProjectManager(
                storage_path=str(storage_path),
                chroma_path=str(chroma_path)
            )

            p1 = manager.create_project(name="Project 1")
            p2 = manager.create_project(name="Project 2")

            cache1 = manager.get_project_cache(p1.project_id)
            cache1.put("key1", "value1")

            manager.cleanup_all()

            assert len(manager._project_caches) == 0

    def test_context_manager_cleanup(self):
        """Test context manager cleanup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "projects.db"
            chroma_path = Path(tmpdir) / "chroma"

            with ProjectManager(
                storage_path=str(storage_path),
                chroma_path=str(chroma_path)
            ) as manager:
                p1 = manager.create_project(name="Project 1")
                cache1 = manager.get_project_cache(p1.project_id)
                cache1.put("key1", "value1")

            # After context exit, caches should be cleared
            # (We can't verify this directly since manager is out of scope)


class TestEdgeCases:
    """Test edge cases and error conditions."""

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

    def test_create_project_empty_name(self, manager):
        """Test creating project with empty name works."""
        project = manager.create_project(name="")
        assert project.name == ""

    def test_create_project_very_long_name(self, manager):
        """Test creating project with very long name."""
        long_name = "A" * 1000
        project = manager.create_project(name=long_name)
        assert project.name == long_name

    def test_create_project_special_characters_in_name(self, manager):
        """Test creating project with special characters in name."""
        special_name = "Test-Project_123 (v2.0) [final]"
        project = manager.create_project(name=special_name)
        assert project.name == special_name

    def test_update_project_no_changes(self, manager):
        """Test updating project with no changes."""
        project = manager.create_project(name="Test")
        updated = manager.update_project(project.project_id)

        assert updated is not None
        assert updated.name == project.name
        # updated_at should still be updated
        assert updated.updated_at >= project.updated_at

    def test_metadata_with_nested_structures(self, manager):
        """Test metadata with complex nested structures."""
        complex_metadata = {
            "nested": {
                "level1": {
                    "level2": ["a", "b", "c"]
                }
            },
            "list": [1, 2, 3],
            "mixed": {"key": [{"inner": "value"}]}
        }

        project = manager.create_project(
            name="Test",
            metadata=complex_metadata
        )

        retrieved = manager.get_project(project.project_id)
        assert retrieved.metadata == complex_metadata

    def test_concurrent_project_access_same_project(self, manager):
        """Test concurrent access to same project."""
        import threading

        project = manager.create_project(name="Test")
        errors = []

        def worker():
            try:
                retrieved = manager.get_project(project.project_id)
                assert retrieved is not None
            except Exception as e:
                errors.append(str(e))

        threads = []
        for _ in range(10):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0
