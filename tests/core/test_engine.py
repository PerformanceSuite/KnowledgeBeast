"""Tests for core KnowledgeBase engine."""

import time
from pathlib import Path
import pytest

from knowledgebeast.core.engine import KnowledgeBase
from knowledgebeast.core.config import KnowledgeBeastConfig


class TestKnowledgeBaseInitialization:
    """Test KnowledgeBase initialization."""

    def test_initialization_with_config(self, kb_config: KnowledgeBeastConfig):
        """Test KB initializes with provided config."""
        kb = KnowledgeBase(kb_config)
        assert kb.config == kb_config
        assert kb.documents == {}
        assert kb.index == {}
        assert len(kb.query_cache) == 0

    def test_initialization_without_config(self):
        """Test KB initializes with default config."""
        kb = KnowledgeBase()
        assert isinstance(kb.config, KnowledgeBeastConfig)
        assert kb.config.auto_warm is True  # Default should be True

    def test_initialization_with_progress_callback(self, kb_config: KnowledgeBeastConfig, mock_progress_callback):
        """Test KB initialization with progress callback."""
        kb_config.enable_progress_callbacks = True
        kb = KnowledgeBase(kb_config, progress_callback=mock_progress_callback)
        assert kb.progress_callback is not None

    def test_auto_warm_on_init(self, temp_kb_dir: Path):
        """Test automatic warming on initialization."""
        config = KnowledgeBeastConfig(
            knowledge_dirs=[temp_kb_dir],
            cache_file=temp_kb_dir.parent / ".cache.pkl",
            auto_warm=True,
            verbose=False
        )
        kb = KnowledgeBase(config)
        assert len(kb.documents) > 0
        assert len(kb.index) > 0
        assert kb.stats['last_warm_time'] is not None


class TestDocumentIngestion:
    """Test document ingestion functionality."""

    def test_ingest_all_creates_documents(self, kb_instance: KnowledgeBase):
        """Test ingesting all documents populates KB."""
        kb_instance.ingest_all()
        assert len(kb_instance.documents) > 0
        assert len(kb_instance.index) > 0
        assert kb_instance.stats['total_documents'] > 0
        assert kb_instance.stats['total_terms'] > 0

    def test_ingest_all_creates_cache(self, kb_instance: KnowledgeBase):
        """Test ingestion creates cache file."""
        kb_instance.ingest_all()
        assert kb_instance.config.cache_file.exists()

    def test_ingest_all_uses_cache_when_valid(self, kb_instance: KnowledgeBase):
        """Test subsequent loads use cache."""
        # First ingestion
        kb_instance.ingest_all()
        doc_count_1 = len(kb_instance.documents)

        # Second KB instance should use cache
        kb2 = KnowledgeBase(kb_instance.config)
        kb2.ingest_all()
        assert len(kb2.documents) == doc_count_1

    def test_rebuild_index_clears_cache(self, kb_instance: KnowledgeBase):
        """Test rebuild_index forces re-ingestion."""
        kb_instance.ingest_all()
        original_docs = len(kb_instance.documents)

        kb_instance.rebuild_index()
        assert len(kb_instance.documents) == original_docs
        # Query cache should be cleared
        assert len(kb_instance.query_cache) == 0

    def test_ingest_nonexistent_directory(self, temp_kb_dir: Path):
        """Test ingestion handles nonexistent directories gracefully."""
        config = KnowledgeBeastConfig(
            knowledge_dirs=[temp_kb_dir / "nonexistent"],
            cache_file=temp_kb_dir / "test_cache.pkl",  # Unique cache file
            auto_warm=False,
            verbose=False
        )
        kb = KnowledgeBase(config)
        kb.ingest_all()
        assert len(kb.documents) == 0


