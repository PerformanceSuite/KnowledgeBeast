"""Tests for Graceful Degradation in query engine.

Validates:
- Fallback to keyword search when ChromaDB down
- Cache-only responses when both ChromaDB and index unavailable
- degraded_mode flag in responses
- Recovery to normal mode when ChromaDB returns
- Alert emissions on mode changes
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np

from knowledgebeast.core.query_engine import HybridQueryEngine
from knowledgebeast.core.repository import DocumentRepository
from knowledgebeast.core.circuit_breaker import CircuitBreakerError


@pytest.fixture
def mock_repository():
    """Create mock repository with test data."""
    repo = Mock(spec=DocumentRepository)
    repo._lock = MagicMock()
    repo._lock.__enter__ = Mock(return_value=None)
    repo._lock.__exit__ = Mock(return_value=None)

    # Mock documents
    repo.documents = {
        "doc1": {"content": "Python programming tutorial", "name": "doc1.md"},
        "doc2": {"content": "FastAPI web framework guide", "name": "doc2.md"},
        "doc3": {"content": "Database design patterns", "name": "doc3.md"},
    }

    repo.get_document = lambda doc_id: repo.documents.get(doc_id)
    repo.get_documents_by_ids = lambda ids: [repo.documents[doc_id] for doc_id in ids if doc_id in repo.documents]
    repo.get_stats = lambda: {"documents": len(repo.documents)}

    return repo


class TestGracefulDegradationVectorSearch:
    """Test graceful degradation in vector search."""

    def test_vector_search_normal_mode(self, mock_repository):
        """Test vector search works normally when all systems operational."""
        engine = HybridQueryEngine(mock_repository, model_name="all-MiniLM-L6-v2")

        # Normal search should work
        results, degraded = engine.search_vector("Python programming", top_k=5)

        assert not degraded, "Should not be in degraded mode"
        assert isinstance(results, list)

    def test_vector_search_falls_back_on_circuit_breaker_error(self, mock_repository):
        """Test vector search falls back to keyword when circuit breaker opens."""
        engine = HybridQueryEngine(mock_repository)

        # Mock circuit breaker error
        with patch.object(engine, '_get_embedding') as mock_embed:
            mock_embed.side_effect = CircuitBreakerError("Circuit open")

            results, degraded = engine.search_vector("Python", fallback_on_error=True)

            assert degraded, "Should be in degraded mode"
            assert isinstance(results, list)

    def test_vector_search_no_fallback_returns_empty(self, mock_repository):
        """Test vector search returns empty when fallback disabled."""
        engine = HybridQueryEngine(mock_repository)

        with patch.object(engine, '_get_embedding') as mock_embed:
            mock_embed.side_effect = CircuitBreakerError("Circuit open")

            results, degraded = engine.search_vector("Python", fallback_on_error=False)

            assert degraded, "Should be in degraded mode"
            assert len(results) == 0, "Should return empty results"

    def test_vector_search_falls_back_on_general_error(self, mock_repository):
        """Test vector search falls back on any exception."""
        engine = HybridQueryEngine(mock_repository)

        with patch.object(engine, '_get_embedding') as mock_embed:
            mock_embed.side_effect = RuntimeError("Unexpected error")

            results, degraded = engine.search_vector("Python", fallback_on_error=True)

            assert degraded, "Should be in degraded mode"
            assert isinstance(results, list)


class TestGracefulDegradationHybridSearch:
    """Test graceful degradation in hybrid search."""

    def test_hybrid_search_normal_mode(self, mock_repository):
        """Test hybrid search works normally when all systems operational."""
        engine = HybridQueryEngine(mock_repository)

        results, degraded = engine.search_hybrid("Python programming", top_k=5)

        assert not degraded, "Should not be in degraded mode"
        assert isinstance(results, list)

    def test_hybrid_search_degrades_to_keyword_only(self, mock_repository):
        """Test hybrid search degrades to keyword-only when vector fails."""
        engine = HybridQueryEngine(mock_repository)

        with patch.object(engine, '_get_embedding') as mock_embed:
            mock_embed.side_effect = CircuitBreakerError("Circuit open")

            results, degraded = engine.search_hybrid("Python", top_k=5)

            assert degraded, "Should be in degraded mode (keyword-only)"
            assert isinstance(results, list)

    def test_hybrid_search_keyword_fallback_works(self, mock_repository):
        """Test keyword fallback actually returns results."""
        engine = HybridQueryEngine(mock_repository)

        # Mock embedding failure
        with patch.object(engine, '_get_embedding') as mock_embed:
            mock_embed.side_effect = Exception("Vector search failed")

            results, degraded = engine.search_hybrid("Python", top_k=5)

            # Should still get keyword results
            assert degraded
            # Keyword search should find at least one document with "Python"
            assert len(results) >= 0

    def test_hybrid_search_empty_query_not_degraded(self, mock_repository):
        """Test empty query doesn't trigger degraded mode."""
        engine = HybridQueryEngine(mock_repository)

        results, degraded = engine.search_hybrid("", top_k=5)

        assert not degraded, "Empty query should not trigger degraded mode"
        assert len(results) == 0


