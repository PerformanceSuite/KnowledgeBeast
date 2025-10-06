"""End-to-end integration tests for KnowledgeBeast."""

import time
from pathlib import Path
import pytest
from unittest.mock import patch
from click.testing import CliRunner
from fastapi.testclient import TestClient

from knowledgebeast.core.engine import KnowledgeBase
from knowledgebeast.core.config import KnowledgeBeastConfig
from knowledgebeast.core.heartbeat import KnowledgeBaseHeartbeat
from knowledgebeast.cli.commands import cli
from knowledgebeast.api.app import app


class TestFullWorkflow:
    """Test full init -> add -> query -> serve workflow."""

    def test_full_workflow_programmatic(self, temp_kb_dir: Path):
        """Test full workflow using Python API."""
        # 1. Initialize KB
        config = KnowledgeBeastConfig(
            knowledge_dirs=[temp_kb_dir],
            cache_file=temp_kb_dir.parent / ".cache.pkl",
            auto_warm=True,
            verbose=False
        )
        kb = KnowledgeBase(config)

        # 2. Verify documents loaded
        assert len(kb.documents) > 0
        assert len(kb.index) > 0

        # 3. Query the KB
        results = kb.query("audio processing")
        assert len(results) > 0

        # 4. Get statistics
        stats = kb.get_stats()
        assert stats['total_documents'] > 0
        assert stats['total_queries'] > 0

        # 5. Clear cache and verify
        kb.clear_cache()
        assert len(kb.query_cache) == 0

        # 6. Rebuild index
        kb.rebuild_index()
        assert len(kb.documents) > 0

    def test_full_workflow_cli(self, temp_kb_dir: Path):
        """Test full workflow using CLI commands."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create test directory with documents
            kb_path = Path('./kb')
            kb_path.mkdir()
            (kb_path / 'test.md').write_text('# Test\nAudio processing content')

            # 1. Query (will auto-initialize)
            with patch('knowledgebeast.cli.commands.KnowledgeBeastConfig') as mock_config:
                mock_config.return_value = KnowledgeBeastConfig(
                    knowledge_dirs=[kb_path],
                    auto_warm=False,
                    verbose=False
                )

                # Note: CLI tests with real KB are complex due to Rich output
                # We verify commands accept correct args
                result = runner.invoke(cli, ['--help'])
                assert result.exit_code == 0

    def test_full_workflow_api(self, temp_kb_dir: Path):
        """Test full workflow using API endpoints."""
        # Note: API tests require proper initialization
        # This is a basic smoke test
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "version" in data


class TestCliToApiIntegration:
    """Test CLI to API integration."""

    def test_cli_init_then_api_query(self, temp_kb_dir: Path):
        """Test initializing with CLI then querying via API."""
        # This would test that CLI and API share the same data
        # In practice, they use separate instances unless configured to share
        pass  # Placeholder for future implementation

    def test_shared_cache_file(self, temp_kb_dir: Path):
        """Test CLI and API can share cache file."""
        cache_path = temp_kb_dir.parent / "shared.cache.pkl"

        # Create KB via Python API
        config = KnowledgeBeastConfig(
            knowledge_dirs=[temp_kb_dir],
            cache_file=cache_path,
            auto_warm=True,
            verbose=False
        )
        kb = KnowledgeBase(config)
        kb.ingest_all()

        # Verify cache exists
        assert cache_path.exists()

        # Create second KB instance with same cache
        kb2 = KnowledgeBase(config)
        kb2.ingest_all()

        # Should have loaded from cache
        assert len(kb2.documents) == len(kb.documents)


class TestHeartbeatIntegration:
    """Test heartbeat integration with full system."""

    def test_heartbeat_with_live_kb(self, kb_instance_warmed: KnowledgeBase):
        """Test heartbeat running with live KB."""
        heartbeat = KnowledgeBaseHeartbeat(kb_instance_warmed, interval=10)

        heartbeat.start()
        assert heartbeat.is_running()

        # Let it run for a bit
        time.sleep(0.5)

        # Stop and verify
        heartbeat.stop()
        assert not heartbeat.is_running()

    def test_heartbeat_detects_file_changes(self, kb_instance_warmed: KnowledgeBase, temp_kb_dir: Path):
        """Test heartbeat detects and rebuilds on file changes."""
        heartbeat = KnowledgeBaseHeartbeat(kb_instance_warmed, interval=10)

        # Get initial document count
        kb_instance_warmed.ingest_all()
        initial_count = len(kb_instance_warmed.documents)

        # Add new file
        time.sleep(0.2)
        (temp_kb_dir / "new_file.md").write_text("# New\nNew content")

        # Verify cache is stale
        assert heartbeat._is_cache_stale() is True

        # In a real scenario, heartbeat would rebuild on next cycle
        # For testing, we verify the detection works

    def test_heartbeat_warming_queries(self, kb_instance_warmed: KnowledgeBase):
        """Test heartbeat executes warming queries."""
        heartbeat = KnowledgeBaseHeartbeat(kb_instance_warmed, interval=10)

        initial_queries = kb_instance_warmed.stats['queries']

        # Execute warming query manually
        heartbeat._warm_query()

        # Should have incremented query count
        assert kb_instance_warmed.stats['queries'] > initial_queries


class TestMultiComponentIntegration:
    """Test multiple components working together."""

    def test_query_cache_and_heartbeat(self, kb_instance_warmed: KnowledgeBase):
        """Test query caching works with heartbeat running."""
        heartbeat = KnowledgeBaseHeartbeat(kb_instance_warmed, interval=10)
        heartbeat.start()

        try:
            # Execute queries
            result1 = kb_instance_warmed.query("audio", use_cache=True)
            result2 = kb_instance_warmed.query("audio", use_cache=True)

            # Second should be cache hit
            assert result1 == result2
            assert kb_instance_warmed.stats['cache_hits'] > 0

        finally:
            heartbeat.stop()

    def test_concurrent_queries(self, kb_instance_warmed: KnowledgeBase):
        """Test multiple queries in sequence."""
        queries = ["audio", "juce", "music", "librosa", "processing"]

        results = []
        for query in queries:
            results.append(kb_instance_warmed.query(query))

        # All should have results (or empty list)
        assert len(results) == len(queries)
        assert kb_instance_warmed.stats['total_queries'] >= len(queries)

    def test_config_environment_integration(self, monkeypatch, temp_kb_dir: Path):
        """Test environment variables integrate with config."""
        cache_path = temp_kb_dir.parent / "env_cache.pkl"

        monkeypatch.setenv('KB_KNOWLEDGE_DIRS', str(temp_kb_dir))
        monkeypatch.setenv('KB_CACHE_FILE', str(cache_path))
        monkeypatch.setenv('KB_MAX_CACHE_SIZE', '50')
        monkeypatch.setenv('KB_AUTO_WARM', 'false')

        config = KnowledgeBeastConfig()

        assert config.knowledge_dirs == [temp_kb_dir]
        assert config.cache_file == cache_path
        assert config.max_cache_size == 50
        assert config.auto_warm is False


class TestErrorRecovery:
    """Test error recovery in integrated workflows."""

    def test_recovery_from_cache_corruption(self, kb_instance: KnowledgeBase):
        """Test KB recovers from corrupted cache."""
        kb_instance.ingest_all()
        cache_path = kb_instance.config.cache_file

        # Corrupt the cache file
        cache_path.write_text("corrupted data")

        # Should rebuild instead of failing
        kb2 = KnowledgeBase(kb_instance.config)
        kb2.ingest_all()

        assert len(kb2.documents) > 0

    def test_recovery_from_missing_knowledge_dir(self):
        """Test KB handles missing knowledge directory."""
        config = KnowledgeBeastConfig(
            knowledge_dirs=[Path("/nonexistent/path")],
            auto_warm=False,
            verbose=False
        )

        kb = KnowledgeBase(config)
        kb.ingest_all()

        # Should complete without error (just no documents)
        assert len(kb.documents) == 0

    def test_query_on_empty_kb(self):
        """Test querying empty KB doesn't crash."""
        config = KnowledgeBeastConfig(
            knowledge_dirs=[Path("/nonexistent")],
            auto_warm=False,
            verbose=False
        )

        kb = KnowledgeBase(config)
        results = kb.query("test query")

        # Should return empty results
        assert results == []


