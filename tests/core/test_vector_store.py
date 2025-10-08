"""Tests for vector store implementation."""

import tempfile
import threading
import uuid
from pathlib import Path

import numpy as np
import pytest

from knowledgebeast.core.vector_store import VectorStore


@pytest.fixture
def unique_collection():
    """Generate unique collection name for each test."""
    return f"test_{uuid.uuid4().hex[:8]}"


class TestVectorStoreInitialization:
    """Test vector store initialization."""

    def test_init_in_memory(self):
        """Test initializing in-memory store."""
        store = VectorStore()
        assert store.persist_directory is None
        assert store.collection_name == "default"
        assert store.count() == 0

    def test_init_persistent(self):
        """Test initializing persistent store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(persist_directory=tmpdir)
            assert store.persist_directory == Path(tmpdir)
            assert store.collection_name == "default"

    def test_init_custom_collection(self):
        """Test initializing with custom collection."""
        store = VectorStore(collection_name="custom")
        assert store.collection_name == "custom"

    def test_init_creates_directory(self):
        """Test initialization creates persist directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            persist_path = Path(tmpdir) / "new_dir"
            store = VectorStore(persist_directory=str(persist_path))
            assert persist_path.exists()

    def test_init_stats(self):
        """Test initial statistics."""
        store = VectorStore()
        stats = store.get_stats()

        assert stats["total_documents"] == 0
        assert stats["total_queries"] == 0
        assert stats["total_collections"] >= 1
        assert stats["total_adds"] == 0
        assert stats["total_deletes"] == 0


class TestAddDocuments:
    """Test adding documents."""

    def test_add_single_document(self):
        """Test adding single document."""
        store = VectorStore()
        embedding = np.random.rand(384).astype(np.float32)

        store.add(
            ids="doc1",
            embeddings=embedding,
            documents="Test document",
            metadatas={"source": "test"}
        )

        assert store.count() == 1

    def test_add_multiple_documents(self):
        """Test adding multiple documents."""
        store = VectorStore()
        embeddings = [np.random.rand(384).astype(np.float32) for _ in range(3)]

        store.add(
            ids=["doc1", "doc2", "doc3"],
            embeddings=embeddings,
            documents=["Doc 1", "Doc 2", "Doc 3"],
            metadatas=[{"idx": 1}, {"idx": 2}, {"idx": 3}]
        )

        assert store.count() == 3

    def test_add_without_metadata(self):
        """Test adding documents without metadata."""
        store = VectorStore()
        embedding = np.random.rand(384).astype(np.float32)

        store.add(ids="doc1", embeddings=embedding)

        assert store.count() == 1

    def test_add_without_documents(self):
        """Test adding embeddings without document text."""
        store = VectorStore()
        embedding = np.random.rand(384).astype(np.float32)

        store.add(ids="doc1", embeddings=embedding, metadatas={"key": "value"})

        assert store.count() == 1

    def test_add_mismatched_lengths(self):
        """Test adding with mismatched lengths raises error."""
        store = VectorStore()
        embeddings = [np.random.rand(384).astype(np.float32) for _ in range(2)]

        with pytest.raises(ValueError, match="Number of ids must match"):
            store.add(ids=["doc1"], embeddings=embeddings)

    def test_add_updates_stats(self):
        """Test adding updates statistics."""
        store = VectorStore()
        embedding = np.random.rand(384).astype(np.float32)

        store.add(ids="doc1", embeddings=embedding)

        stats = store.get_stats()
        assert stats["total_adds"] == 1
        assert stats["total_documents"] == 1


class TestQueryDocuments:
    """Test querying documents."""

    def test_query_single_result(self):
        """Test querying for single result."""
        store = VectorStore()

        # Add documents
        embeddings = [np.random.rand(384).astype(np.float32) for _ in range(5)]
        store.add(
            ids=[f"doc{i}" for i in range(5)],
            embeddings=embeddings,
            documents=[f"Document {i}" for i in range(5)]
        )

        # Query
        query_embedding = embeddings[0]
        results = store.query(query_embeddings=query_embedding, n_results=1)

        assert len(results["ids"]) == 1
        assert len(results["ids"][0]) == 1

    def test_query_multiple_results(self):
        """Test querying for multiple results."""
        store = VectorStore()

        # Add documents
        embeddings = [np.random.rand(384).astype(np.float32) for _ in range(5)]
        store.add(
            ids=[f"doc{i}" for i in range(5)],
            embeddings=embeddings
        )

        # Query
        query_embedding = embeddings[0]
        results = store.query(query_embeddings=query_embedding, n_results=3)

        assert len(results["ids"][0]) == 3

    def test_query_with_metadata_filter(self):
        """Test querying with metadata filter."""
        store = VectorStore()

        # Add documents with metadata
        embeddings = [np.random.rand(384).astype(np.float32) for _ in range(5)]
        store.add(
            ids=[f"doc{i}" for i in range(5)],
            embeddings=embeddings,
            metadatas=[{"category": "A" if i < 3 else "B"} for i in range(5)]
        )

        # Query with filter
        query_embedding = np.random.rand(384).astype(np.float32)
        results = store.query(
            query_embeddings=query_embedding,
            n_results=10,
            where={"category": "A"}
        )

        # Should only return category A documents
        assert len(results["ids"][0]) <= 3

    def test_query_updates_stats(self):
        """Test querying updates statistics."""
        store = VectorStore()

        embedding = np.random.rand(384).astype(np.float32)
        store.add(ids="doc1", embeddings=embedding)

        store.query(query_embeddings=embedding, n_results=1)

        stats = store.get_stats()
        assert stats["total_queries"] == 1