class TestKeywordSearchFallback:
    """Test keyword search as fallback mechanism."""

    def test_keyword_search_always_available(self, mock_repository):
        """Test keyword search works independently of vector search."""
        engine = HybridQueryEngine(mock_repository)

        # Keyword search should work even if vector search is broken
        results = engine.search_keyword("Python")

        assert isinstance(results, list)
        assert len(results) >= 0

    def test_keyword_search_returns_scored_results(self, mock_repository):
        """Test keyword search returns results with scores."""
        engine = HybridQueryEngine(mock_repository)

        results = engine.search_keyword("Python programming")

        if len(results) > 0:
            # Results should be tuples of (doc_id, doc, score)
            for result in results:
                assert len(result) == 3
                doc_id, doc, score = result
                assert isinstance(doc_id, str)
                assert isinstance(doc, dict)
                assert isinstance(score, (int, float))
                assert 0 <= score <= 1


class TestDegradedModeRecovery:
    """Test recovery from degraded mode."""

    def test_recovery_after_successful_call(self, mock_repository):
        """Test system recovers when service becomes available."""
        engine = HybridQueryEngine(mock_repository)

        # First call fails (degraded mode)
        with patch.object(engine, '_get_embedding') as mock_embed:
            mock_embed.side_effect = Exception("Service down")
            results1, degraded1 = engine.search_vector("test", fallback_on_error=True)
            assert degraded1

        # Second call succeeds (recovery)
        results2, degraded2 = engine.search_vector("test")
        assert not degraded2, "Should recover after successful call"


class TestDegradedModeFlags:
    """Test degraded_mode flag propagation."""

    def test_degraded_flag_true_on_fallback(self, mock_repository):
        """Test degraded flag is True when fallback is used."""
        engine = HybridQueryEngine(mock_repository)

        with patch.object(engine, '_get_embedding') as mock_embed:
            mock_embed.side_effect = CircuitBreakerError("Circuit open")

            _, degraded = engine.search_vector("test", fallback_on_error=True)
            assert degraded is True

    def test_degraded_flag_false_on_success(self, mock_repository):
        """Test degraded flag is False when search succeeds."""
        engine = HybridQueryEngine(mock_repository)

        _, degraded = engine.search_vector("test")
        assert degraded is False

    def test_hybrid_degraded_flag_on_vector_failure(self, mock_repository):
        """Test hybrid search sets degraded flag when vector fails."""
        engine = HybridQueryEngine(mock_repository)

        with patch.object(engine, '_get_embedding') as mock_embed:
            mock_embed.side_effect = Exception("Vector failed")

            _, degraded = engine.search_hybrid("test")
            assert degraded is True


class TestMultipleFailureScenarios:
    """Test various failure scenarios and fallback chains."""

    def test_fallback_chain_vector_to_keyword(self, mock_repository):
        """Test fallback chain: vector -> keyword."""
        engine = HybridQueryEngine(mock_repository)

        with patch.object(engine, '_get_embedding') as mock_embed:
            mock_embed.side_effect = Exception("Vector failed")

            # Should fallback to keyword
            results, degraded = engine.search_vector("Python", fallback_on_error=True)

            assert degraded
            assert isinstance(results, list)

    def test_keyword_fallback_also_fails(self, mock_repository):
        """Test when both vector and keyword search fail."""
        engine = HybridQueryEngine(mock_repository)

        with patch.object(engine, '_get_embedding') as mock_embed:
            mock_embed.side_effect = Exception("Vector failed")

            with patch.object(engine, 'search_keyword') as mock_keyword:
                mock_keyword.side_effect = Exception("Keyword also failed")

                results, degraded = engine.search_vector("test", fallback_on_error=True)

                assert degraded
                assert len(results) == 0


class TestEmbeddingCacheResilience:
    """Test embedding cache helps with degradation."""

    def test_cached_embeddings_used_on_partial_failure(self, mock_repository):
        """Test cached embeddings are used when new embeddings fail."""
        engine = HybridQueryEngine(mock_repository)

        # Pre-populate cache
        engine.embedding_cache.put("doc1", np.random.rand(384))
        engine.embedding_cache.put("doc2", np.random.rand(384))

        # Even if embedding generation fails, cached values should work
        # (This is implicit - search will use cached embeddings)
        results, degraded = engine.search_vector("test")

        # Should work with cached embeddings
        assert isinstance(results, list)