class TestQuerying:
    """Test query functionality."""

    def test_query_basic(self, kb_instance_warmed: KnowledgeBase):
        """Test basic query returns results."""
        results = kb_instance_warmed.query("audio processing")
        assert len(results) > 0
        assert all(isinstance(r, tuple) for r in results)
        assert all(len(r) == 2 for r in results)

    def test_query_with_cache(self, kb_instance_warmed: KnowledgeBase):
        """Test query uses cache on subsequent calls."""
        query = "juce framework"

        # First query - cache miss
        result1 = kb_instance_warmed.query(query, use_cache=True)
        cache_misses_1 = kb_instance_warmed.stats['cache_misses']

        # Second query - should be cache hit
        result2 = kb_instance_warmed.query(query, use_cache=True)
        cache_hits = kb_instance_warmed.stats['cache_hits']

        assert result1 == result2
        assert cache_hits > 0

    def test_query_without_cache(self, kb_instance_warmed: KnowledgeBase):
        """Test query without using cache."""
        query = "music theory"

        result1 = kb_instance_warmed.query(query, use_cache=False)
        result2 = kb_instance_warmed.query(query, use_cache=False)

        # Both should be cache misses
        assert kb_instance_warmed.stats['cache_hits'] == 0
        assert kb_instance_warmed.stats['cache_misses'] > 0

    def test_query_empty_string_raises_error(self, kb_instance_warmed: KnowledgeBase):
        """Test query with empty string raises ValueError."""
        with pytest.raises(ValueError, match="Search terms cannot be empty"):
            kb_instance_warmed.query("")

    def test_query_whitespace_raises_error(self, kb_instance_warmed: KnowledgeBase):
        """Test query with whitespace raises ValueError."""
        with pytest.raises(ValueError, match="Search terms cannot be empty"):
            kb_instance_warmed.query("   ")

    def test_query_no_results(self, kb_instance_warmed: KnowledgeBase):
        """Test query with no matching documents."""
        results = kb_instance_warmed.query("quantum mechanics superconductor")
        assert isinstance(results, list)
        # May be empty or have very low relevance

    def test_query_updates_last_access(self, kb_instance_warmed: KnowledgeBase):
        """Test query updates last_access timestamp."""
        before = kb_instance_warmed.last_access
        time.sleep(0.1)
        kb_instance_warmed.query("test")
        after = kb_instance_warmed.last_access
        assert after > before


class TestCacheManagement:
    """Test cache hit rate and management."""

    def test_cache_hit_rate(self, kb_instance_warmed: KnowledgeBase):
        """Test cache hit rate calculation."""
        queries = ["audio", "juce", "audio", "juce", "audio"]
        for q in queries:
            kb_instance_warmed.query(q, use_cache=True)

        stats = kb_instance_warmed.get_stats()
        assert 'cache_hit_rate' in stats
        # Should have some cache hits
        hit_rate_pct = float(stats['cache_hit_rate'].rstrip('%'))
        assert hit_rate_pct > 0

    def test_clear_cache(self, kb_instance_warmed: KnowledgeBase):
        """Test clear_cache removes all cached queries."""
        kb_instance_warmed.query("test", use_cache=True)
        assert len(kb_instance_warmed.query_cache) > 0

        kb_instance_warmed.clear_cache()
        assert len(kb_instance_warmed.query_cache) == 0

    def test_cache_capacity_limit(self, kb_config: KnowledgeBeastConfig):
        """Test cache respects capacity limit."""
        kb_config.max_cache_size = 3
        kb_config.auto_warm = True
        kb = KnowledgeBase(kb_config)

        # Execute more queries than cache capacity
        for i in range(10):
            kb.query(f"query {i}", use_cache=True)

        # Cache should not exceed capacity
        assert len(kb.query_cache) <= 3


class TestWarming:
    """Test warming functionality."""

    def test_warming(self, kb_instance: KnowledgeBase):
        """Test manual warming populates cache."""
        kb_instance.warm_up()
        assert len(kb_instance.documents) > 0
        assert len(kb_instance.index) > 0
        assert kb_instance.stats['warm_queries'] > 0
        assert kb_instance.stats['last_warm_time'] is not None

    def test_warming_executes_queries(self, kb_config: KnowledgeBeastConfig):
        """Test warming executes configured queries."""
        kb_config.warming_queries = ["test1", "test2", "test3"]
        kb_config.auto_warm = False
        kb = KnowledgeBase(kb_config)

        kb.warm_up()
        # Should have executed warming queries
        assert kb.stats['warm_queries'] == 3

    def test_warming_handles_errors_gracefully(self, kb_config: KnowledgeBeastConfig):
        """Test warming continues on query errors."""
        kb_config.warming_queries = ["", "valid query", ""]  # Empty queries will fail
        kb_config.auto_warm = False
        kb = KnowledgeBase(kb_config)

        # Should not raise exception
        kb.warm_up()
        # At least the valid query should succeed
        assert kb.stats['warm_queries'] > 0


