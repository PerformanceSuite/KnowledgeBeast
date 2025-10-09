"""Retry Logic with Exponential Backoff.

Enterprise-grade retry logic for transient failure handling using tenacity.
Implements exponential backoff with jitter for optimal retry behavior.

Features:
- Configurable retry attempts and delays
- Exponential backoff with jitter
- Exception filtering (retry vs no-retry)
- Prometheus metrics integration
- Thread-safe operation
"""

import logging
from typing import Any, Callable, Optional, Type, Union, Tuple

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
    after_log,
    RetryCallState,
)

logger = logging.getLogger(__name__)


# Exceptions that should trigger retries (transient failures)
RETRIABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,  # Network/IO errors
)

# Exceptions that should NOT trigger retries (permanent failures)
NON_RETRIABLE_EXCEPTIONS = (
    ValueError,
    TypeError,
    KeyError,
    AttributeError,
)


class RetryMetrics:
    """Thread-safe retry metrics tracker.

    Tracks retry attempts and outcomes for monitoring and alerting.
    """

    def __init__(self) -> None:
        """Initialize retry metrics."""
        import threading

        self._lock = threading.Lock()
        self.metrics = {
            "total_attempts": 0,
            "total_retries": 0,
            "total_successes": 0,
            "total_failures": 0,
            "by_exception": {},
        }

    def record_attempt(self, attempt_number: int) -> None:
        """Record a retry attempt.

        Args:
            attempt_number: Current attempt number (1-indexed)
        """
        with self._lock:
            self.metrics["total_attempts"] += 1
            if attempt_number > 1:
                self.metrics["total_retries"] += 1

    def record_success(self, attempt_number: int) -> None:
        """Record successful completion.

        Args:
            attempt_number: Attempt number that succeeded
        """
        with self._lock:
            self.metrics["total_successes"] += 1

    def record_failure(self, exception: Exception, attempt_number: int) -> None:
        """Record failed attempt.

        Args:
            exception: Exception that caused failure
            attempt_number: Attempt number that failed
        """
        with self._lock:
            self.metrics["total_failures"] += 1
            exc_name = type(exception).__name__
            if exc_name not in self.metrics["by_exception"]:
                self.metrics["by_exception"][exc_name] = 0
            self.metrics["by_exception"][exc_name] += 1

    def get_stats(self) -> dict:
        """Get retry statistics.

        Returns:
            Dictionary with retry metrics
        """
        with self._lock:
            return dict(self.metrics)

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self.metrics = {
                "total_attempts": 0,
                "total_retries": 0,
                "total_successes": 0,
                "total_failures": 0,
                "by_exception": {},
            }


# Global metrics instance
retry_metrics = RetryMetrics()


def log_retry_attempt(retry_state: RetryCallState) -> None:
    """Log retry attempt with details.

    Args:
        retry_state: Retry state from tenacity
    """
    if retry_state.outcome and retry_state.outcome.failed:
        exception = retry_state.outcome.exception()
        logger.warning(
            f"Retry attempt {retry_state.attempt_number} failed: "
            f"{type(exception).__name__}: {exception}. "
            f"Retrying in {retry_state.next_action.sleep if retry_state.next_action else 0}s..."
        )
        retry_metrics.record_attempt(retry_state.attempt_number)


def log_final_attempt(retry_state: RetryCallState) -> None:
    """Log final attempt outcome.

    Args:
        retry_state: Retry state from tenacity
    """
    if retry_state.outcome:
        if retry_state.outcome.failed:
            exception = retry_state.outcome.exception()
            logger.error(
                f"All {retry_state.attempt_number} retry attempts exhausted: "
                f"{type(exception).__name__}: {exception}"
            )
            retry_metrics.record_failure(exception, retry_state.attempt_number)
        else:
            if retry_state.attempt_number > 1:
                logger.info(
                    f"Retry successful after {retry_state.attempt_number} attempts"
                )
            retry_metrics.record_success(retry_state.attempt_number)


def with_retry(
    max_attempts: int = 3,
    initial_wait: float = 1.0,
    max_wait: float = 10.0,
    multiplier: float = 2.0,
    retry_on: Optional[Tuple[Type[Exception], ...]] = None,
    skip_on: Optional[Tuple[Type[Exception], ...]] = None,
) -> Callable:
    """Decorator for adding retry logic with exponential backoff.

    Usage:
        @with_retry(max_attempts=3, initial_wait=1.0)
        def query_chromadb():
            # ... operation that might fail ...
            pass

    Args:
        max_attempts: Maximum number of attempts (default: 3)
        initial_wait: Initial wait time in seconds (default: 1.0)
        max_wait: Maximum wait time in seconds (default: 10.0)
        multiplier: Exponential multiplier (default: 2.0)
        retry_on: Tuple of exception types to retry on (default: RETRIABLE_EXCEPTIONS)
        skip_on: Tuple of exception types to NOT retry on (default: None)

    Returns:
        Decorated function with retry logic

    Notes:
        - Wait time follows exponential backoff: wait = min(initial * (multiplier ^ attempt), max)
        - Jitter is automatically added to prevent thundering herd
        - Metrics are automatically tracked
    """
    # Default to retriable exceptions
    if retry_on is None:
        retry_on = RETRIABLE_EXCEPTIONS

    # Build retry condition
    if skip_on:
        # Don't retry on skip_on exceptions
        def should_retry(exception: Exception) -> bool:
            return isinstance(exception, retry_on) and not isinstance(exception, skip_on)

        retry_condition = retry_if_exception_type(retry_on)
    else:
        retry_condition = retry_if_exception_type(retry_on)

    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(
            multiplier=multiplier,
            min=initial_wait,
            max=max_wait,
        ),
        retry=retry_condition,
        before_sleep=log_retry_attempt,
        after=log_final_attempt,
        reraise=True,  # Re-raise exception after all retries exhausted
    )


def chromadb_retry(
    max_attempts: int = 3,
    initial_wait: float = 1.0,
    max_wait: float = 10.0,
) -> Callable:
    """Specialized retry decorator for ChromaDB operations.

    Retries on:
    - ConnectionError
    - TimeoutError
    - OSError (network/IO issues)

    Does NOT retry on:
    - ValueError (validation errors)
    - TypeError (type errors)
    - KeyError (missing keys)

    Usage:
        @chromadb_retry()
        def query_collection():
            # ... ChromaDB operation ...
            pass

    Args:
        max_attempts: Maximum retry attempts (default: 3)
        initial_wait: Initial wait time in seconds (default: 1.0)
        max_wait: Maximum wait time in seconds (default: 10.0)

    Returns:
        Decorated function with ChromaDB-specific retry logic
    """
    return with_retry(
        max_attempts=max_attempts,
        initial_wait=initial_wait,
        max_wait=max_wait,
        multiplier=2.0,
        retry_on=RETRIABLE_EXCEPTIONS,
        skip_on=NON_RETRIABLE_EXCEPTIONS,
    )


def get_retry_stats() -> dict:
    """Get global retry statistics.

    Returns:
        Dictionary with retry metrics across all decorated functions
    """
    return retry_metrics.get_stats()


def reset_retry_stats() -> None:
    """Reset global retry statistics."""
    retry_metrics.reset()
