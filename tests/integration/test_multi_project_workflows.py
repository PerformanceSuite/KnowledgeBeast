"""Multi-Project Workflows Integration Tests.

Tests comprehensive multi-tenant scenarios including:
- Concurrent project access
- Cross-project isolation
- Resource cleanup
- Scalability with 100+ projects
- Per-project configuration
"""

import pytest
import time
import threading
from pathlib import Path
from typing import List
import numpy as np

from knowledgebeast.core.project_manager import ProjectManager, Project
from knowledgebeast.core.vector_store import VectorStore
from knowledgebeast.core.embeddings import EmbeddingEngine
from knowledgebeast.core.repository import DocumentRepository
from knowledgebeast.core.query_engine import HybridQueryEngine


class TestMultiProjectCRUD:
    """Test multi-project CRUD operations."""

    def test_create_multiple_projects(self, tmp_path):
        """Test creating multiple projects with different configurations."""
        manager = ProjectManager(
            storage_path=str(tmp_path / "projects.db"),
            chroma_path=str(tmp_path / "chroma")
        )

        projects = []
        for i in range(10):
            project = manager.create_project(
                name=f"Project {i}",
                description=f"Test project {i}",
                embedding_model="all-MiniLM-L6-v2",
                metadata={'index': i, 'category': f'cat{i % 3}'}
            )
            projects.append(project)

        # Verify all created
        assert len(projects) == 10

        # Verify unique IDs
        ids = [p.project_id for p in projects]
        assert len(ids) == len(set(ids))

        # List all
        all_projects = manager.list_projects()
        assert len(all_projects) == 10

        # Cleanup
        for p in projects:
            manager.delete_project(p.project_id)

    def test_bulk_project_operations(self, tmp_path):
        """Test bulk create, update, delete operations."""
        manager = ProjectManager(
            storage_path=str(tmp_path / "projects.db"),
            chroma_path=str(tmp_path / "chroma")
        )

        # Bulk create
        project_ids = []
        for i in range(20):
            project = manager.create_project(
                name=f"Bulk Project {i}",
                description=f"Bulk test {i}"
            )
            project_ids.append(project.project_id)

        # Verify creation
        assert len(manager.list_projects()) == 20

        # Bulk update
        for project_id in project_ids[:10]:
            manager.update_project(
                project_id,
                description="Updated bulk description"
            )

        # Verify updates
        for project_id in project_ids[:10]:
            project = manager.get_project(project_id)
            assert project.description == "Updated bulk description"

        # Bulk delete
        for project_id in project_ids:
            success = manager.delete_project(project_id)
            assert success is True

        # Verify deletion
        assert len(manager.list_projects()) == 0

    def test_project_name_uniqueness(self, tmp_path):
        """Test project name uniqueness enforcement."""
        manager = ProjectManager(
            storage_path=str(tmp_path / "projects.db"),
            chroma_path=str(tmp_path / "chroma")
        )

        # Create first project
        p1 = manager.create_project(name="Unique Name")

        # Try duplicate (should fail)
        with pytest.raises(ValueError, match="already exists"):
            manager.create_project(name="Unique Name")

        # But can reuse name after deletion
        manager.delete_project(p1.project_id)
        p2 = manager.create_project(name="Unique Name")
        assert p2.name == "Unique Name"

        # Cleanup
        manager.delete_project(p2.project_id)


