"""Tests for structured logging integration.

This module tests structured logging with JSON format, correlation IDs,
and trace context integration.
"""

import pytest
import json
import logging
import time
import io
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
import structlog

from knowledgebeast.utils.observability import (
    setup_structured_logging,
    add_trace_context,
    set_request_id,
    get_request_id,
    get_tracer,
)


@pytest.fixture
def log_output():
    """Capture log output for testing."""
    stream = io.StringIO()

    # Configure structlog to write directly to our stream
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(file=stream),
        cache_logger_on_first_use=False,
    )

    yield stream

    # Reset structlog configuration
    structlog.reset_defaults()


@pytest.fixture
def span_exporter():
    """Create an in-memory span exporter for testing."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    yield exporter
    exporter.clear()


class TestStructuredLogging:
    """Test suite for structured logging functionality."""

    def test_json_log_format(self, log_output):
        """Test that logs are output in valid JSON format."""
        setup_structured_logging(json_logs=True)
        logger = structlog.get_logger()

        logger.info("test_event", key1="value1", key2=42)

        log_output.seek(0)
        log_line = log_output.readline()

        # Should be valid JSON
        try:
            log_data = json.loads(log_line)
            assert log_data["event"] == "test_event"
            assert log_data["key1"] == "value1"
            assert log_data["key2"] == 42
        except json.JSONDecodeError:
            pytest.fail("Log output is not valid JSON")

    def test_log_level_filtering(self, log_output):
        """Test that log level filtering works correctly."""
        setup_structured_logging(log_level="WARNING", json_logs=True)
        logger = structlog.get_logger()

        # Debug should not appear
        logger.debug("debug_event", should_appear=False)

        # Warning should appear
        logger.warning("warning_event", should_appear=True)

        log_output.seek(0)
        logs = log_output.readlines()

        # Should only have warning log
        assert len(logs) == 1

        warning_log = json.loads(logs[0])
        assert warning_log["event"] == "warning_event"
        assert warning_log["should_appear"] is True

    def test_correlation_id_propagation(self, log_output):
        """Test that correlation IDs are included in logs."""
        setup_structured_logging(json_logs=True, include_trace_context=True)
        logger = structlog.get_logger()

        # Set request ID
        request_id = "req-test-123"
        set_request_id(request_id)

        # Log with request ID
        logger.info("test_with_correlation", data="test")

        log_output.seek(0)
        log_data = json.loads(log_output.readline())

        # Request ID should be in log
        assert "request_id" in log_data
        assert log_data["request_id"] == request_id

        # Cleanup
        set_request_id(None)

    def test_trace_context_in_logs(self, log_output, span_exporter):
        """Test that trace context (trace_id, span_id) is included in logs."""
        setup_structured_logging(json_logs=True, include_trace_context=True)
        logger = structlog.get_logger()
        tracer = get_tracer()

        with tracer.start_as_current_span("test_span") as span:
            span_context = span.get_span_context()
            trace_id = format(span_context.trace_id, "032x")
            span_id = format(span_context.span_id, "016x")

            # Log within span context
            logger.info("test_with_trace", message="inside span")

            log_output.seek(0)
            log_data = json.loads(log_output.readline())

            # Trace context should be in log
            assert "trace_id" in log_data
            assert "span_id" in log_data
            assert log_data["trace_id"] == trace_id
            assert log_data["span_id"] == span_id

    def test_error_logs_capture_exceptions(self, log_output):
        """Test that error logs capture exception information."""
        setup_structured_logging(json_logs=True)
        logger = structlog.get_logger()

        try:
            raise ValueError("Test exception")
        except ValueError as e:
            logger.error("error_event", error=str(e), exc_info=True)

        log_output.seek(0)
        log_data = json.loads(log_output.readline())

        assert log_data["event"] == "error_event"
        assert "error" in log_data
        assert "Test exception" in log_data["error"]

    def test_log_timestamp_format(self, log_output):
        """Test that logs include ISO format timestamps."""
        setup_structured_logging(json_logs=True)
        logger = structlog.get_logger()

        logger.info("timestamp_test")

        log_output.seek(0)
        log_data = json.loads(log_output.readline())

        # Should have timestamp field
        assert "timestamp" in log_data

        # Timestamp should be ISO format (contains 'T' and ':')
        timestamp = log_data["timestamp"]
        assert "T" in timestamp
        assert ":" in timestamp

    def test_structured_fields_in_logs(self, log_output):
        """Test that structured fields are properly included."""
        setup_structured_logging(json_logs=True)
        logger = structlog.get_logger()

        # Log with various structured fields
        logger.info(
            "structured_event",
            user_id=12345,
            operation="test_operation",
            duration_ms=156.7,
            success=True,
            items=["item1", "item2", "item3"]
        )

        log_output.seek(0)
        log_data = json.loads(log_output.readline())

        assert log_data["event"] == "structured_event"
        assert log_data["user_id"] == 12345
        assert log_data["operation"] == "test_operation"
        assert abs(log_data["duration_ms"] - 156.7) < 0.1
        assert log_data["success"] is True
        assert log_data["items"] == ["item1", "item2", "item3"]

    def test_logging_performance_overhead(self, log_output):
        """Test that logging overhead is minimal (< 1ms per log)."""
        setup_structured_logging(json_logs=True)
        logger = structlog.get_logger()

        # Measure logging overhead
        num_logs = 100
        start_time = time.time()

        for i in range(num_logs):
            logger.info("performance_test", iteration=i, data="test_data")

        end_time = time.time()
        total_time = end_time - start_time
        avg_time_ms = (total_time / num_logs) * 1000

        # Average time per log should be < 1ms
        assert avg_time_ms < 1.0, f"Logging overhead too high: {avg_time_ms:.3f}ms per log"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