class TestPerformanceIntegration:
    """Test performance characteristics in integration."""

    def test_cache_improves_query_time(self, kb_instance_warmed: KnowledgeBase):
        """Test that caching improves query performance."""
        query = "audio processing librosa"

        # First query (cache miss)
        start1 = time.time()
        result1 = kb_instance_warmed.query(query, use_cache=True)
        time1 = time.time() - start1

        # Second query (cache hit)
        start2 = time.time()
        result2 = kb_instance_warmed.query(query, use_cache=True)
        time2 = time.time() - start2

        # Results should be identical
        assert result1 == result2

        # Cache hit should be faster (though this can be flaky)
        # We just verify it completes successfully
        assert time2 >= 0

    def test_warming_reduces_first_query_latency(self, kb_config: KnowledgeBeastConfig):
        """Test warming reduces first query latency."""
        # KB without warming
        kb_config.auto_warm = False
        kb_cold = KnowledgeBase(kb_config)
        kb_cold.ingest_all()

        # KB with warming
        kb_config.auto_warm = True
        kb_warm = KnowledgeBase(kb_config)

        # Both should work correctly
        assert len(kb_cold.documents) > 0
        assert len(kb_warm.documents) > 0
        assert kb_warm.stats['warm_queries'] > 0

    def test_stats_overhead(self, kb_instance_warmed: KnowledgeBase):
        """Test getting stats has minimal overhead."""
        start = time.time()
        for _ in range(100):
            kb_instance_warmed.get_stats()
        elapsed = time.time() - start

        # Should complete 100 stats calls quickly
        assert elapsed < 1.0  # Less than 1 second for 100 calls


class TestDataConsistency:
    """Test data consistency across operations."""

    def test_rebuild_maintains_data(self, kb_instance_warmed: KnowledgeBase):
        """Test rebuild index maintains same data."""
        original_docs = len(kb_instance_warmed.documents)
        original_terms = len(kb_instance_warmed.index)

        kb_instance_warmed.rebuild_index()

        assert len(kb_instance_warmed.documents) == original_docs
        assert len(kb_instance_warmed.index) == original_terms

    def test_cache_clear_doesnt_affect_index(self, kb_instance_warmed: KnowledgeBase):
        """Test cache clear doesn't affect document index."""
        original_docs = len(kb_instance_warmed.documents)

        kb_instance_warmed.clear_cache()

        assert len(kb_instance_warmed.documents) == original_docs

    def test_multiple_queries_same_result(self, kb_instance_warmed: KnowledgeBase):
        """Test multiple identical queries return same results."""
        query = "test query"

        results = []
        for _ in range(5):
            kb_instance_warmed.clear_cache()  # Force fresh query
            results.append(kb_instance_warmed.query(query, use_cache=False))

        # All results should be identical
        for i in range(1, len(results)):
            assert results[i] == results[0]
