"""Integration tests for vector store with ChromaDB persistence."""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from knowledgebeast.core.embeddings import EmbeddingEngine
from knowledgebeast.core.vector_store import VectorStore


class TestPersistence:
    """Test ChromaDB persistence."""

    def test_persist_and_reload(self):
        """Test data persists across store instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create store and add data
            store1 = VectorStore(persist_directory=tmpdir, collection_name="test")
            embeddings = [np.random.rand(384).astype(np.float32) for _ in range(5)]
            store1.add(
                ids=[f"doc{i}" for i in range(5)],
                embeddings=embeddings,
                documents=[f"Document {i}" for i in range(5)],
                metadatas=[{"idx": i} for i in range(5)]
            )

            count1 = store1.count()

            # Create new store instance with same directory
            store2 = VectorStore(persist_directory=tmpdir, collection_name="test")

            assert store2.count() == count1

            # Verify data is accessible
            result = store2.get(ids="doc0")
            assert "doc0" in result["ids"]

    def test_multiple_collections_persist(self):
        """Test multiple collections persist independently."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store1 = VectorStore(persist_directory=tmpdir, collection_name="col1")
            store1.add(
                ids="doc1",
                embeddings=np.random.rand(384).astype(np.float32),
                documents="Collection 1"
            )

            store2 = VectorStore(persist_directory=tmpdir, collection_name="col2")
            store2.add(
                ids="doc2",
                embeddings=np.random.rand(384).astype(np.float32),
                documents="Collection 2"
            )

            # Reload and verify
            store3 = VectorStore(persist_directory=tmpdir, collection_name="col1")
            assert store3.count() == 1

            store4 = VectorStore(persist_directory=tmpdir, collection_name="col2")
            assert store4.count() == 1

    def test_persist_after_delete(self):
        """Test deletions persist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store1 = VectorStore(persist_directory=tmpdir)
            embeddings = [np.random.rand(384).astype(np.float32) for _ in range(3)]
            store1.add(
                ids=["doc1", "doc2", "doc3"],
                embeddings=embeddings
            )

            store1.delete(ids="doc2")

            # Reload and verify
            store2 = VectorStore(persist_directory=tmpdir)
            assert store2.count() == 2

            result = store2.get()
            assert "doc2" not in result["ids"]

    def test_persist_after_update(self):
        """Test updates persist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store1 = VectorStore(persist_directory=tmpdir)
            store1.add(
                ids="doc1",
                embeddings=np.random.rand(384).astype(np.float32),
                metadatas={"version": 1}
            )

            store1.update(ids="doc1", metadatas={"version": 2})

            # Reload and verify
            store2 = VectorStore(persist_directory=tmpdir)
            result = store2.get(ids="doc1", include=["metadatas"])
            assert result["metadatas"][0]["version"] == 2


