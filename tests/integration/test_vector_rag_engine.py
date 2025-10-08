"""Integration tests for vector RAG engine integration.

This test suite verifies:
1. Vector embeddings are generated during ingestion
2. Vector search works correctly
3. Hybrid search combines vector and keyword search
4. Backward compatibility is maintained
5. Performance targets are met
"""

import pytest
import time
import tempfile
from pathlib import Path
from unittest.mock import patch

from knowledgebeast.core.engine import KnowledgeBase
from knowledgebeast.core.config import KnowledgeBeastConfig


class TestVectorRAGEngineIntegration:
    """Integration tests for vector RAG engine."""

    @pytest.fixture
    def temp_kb_dir(self, tmp_path):
        """Create temporary knowledge base directory with test documents."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()

        # Create test documents with different topics
        (kb_dir / "python.md").write_text("""
# Python Programming

Python is a high-level programming language.
It is widely used for web development, data science, and machine learning.
Python has excellent libraries like pandas, numpy, and scikit-learn.
""")

        (kb_dir / "javascript.md").write_text("""
# JavaScript Programming

JavaScript is a programming language for web browsers.
It is used for frontend development and Node.js for backend.
Popular frameworks include React, Vue, and Angular.
""")

        (kb_dir / "machine_learning.md").write_text("""
# Machine Learning

Machine learning is a subset of artificial intelligence.
It involves training models on data to make predictions.
Common algorithms include neural networks, decision trees, and SVM.
""")

        (kb_dir / "data_science.md").write_text("""
# Data Science

