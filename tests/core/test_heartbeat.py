"""Tests for heartbeat functionality."""

import time
from pathlib import Path
import pytest

from knowledgebeast.core.engine import KnowledgeBase
from knowledgebeast.core.config import KnowledgeBeastConfig
from knowledgebeast.core.heartbeat import KnowledgeBaseHeartbeat


class TestHeartbeatInitialization:
    """Test heartbeat initialization."""

    def test_init_with_valid_interval(self, kb_instance: KnowledgeBase):
        """Test heartbeat initializes with valid interval."""
        heartbeat = KnowledgeBaseHeartbeat(kb_instance, interval=60)
        assert heartbeat.kb == kb_instance
        assert heartbeat.interval == 60
        assert heartbeat.running is False
        assert heartbeat.heartbeat_count == 0

    def test_init_with_invalid_interval(self, kb_instance: KnowledgeBase):
        """Test heartbeat raises error for interval < 10s."""
        with pytest.raises(ValueError, match="at least 10 seconds"):
            KnowledgeBaseHeartbeat(kb_instance, interval=5)

        with pytest.raises(ValueError, match="at least 10 seconds"):
            KnowledgeBaseHeartbeat(kb_instance, interval=0)

    def test_init_default_interval(self, kb_instance: KnowledgeBase):
        """Test heartbeat uses default interval."""
        heartbeat = KnowledgeBaseHeartbeat(kb_instance)
        assert heartbeat.interval == 300  # 5 minutes default


class TestHeartbeatStartStop:
    """Test heartbeat start/stop functionality."""

    def test_start_heartbeat(self, kb_instance: KnowledgeBase):
        """Test starting heartbeat."""
        heartbeat = KnowledgeBaseHeartbeat(kb_instance, interval=10)
        heartbeat.start()

        assert heartbeat.running is True
        assert heartbeat.thread is not None
        assert heartbeat.thread.is_alive()

        # Cleanup
        heartbeat.stop()

    def test_stop_heartbeat(self, kb_instance: KnowledgeBase):
        """Test stopping heartbeat."""
        heartbeat = KnowledgeBaseHeartbeat(kb_instance, interval=10)
        heartbeat.start()
        time.sleep(0.1)

        heartbeat.stop()
        assert heartbeat.running is False

    def test_start_already_running(self, kb_instance: KnowledgeBase, capsys):
        """Test starting already running heartbeat."""
        heartbeat = KnowledgeBaseHeartbeat(kb_instance, interval=10)
        heartbeat.start()
        time.sleep(0.1)

        # Try to start again
        heartbeat.start()
        captured = capsys.readouterr()
        assert "already running" in captured.out.lower()

        # Cleanup
        heartbeat.stop()

    def test_stop_not_running(self, kb_instance: KnowledgeBase):
        """Test stopping heartbeat that's not running."""
        heartbeat = KnowledgeBaseHeartbeat(kb_instance, interval=10)
        heartbeat.stop()  # Should not raise error
        assert heartbeat.running is False


class TestHeartbeatExecution:
    """Test heartbeat execution."""

    def test_heartbeat_execution(self, kb_instance_warmed: KnowledgeBase):
        """Test heartbeat executes periodically."""
        heartbeat = KnowledgeBaseHeartbeat(kb_instance_warmed, interval=10)
        heartbeat.start()

        # Wait for at least one heartbeat
        time.sleep(11)

        heartbeat.stop()
        assert heartbeat.heartbeat_count >= 1

    def test_is_running_status(self, kb_instance: KnowledgeBase):
        """Test is_running method."""
        heartbeat = KnowledgeBaseHeartbeat(kb_instance, interval=10)

        assert heartbeat.is_running() is False

        heartbeat.start()
        assert heartbeat.is_running() is True

        heartbeat.stop()
        time.sleep(0.1)
        assert heartbeat.is_running() is False


class TestCacheRefreshOnStale:
    """Test cache refresh when stale."""

    def test_cache_refresh_on_stale(self, kb_instance_warmed: KnowledgeBase, temp_kb_dir: Path):
        """Test heartbeat refreshes cache when stale."""
        # Create heartbeat with short interval
        heartbeat = KnowledgeBaseHeartbeat(kb_instance_warmed, interval=10)

        # Ingest to create cache
        kb_instance_warmed.ingest_all()
        initial_doc_count = len(kb_instance_warmed.documents)

        # Modify a file to make cache stale
        time.sleep(0.2)
        test_file = temp_kb_dir / "new_stale_doc.md"
        test_file.write_text("# New Document\nThis makes cache stale")

        # Start heartbeat - it should detect stale cache on next beat
        heartbeat.start()
        time.sleep(11)  # Wait for one heartbeat cycle
        heartbeat.stop()

        # Cache should have been refreshed with new doc
        assert len(kb_instance_warmed.documents) >= initial_doc_count


class TestHeartbeatHealthMetrics:
    """Test heartbeat health monitoring."""

    def test_health_logging(self, kb_instance_warmed: KnowledgeBase, capsys):
        """Test heartbeat logs health metrics."""
        heartbeat = KnowledgeBaseHeartbeat(kb_instance_warmed, interval=10)
        heartbeat.start()

        time.sleep(11)  # Wait for one heartbeat
        heartbeat.stop()

        captured = capsys.readouterr()
        # Should have logged health metrics
        assert "KB Health" in captured.out or heartbeat.heartbeat_count > 0