class TestEmbeddingIntegration:
    """Test integration with embedding engine."""

    def test_embed_and_store(self):
        """Test embedding text and storing in vector store."""
        engine = EmbeddingEngine()
        store = VectorStore()

        # Generate embeddings
        texts = ["Hello world", "Test document", "Another example"]
        embeddings = engine.embed(texts)

        # Store embeddings
        store.add(
            ids=[f"doc{i}" for i in range(len(texts))],
            embeddings=embeddings,
            documents=texts
        )

        assert store.count() == 3

    def test_semantic_search(self):
        """Test semantic search with embeddings."""
        engine = EmbeddingEngine()
        store = VectorStore()

        # Add documents
        texts = [
            "The cat sits on the mat",
            "Dogs are great pets",
            "Machine learning is fascinating",
            "Python is a programming language",
            "Cats and dogs are animals"
        ]

        embeddings = engine.embed(texts)
        store.add(
            ids=[f"doc{i}" for i in range(len(texts))],
            embeddings=embeddings,
            documents=texts
        )

        # Query for cat-related content
        query_text = "feline on a rug"
        query_embedding = engine.embed(query_text)
        results = store.query(query_embeddings=query_embedding, n_results=2)

        # First result should be about cats
        top_doc_idx = int(results["ids"][0][0].replace("doc", ""))
        assert "cat" in texts[top_doc_idx].lower()

    def test_batch_embed_and_store(self):
        """Test batch embedding and storage."""
        engine = EmbeddingEngine()
        store = VectorStore()

        # Generate large batch
        texts = [f"Document {i}" for i in range(100)]
        embeddings = engine.embed_batch(texts, batch_size=32)

        # Store in batches
        batch_size = 25
        for i in range(0, len(texts), batch_size):
            batch_end = min(i + batch_size, len(texts))
            store.add(
                ids=[f"doc{j}" for j in range(i, batch_end)],
                embeddings=embeddings[i:batch_end],
                documents=texts[i:batch_end]
            )

        assert store.count() == 100

    def test_similarity_threshold(self):
        """Test filtering results by similarity threshold."""
        engine = EmbeddingEngine()
        store = VectorStore()

        # Add similar and dissimilar documents
        texts = [
            "Machine learning",
            "Deep learning",
            "Neural networks",
            "Cooking recipes",
            "Travel destinations"
        ]

        embeddings = engine.embed(texts)
        store.add(
            ids=[f"doc{i}" for i in range(len(texts))],
            embeddings=embeddings,
            documents=texts
        )

        # Query for ML-related content
        query_embedding = engine.embed("artificial intelligence")
        results = store.query(query_embeddings=query_embedding, n_results=5)

        # Top results should have higher similarity (lower distance)
        distances = results["distances"][0]
        assert distances[0] < distances[-1]


class TestLargeScaleOperations:
    """Test large-scale operations."""

    def test_large_dataset_storage(self):
        """Test storing and querying large dataset."""
        engine = EmbeddingEngine()
        store = VectorStore()

        # Generate large dataset
        num_docs = 1000
        texts = [f"Document {i} with unique content" for i in range(num_docs)]

        # Embed and store in batches
        batch_size = 100
        for i in range(0, num_docs, batch_size):
            batch_texts = texts[i:i+batch_size]
            batch_embeddings = engine.embed(batch_texts)

            store.add(
                ids=[f"doc{j}" for j in range(i, i+len(batch_texts))],
                embeddings=batch_embeddings,
                documents=batch_texts
            )

        assert store.count() == num_docs

        # Query should still be fast
        query_embedding = engine.embed("test query")
        results = store.query(query_embeddings=query_embedding, n_results=10)

        assert len(results["ids"][0]) == 10

    def test_large_dataset_with_metadata_filtering(self):
        """Test metadata filtering on large dataset."""
        store = VectorStore()

        # Add documents with categories
        num_docs = 500
        embeddings = [np.random.rand(384).astype(np.float32) for _ in range(num_docs)]
        metadatas = [{"category": f"cat{i % 5}"} for i in range(num_docs)]

        store.add(
            ids=[f"doc{i}" for i in range(num_docs)],
            embeddings=embeddings,
            metadatas=metadatas
        )

        # Query with filter
        query_embedding = np.random.rand(384).astype(np.float32)
        results = store.query(
            query_embeddings=query_embedding,
            n_results=50,
            where={"category": "cat0"}
        )

        # Should only return cat0 documents (100 total)
        assert len(results["ids"][0]) <= 100


class TestCollectionIsolation:
    """Test collection isolation."""

    def test_collections_isolated(self):
        """Test collections don't interfere with each other."""
        store = VectorStore(collection_name="col1")

        # Add to collection 1
        store.add(
            ids="doc1",
            embeddings=np.random.rand(384).astype(np.float32),
            documents="Collection 1 doc"
        )

        # Switch to collection 2
        store.create_collection("col2")
        store.get_collection("col2")

        # Add to collection 2
        store.add(
            ids="doc2",
            embeddings=np.random.rand(384).astype(np.float32),
            documents="Collection 2 doc"
        )

        # Verify counts
        assert store.count() == 1

        store.get_collection("col1")
        assert store.count() == 1

    def test_delete_collection_doesnt_affect_others(self):
        """Test deleting collection doesn't affect others."""
        store = VectorStore()

        # Create multiple collections
        for i in range(3):
            name = f"col{i}"
            store.create_collection(name)
            store.get_collection(name)
            store.add(
                ids="doc1",
                embeddings=np.random.rand(384).astype(np.float32)
            )

        # Delete one collection
        store.delete_collection("col1")

        # Others should still exist
        store.get_collection("col0")
        assert store.count() == 1

        store.get_collection("col2")
        assert store.count() == 1


