"""Circuit Breaker Pattern Implementation.

Enterprise-grade circuit breaker for fault tolerance and graceful degradation.
Prevents cascading failures by stopping requests to failing services.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Service is failing, requests are rejected immediately
- HALF_OPEN: Testing if service has recovered

Configuration:
- failure_threshold: Number of failures before opening circuit (default: 5)
- failure_window: Time window for counting failures in seconds (default: 60)
- recovery_timeout: Seconds before trying to recover (default: 30)
- expected_exception: Exception type(s) that trigger circuit (default: Exception)
"""

import logging
import threading
import time
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, Optional, Type, Union

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Circuit is open, failing fast
    HALF_OPEN = "half_open" # Testing recovery


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """Thread-safe circuit breaker implementation.

    Implements the Circuit Breaker pattern to prevent cascading failures
    and provide graceful degradation when services are unavailable.

    Features:
    - Thread-safe state management
    - Configurable failure thresholds and recovery timeouts
    - Automatic state transitions
    - Metrics tracking (open/close events, failures, successes)
    - Half-open state for testing recovery

    Thread Safety:
        All state modifications are protected by threading.Lock()

    Attributes:
        name: Circuit breaker identifier
        failure_threshold: Failures before opening circuit
        failure_window: Time window for counting failures (seconds)
        recovery_timeout: Time before attempting recovery (seconds)
        expected_exception: Exception type(s) that trigger circuit
        state: Current circuit state
        failure_count: Number of recent failures
        last_failure_time: Timestamp of last failure
        last_state_change: Timestamp of last state change
        metrics: Circuit breaker metrics
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        failure_window: int = 60,
        recovery_timeout: int = 30,
        expected_exception: Type[BaseException] = Exception,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            name: Circuit breaker identifier for logging/metrics
            failure_threshold: Number of failures before opening circuit
            failure_window: Time window for counting failures (seconds)
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception: Exception type(s) that trigger the circuit
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.failure_window = failure_window
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        # State management
        self._state = CircuitState.CLOSED
        self._lock = threading.Lock()

        # Failure tracking
        self.failure_count = 0
        self.failure_times: list = []  # Timestamps of failures
        self.last_failure_time: Optional[float] = None
        self.last_state_change: float = time.time()

        # Metrics
        self.metrics = {
            "state_changes": 0,
            "total_failures": 0,
            "total_successes": 0,
            "circuit_opened": 0,
            "circuit_closed": 0,
            "circuit_half_opened": 0,
            "rejected_requests": 0,
        }

        logger.info(f"Circuit breaker '{name}' initialized: "
                   f"threshold={failure_threshold}, window={failure_window}s, "
                   f"recovery={recovery_timeout}s")

    @property
    def state(self) -> CircuitState:
        """Get current circuit state (thread-safe)."""
        with self._lock:
            return self._state

    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt to reset (move to half-open).

        Called when circuit is OPEN to determine if enough time has passed
        to attempt recovery.

        Returns:
            True if recovery timeout has elapsed
        """
        return time.time() - self.last_state_change >= self.recovery_timeout

    def _record_success(self) -> None:
        """Record successful call (thread-safe).

        In HALF_OPEN state, this closes the circuit.
        Resets failure count in all states.
        """
        with self._lock:
            self.metrics["total_successes"] += 1
            self.failure_count = 0
            self.failure_times.clear()

            if self._state == CircuitState.HALF_OPEN:
                self._transition_to_closed()

    def _record_failure(self) -> None:
        """Record failed call and update circuit state (thread-safe).

        Increments failure count and opens circuit if threshold exceeded
        within the failure window.
        """
        with self._lock:
            current_time = time.time()
            self.metrics["total_failures"] += 1
            self.last_failure_time = current_time

            # Add failure timestamp
            self.failure_times.append(current_time)

            # Remove failures outside window
            window_start = current_time - self.failure_window
            self.failure_times = [t for t in self.failure_times if t >= window_start]
            self.failure_count = len(self.failure_times)

            # Check if threshold exceeded
            if self.failure_count >= self.failure_threshold:
                if self._state == CircuitState.HALF_OPEN:
                    # Failed recovery attempt - reopen circuit
                    self._transition_to_open()
                elif self._state == CircuitState.CLOSED:
                    # Exceeded threshold - open circuit
                    self._transition_to_open()

    def _transition_to_open(self) -> None:
        """Transition to OPEN state (call within lock)."""
        if self._state != CircuitState.OPEN:
            logger.warning(f"Circuit breaker '{self.name}' OPENED "
                          f"(failures: {self.failure_count}/{self.failure_threshold})")
            self._state = CircuitState.OPEN
            self.last_state_change = time.time()
            self.metrics["state_changes"] += 1
            self.metrics["circuit_opened"] += 1

    def _transition_to_half_open(self) -> None:
        """Transition to HALF_OPEN state (call within lock)."""
        if self._state != CircuitState.HALF_OPEN:
            logger.info(f"Circuit breaker '{self.name}' entered HALF_OPEN state "
                       "(testing recovery)")
            self._state = CircuitState.HALF_OPEN
            self.last_state_change = time.time()
            self.metrics["state_changes"] += 1
            self.metrics["circuit_half_opened"] += 1

    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state (call within lock)."""
        if self._state != CircuitState.CLOSED:
            logger.info(f"Circuit breaker '{self.name}' CLOSED (recovery successful)")
            self._state = CircuitState.CLOSED
            self.last_state_change = time.time()
            self.failure_count = 0
            self.failure_times.clear()
            self.metrics["state_changes"] += 1
            self.metrics["circuit_closed"] += 1

    def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute function with circuit breaker protection.

        Args:
            func: Function to call
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
            Exception: Original exception from function
        """
        # Check circuit state
        with self._lock:
            current_state = self._state

            if current_state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                    current_state = CircuitState.HALF_OPEN
                else:
                    self.metrics["rejected_requests"] += 1
                    raise CircuitBreakerError(
                        f"Circuit breaker '{self.name}' is OPEN "
                        f"(will retry in {self.recovery_timeout}s)"
                    )

        # Execute function
        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except self.expected_exception as e:
            self._record_failure()
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics (thread-safe).

        Returns:
            Dictionary with current state and metrics
        """
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self.failure_count,
                "failure_threshold": self.failure_threshold,
                "last_failure_time": self.last_failure_time,
                "last_state_change": self.last_state_change,
                "metrics": dict(self.metrics),
            }

    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state."""
        with self._lock:
            logger.info(f"Circuit breaker '{self.name}' manually reset")
            self._state = CircuitState.CLOSED
            self.failure_count = 0
            self.failure_times.clear()
            self.last_state_change = time.time()

    def __repr__(self) -> str:
        """String representation of circuit breaker."""
        return (f"CircuitBreaker(name='{self.name}', state={self.state.value}, "
                f"failures={self.failure_count}/{self.failure_threshold})")


def circuit_breaker(
    name: str = "default",
    failure_threshold: int = 5,
    failure_window: int = 60,
    recovery_timeout: int = 30,
    expected_exception: Type[BaseException] = Exception,
) -> Callable:
    """Decorator for circuit breaker protection.

    Usage:
        @circuit_breaker(name="chromadb", failure_threshold=5)
        def query_database():
            # ... database operation ...
            pass

    Args:
        name: Circuit breaker identifier
        failure_threshold: Failures before opening
        failure_window: Time window for failures (seconds)
        recovery_timeout: Recovery attempt delay (seconds)
        expected_exception: Exception type(s) to catch

    Returns:
        Decorator function
    """
    cb = CircuitBreaker(
        name=name,
        failure_threshold=failure_threshold,
        failure_window=failure_window,
        recovery_timeout=recovery_timeout,
        expected_exception=expected_exception,
    )

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return cb.call(func, *args, **kwargs)

        # Attach circuit breaker instance to wrapper for testing/monitoring
        wrapper.circuit_breaker = cb
        return wrapper

    return decorator