class TestGetDocuments:
    """Test getting documents."""

    def test_get_by_id(self):
        """Test getting document by ID."""
        store = VectorStore()

        embedding = np.random.rand(384).astype(np.float32)
        store.add(
            ids="doc1",
            embeddings=embedding,
            documents="Test document"
        )

        result = store.get(ids="doc1")

        assert "doc1" in result["ids"]

    def test_get_multiple_ids(self):
        """Test getting multiple documents by IDs."""
        store = VectorStore()

        embeddings = [np.random.rand(384).astype(np.float32) for _ in range(3)]
        store.add(
            ids=["doc1", "doc2", "doc3"],
            embeddings=embeddings
        )

        result = store.get(ids=["doc1", "doc3"])

        assert len(result["ids"]) == 2

    def test_get_with_filter(self):
        """Test getting documents with metadata filter."""
        store = VectorStore()

        embeddings = [np.random.rand(384).astype(np.float32) for _ in range(3)]
        store.add(
            ids=["doc1", "doc2", "doc3"],
            embeddings=embeddings,
            metadatas=[{"type": "A"}, {"type": "B"}, {"type": "A"}]
        )

        result = store.get(where={"type": "A"})

        assert len(result["ids"]) == 2

    def test_get_with_limit(self):
        """Test getting documents with limit."""
        store = VectorStore()

        embeddings = [np.random.rand(384).astype(np.float32) for _ in range(5)]
        store.add(
            ids=[f"doc{i}" for i in range(5)],
            embeddings=embeddings
        )

        result = store.get(limit=3)

        assert len(result["ids"]) == 3

    def test_get_with_offset(self):
        """Test getting documents with offset."""
        store = VectorStore()

        embeddings = [np.random.rand(384).astype(np.float32) for _ in range(5)]
        store.add(
            ids=[f"doc{i}" for i in range(5)],
            embeddings=embeddings
        )

        result = store.get(limit=2, offset=2)

        assert len(result["ids"]) == 2


class TestDeleteDocuments:
    """Test deleting documents."""

    def test_delete_by_id(self):
        """Test deleting document by ID."""
        store = VectorStore()

        embedding = np.random.rand(384).astype(np.float32)
        store.add(ids="doc1", embeddings=embedding)

        assert store.count() == 1

        store.delete(ids="doc1")

        assert store.count() == 0

    def test_delete_multiple_ids(self):
        """Test deleting multiple documents."""
        store = VectorStore()

        embeddings = [np.random.rand(384).astype(np.float32) for _ in range(3)]
        store.add(
            ids=["doc1", "doc2", "doc3"],
            embeddings=embeddings
        )

        store.delete(ids=["doc1", "doc3"])

        assert store.count() == 1

    def test_delete_with_filter(self):
        """Test deleting with metadata filter."""
        store = VectorStore()

        embeddings = [np.random.rand(384).astype(np.float32) for _ in range(3)]
        store.add(
            ids=["doc1", "doc2", "doc3"],
            embeddings=embeddings,
            metadatas=[{"type": "A"}, {"type": "B"}, {"type": "A"}]
        )

        store.delete(where={"type": "A"})

        assert store.count() == 1

    def test_delete_updates_stats(self):
        """Test deleting updates statistics."""
        store = VectorStore()

        embedding = np.random.rand(384).astype(np.float32)
        store.add(ids="doc1", embeddings=embedding)

        store.delete(ids="doc1")

        stats = store.get_stats()
        assert stats["total_deletes"] == 1
        assert stats["total_documents"] == 0


class TestUpdateDocuments:
    """Test updating documents."""

    def test_update_embedding(self):
        """Test updating document embedding."""
        store = VectorStore()

        embedding1 = np.random.rand(384).astype(np.float32)
        store.add(ids="doc1", embeddings=embedding1)

        embedding2 = np.random.rand(384).astype(np.float32)
        store.update(ids="doc1", embeddings=embedding2)

        result = store.get(ids="doc1", include=["embeddings"])
        # Update successful if no error

    def test_update_metadata(self):
        """Test updating document metadata."""
        store = VectorStore()

        embedding = np.random.rand(384).astype(np.float32)
        store.add(
            ids="doc1",
            embeddings=embedding,
            metadatas={"key": "old"}
        )

        store.update(ids="doc1", metadatas={"key": "new"})

        result = store.get(ids="doc1", include=["metadatas"])
        assert result["metadatas"][0]["key"] == "new"

    def test_update_document_text(self):
        """Test updating document text."""
        store = VectorStore()

        embedding = np.random.rand(384).astype(np.float32)
        store.add(
            ids="doc1",
            embeddings=embedding,
            documents="Old text"
        )

        store.update(ids="doc1", documents="New text")

        result = store.get(ids="doc1", include=["documents"])
        assert result["documents"][0] == "New text"