class TestErrorHandling:
    """Test error handling in integration scenarios."""

    def test_query_empty_collection(self):
        """Test querying empty collection."""
        store = VectorStore()

        query_embedding = np.random.rand(384).astype(np.float32)
        results = store.query(query_embeddings=query_embedding, n_results=10)

        # Should return empty results
        assert len(results["ids"][0]) == 0

    def test_get_nonexistent_document(self):
        """Test getting nonexistent document."""
        store = VectorStore()

        result = store.get(ids="nonexistent")

        assert len(result["ids"]) == 0

    def test_update_nonexistent_document(self):
        """Test updating nonexistent document (should not error)."""
        store = VectorStore()

        # ChromaDB update creates if doesn't exist
        store.update(
            ids="new_doc",
            embeddings=np.random.rand(384).astype(np.float32)
        )

        # Document should now exist
        assert store.count() == 1


class TestConcurrentPersistence:
    """Test concurrent operations with persistence."""

    def test_concurrent_stores_same_directory(self):
        """Test multiple stores accessing same persistent directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create two stores on same directory
            store1 = VectorStore(persist_directory=tmpdir, collection_name="shared")
            store2 = VectorStore(persist_directory=tmpdir, collection_name="shared")

            # Add from both stores
            store1.add(
                ids="doc1",
                embeddings=np.random.rand(384).astype(np.float32)
            )

            store2.add(
                ids="doc2",
                embeddings=np.random.rand(384).astype(np.float32)
            )

            # Both should see all documents
            assert store1.count() == 2
            assert store2.count() == 2


class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""

    def test_document_ingestion_pipeline(self):
        """Test complete document ingestion pipeline."""
        engine = EmbeddingEngine()
        store = VectorStore()

        # Simulate document ingestion
        documents = [
            {"id": "doc1", "text": "Introduction to Python", "author": "Alice"},
            {"id": "doc2", "text": "Advanced Python techniques", "author": "Bob"},
            {"id": "doc3", "text": "JavaScript basics", "author": "Charlie"},
            {"id": "doc4", "text": "Python for data science", "author": "Alice"},
        ]

        # Embed and store
        texts = [doc["text"] for doc in documents]
        embeddings = engine.embed(texts)

        store.add(
            ids=[doc["id"] for doc in documents],
            embeddings=embeddings,
            documents=texts,
            metadatas=[{"author": doc["author"]} for doc in documents]
        )

        # Query for Python content
        query = "Python programming"
        query_emb = engine.embed(query)
        results = store.query(query_embeddings=query_emb, n_results=3)

        # Should return Python-related documents
        top_docs = results["documents"][0]
        assert any("Python" in doc for doc in top_docs)

        # Filter by author
        alice_results = store.query(
            query_embeddings=query_emb,
            n_results=10,
            where={"author": "Alice"}
        )

        assert len(alice_results["ids"][0]) == 2

    def test_update_and_requery_workflow(self):
        """Test updating documents and requerying."""
        engine = EmbeddingEngine()
        store = VectorStore()

        # Initial documents
        texts = ["Old version", "Another document"]
        embeddings = engine.embed(texts)
        store.add(
            ids=["doc1", "doc2"],
            embeddings=embeddings,
            documents=texts
        )

        # Update first document
        new_text = "Updated version with new content"
        new_embedding = engine.embed(new_text)
        store.update(
            ids="doc1",
            embeddings=new_embedding,
            documents=new_text
        )

        # Query for updated content
        query_emb = engine.embed("new content")
        results = store.query(query_embeddings=query_emb, n_results=2)

        # Updated document should rank higher
        top_doc = results["documents"][0][0]
        assert "new content" in top_doc.lower()