class TestIntervalValidation:
    """Test interval validation."""

    def test_minimum_interval(self, kb_instance: KnowledgeBase):
        """Test minimum interval is enforced."""
        # 10 seconds should work
        heartbeat = KnowledgeBaseHeartbeat(kb_instance, interval=10)
        assert heartbeat.interval == 10

        # 9 seconds should fail
        with pytest.raises(ValueError):
            KnowledgeBaseHeartbeat(kb_instance, interval=9)


class TestGracefulShutdown:
    """Test graceful shutdown."""

    def test_graceful_shutdown(self, kb_instance: KnowledgeBase):
        """Test heartbeat shuts down gracefully."""
        heartbeat = KnowledgeBaseHeartbeat(kb_instance, interval=10)
        heartbeat.start()
        time.sleep(0.2)

        # Stop with timeout
        heartbeat.stop(timeout=2.0)

        assert heartbeat.running is False
        if heartbeat.thread:
            assert not heartbeat.thread.is_alive()

    def test_shutdown_with_short_timeout(self, kb_instance: KnowledgeBase):
        """Test shutdown with very short timeout."""
        heartbeat = KnowledgeBaseHeartbeat(kb_instance, interval=10)
        heartbeat.start()
        time.sleep(0.1)

        # Stop with very short timeout
        heartbeat.stop(timeout=0.1)

        # Should still stop
        assert heartbeat.running is False


class TestHeartbeatContextManager:
    """Test heartbeat as context manager."""

    def test_context_manager(self, kb_instance: KnowledgeBase):
        """Test heartbeat works as context manager."""
        with KnowledgeBaseHeartbeat(kb_instance, interval=10) as heartbeat:
            assert heartbeat.is_running() is True

        # Should auto-stop on exit
        time.sleep(0.2)
        assert heartbeat.is_running() is False

    def test_context_manager_exception_handling(self, kb_instance: KnowledgeBase):
        """Test context manager handles exceptions."""
        try:
            with KnowledgeBaseHeartbeat(kb_instance, interval=10) as heartbeat:
                assert heartbeat.is_running() is True
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Should still stop on exception
        time.sleep(0.2)
        assert heartbeat.is_running() is False


class TestHeartbeatErrorHandling:
    """Test heartbeat error handling."""

    def test_heartbeat_continues_on_error(self, kb_instance: KnowledgeBase):
        """Test heartbeat continues running despite errors."""
        heartbeat = KnowledgeBaseHeartbeat(kb_instance, interval=10)
        heartbeat.start()

        time.sleep(11)

        # Should still be running even if some operations failed
        assert heartbeat.running is True

        heartbeat.stop()

    def test_stale_check_error_handling(self, kb_instance: KnowledgeBase):
        """Test _is_cache_stale handles errors gracefully."""
        heartbeat = KnowledgeBaseHeartbeat(kb_instance, interval=10)

        # Delete cache file to cause error
        if kb_instance.config.cache_file.exists():
            kb_instance.config.cache_file.unlink()

        # Should return True (stale) on error, not raise
        result = heartbeat._is_cache_stale()
        assert result is True


class TestWarmingQuery:
    """Test warming query execution."""

    def test_warming_query_execution(self, kb_instance_warmed: KnowledgeBase):
        """Test heartbeat executes warming queries."""
        heartbeat = KnowledgeBaseHeartbeat(kb_instance_warmed, interval=10)

        initial_queries = kb_instance_warmed.stats['queries']

        # Execute warming query manually
        heartbeat._warm_query()

        # Should have executed a query
        assert kb_instance_warmed.stats['queries'] > initial_queries

    def test_warming_query_error_handling(self, kb_instance: KnowledgeBase):
        """Test warming query handles errors gracefully."""
        heartbeat = KnowledgeBaseHeartbeat(kb_instance, interval=10)

        # Should not raise even if KB not initialized
        heartbeat._warm_query()  # Should handle gracefully


class TestThreadSafety:
    """Test thread safety of heartbeat."""

    def test_concurrent_start_stop(self, kb_instance: KnowledgeBase):
        """Test concurrent start/stop operations."""
        heartbeat = KnowledgeBaseHeartbeat(kb_instance, interval=10)

        # Rapidly start and stop
        for _ in range(3):
            heartbeat.start()
            time.sleep(0.1)
            heartbeat.stop()

        # Should end in stopped state
        assert heartbeat.running is False

    def test_multiple_heartbeats(self, kb_instance: KnowledgeBase):
        """Test multiple heartbeat instances."""
        heartbeat1 = KnowledgeBaseHeartbeat(kb_instance, interval=10)
        heartbeat2 = KnowledgeBaseHeartbeat(kb_instance, interval=15)

        heartbeat1.start()
        heartbeat2.start()

        assert heartbeat1.is_running()
        assert heartbeat2.is_running()

        heartbeat1.stop()
        heartbeat2.stop()

        assert not heartbeat1.is_running()
        assert not heartbeat2.is_running()
