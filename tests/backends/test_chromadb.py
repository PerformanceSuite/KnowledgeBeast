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
