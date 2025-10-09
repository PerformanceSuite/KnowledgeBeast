"""Tests for Retry Logic with Exponential Backoff.

Validates:
- Retry on ConnectionError (max 3 attempts)
- Retry on TimeoutError
- NO retry on ValidationError
- Exponential backoff timing validated
- Max attempts respected
- Retry counters in metrics
"""

import pytest
import time
from unittest.mock import Mock, patch

from knowledgebeast.core.retry_logic import (
    with_retry,
    chromadb_retry,
    get_retry_stats,
    reset_retry_stats,
    retry_metrics,
    RETRIABLE_EXCEPTIONS,
    NON_RETRIABLE_EXCEPTIONS,
)


class TestRetryBasics:
    """Test basic retry functionality."""

    def setup_method(self):
        """Reset metrics before each test."""
        reset_retry_stats()

    def test_successful_call_no_retry(self):
        """Test successful call doesn't trigger retry."""

        @with_retry(max_attempts=3)
        def success_func():
            return "success"

        result = success_func()
        assert result == "success"

        stats = get_retry_stats()
        assert stats["total_attempts"] == 1
        assert stats["total_retries"] == 0
        assert stats["total_successes"] == 1

    def test_single_failure_then_success(self):
        """Test retry after single failure."""
        call_count = [0]

        @with_retry(max_attempts=3, initial_wait=0.1)
        def intermittent_func():
            call_count[0] += 1
            if call_count[0] == 1:
                raise ConnectionError("Temporary failure")
            return "success"

        result = intermittent_func()
        assert result == "success"
        assert call_count[0] == 2  # Failed once, succeeded on retry

        stats = get_retry_stats()
        assert stats["total_retries"] == 1


class TestRetriableExceptions:
    """Test which exceptions trigger retries."""

    def setup_method(self):
        """Reset metrics before each test."""
        reset_retry_stats()

    def test_connection_error_triggers_retry(self):
        """Test ConnectionError triggers retry."""
        call_count = [0]

        @with_retry(max_attempts=3, initial_wait=0.1)
        def connection_fail():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ConnectionError("Network issue")
            return "recovered"

        result = connection_fail()
        assert result == "recovered"
        assert call_count[0] == 2

    def test_timeout_error_triggers_retry(self):
        """Test TimeoutError triggers retry."""
        call_count = [0]

        @with_retry(max_attempts=3, initial_wait=0.1)
        def timeout_fail():
            call_count[0] += 1
            if call_count[0] < 2:
                raise TimeoutError("Request timeout")
            return "recovered"

        result = timeout_fail()
        assert result == "recovered"
        assert call_count[0] == 2

    def test_oserror_triggers_retry(self):
        """Test OSError triggers retry."""
        call_count = [0]

        @with_retry(max_attempts=3, initial_wait=0.1)
        def os_fail():
            call_count[0] += 1
            if call_count[0] < 2:
                raise OSError("IO error")
            return "recovered"

        result = os_fail()
        assert result == "recovered"
        assert call_count[0] == 2

    def test_value_error_no_retry(self):
        """Test ValueError does NOT trigger retry."""
        call_count = [0]

        @with_retry(max_attempts=3, initial_wait=0.1)
        def value_error_func():
            call_count[0] += 1
            raise ValueError("Validation error")

        with pytest.raises(ValueError, match="Validation error"):
            value_error_func()

        # Should not retry on ValueError
        assert call_count[0] == 1
        stats = get_retry_stats()
        assert stats["total_retries"] == 0

    def test_type_error_no_retry(self):
        """Test TypeError does NOT trigger retry."""
        call_count = [0]

        @with_retry(max_attempts=3, initial_wait=0.1, retry_on=RETRIABLE_EXCEPTIONS)
        def type_error_func():
            call_count[0] += 1
            raise TypeError("Type error")

        with pytest.raises(TypeError):
            type_error_func()

        assert call_count[0] == 1


class TestMaxAttempts:
    """Test max attempts enforcement."""

    def setup_method(self):
        """Reset metrics before each test."""
        reset_retry_stats()

    def test_max_attempts_respected(self):
        """Test retry stops after max attempts."""
        call_count = [0]

        @with_retry(max_attempts=3, initial_wait=0.1)
        def always_fail():
            call_count[0] += 1
            raise ConnectionError("Always fails")

        with pytest.raises(ConnectionError):
            always_fail()

        assert call_count[0] == 3  # Initial + 2 retries
        stats = get_retry_stats()
        assert stats["total_attempts"] == 3
        assert stats["total_retries"] == 2

    def test_custom_max_attempts(self):
        """Test custom max attempts value."""
        call_count = [0]

        @with_retry(max_attempts=5, initial_wait=0.1)
        def always_fail():
            call_count[0] += 1
            raise ConnectionError("Fail")

        with pytest.raises(ConnectionError):
            always_fail()

        assert call_count[0] == 5


