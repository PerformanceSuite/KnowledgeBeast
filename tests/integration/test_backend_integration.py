"""Integration tests for backend abstraction with HybridQueryEngine."""

import pytest
import tempfile
from pathlib import Path

from knowledgebeast.backends.chromadb import ChromaDBBackend
from knowledgebeast.core.repository import DocumentRepository
from knowledgebeast.core.query_engine import HybridQueryEngine


@pytest.fixture
def temp_chromadb():
    """Temporary ChromaDB backend."""
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = ChromaDBBackend(
            persist_directory=tmpdir,
            collection_name="test_integration"
        )
        yield backend


@pytest.mark.asyncio
async def test_hybrid_engine_with_chromadb_backend(temp_chromadb):
    """HybridQueryEngine should work with ChromaDBBackend."""
    repo = DocumentRepository()

    # Add test documents
    repo.add_document("doc1", {"content": "machine learning and AI"})
    repo.add_document("doc2", {"content": "deep learning neural networks"})
    repo.add_document("doc3", {"content": "data science and analytics"})

    # Create engine with backend
    engine = HybridQueryEngine(
        repository=repo,
        backend=temp_chromadb,
        model_name="all-MiniLM-L6-v2"
    )

    # Verify backend is set
    assert engine.backend == temp_chromadb

    # Legacy mode should still work (without backend)
    legacy_engine = HybridQueryEngine(
        repository=repo,
        model_name="all-MiniLM-L6-v2"
    )

    assert legacy_engine.backend is None
    assert len(legacy_engine.embedding_cache.cache) > 0  # Embeddings cached


@pytest.mark.asyncio
async def test_backend_statistics_integration(temp_chromadb):
    """Backend statistics should integrate with query engine."""
    repo = DocumentRepository()
    repo.add_document("doc1", {"content": "test document"})

    engine = HybridQueryEngine(
        repository=repo,
        backend=temp_chromadb
    )

    # Get backend stats
    stats = await temp_chromadb.get_statistics()

    assert stats["backend"] == "chromadb"
    assert stats["collection"] == "test_integration"
    assert "total_documents" in stats


@pytest.mark.asyncio
async def test_backend_health_integration(temp_chromadb):
    """Backend health check should work."""
    repo = DocumentRepository()
    engine = HybridQueryEngine(repository=repo, backend=temp_chromadb)

    health = await temp_chromadb.get_health()

    assert health["status"] in ["healthy", "degraded", "unhealthy"]
    assert "backend_available" in health