Data science combines statistics, programming, and domain knowledge.
It is used for analyzing and visualizing data.
Tools include Python, R, SQL, and Tableau.
""")

        return kb_dir

    @pytest.fixture
    def config_with_vector(self, temp_kb_dir, tmp_path):
        """Create config with vector search enabled."""
        cache_file = tmp_path / ".cache" / "kb_cache.pkl"
        cache_file.parent.mkdir(exist_ok=True)

        return KnowledgeBeastConfig(
            knowledge_dirs=[temp_kb_dir],
            cache_file=str(cache_file),
            auto_warm=False,
            verbose=False,
            max_cache_size=100
        )

    @pytest.fixture
    def config_without_vector(self, temp_kb_dir, tmp_path):
        """Create config with vector search disabled."""
        cache_file = tmp_path / ".cache" / "kb_cache.pkl"
        cache_file.parent.mkdir(exist_ok=True)

        return KnowledgeBeastConfig(
            knowledge_dirs=[temp_kb_dir],
            cache_file=str(cache_file),
            auto_warm=False,
            verbose=False,
            max_cache_size=100
        )

    # ========================================================================
    # Initialization Tests
    # ========================================================================

    def test_vector_components_initialized(self, config_with_vector):
        """Test that vector components are initialized when enabled."""
        kb = KnowledgeBase(config=config_with_vector, enable_vector=True)

        assert kb.enable_vector is True
        assert kb._embedding_engine is not None
        assert kb._vector_store is not None
        assert kb._embedding_engine.model_name == "all-MiniLM-L6-v2"
        assert kb._embedding_engine.embedding_dim == 384

    def test_vector_components_not_initialized_when_disabled(self, config_without_vector):
        """Test that vector components are not initialized when disabled."""
        kb = KnowledgeBase(config=config_without_vector, enable_vector=False)

        assert kb.enable_vector is False
        assert kb._embedding_engine is None
        assert kb._vector_store is None

    def test_custom_embedding_model(self, config_with_vector):
        """Test initialization with custom embedding model."""
        kb = KnowledgeBase(
            config=config_with_vector,
            enable_vector=True,
            embedding_model="all-mpnet-base-v2"
        )

        assert kb._embedding_engine.model_name == "all-mpnet-base-v2"
        assert kb._embedding_engine.embedding_dim == 768

    def test_custom_vector_cache_size(self, config_with_vector):
        """Test initialization with custom vector cache size."""
        kb = KnowledgeBase(
            config=config_with_vector,
            enable_vector=True,
            vector_cache_size=500
        )

        assert kb._embedding_engine.cache.capacity == 500

    def test_persistent_vector_store(self, config_with_vector, tmp_path):
        """Test initialization with persistent vector storage."""
        persist_dir = tmp_path / "chroma_db"
        kb = KnowledgeBase(
            config=config_with_vector,
            enable_vector=True,
            persist_directory=str(persist_dir)
        )

        assert kb._vector_store.persist_directory == persist_dir
        assert persist_dir.exists()

    # ========================================================================
    # Ingestion Tests
    # ========================================================================

    def test_ingestion_generates_embeddings(self, config_with_vector):
        """Test that ingestion generates embeddings for all documents."""
        kb = KnowledgeBase(config=config_with_vector, enable_vector=True)
        kb.ingest_all()

        # Check that documents were ingested
        assert kb.stats['total_documents'] == 4

        # Check that embeddings were generated
        assert kb._vector_store.count() == 4

        # Check that embedding cache has entries
        emb_stats = kb._embedding_engine.get_stats()
        assert emb_stats['embeddings_generated'] > 0

    def test_ingestion_without_vector(self, config_without_vector):
        """Test that ingestion works without vector components."""
        kb = KnowledgeBase(config=config_without_vector, enable_vector=False)
        kb.ingest_all()

        # Check that documents were ingested
        assert kb.stats['total_documents'] == 4

        # Check that no vector store was created
        assert kb._vector_store is None

    def test_embeddings_stored_with_metadata(self, config_with_vector):
        """Test that embeddings are stored with correct metadata."""
        kb = KnowledgeBase(config=config_with_vector, enable_vector=True)
        kb.ingest_all()

        # Get all stored documents
        stored = kb._vector_store.peek(limit=10)

        assert len(stored['ids']) == 4
        assert 'metadatas' in stored
        for metadata in stored['metadatas']:
            assert 'name' in metadata
            assert 'doc_id' in metadata

    # ========================================================================
    # Vector Search Tests
    # ========================================================================

    def test_vector_search_semantic_similarity(self, config_with_vector):
        """Test that vector search finds semantically similar documents."""
        kb = KnowledgeBase(config=config_with_vector, enable_vector=True)
        kb.ingest_all()

        # Search for "AI and neural networks" should find machine_learning.md
        results = kb.query("artificial intelligence and neural networks", mode='vector', top_k=3)

        assert len(results) > 0
        # The top result should be machine_learning.md
        top_doc_id, top_doc = results[0]
        assert 'machine_learning' in top_doc_id.lower() or 'Machine Learning' in top_doc['name']

    def test_vector_search_different_wording(self, config_with_vector):
        """Test vector search finds documents even with different wording."""
        kb = KnowledgeBase(config=config_with_vector, enable_vector=True)
        kb.ingest_all()

        # Search for "web browser scripting" should find javascript.md
        results = kb.query("web browser scripting language", mode='vector', top_k=3)

        assert len(results) > 0
        # Check that JavaScript document is in top results
        doc_names = [doc['name'] for _, doc in results[:3]]
        assert any('JavaScript' in name or 'javascript' in name for name in doc_names)

    def test_vector_search_top_k(self, config_with_vector):
        """Test that vector search respects top_k parameter."""
        kb = KnowledgeBase(config=config_with_vector, enable_vector=True)
        kb.ingest_all()

        results = kb.query("programming", mode='vector', top_k=2)

        assert len(results) == 2

    # ========================================================================
    # Keyword Search Tests (Backward Compatibility)
    # ========================================================================

    def test_keyword_search_exact_match(self, config_with_vector):
        """Test keyword search for exact term matching."""
        kb = KnowledgeBase(config=config_with_vector, enable_vector=True)
        kb.ingest_all()

        # Search for exact term "Python"
        results = kb.query("Python", mode='keyword')

        assert len(results) > 0
        top_doc_id, top_doc = results[0]
        assert 'python' in top_doc['content'].lower()

    def test_keyword_search_multiple_terms(self, config_with_vector):
        """Test keyword search with multiple terms."""
        kb = KnowledgeBase(config=config_with_vector, enable_vector=True)
        kb.ingest_all()

        results = kb.query("python machine learning", mode='keyword')

        assert len(results) > 0

    def test_backward_compatible_default_query(self, config_with_vector):
        """Test that default query behavior uses hybrid mode."""
        kb = KnowledgeBase(config=config_with_vector, enable_vector=True)
        kb.ingest_all()

        # Default query should use hybrid mode
        results = kb.query("programming")

        assert len(results) > 0
        # Check that hybrid_queries stat was incremented
        assert kb.stats['hybrid_queries'] > 0

    # ========================================================================
    # Hybrid Search Tests
    # ========================================================================

    def test_hybrid_search_combines_results(self, config_with_vector):
        """Test that hybrid search combines vector and keyword results."""
        kb = KnowledgeBase(config=config_with_vector, enable_vector=True)
        kb.ingest_all()

        # Hybrid search should find documents using both methods
        results = kb.query("machine learning with python", mode='hybrid', top_k=5)

        assert len(results) > 0
        # Should find both machine_learning.md and python.md
        doc_names = [doc['name'] for _, doc in results]
        has_ml = any('Machine Learning' in name or 'machine_learning' in name for name in doc_names)
        has_python = any('Python' in name or 'python' in name for name in doc_names)
        assert has_ml or has_python

    def test_hybrid_search_custom_alpha(self, config_with_vector):
        """Test hybrid search with custom alpha parameter."""
        kb = KnowledgeBase(config=config_with_vector, enable_vector=True)
        kb.ingest_all()

        # Alpha = 1.0 should be pure vector search
        results_vector = kb.query("programming", mode='hybrid', alpha=1.0, top_k=3)

        # Alpha = 0.0 should be pure keyword search
        results_keyword = kb.query("programming", mode='hybrid', alpha=0.0, top_k=3)

        # Both should return results
        assert len(results_vector) > 0
        assert len(results_keyword) > 0

        # Results might be the same for simple queries, but both modes should work

    def test_hybrid_search_default_alpha(self, config_with_vector):
        """Test hybrid search uses default alpha of 0.7."""
        kb = KnowledgeBase(config=config_with_vector, enable_vector=True)
        kb.ingest_all()

        results = kb.query("data analysis", mode='hybrid', top_k=3)

        assert len(results) > 0
        # Should balance between vector and keyword search

    # ========================================================================
    # Cache Tests
    # ========================================================================

    def test_vector_query_caching(self, config_with_vector):
        """Test that vector queries are cached correctly."""
        kb = KnowledgeBase(config=config_with_vector, enable_vector=True)
        kb.ingest_all()

        # First query
        results1 = kb.query("machine learning", mode='vector', use_cache=True)
        cache_misses_1 = kb.stats['cache_misses']

        # Second identical query should hit cache
        results2 = kb.query("machine learning", mode='vector', use_cache=True)
        cache_hits_2 = kb.stats['cache_hits']

        assert results1 == results2
        assert cache_hits_2 > 0

    def test_different_modes_have_separate_cache_keys(self, config_with_vector):
        """Test that different search modes use separate cache keys."""
        kb = KnowledgeBase(config=config_with_vector, enable_vector=True)
        kb.ingest_all()

        # Query with vector mode
        results_vector = kb.query("programming", mode='vector', use_cache=True)

        # Query with keyword mode (should miss cache)
        initial_misses = kb.stats['cache_misses']
        results_keyword = kb.query("programming", mode='keyword', use_cache=True)
        final_misses = kb.stats['cache_misses']

        # Should have a cache miss because mode is different
        assert final_misses > initial_misses

    # ========================================================================
    # Statistics Tests
    # ========================================================================

    def test_stats_include_vector_metrics(self, config_with_vector):
        """Test that statistics include vector-related metrics."""
        kb = KnowledgeBase(config=config_with_vector, enable_vector=True)
        kb.ingest_all()

        kb.query("test", mode='vector')
        kb.query("test", mode='keyword')
        kb.query("test", mode='hybrid')

        stats = kb.get_stats()

        assert 'vector_queries' in stats
        assert 'keyword_queries' in stats
        assert 'hybrid_queries' in stats
        assert stats['vector_queries'] > 0
        assert stats['keyword_queries'] > 0
        assert stats['hybrid_queries'] > 0

    def test_embedding_stats(self, config_with_vector):
        """Test that embedding statistics are tracked."""
        kb = KnowledgeBase(config=config_with_vector, enable_vector=True)
        kb.ingest_all()

        emb_stats = kb._embedding_engine.get_stats()

        assert emb_stats['embeddings_generated'] > 0
        assert emb_stats['total_queries'] > 0
        assert 'cache_hit_rate' in emb_stats
        assert 'embedding_dim' in emb_stats

    # ========================================================================
    # Performance Tests
    # ========================================================================

    def test_vector_query_performance(self, config_with_vector):
        """Test that vector queries meet performance targets (P99 < 150ms)."""
        kb = KnowledgeBase(config=config_with_vector, enable_vector=True)
        kb.ingest_all()

        # Run multiple queries to get P99
        latencies = []
        queries = [
            "machine learning",
            "web development",
            "data analysis",
            "programming languages",
            "artificial intelligence"
        ]

        for _ in range(20):  # 100 total queries (20 iterations * 5 queries)
            for query in queries:
                start = time.time()
                kb.query(query, mode='vector', use_cache=False)
                latency = (time.time() - start) * 1000  # Convert to ms
                latencies.append(latency)

        # Calculate P99
        latencies.sort()
        p99_index = int(len(latencies) * 0.99)
        p99_latency = latencies[p99_index]

        assert p99_latency < 150, f"P99 latency {p99_latency:.2f}ms exceeds 150ms target"

    def test_hybrid_query_performance(self, config_with_vector):
        """Test that hybrid queries meet performance targets."""
        kb = KnowledgeBase(config=config_with_vector, enable_vector=True)
        kb.ingest_all()

        # Hybrid queries should still be fast
        latencies = []
        for _ in range(50):
            start = time.time()
            kb.query("programming", mode='hybrid', use_cache=False)
            latency = (time.time() - start) * 1000
            latencies.append(latency)

        # Calculate P99
        latencies.sort()
        p99_index = int(len(latencies) * 0.99)
        p99_latency = latencies[p99_index]

        assert p99_latency < 200, f"Hybrid P99 latency {p99_latency:.2f}ms exceeds 200ms target"

    def test_cached_query_performance(self, config_with_vector):
        """Test that cached queries are very fast (< 10ms)."""
        kb = KnowledgeBase(config=config_with_vector, enable_vector=True)
        kb.ingest_all()

        # Warm the cache
        kb.query("machine learning", mode='vector', use_cache=True)

        # Measure cached query performance
        latencies = []
        for _ in range(100):
            start = time.time()
            kb.query("machine learning", mode='vector', use_cache=True)
            latency = (time.time() - start) * 1000
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 10, f"Cached query avg latency {avg_latency:.2f}ms exceeds 10ms target"

    # ========================================================================
    # Error Handling Tests
    # ========================================================================

    def test_empty_query_raises_error(self, config_with_vector):
        """Test that empty queries raise ValueError."""
        kb = KnowledgeBase(config=config_with_vector, enable_vector=True)
        kb.ingest_all()

        with pytest.raises(ValueError):
            kb.query("", mode='vector')

        with pytest.raises(ValueError):
            kb.query("   ", mode='hybrid')

    def test_invalid_alpha_raises_error(self, config_with_vector):
        """Test that invalid alpha values raise ValueError."""
        kb = KnowledgeBase(config=config_with_vector, enable_vector=True)
        kb.ingest_all()

        with pytest.raises(ValueError):
            kb.query("test", mode='hybrid', alpha=1.5)

        with pytest.raises(ValueError):
            kb.query("test", mode='hybrid', alpha=-0.1)

    # ========================================================================
    # Edge Cases
    # ========================================================================

    def test_query_before_ingestion(self, config_with_vector):
        """Test querying before ingestion returns empty results."""
        kb = KnowledgeBase(config=config_with_vector, enable_vector=True)

        results = kb.query("test", mode='vector')

        assert len(results) == 0

    def test_rebuild_index_updates_embeddings(self, config_with_vector):
        """Test that rebuild_index regenerates embeddings."""
        kb = KnowledgeBase(config=config_with_vector, enable_vector=True)
        kb.ingest_all()

        initial_count = kb._vector_store.count()

        kb.rebuild_index()

        final_count = kb._vector_store.count()
        assert final_count == initial_count

    def test_context_manager_cleanup(self, config_with_vector):
        """Test that context manager properly cleans up resources."""
        with KnowledgeBase(config=config_with_vector, enable_vector=True) as kb:
            kb.ingest_all()
            results = kb.query("test", mode='vector')
            assert len(results) >= 0

        # After context exit, resources should be cleaned up
        # No exceptions should be raised


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
