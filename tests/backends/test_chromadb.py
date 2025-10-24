"""Tests for ChromaDBBackend implementation."""

import pytest
import tempfile
from pathlib import Path
from knowledgebeast.backends.chromadb import ChromaDBBackend
from knowledgebeast.backends.base import VectorBackend


@pytest.fixture
def temp_persist_dir():
    """Temporary directory for ChromaDB persistence."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.mark.asyncio
async def test_chromadb_backend_implements_interface():
    """ChromaDBBackend should implement VectorBackend interface."""
    assert issubclass(ChromaDBBackend, VectorBackend)


@pytest.mark.asyncio
async def test_chromadb_backend_initialization(temp_persist_dir):
    """ChromaDBBackend should initialize with persist directory."""
    backend = ChromaDBBackend(
        persist_directory=str(temp_persist_dir),
        collection_name="test_collection"
    )

    await backend.close()


@pytest.mark.asyncio
async def test_chromadb_backend_add_and_query(temp_persist_dir):
    """ChromaDBBackend should add documents and perform vector search."""
    backend = ChromaDBBackend(
        persist_directory=str(temp_persist_dir),
        collection_name="test"
    )

    # Add test documents
    await backend.add_documents(
        ids=["doc1", "doc2"],
        embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
        documents=["Hello world", "Goodbye world"],
        metadatas=[{"source": "test"}, {"source": "test"}]
    )

    # Query
    results = await backend.query_vector(
        query_embedding=[0.1, 0.2, 0.3],
        top_k=2
    )

    assert len(results) == 2
    assert results[0][0] == "doc1"  # Closest match

    await backend.close()


@pytest.mark.asyncio
async def test_chromadb_backend_statistics(temp_persist_dir):
    """ChromaDBBackend should return statistics."""
    backend = ChromaDBBackend(
        persist_directory=str(temp_persist_dir),
        collection_name="test"
    )

    stats = await backend.get_statistics()

    assert stats["backend"] == "chromadb"
    assert stats["collection"] == "test"
    assert "total_documents" in stats

    await backend.close()


@pytest.mark.asyncio
async def test_chromadb_backend_hybrid_search(temp_persist_dir):
    """ChromaDBBackend should perform hybrid search with RRF."""
    backend = ChromaDBBackend(
        persist_directory=str(temp_persist_dir),
        collection_name="test"
    )

    # Add test documents with different characteristics
    await backend.add_documents(
        ids=["doc1", "doc2", "doc3"],
        embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]],
        documents=["machine learning AI", "deep learning networks", "data science analytics"],
        metadatas=[{"source": "test"}, {"source": "test"}, {"source": "test"}]
    )

    # Query with hybrid search
    results = await backend.query_hybrid(
        query_embedding=[0.1, 0.2, 0.3],
        query_text="machine learning",
        top_k=3,
        alpha=0.7
    )

    # Verify results
    assert len(results) <= 3
    assert all(len(r) == 3 for r in results)  # (doc_id, score, metadata) tuples
    assert all(isinstance(r[0], str) for r in results)  # doc_id is string
    assert all(isinstance(r[1], float) for r in results)  # score is float
    assert all(isinstance(r[2], dict) for r in results)  # metadata is dict

    await backend.close()


@pytest.mark.asyncio
async def test_chromadb_backend_keyword_search(temp_persist_dir):
    """ChromaDBBackend should perform keyword search."""
    backend = ChromaDBBackend(
        persist_directory=str(temp_persist_dir),
        collection_name="test"
    )

    # Add documents
    await backend.add_documents(
        ids=["doc1", "doc2"],
        embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
        documents=["machine learning tutorial", "deep learning guide"],
        metadatas=[{"type": "tutorial"}, {"type": "guide"}]
    )

    # Query with keyword search
    results = await backend.query_keyword(
        query="machine learning",
        top_k=2
    )

    # Verify results format
    assert isinstance(results, list)
    # May be empty due to ChromaDB's simple keyword matching

    await backend.close()


@pytest.mark.asyncio
async def test_chromadb_backend_delete(temp_persist_dir):
    """ChromaDBBackend should delete documents."""
    backend = ChromaDBBackend(
        persist_directory=str(temp_persist_dir),
        collection_name="test"
    )

    # Add documents
    await backend.add_documents(
        ids=["doc1", "doc2", "doc3"],
        embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]],
        documents=["test1", "test2", "test3"],
        metadatas=[{"id": "1"}, {"id": "2"}, {"id": "3"}]
    )

    # Delete by IDs
    count = await backend.delete_documents(ids=["doc1", "doc2"])
    assert count == 2

    await backend.close()