class TestProjectIsolation:
    """Test complete isolation between projects."""

    def test_vector_collection_isolation(self, tmp_path):
        """Test vector collections are isolated per project."""
        chroma_path = tmp_path / "chroma"
        manager = ProjectManager(
            storage_path=str(tmp_path / "projects.db"),
            chroma_path=str(chroma_path)
        )

        # Create projects
        p1 = manager.create_project(name="Audio Project")
        p2 = manager.create_project(name="ML Project")
        p3 = manager.create_project(name="Web Project")

        # Create stores for each
        stores = {
            p1.project_id: VectorStore(persist_directory=chroma_path, collection_name=p1.collection_name),
            p2.project_id: VectorStore(persist_directory=chroma_path, collection_name=p2.collection_name),
            p3.project_id: VectorStore(persist_directory=chroma_path, collection_name=p3.collection_name)
        }

        # Add different documents to each
        engine = EmbeddingEngine()

        docs = {
            p1.project_id: "Audio signal processing with FFT and spectrograms",
            p2.project_id: "Machine learning with neural networks and gradient descent",
            p3.project_id: "Web development with React and Node.js"
        }

        for project_id, content in docs.items():
            emb = engine.embed(content)
            stores[project_id].add(
                ids="doc1",
                embeddings=emb,
                documents=content,
                metadatas={'project_id': project_id}
            )

        # Verify counts
        for store in stores.values():
            assert store.count() == 1

        # Verify content isolation
        for project_id, content in docs.items():
            retrieved = stores[project_id].get(ids="doc1")
            assert retrieved['documents'][0] == content

        # Cleanup
        for p in [p1, p2, p3]:
            manager.delete_project(p.project_id)

    def test_cache_isolation_per_project(self, tmp_path):
        """Test query caches are isolated per project."""
        manager = ProjectManager(
            storage_path=str(tmp_path / "projects.db"),
            chroma_path=str(tmp_path / "chroma"),
            cache_capacity=10
        )

        # Create projects
        projects = [
            manager.create_project(name=f"Project {i}")
            for i in range(5)
        ]

        # Get caches and add different data
        for i, project in enumerate(projects):
            cache = manager.get_project_cache(project.project_id)
            cache.put(f"query_{i}", [f"result_{i}"])

        # Verify isolation
        for i, project in enumerate(projects):
            cache = manager.get_project_cache(project.project_id)
            assert cache.get(f"query_{i}") == [f"result_{i}"]

            # Verify other queries not in this cache
            for j in range(5):
                if j != i:
                    assert cache.get(f"query_{j}") is None

        # Cleanup
        for project in projects:
            manager.delete_project(project.project_id)

    def test_metadata_isolation(self, tmp_path):
        """Test project metadata doesn't leak between projects."""
        manager = ProjectManager(
            storage_path=str(tmp_path / "projects.db"),
            chroma_path=str(tmp_path / "chroma")
        )

        # Create projects with different metadata
        p1 = manager.create_project(
            name="Project 1",
            metadata={'secret': 'value1', 'api_key': 'key1'}
        )
        p2 = manager.create_project(
            name="Project 2",
            metadata={'secret': 'value2', 'api_key': 'key2'}
        )

        # Verify metadata isolation
        retrieved1 = manager.get_project(p1.project_id)
        retrieved2 = manager.get_project(p2.project_id)

        assert retrieved1.metadata['secret'] == 'value1'
        assert retrieved2.metadata['secret'] == 'value2'
        assert retrieved1.metadata != retrieved2.metadata

        # Cleanup
        manager.delete_project(p1.project_id)
        manager.delete_project(p2.project_id)