class TestCollectionManagement:
    """Test collection management."""

    def test_create_collection(self):
        """Test creating new collection."""
        store = VectorStore()

        initial_count = len(store.list_collections())
        store.create_collection("new_collection")

        assert len(store.list_collections()) == initial_count + 1

    def test_create_existing_collection_raises_error(self):
        """Test creating existing collection raises error."""
        store = VectorStore()

        store.create_collection("test_collection")

        with pytest.raises(ValueError, match="already exists"):
            store.create_collection("test_collection")

    def test_get_collection(self):
        """Test switching to existing collection."""
        store = VectorStore()

        # Add to default collection
        embedding = np.random.rand(384).astype(np.float32)
        store.add(ids="doc1", embeddings=embedding)

        # Create and switch to new collection
        store.create_collection("new_collection")
        store.get_collection("new_collection")

        assert store.collection_name == "new_collection"
        assert store.count() == 0

    def test_get_nonexistent_collection_raises_error(self):
        """Test getting nonexistent collection raises error."""
        store = VectorStore()

        with pytest.raises(ValueError, match="not found"):
            store.get_collection("nonexistent")

    def test_delete_collection(self):
        """Test deleting collection."""
        store = VectorStore()

        store.create_collection("to_delete")
        initial_count = len(store.list_collections())

        store.delete_collection("to_delete")

        assert len(store.list_collections()) == initial_count - 1

    def test_delete_current_collection_switches_to_default(self):
        """Test deleting current collection switches to default."""
        store = VectorStore(collection_name="temp")

        store.delete_collection("temp")

        assert store.collection_name == "default"

    def test_list_collections(self):
        """Test listing all collections."""
        store = VectorStore()

        collections = store.list_collections()

        assert isinstance(collections, list)
        assert "default" in collections


class TestUtilityMethods:
    """Test utility methods."""

    def test_count(self):
        """Test counting documents."""
        store = VectorStore()

        assert store.count() == 0

        embeddings = [np.random.rand(384).astype(np.float32) for _ in range(3)]
        store.add(
            ids=["doc1", "doc2", "doc3"],
            embeddings=embeddings
        )

        assert store.count() == 3

    def test_peek(self):
        """Test peeking at documents."""
        store = VectorStore()

        embeddings = [np.random.rand(384).astype(np.float32) for _ in range(10)]
        store.add(
            ids=[f"doc{i}" for i in range(10)],
            embeddings=embeddings
        )

        result = store.peek(limit=5)

        assert len(result["ids"]) == 5

    def test_reset(self):
        """Test resetting collection."""
        store = VectorStore()

        embeddings = [np.random.rand(384).astype(np.float32) for _ in range(5)]
        store.add(
            ids=[f"doc{i}" for i in range(5)],
            embeddings=embeddings
        )

        assert store.count() == 5

        store.reset()

        assert store.count() == 0
        assert store.collection_name == "default"

    def test_repr(self):
        """Test string representation."""
        store = VectorStore(collection_name="test")

        repr_str = repr(store)

        assert "test" in repr_str
        assert "persist=False" in repr_str


class TestThreadSafety:
    """Test thread safety."""

    def test_concurrent_adds(self):
        """Test concurrent document additions."""
        store = VectorStore()
        errors = []

        def add_document(idx):
            try:
                embedding = np.random.rand(384).astype(np.float32)
                store.add(ids=f"doc{idx}", embeddings=embedding)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_document, args=(i,)) for i in range(50)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert store.count() == 50

    def test_concurrent_queries(self):
        """Test concurrent queries."""
        store = VectorStore()

        # Add documents
        embeddings = [np.random.rand(384).astype(np.float32) for _ in range(10)]
        store.add(
            ids=[f"doc{i}" for i in range(10)],
            embeddings=embeddings
        )

        results = []
        errors = []

        def query_store():
            try:
                query_embedding = np.random.rand(384).astype(np.float32)
                result = store.query(query_embeddings=query_embedding, n_results=5)
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=query_store) for _ in range(20)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20

    def test_stats_consistency_under_load(self):
        """Test statistics remain consistent under concurrent load."""
        store = VectorStore()

        def operations():
            for i in range(5):
                embedding = np.random.rand(384).astype(np.float32)
                store.add(ids=f"doc_{threading.current_thread().name}_{i}", embeddings=embedding)

        threads = [threading.Thread(target=operations) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        stats = store.get_stats()
        assert stats["total_documents"] == 50
        assert stats["total_adds"] == 50
