"""Backward compatibility tests for vector RAG integration.

This test suite ensures that:
1. Existing code works without modification
2. Default behavior remains unchanged when vector is disabled
3. All existing APIs remain functional
4. Performance characteristics are maintained
"""

import pytest
import time
from pathlib import Path

from knowledgebeast.core.engine import KnowledgeBase
from knowledgebeast.core.config import KnowledgeBeastConfig


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""

    @pytest.fixture
    def temp_kb_dir(self, tmp_path):
        """Create temporary knowledge base directory with test documents."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()

        (kb_dir / "doc1.md").write_text("""
# Python Best Practices

Python code should follow PEP 8 style guide.
Use meaningful variable names and write docstrings.
""")

        (kb_dir / "doc2.md").write_text("""
# JavaScript Guide

JavaScript is used for web development.
Modern JavaScript uses ES6+ features.
""")

        (kb_dir / "doc3.md").write_text("""
# Testing Guide

Write unit tests for your code.
Use pytest for Python testing.
""")

        return kb_dir

    @pytest.fixture
    def legacy_config(self, temp_kb_dir, tmp_path):
        """Create config matching pre-vector RAG behavior."""
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
    # API Compatibility Tests
    # ========================================================================

    def test_default_initialization_works(self, legacy_config):
        """Test that default initialization without vector params works."""
        # This is how existing code initializes KnowledgeBase
        kb = KnowledgeBase(config=legacy_config)

        # Should initialize successfully with vector enabled by default
        assert kb is not None
        assert kb.enable_vector is True  # Default is True now

    def test_initialization_with_vector_disabled(self, legacy_config):
        """Test initialization with vector search explicitly disabled."""
        # Existing code can disable vector search
        kb = KnowledgeBase(config=legacy_config, enable_vector=False)

        assert kb.enable_vector is False
        assert kb._embedding_engine is None
        assert kb._vector_store is None

    def test_query_without_mode_parameter(self, legacy_config):
        """Test that query() works without specifying mode parameter."""
        kb = KnowledgeBase(config=legacy_config, enable_vector=False)
        kb.ingest_all()

        # Legacy code calls query without mode parameter
        results = kb.query("python")

        assert isinstance(results, list)
        assert len(results) > 0
        # Check result format is (doc_id, document) tuple
        doc_id, doc = results[0]
        assert isinstance(doc_id, str)
        assert isinstance(doc, dict)
        assert 'content' in doc
        assert 'name' in doc

    def test_query_with_use_cache_parameter(self, legacy_config):
        """Test that query() respects use_cache parameter (backward compatible)."""
        kb = KnowledgeBase(config=legacy_config, enable_vector=False)
        kb.ingest_all()

        # Legacy code uses use_cache parameter
        results1 = kb.query("python", use_cache=True)
        results2 = kb.query("python", use_cache=True)

        assert results1 == results2
        assert kb.stats['cache_hits'] > 0

    def test_ingest_all_works_unchanged(self, legacy_config):
        """Test that ingest_all() works without modifications."""
        kb = KnowledgeBase(config=legacy_config, enable_vector=False)

        # Legacy code calls ingest_all()
        kb.ingest_all()

        assert kb.stats['total_documents'] > 0
        assert kb.stats['total_terms'] > 0

    def test_get_stats_includes_legacy_fields(self, legacy_config):
        """Test that get_stats() includes all legacy fields."""
        kb = KnowledgeBase(config=legacy_config, enable_vector=False)
        kb.ingest_all()
        kb.query("test")

        stats = kb.get_stats()

        # Legacy fields must be present
        assert 'queries' in stats
        assert 'cache_hits' in stats
        assert 'cache_misses' in stats
        assert 'total_documents' in stats
        assert 'total_terms' in stats
        assert 'documents' in stats
        assert 'terms' in stats

    def test_get_answer_works_unchanged(self, legacy_config):
        """Test that get_answer() works without modifications."""
        kb = KnowledgeBase(config=legacy_config, enable_vector=False)
        kb.ingest_all()

        # Legacy code calls get_answer()
        answer = kb.get_answer("python testing")

        assert isinstance(answer, str)
        assert len(answer) > 0

    def test_clear_cache_works(self, legacy_config):
        """Test that clear_cache() works unchanged."""
        kb = KnowledgeBase(config=legacy_config, enable_vector=False)
        kb.ingest_all()

        # First query should miss cache
        kb.query("test", use_cache=True)
        initial_misses = kb.stats['cache_misses']

        # Second query should hit cache
        kb.query("test", use_cache=True)
        assert kb.stats['cache_hits'] > 0

        # Clear cache
        kb.clear_cache()

        # After clear, stats should be reset
        assert kb.stats['cache_hits'] == 0
        assert kb.stats['cache_misses'] == 0

        # Next query should miss cache again
        kb.query("test", use_cache=True)
        assert kb.stats['cache_misses'] == 1
        assert kb.stats['cache_hits'] == 0

    def test_rebuild_index_works(self, legacy_config):
        """Test that rebuild_index() works unchanged."""
        kb = KnowledgeBase(config=legacy_config, enable_vector=False)
        kb.ingest_all()

        initial_docs = kb.stats['total_documents']

        kb.rebuild_index()

        assert kb.stats['total_documents'] == initial_docs

    # ========================================================================
    # Property Access Tests
    # ========================================================================

    def test_documents_property_access(self, legacy_config):
        """Test that documents property provides backward compatibility."""
        kb = KnowledgeBase(config=legacy_config, enable_vector=False)
        kb.ingest_all()

        # Legacy code accesses kb.documents
        documents = kb.documents

        assert isinstance(documents, dict) or hasattr(documents, '__getitem__')
        assert len(documents) > 0

    def test_index_property_access(self, legacy_config):
        """Test that index property provides backward compatibility."""
        kb = KnowledgeBase(config=legacy_config, enable_vector=False)
        kb.ingest_all()

        # Legacy code accesses kb.index
        index = kb.index

        assert isinstance(index, dict) or hasattr(index, '__getitem__')
        assert len(index) > 0

    def test_query_cache_property_access(self, legacy_config):
        """Test that query_cache property provides backward compatibility."""
        kb = KnowledgeBase(config=legacy_config, enable_vector=False)
        kb.ingest_all()

        # Legacy code accesses kb.query_cache
        cache = kb.query_cache

        assert cache is not None

    # ========================================================================
    # Performance Regression Tests
    # ========================================================================

    def test_keyword_query_performance_not_degraded(self, legacy_config):
        """Test that keyword queries maintain same performance."""
        kb = KnowledgeBase(config=legacy_config, enable_vector=False)
        kb.ingest_all()

        # Measure query performance
        latencies = []
        for _ in range(100):
            start = time.time()
            kb.query("python", use_cache=False)
            latency = (time.time() - start) * 1000  # ms
            latencies.append(latency)

        latencies.sort()
        p99_latency = latencies[int(len(latencies) * 0.99)]

        # Should meet original performance target
        assert p99_latency < 100, f"P99 latency {p99_latency:.2f}ms exceeds 100ms target"

    def test_ingestion_performance_acceptable(self, legacy_config):
        """Test that ingestion performance is acceptable."""
        kb = KnowledgeBase(config=legacy_config, enable_vector=False)

        start = time.time()
        kb.ingest_all()
        elapsed = time.time() - start

        # Ingestion should be reasonably fast for small dataset
        assert elapsed < 5.0, f"Ingestion took {elapsed:.2f}s, exceeds 5s target"

    # ========================================================================
    # Result Format Compatibility Tests
    # ========================================================================

    def test_query_result_format_unchanged(self, legacy_config):
        """Test that query results maintain expected format."""
        kb = KnowledgeBase(config=legacy_config, enable_vector=False)
        kb.ingest_all()

        results = kb.query("python")

        # Results should be list of (doc_id, document) tuples
        assert isinstance(results, list)
        for result in results:
            assert isinstance(result, tuple)
            assert len(result) == 2
            doc_id, doc = result
            assert isinstance(doc_id, str)
            assert isinstance(doc, dict)
            assert 'content' in doc
            assert 'name' in doc
            assert 'path' in doc

    def test_empty_query_results_format(self, legacy_config):
        """Test that empty results maintain expected format."""
        kb = KnowledgeBase(config=legacy_config, enable_vector=False)
        kb.ingest_all()

        results = kb.query("nonexistent_term_xyz")

        # Should return empty list, not None
        assert isinstance(results, list)
        assert len(results) == 0

    # ========================================================================
    # Context Manager Tests
    # ========================================================================

    def test_context_manager_protocol(self, legacy_config):
        """Test that context manager protocol works unchanged."""
        # Legacy code uses context manager
        with KnowledgeBase(config=legacy_config, enable_vector=False) as kb:
            kb.ingest_all()
            results = kb.query("test")
            assert isinstance(results, list)

        # No exceptions should be raised

    # ========================================================================
    # Edge Case Compatibility Tests
    # ========================================================================

    def test_query_with_empty_index(self, legacy_config):
        """Test querying with empty index (no ingestion)."""
        kb = KnowledgeBase(config=legacy_config, enable_vector=False)

        # Query before ingestion
        results = kb.query("test")

        # Should return empty list, not error
        assert isinstance(results, list)
        assert len(results) == 0

    def test_multiple_query_calls(self, legacy_config):
        """Test multiple sequential query calls work correctly."""
        kb = KnowledgeBase(config=legacy_config, enable_vector=False)
        kb.ingest_all()

        # Multiple queries should all work
        results1 = kb.query("python")
        results2 = kb.query("javascript")
        results3 = kb.query("testing")

        assert len(results1) > 0
        assert len(results2) > 0
        assert len(results3) > 0

    def test_stats_after_multiple_operations(self, legacy_config):
        """Test that stats remain consistent after multiple operations."""
        kb = KnowledgeBase(config=legacy_config, enable_vector=False)
        kb.ingest_all()

        kb.query("test1")
        kb.query("test2")
        kb.clear_cache()
        kb.query("test3")

        stats = kb.get_stats()

        assert stats['queries'] == 3
        assert stats['total_documents'] > 0

    # ========================================================================
    # Configuration Compatibility Tests
    # ========================================================================

    def test_from_config_class_method(self, legacy_config):
        """Test that from_config class method works unchanged."""
        # Legacy code might use class method
        kb = KnowledgeBase.from_config(legacy_config)

        assert kb is not None
        assert isinstance(kb, KnowledgeBase)

    def test_auto_warm_config(self, temp_kb_dir, tmp_path):
        """Test that auto_warm config works unchanged."""
        cache_file = tmp_path / ".cache" / "kb_cache.pkl"
        cache_file.parent.mkdir(exist_ok=True)

        config = KnowledgeBeastConfig(
            knowledge_dirs=[temp_kb_dir],
            cache_file=str(cache_file),
            auto_warm=True,
            verbose=False,
            warming_queries=["python", "javascript"]
        )

        # Should auto-warm on initialization
        kb = KnowledgeBase(config=config, enable_vector=False)

        assert kb.stats['warm_queries'] > 0

    # ========================================================================
    # Vector Disabled Explicitly Tests
    # ========================================================================

    def test_vector_disabled_uses_keyword_search(self, legacy_config):
        """Test that vector disabled falls back to keyword search."""
        kb = KnowledgeBase(config=legacy_config, enable_vector=False)
        kb.ingest_all()

        # Query should use keyword search
        results = kb.query("python")

        assert len(results) > 0
        assert kb.stats['keyword_queries'] > 0
        assert kb.stats['vector_queries'] == 0
        assert kb.stats['hybrid_queries'] == 0

    def test_mode_parameter_ignored_when_vector_disabled(self, legacy_config):
        """Test that mode parameter is ignored when vector is disabled."""
        kb = KnowledgeBase(config=legacy_config, enable_vector=False)
        kb.ingest_all()

        # Even if mode is specified, should use keyword search
        results = kb.query("python", mode='vector')

        assert len(results) > 0
        # Should still use keyword search since vector is disabled
        assert kb.stats['keyword_queries'] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