class TestStaleCacheDetection:
    """Test stale cache detection."""

    def test_stale_cache_detection_on_file_change(self, kb_instance: KnowledgeBase, temp_kb_dir: Path):
        """Test cache detected as stale when file modified."""
        kb_instance.ingest_all()
        cache_path = kb_instance.config.cache_file

        # Modify a file
        time.sleep(0.1)
        test_file = temp_kb_dir / "audio_processing.md"
        test_file.write_text("# Modified content\nNew information")

        # Cache should be stale
        is_stale = kb_instance._is_cache_stale(cache_path)
        assert is_stale is True

    def test_stale_cache_detection_on_file_addition(self, kb_instance: KnowledgeBase, temp_kb_dir: Path):
        """Test cache detected as stale when files added."""
        kb_instance.ingest_all()
        cache_path = kb_instance.config.cache_file

        # Add new file
        (temp_kb_dir / "new_file.md").write_text("# New Document\nBrand new content")

        # Cache should be stale
        is_stale = kb_instance._is_cache_stale(cache_path)
        assert is_stale is True


class TestMultiDirectorySupport:
    """Test multi-directory knowledge base support."""

    def test_multi_directory_ingestion(self, temp_kb_dir: Path):
        """Test ingesting from multiple directories."""
        # Create second directory
        kb_dir2 = temp_kb_dir.parent / "knowledge-base-2"
        kb_dir2.mkdir()
        (kb_dir2 / "extra_doc.md").write_text("# Extra Document\nAdditional content")

        config = KnowledgeBeastConfig(
            knowledge_dirs=[temp_kb_dir, kb_dir2],
            auto_warm=False,
            verbose=False
        )
        kb = KnowledgeBase(config)
        kb.ingest_all()

        # Should have documents from both directories
        assert len(kb.documents) >= 4  # 3 from original + 1 from second


class TestProgressCallbacks:
    """Test progress callback functionality."""

    def test_progress_callbacks_during_ingestion(self, kb_config: KnowledgeBeastConfig, mock_progress_callback):
        """Test progress callbacks during document ingestion."""
        kb_config.enable_progress_callbacks = True
        kb = KnowledgeBase(kb_config, progress_callback=mock_progress_callback)
        kb.ingest_all()

        # Should have received progress updates
        assert len(mock_progress_callback.calls) > 0

    def test_progress_callbacks_during_warming(self, kb_config: KnowledgeBeastConfig, mock_progress_callback):
        """Test progress callbacks during warming."""
        kb_config.enable_progress_callbacks = True
        kb_config.auto_warm = False
        kb = KnowledgeBase(kb_config, progress_callback=mock_progress_callback)

        mock_progress_callback.calls.clear()
        kb.warm_up()

        # Should have received warming progress
        assert len(mock_progress_callback.calls) > 0


class TestContextManager:
    """Test context manager functionality."""

    def test_context_manager_entry_exit(self, kb_config: KnowledgeBeastConfig):
        """Test KB works as context manager."""
        with KnowledgeBase(kb_config) as kb:
            assert isinstance(kb, KnowledgeBase)
            kb.ingest_all()
            results = kb.query("test")
            assert isinstance(results, list)


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_get_answer(self, kb_instance_warmed: KnowledgeBase):
        """Test get_answer returns formatted answer."""
        answer = kb_instance_warmed.get_answer("audio processing")
        assert isinstance(answer, str)
        assert len(answer) > 0

    def test_get_answer_no_results(self, kb_instance_warmed: KnowledgeBase):
        """Test get_answer with no results."""
        answer = kb_instance_warmed.get_answer("nonexistent topic xyz123")
        assert "No relevant documentation found" in answer or len(answer) > 0

    def test_get_stats(self, kb_instance_warmed: KnowledgeBase):
        """Test get_stats returns comprehensive stats."""
        stats = kb_instance_warmed.get_stats()

        required_keys = [
            'queries', 'cache_hits', 'cache_misses', 'cache_hit_rate',
            'total_queries', 'documents', 'terms', 'cached_queries',
            'last_access_age', 'knowledge_dirs'
        ]
        for key in required_keys:
            assert key in stats

    def test_query_error_handling(self, kb_instance_warmed: KnowledgeBase):
        """Test query handles errors gracefully."""
        # This should not raise exception
        try:
            kb_instance_warmed.query("test query")
        except Exception as e:
            pytest.fail(f"Query raised unexpected exception: {e}")