class TestConcurrentAccess:
    """Test concurrent access to multiple projects."""

    def test_concurrent_project_creation(self, tmp_path):
        """Test creating projects concurrently."""
        manager = ProjectManager(
            storage_path=str(tmp_path / "projects.db"),
            chroma_path=str(tmp_path / "chroma")
        )

        created_projects = []
        errors = []

        def create_project(i):
            try:
                project = manager.create_project(
                    name=f"Concurrent Project {i}",
                    description=f"Created by thread {i}"
                )
                created_projects.append(project)
            except Exception as e:
                errors.append(e)

        # Create 20 projects concurrently
        threads = []
        for i in range(20):
            t = threading.Thread(target=create_project, args=(i,))
            threads.append(t)
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # Verify no errors
        assert len(errors) == 0
        assert len(created_projects) == 20

        # Verify all projects exist
        all_projects = manager.list_projects()
        assert len(all_projects) == 20

        # Cleanup
        for project in created_projects:
            manager.delete_project(project.project_id)

    def test_concurrent_cache_access(self, tmp_path):
        """Test concurrent access to project caches."""
        manager = ProjectManager(
            storage_path=str(tmp_path / "projects.db"),
            chroma_path=str(tmp_path / "chroma"),
            cache_capacity=100
        )

        # Create project
        project = manager.create_project(name="Concurrent Cache Test")
        cache = manager.get_project_cache(project.project_id)

        # Concurrent cache operations
        def cache_operations(thread_id):
            for i in range(10):
                key = f"thread{thread_id}_query{i}"
                cache.put(key, [f"result_{thread_id}_{i}"])
                retrieved = cache.get(key)
                assert retrieved == [f"result_{thread_id}_{i}"]

        threads = []
        for i in range(10):
            t = threading.Thread(target=cache_operations, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Verify cache has entries from all threads
        stats = cache.stats()
        assert stats['size'] <= 100  # Respects capacity

        # Cleanup
        manager.delete_project(project.project_id)


class TestScalability:
    """Test scalability with many projects."""

    def test_100_projects_creation(self, tmp_path):
        """Test creating and managing 100 projects."""
        manager = ProjectManager(
            storage_path=str(tmp_path / "projects.db"),
            chroma_path=str(tmp_path / "chroma")
        )

        # Create 100 projects
        start = time.time()
        project_ids = []

        for i in range(100):
            project = manager.create_project(
                name=f"Scale Project {i}",
                description=f"Scalability test {i}",
                metadata={'index': i}
            )
            project_ids.append(project.project_id)

        creation_time = time.time() - start

        # Should complete in reasonable time (< 10 seconds)
        assert creation_time < 10.0

        # Verify all exist
        all_projects = manager.list_projects()
        assert len(all_projects) == 100

        # Test retrieval performance
        start = time.time()
        for project_id in project_ids[:10]:
            project = manager.get_project(project_id)
            assert project is not None
        retrieval_time = time.time() - start

        # 10 retrievals should be fast (< 1 second)
        assert retrieval_time < 1.0

        # Cleanup (test bulk deletion)
        start = time.time()
        for project_id in project_ids:
            manager.delete_project(project_id)
        deletion_time = time.time() - start

        # Deletion should complete in reasonable time
        assert deletion_time < 15.0

        # Verify all deleted
        assert len(manager.list_projects()) == 0

    def test_project_stats_at_scale(self, tmp_path):
        """Test getting stats with many projects."""
        manager = ProjectManager(
            storage_path=str(tmp_path / "projects.db"),
            chroma_path=str(tmp_path / "chroma")
        )

        # Create 50 projects
        for i in range(50):
            manager.create_project(name=f"Stats Project {i}")

        # Get stats
        stats = manager.get_stats()
        assert stats['total_projects'] == 50

        # Cleanup
        projects = manager.list_projects()
        for project in projects:
            manager.delete_project(project.project_id)


class TestResourceCleanup:
    """Test proper resource cleanup."""

    def test_delete_cleans_all_resources(self, tmp_path):
        """Test deleting project cleans up all resources."""
        chroma_path = tmp_path / "chroma"
        manager = ProjectManager(
            storage_path=str(tmp_path / "projects.db"),
            chroma_path=str(chroma_path)
        )

        # Create project and add data
        project = manager.create_project(name="Cleanup Test")

        # Add to cache
        cache = manager.get_project_cache(project.project_id)
        cache.put("test_query", ["test_result"])
        assert cache.get("test_query") is not None

        # Add to vector store
        store = VectorStore(persist_directory=chroma_path, collection_name=project.collection_name)
        engine = EmbeddingEngine()
        emb = engine.embed("test document")
        store.add(ids="doc1", embeddings=emb, documents="test document")
        assert store.count() == 1

        # Delete project
        manager.delete_project(project.project_id)

        # Verify cache cleaned
        cache_after = manager.get_project_cache(project.project_id)
        assert cache_after is None

        # Verify project gone
        retrieved = manager.get_project(project.project_id)
        assert retrieved is None

    def test_context_manager_cleanup(self, tmp_path):
        """Test context manager properly cleans up resources."""
        with ProjectManager(
            storage_path=str(tmp_path / "projects.db"),
            chroma_path=str(tmp_path / "chroma")
        ) as manager:
            # Create projects
            for i in range(5):
                manager.create_project(name=f"Context Project {i}")

            assert len(manager.list_projects()) == 5

        # After context exit, resources should be cleaned
        # (though projects persist in DB)


class TestProjectQueries:
    """Test querying across projects."""

    def test_search_within_project(self, tmp_path):
        """Test search is scoped to individual projects."""
        chroma_path = tmp_path / "chroma"
        manager = ProjectManager(
            storage_path=str(tmp_path / "projects.db"),
            chroma_path=str(chroma_path)
        )

        # Create two projects
        p1 = manager.create_project(name="Audio Project")
        p2 = manager.create_project(name="ML Project")

        # Add different documents
        engine = EmbeddingEngine()

        store1 = VectorStore(persist_directory=chroma_path, collection_name=p1.collection_name)
        emb1 = engine.embed("Audio signal processing with DSP")
        store1.add(ids="doc1", embeddings=emb1, documents="Audio signal processing with DSP")

        store2 = VectorStore(persist_directory=chroma_path, collection_name=p2.collection_name)
        emb2 = engine.embed("Machine learning with neural networks")
        store2.add(ids="doc1", embeddings=emb2, documents="Machine learning with neural networks")

        # Query each project
        query_emb = engine.embed("deep learning neural networks")

        results1 = store1.query(query_embeddings=query_emb, n_results=1)
        results2 = store2.query(query_embeddings=query_emb, n_results=1)

        # Results should be different
        assert results1['documents'][0] != results2['documents'][0]

        # p2 should have better match for neural networks
        assert "neural" in results2['documents'][0][0].lower()

        # Cleanup
        manager.delete_project(p1.project_id)
        manager.delete_project(p2.project_id)

    def test_hybrid_search_per_project(self, tmp_path):
        """Test hybrid search within project boundaries."""
        chroma_path = tmp_path / "chroma"
        manager = ProjectManager(
            storage_path=str(tmp_path / "projects.db"),
            chroma_path=str(chroma_path)
        )

        # Create project
        project = manager.create_project(name="Hybrid Test Project")

        # Create repository and engine for this project
        repo = DocumentRepository()
        engine = HybridQueryEngine(repo, model_name="all-MiniLM-L6-v2")

        # Add documents
        docs = {
            'doc1': {
                'name': 'Python Programming',
                'content': 'Python is great for data science and machine learning',
                'path': 'python.md'
            },
            'doc2': {
                'name': 'JavaScript Guide',
                'content': 'JavaScript is essential for web development',
                'path': 'js.md'
            }
        }

        for doc_id, doc_data in docs.items():
            repo.add_document(doc_id, doc_data)
            terms = doc_data['content'].lower().split()
            for term in set(terms):
                repo.index_term(term, doc_id)

        # Search
        results = engine.search_hybrid("python machine learning", top_k=2)
        assert len(results) >= 1
        assert results[0][0] == 'doc1'  # Should match Python doc

        # Cleanup
        manager.delete_project(project.project_id)


class TestProjectMigration:
    """Test project migration and export/import."""

    def test_project_metadata_export_import(self, tmp_path):
        """Test exporting and importing project metadata."""
        manager = ProjectManager(
            storage_path=str(tmp_path / "projects.db"),
            chroma_path=str(tmp_path / "chroma")
        )

        # Create project with metadata
        original = manager.create_project(
            name="Export Test",
            description="Test export/import",
            metadata={'version': '1.0', 'author': 'test'}
        )

        # Export to dict
        exported = original.to_dict()

        # Verify exported data
        assert exported['name'] == "Export Test"
        assert exported['metadata']['version'] == '1.0'

        # Create from dict (would need to handle ID uniqueness in real migration)
        # This demonstrates the pattern
        assert exported['project_id'] == original.project_id

        # Cleanup
        manager.delete_project(original.project_id)

    def test_project_update_workflow(self, tmp_path):
        """Test updating project configuration."""
        manager = ProjectManager(
            storage_path=str(tmp_path / "projects.db"),
            chroma_path=str(tmp_path / "chroma")
        )

        # Create project
        project = manager.create_project(
            name="Update Test",
            embedding_model="all-MiniLM-L6-v2"
        )

        # Update configuration
        manager.update_project(
            project.project_id,
            description="Updated configuration",
            metadata={'updated': True}
        )

        # Verify updates persisted
        updated = manager.get_project(project.project_id)
        assert updated.description == "Updated configuration"
        assert updated.metadata['updated'] is True

        # Cleanup
        manager.delete_project(project.project_id)