class TestExponentialBackoff:
    """Test exponential backoff timing."""

    def setup_method(self):
        """Reset metrics before each test."""
        reset_retry_stats()

    def test_exponential_backoff_timing(self):
        """Test wait times follow exponential backoff."""
        call_times = []

        @with_retry(max_attempts=3, initial_wait=0.5, multiplier=2.0, max_wait=10.0)
        def timed_fail():
            call_times.append(time.time())
            raise ConnectionError("Fail")

        with pytest.raises(ConnectionError):
            timed_fail()

        # Should have 3 calls
        assert len(call_times) == 3

        # Check wait times (allowing for some variance)
        if len(call_times) >= 2:
            wait1 = call_times[1] - call_times[0]
            # First wait should be approximately initial_wait (0.5s)
            assert 0.4 < wait1 < 0.7, f"First wait was {wait1}s, expected ~0.5s"

        if len(call_times) >= 3:
            wait2 = call_times[2] - call_times[1]
            # Second wait should be approximately initial_wait * multiplier (1.0s)
            assert 0.8 < wait2 < 1.5, f"Second wait was {wait2}s, expected ~1.0s"

    def test_max_wait_enforced(self):
        """Test max wait time is enforced."""
        call_times = []

        @with_retry(max_attempts=4, initial_wait=1.0, multiplier=2.0, max_wait=2.0)
        def capped_wait():
            call_times.append(time.time())
            raise ConnectionError("Fail")

        with pytest.raises(ConnectionError):
            capped_wait()

        # Check that wait times don't exceed max_wait
        if len(call_times) >= 3:
            wait2 = call_times[2] - call_times[1]
            # Should be capped at max_wait (2.0s)
            assert wait2 < 3.0, f"Wait time {wait2}s exceeded max_wait"


class TestChromaDBRetry:
    """Test ChromaDB-specific retry decorator."""

    def setup_method(self):
        """Reset metrics before each test."""
        reset_retry_stats()

    def test_chromadb_retry_on_connection_error(self):
        """Test chromadb_retry retries on connection errors."""
        call_count = [0]

        @chromadb_retry(max_attempts=3, initial_wait=0.1)
        def chromadb_operation():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ConnectionError("ChromaDB connection failed")
            return "success"

        result = chromadb_operation()
        assert result == "success"
        assert call_count[0] == 2

    def test_chromadb_retry_no_retry_on_value_error(self):
        """Test chromadb_retry doesn't retry on ValueError."""
        call_count = [0]

        @chromadb_retry(max_attempts=3)
        def validation_error():
            call_count[0] += 1
            raise ValueError("Invalid parameters")

        with pytest.raises(ValueError):
            validation_error()

        assert call_count[0] == 1

    def test_chromadb_retry_on_timeout(self):
        """Test chromadb_retry retries on timeout."""
        call_count = [0]

        @chromadb_retry(max_attempts=3, initial_wait=0.1)
        def timeout_operation():
            call_count[0] += 1
            if call_count[0] < 2:
                raise TimeoutError("Request timeout")
            return "success"

        result = timeout_operation()
        assert result == "success"
        assert call_count[0] == 2


class TestRetryMetrics:
    """Test retry metrics tracking."""

    def setup_method(self):
        """Reset metrics before each test."""
        reset_retry_stats()

    def test_metrics_track_attempts(self):
        """Test metrics track total attempts."""

        @with_retry(max_attempts=3, initial_wait=0.1)
        def multi_fail():
            raise ConnectionError("Fail")

        with pytest.raises(ConnectionError):
            multi_fail()

        stats = get_retry_stats()
        assert stats["total_attempts"] == 3
        assert stats["total_retries"] == 2  # attempts - 1

    def test_metrics_track_successes(self):
        """Test metrics track successful completions."""

        @with_retry(max_attempts=3, initial_wait=0.1)
        def success():
            return "ok"

        for _ in range(5):
            success()

        stats = get_retry_stats()
        assert stats["total_successes"] == 5

    def test_metrics_track_failures(self):
        """Test metrics track failures."""

        @with_retry(max_attempts=2, initial_wait=0.1)
        def fail():
            raise ConnectionError("Fail")

        for _ in range(3):
            with pytest.raises(ConnectionError):
                fail()

        stats = get_retry_stats()
        assert stats["total_failures"] == 3

    def test_metrics_track_by_exception_type(self):
        """Test metrics track failures by exception type."""

        @with_retry(max_attempts=2, initial_wait=0.1)
        def connection_fail():
            raise ConnectionError("Network")

        @with_retry(max_attempts=2, initial_wait=0.1)
        def timeout_fail():
            raise TimeoutError("Timeout")

        with pytest.raises(ConnectionError):
            connection_fail()

        with pytest.raises(TimeoutError):
            timeout_fail()

        stats = get_retry_stats()
        assert "ConnectionError" in stats["by_exception"]
        assert "TimeoutError" in stats["by_exception"]
        assert stats["by_exception"]["ConnectionError"] == 1
        assert stats["by_exception"]["TimeoutError"] == 1

    def test_metrics_reset(self):
        """Test metrics can be reset."""

        @with_retry(max_attempts=2, initial_wait=0.1)
        def test_func():
            return "ok"

        test_func()

        stats_before = get_retry_stats()
        assert stats_before["total_successes"] > 0

        reset_retry_stats()

        stats_after = get_retry_stats()
        assert stats_after["total_successes"] == 0
        assert stats_after["total_attempts"] == 0


class TestRetryCustomConfiguration:
    """Test custom retry configuration."""

    def setup_method(self):
        """Reset metrics before each test."""
        reset_retry_stats()

    def test_custom_initial_wait(self):
        """Test custom initial wait time."""
        call_times = []

        @with_retry(max_attempts=2, initial_wait=1.0)
        def custom_wait():
            call_times.append(time.time())
            raise ConnectionError("Fail")

        with pytest.raises(ConnectionError):
            custom_wait()

        if len(call_times) >= 2:
            wait = call_times[1] - call_times[0]
            assert 0.8 < wait < 1.5  # ~1.0s initial wait

    def test_custom_retry_on_exceptions(self):
        """Test custom exception types for retry."""

        # Only retry on RuntimeError
        @with_retry(max_attempts=3, initial_wait=0.1, retry_on=(RuntimeError,))
        def runtime_fail():
            raise RuntimeError("Retry this")

        # Should retry
        with pytest.raises(RuntimeError):
            runtime_fail()

        stats = get_retry_stats()
        assert stats["total_retries"] > 0
