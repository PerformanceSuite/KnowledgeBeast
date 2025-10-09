"""Tests for Circuit Breaker pattern implementation.

Validates:
- Circuit opens after threshold failures
- Half-open state transitions correctly
- Circuit closes after successful requests in half-open
- Circuit reset after recovery timeout
- ChromaDB failure scenarios trigger circuit
- Metrics emitted on state changes
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch

from knowledgebeast.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitState,
)


class TestCircuitBreakerBasics:
    """Test basic circuit breaker functionality."""

    def test_circuit_breaker_initialization(self):
        """Test circuit breaker initializes in CLOSED state."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=5,
            failure_window=60,
            recovery_timeout=30
        )
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.name == "test"
        assert cb.failure_threshold == 5

    def test_successful_call(self):
        """Test successful function call doesn't affect circuit."""
        cb = CircuitBreaker(name="test", failure_threshold=5)

        def success_func():
            return "success"

        result = cb.call(success_func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_single_failure(self):
        """Test single failure is recorded but doesn't open circuit."""
        cb = CircuitBreaker(name="test", failure_threshold=5)

        def fail_func():
            raise Exception("Test failure")

        with pytest.raises(Exception, match="Test failure"):
            cb.call(fail_func)

        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 1


class TestCircuitBreakerOpening:
    """Test circuit breaker opening behavior."""

    def test_circuit_opens_after_threshold_failures(self):
        """Test circuit opens after reaching failure threshold."""
        cb = CircuitBreaker(name="test", failure_threshold=5, failure_window=60)

        def fail_func():
            raise Exception("Test failure")

        # Trigger 5 failures
        for i in range(5):
            with pytest.raises(Exception):
                cb.call(fail_func)

        # Circuit should now be open
        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 5
        assert cb.metrics["circuit_opened"] == 1

    def test_circuit_rejects_calls_when_open(self):
        """Test circuit rejects calls immediately when open."""
        cb = CircuitBreaker(name="test", failure_threshold=3)

        def fail_func():
            raise Exception("Test failure")

        # Open the circuit
        for i in range(3):
            with pytest.raises(Exception):
                cb.call(fail_func)

        assert cb.state == CircuitState.OPEN

        # Next call should be rejected immediately
        def success_func():
            return "success"

        with pytest.raises(CircuitBreakerError, match="Circuit breaker.*is OPEN"):
            cb.call(success_func)

        assert cb.metrics["rejected_requests"] == 1

    def test_failures_outside_window_dont_count(self):
        """Test failures outside the time window are not counted."""
        cb = CircuitBreaker(name="test", failure_threshold=3, failure_window=1)

        def fail_func():
            raise Exception("Test failure")

        # First failure
        with pytest.raises(Exception):
            cb.call(fail_func)

        # Wait for window to expire
        time.sleep(1.1)

        # Second failure (first one should have expired)
        with pytest.raises(Exception):
            cb.call(fail_func)

        # Circuit should still be closed (only 1 failure in window)
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 1


class TestCircuitBreakerRecovery:
    """Test circuit breaker recovery behavior."""

    def test_circuit_enters_half_open_after_timeout(self):
        """Test circuit enters half-open state after recovery timeout."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=3,
            recovery_timeout=1  # Short timeout for testing
        )

        def fail_func():
            raise Exception("Test failure")

        # Open the circuit
        for i in range(3):
            with pytest.raises(Exception):
                cb.call(fail_func)

        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(1.1)

        # Next call should transition to half-open
        def success_func():
            return "success"

        result = cb.call(success_func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED  # Closes on success in half-open

    def test_circuit_closes_on_success_in_half_open(self):
        """Test circuit closes after successful call in half-open state."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=1
        )

        def fail_func():
            raise Exception("Test failure")

        # Open circuit
        for i in range(2):
            with pytest.raises(Exception):
                cb.call(fail_func)

        time.sleep(1.1)

        # Successful call in half-open state should close circuit
        def success_func():
            return "success"

        result = cb.call(success_func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.metrics["circuit_closed"] == 1

    def test_circuit_reopens_on_failure_in_half_open(self):
        """Test circuit reopens if call fails in half-open state."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=1
        )

        def fail_func():
            raise Exception("Test failure")

        # Open circuit
        for i in range(2):
            with pytest.raises(Exception):
                cb.call(fail_func)

        assert cb.state == CircuitState.OPEN
        time.sleep(1.1)

        # Failure in half-open state should reopen circuit
        with pytest.raises(Exception):
            cb.call(fail_func)

        assert cb.state == CircuitState.OPEN
        # Circuit opened twice (initial + after failed recovery)
        assert cb.metrics["circuit_opened"] == 2


class TestCircuitBreakerMetrics:
    """Test circuit breaker metrics tracking."""

    def test_metrics_track_state_changes(self):
        """Test metrics correctly track state changes."""
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=1)

        def fail_func():
            raise Exception("fail")

        def success_func():
            return "success"

        # Initial state
        assert cb.metrics["state_changes"] == 0

        # Open circuit
        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(fail_func)

        assert cb.metrics["state_changes"] == 1  # CLOSED -> OPEN
        assert cb.metrics["circuit_opened"] == 1

        # Wait and recover
        time.sleep(1.1)
        cb.call(success_func)

        assert cb.metrics["state_changes"] == 3  # OPEN -> HALF_OPEN -> CLOSED
        assert cb.metrics["circuit_closed"] == 1

    def test_metrics_track_failures_and_successes(self):
        """Test metrics track total failures and successes."""
        cb = CircuitBreaker(name="test", failure_threshold=5)

        def fail_func():
            raise Exception("fail")

        def success_func():
            return "success"

        # Track successes
        for _ in range(3):
            cb.call(success_func)

        assert cb.metrics["total_successes"] == 3
        assert cb.metrics["total_failures"] == 0

        # Track failures
        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(fail_func)

        assert cb.metrics["total_failures"] == 2

    def test_metrics_track_rejected_requests(self):
        """Test metrics track rejected requests when circuit is open."""
        cb = CircuitBreaker(name="test", failure_threshold=2)

        def fail_func():
            raise Exception("fail")

        def success_func():
            return "success"

        # Open circuit
        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(fail_func)

        # Try multiple calls while open
        for _ in range(5):
            with pytest.raises(CircuitBreakerError):
                cb.call(success_func)

        assert cb.metrics["rejected_requests"] == 5


class TestCircuitBreakerThreadSafety:
    """Test circuit breaker thread safety."""

    def test_concurrent_calls_thread_safe(self):
        """Test circuit breaker handles concurrent calls safely."""
        cb = CircuitBreaker(name="test", failure_threshold=10)
        results = []
        lock = threading.Lock()

        def success_func():
            return "success"

        def worker():
            try:
                result = cb.call(success_func)
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    results.append(str(e))

        # Run 20 concurrent workers
        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should succeed
        assert len(results) == 20
        assert all(r == "success" for r in results)
        assert cb.metrics["total_successes"] == 20

    def test_concurrent_failures_counted_correctly(self):
        """Test concurrent failures are counted correctly."""
        cb = CircuitBreaker(name="test", failure_threshold=100)
        failure_count = [0]
        lock = threading.Lock()

        def fail_func():
            raise Exception("fail")

        def worker():
            try:
                cb.call(fail_func)
            except Exception:
                with lock:
                    failure_count[0] += 1

        # Run 50 concurrent failing calls
        threads = [threading.Thread(target=worker) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert failure_count[0] == 50
        assert cb.metrics["total_failures"] == 50
        assert cb.failure_count == 50


class TestCircuitBreakerReset:
    """Test manual circuit breaker reset."""

    def test_manual_reset_closes_circuit(self):
        """Test manual reset closes the circuit."""
        cb = CircuitBreaker(name="test", failure_threshold=2)

        def fail_func():
            raise Exception("fail")

        # Open circuit
        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(fail_func)

        assert cb.state == CircuitState.OPEN

        # Manual reset
        cb.reset()

        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_reset_clears_failure_history(self):
        """Test reset clears failure history."""
        cb = CircuitBreaker(name="test", failure_threshold=5)

        def fail_func():
            raise Exception("fail")

        # Record some failures
        for _ in range(3):
            with pytest.raises(Exception):
                cb.call(fail_func)

        assert cb.failure_count == 3

        # Reset
        cb.reset()

        assert cb.failure_count == 0
        assert len(cb.failure_times) == 0


class TestCircuitBreakerStats:
    """Test circuit breaker statistics reporting."""

    def test_get_stats_returns_complete_info(self):
        """Test get_stats returns all relevant information."""
        cb = CircuitBreaker(
            name="test_cb",
            failure_threshold=5,
            failure_window=60,
            recovery_timeout=30
        )

        stats = cb.get_stats()

        assert stats["name"] == "test_cb"
        assert stats["state"] == "closed"
        assert stats["failure_count"] == 0
        assert stats["failure_threshold"] == 5
        assert "metrics" in stats
        assert "last_state_change" in stats

    def test_stats_reflect_current_state(self):
        """Test stats accurately reflect current circuit state."""
        cb = CircuitBreaker(name="test", failure_threshold=2)

        def fail_func():
            raise Exception("fail")

        # Open circuit
        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(fail_func)

        stats = cb.get_stats()
        assert stats["state"] == "open"
        assert stats["failure_count"] == 2
        assert stats["metrics"]["circuit_opened"] == 1
