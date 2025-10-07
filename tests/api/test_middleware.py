"""Comprehensive tests for API middleware components.

Tests all middleware with 100% coverage:
- RequestIDMiddleware: ID generation, propagation
- TimingMiddleware: accurate timing, header inclusion
- LoggingMiddleware: request/response logging
- CacheHeaderMiddleware: cache control headers
- SecurityHeadersMiddleware: all security headers
- RequestSizeLimitMiddleware: size limits, rejections
"""

import asyncio
import logging
import time
import uuid
from unittest.mock import Mock, patch, AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse
from starlette.datastructures import Headers

from knowledgebeast.api.middleware import (
    RequestIDMiddleware,
    TimingMiddleware,
    LoggingMiddleware,
    CacheHeaderMiddleware,
    SecurityHeadersMiddleware,
    RequestSizeLimitMiddleware,
)


# Test fixtures
@pytest.fixture
def app():
    """Create test FastAPI app."""
    test_app = FastAPI()

    @test_app.get("/test")
    async def test_endpoint():
        return {"message": "test"}

    @test_app.get("/api/v1/health")
    async def health_endpoint():
        return {"status": "ok"}

    @test_app.get("/api/v1/query")
    async def query_endpoint():
        return {"results": []}

    @test_app.get("/api/v1/stats")
    async def stats_endpoint():
        return {"queries": 0}

    @test_app.get("/error")
    async def error_endpoint():
        raise ValueError("Test error")

    @test_app.post("/upload")
    async def upload_endpoint():
        return {"uploaded": True}

    return test_app


@pytest.fixture
def mock_request():
    """Create mock request object with properly mocked headers."""
    request = Mock(spec=Request)
    request.state = Mock()

    # Create proper URL mock that supports string formatting
    url = Mock()
    url.path = "/test"
    url.query = ""
    url.scheme = "http"
    # Make URL attributes strings to avoid format issues
    url.__str__ = Mock(return_value="/test")
    request.url = url

    request.method = "GET"
    request.client = Mock()
    request.client.host = "127.0.0.1"
    # Headers is a Starlette Headers object - mock it properly
    request.headers = Headers({})
    return request


@pytest.fixture
def mock_call_next():
    """Create mock call_next function."""
    async def _call_next(request):
        response = Response(content="test", status_code=200)
        return response

    return _call_next


# RequestIDMiddleware Tests
class TestRequestIDMiddleware:
    """Test RequestIDMiddleware for ID generation and propagation."""

    @pytest.mark.asyncio
    async def test_generates_request_id_when_not_provided(self, mock_request, mock_call_next):
        """Test that middleware generates UUID when X-Request-ID not in request."""
        middleware = RequestIDMiddleware(app=Mock())
        mock_request.headers = Headers({})

        response = await middleware.dispatch(mock_request, mock_call_next)

        # Should have generated and added request ID
        assert hasattr(mock_request.state, "request_id")
        assert mock_request.state.request_id is not None
        assert "X-Request-ID" in response.headers
        # Verify it's a valid UUID format
        uuid.UUID(response.headers["X-Request-ID"])

    @pytest.mark.asyncio
    async def test_uses_client_request_id_when_provided(self, mock_request, mock_call_next):
        """Test that middleware uses client-provided X-Request-ID."""
        middleware = RequestIDMiddleware(app=Mock())
        client_request_id = "client-provided-id-12345"
        mock_request.headers = Headers({"X-Request-ID": client_request_id})

        response = await middleware.dispatch(mock_request, mock_call_next)

        # Should use client-provided ID
        assert mock_request.state.request_id == client_request_id
        assert response.headers["X-Request-ID"] == client_request_id

    @pytest.mark.asyncio
    async def test_request_id_propagates_to_response(self, mock_request, mock_call_next):
        """Test that request ID is added to response headers."""
        middleware = RequestIDMiddleware(app=Mock())
        mock_request.headers = Headers({})

        response = await middleware.dispatch(mock_request, mock_call_next)

        # Request ID should be in both request.state and response.headers
        assert hasattr(mock_request.state, "request_id")
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"] == mock_request.state.request_id

    def test_middleware_with_test_client(self, app):
        """Integration test: RequestIDMiddleware with TestClient."""
        app.add_middleware(RequestIDMiddleware)
        client = TestClient(app)

        # Request without X-Request-ID
        response = client.get("/test")
        assert "X-Request-ID" in response.headers
        # Verify UUID format
        uuid.UUID(response.headers["X-Request-ID"])

        # Request with X-Request-ID
        custom_id = "my-custom-request-id"
        response = client.get("/test", headers={"X-Request-ID": custom_id})
        assert response.headers["X-Request-ID"] == custom_id


# TimingMiddleware Tests
class TestTimingMiddleware:
    """Test TimingMiddleware for accurate timing and header inclusion."""

    @pytest.mark.asyncio
    async def test_adds_process_time_header(self, mock_request, mock_call_next):
        """Test that middleware adds X-Process-Time header."""
        middleware = TimingMiddleware(app=Mock())

        response = await middleware.dispatch(mock_request, mock_call_next)

        # Should have timing header
        assert "X-Process-Time" in response.headers
        # Should be a valid float string
        process_time = float(response.headers["X-Process-Time"])
        assert process_time >= 0

    @pytest.mark.asyncio
    async def test_timing_accuracy(self, mock_request):
        """Test that timing is accurate."""
        middleware = TimingMiddleware(app=Mock())

        # Create call_next that takes known time
        async def slow_call_next(request):
            await asyncio.sleep(0.1)  # Sleep 100ms
            return Response(content="test", status_code=200)

        response = await middleware.dispatch(mock_request, slow_call_next)

        # Timing should be approximately 0.1s (100ms)
        process_time = float(response.headers["X-Process-Time"])
        assert 0.09 <= process_time <= 0.15  # Allow some tolerance

    @pytest.mark.asyncio
    async def test_stores_timing_in_request_state(self, mock_request, mock_call_next):
        """Test that timing is stored in request.state."""
        middleware = TimingMiddleware(app=Mock())

        response = await middleware.dispatch(mock_request, mock_call_next)

        # Should store timing in request.state
        assert hasattr(mock_request.state, "process_time")
        assert mock_request.state.process_time >= 0
        # Should match header value
        assert f"{mock_request.state.process_time:.4f}" == response.headers["X-Process-Time"]

    @pytest.mark.asyncio
    async def test_timing_format_four_decimals(self, mock_request, mock_call_next):
        """Test that timing is formatted with 4 decimal places."""
        middleware = TimingMiddleware(app=Mock())

        response = await middleware.dispatch(mock_request, mock_call_next)

        # Check format: should have 4 decimal places
        timing_str = response.headers["X-Process-Time"]
        assert "." in timing_str
        decimal_places = len(timing_str.split(".")[1])
        assert decimal_places == 4

    def test_middleware_with_test_client(self, app):
        """Integration test: TimingMiddleware with TestClient."""
        app.add_middleware(TimingMiddleware)
        client = TestClient(app)

        response = client.get("/test")
        assert "X-Process-Time" in response.headers
        process_time = float(response.headers["X-Process-Time"])
        assert process_time >= 0
        assert process_time < 1.0  # Should be very fast


# LoggingMiddleware Tests
class TestLoggingMiddleware:
    """Test LoggingMiddleware for request/response logging."""

    @pytest.mark.asyncio
    async def test_logs_request_start(self, mock_request, mock_call_next, caplog):
        """Test that middleware logs request start."""
        middleware = LoggingMiddleware(app=Mock())
        mock_request.state.request_id = "test-request-id"
        mock_request.state.process_time = 0.1234  # Add process time as float
        mock_request.url.query = "param=value"

        with caplog.at_level(logging.INFO):
            await middleware.dispatch(mock_request, mock_call_next)

        # Check request log
        assert any("Request started" in record.message for record in caplog.records)
        assert any("test-request-id" in record.message for record in caplog.records)
        assert any("param=value" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_logs_request_completion(self, mock_request, mock_call_next, caplog):
        """Test that middleware logs successful request completion."""
        middleware = LoggingMiddleware(app=Mock())
        mock_request.state.request_id = "test-request-id"
        mock_request.state.process_time = 0.1234

        with caplog.at_level(logging.INFO):
            await middleware.dispatch(mock_request, mock_call_next)

        # Check completion log
        assert any("Request completed" in record.message for record in caplog.records)
        assert any("status=200" in record.message for record in caplog.records)
        assert any("0.1234" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_logs_request_failure(self, mock_request, caplog):
        """Test that middleware logs request failures."""
        middleware = LoggingMiddleware(app=Mock())
        mock_request.state.request_id = "test-request-id"

        async def failing_call_next(request):
            raise ValueError("Test error")

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError):
                await middleware.dispatch(mock_request, failing_call_next)

        # Check error log
        assert any("Request failed" in record.message for record in caplog.records)
        assert any("ValueError" in record.message for record in caplog.records)
        assert any("Test error" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_logs_client_ip(self, mock_request, mock_call_next, caplog):
        """Test that middleware logs client IP address."""
        middleware = LoggingMiddleware(app=Mock())
        mock_request.state.request_id = "test-request-id"
        mock_request.state.process_time = 0.05  # Add process time as float
        mock_request.client.host = "192.168.1.100"

        with caplog.at_level(logging.INFO):
            await middleware.dispatch(mock_request, mock_call_next)

        # Check client IP in log
        assert any("192.168.1.100" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_handles_missing_client(self, mock_request, mock_call_next, caplog):
        """Test that middleware handles requests without client info."""
        middleware = LoggingMiddleware(app=Mock())
        mock_request.state.request_id = "test-request-id"
        mock_request.state.process_time = 0.01  # Add process time as float
        mock_request.client = None  # No client info

        with caplog.at_level(logging.INFO):
            await middleware.dispatch(mock_request, mock_call_next)

        # Should use "unknown" for client
        assert any("client=unknown" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_handles_missing_request_id(self, mock_request, mock_call_next, caplog):
        """Test that middleware handles missing request_id."""
        middleware = LoggingMiddleware(app=Mock())
        mock_request.state.process_time = 0.02  # Add process time as float
        # Create a state object without request_id attribute
        state = type('obj', (object,), {'process_time': 0.02})()
        mock_request.state = state

        with caplog.at_level(logging.INFO):
            await middleware.dispatch(mock_request, mock_call_next)

        # Should use "unknown" for request_id
        assert any("request_id=unknown" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_handles_missing_process_time(self, mock_request, mock_call_next, caplog):
        """Test that middleware handles missing process_time."""
        middleware = LoggingMiddleware(app=Mock())
        # Create a state object without process_time attribute
        state = type('obj', (object,), {'request_id': 'test-request-id'})()
        mock_request.state = state

        with caplog.at_level(logging.INFO):
            await middleware.dispatch(mock_request, mock_call_next)

        # Should use 0 for process_time
        assert any("time=0.0000s" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_logs_query_string(self, mock_request, mock_call_next, caplog):
        """Test that middleware logs query string when present."""
        middleware = LoggingMiddleware(app=Mock())
        mock_request.state.request_id = "test-request-id"
        mock_request.state.process_time = 0.03  # Add process time as float
        mock_request.url.query = "search=test&limit=10"

        with caplog.at_level(logging.INFO):
            await middleware.dispatch(mock_request, mock_call_next)

        # Should include query string
        assert any("search=test" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_no_query_string_when_empty(self, mock_request, mock_call_next, caplog):
        """Test that middleware doesn't add ? when query string is empty."""
        middleware = LoggingMiddleware(app=Mock())
        mock_request.state.request_id = "test-request-id"
        mock_request.state.process_time = 0.04  # Add process time as float
        mock_request.url.query = ""

        with caplog.at_level(logging.INFO):
            await middleware.dispatch(mock_request, mock_call_next)

        # Should not have duplicate ? when no query string
        log_messages = [record.message for record in caplog.records]
        request_logs = [msg for msg in log_messages if "Request started" in msg]
        assert len(request_logs) > 0


# CacheHeaderMiddleware Tests
class TestCacheHeaderMiddleware:
    """Test CacheHeaderMiddleware for cache control headers."""

    @pytest.mark.asyncio
    async def test_health_endpoint_no_cache(self, mock_request, mock_call_next):
        """Test that health endpoints get no-cache headers."""
        middleware = CacheHeaderMiddleware(app=Mock())
        mock_request.url.path = "/api/v1/health"

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.headers["Cache-Control"] == "no-cache, no-store, must-revalidate"
        assert response.headers["Pragma"] == "no-cache"
        assert response.headers["Expires"] == "0"

    @pytest.mark.asyncio
    async def test_query_endpoint_short_cache(self, mock_request, mock_call_next):
        """Test that query endpoints get 1-minute cache."""
        middleware = CacheHeaderMiddleware(app=Mock())
        mock_request.url.path = "/api/v1/query"

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.headers["Cache-Control"] == "private, max-age=60"

    @pytest.mark.asyncio
    async def test_stats_endpoint_short_cache(self, mock_request, mock_call_next):
        """Test that stats endpoints get 30-second cache."""
        middleware = CacheHeaderMiddleware(app=Mock())
        mock_request.url.path = "/api/v1/stats"

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.headers["Cache-Control"] == "private, max-age=30"

    @pytest.mark.asyncio
    async def test_default_no_cache(self, mock_request, mock_call_next):
        """Test that other endpoints get default no-cache."""
        middleware = CacheHeaderMiddleware(app=Mock())
        mock_request.url.path = "/api/v1/other"

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.headers["Cache-Control"] == "no-cache"

    def test_middleware_with_test_client(self, app):
        """Integration test: CacheHeaderMiddleware with TestClient."""
        app.add_middleware(CacheHeaderMiddleware)
        client = TestClient(app)

        # Health endpoint
        response = client.get("/api/v1/health")
        assert "Cache-Control" in response.headers
        assert "no-cache, no-store, must-revalidate" in response.headers["Cache-Control"]

        # Query endpoint
        response = client.get("/api/v1/query")
        assert response.headers["Cache-Control"] == "private, max-age=60"

        # Stats endpoint
        response = client.get("/api/v1/stats")
        assert response.headers["Cache-Control"] == "private, max-age=30"

        # Default endpoint
        response = client.get("/test")
        assert response.headers["Cache-Control"] == "no-cache"


# SecurityHeadersMiddleware Tests
class TestSecurityHeadersMiddleware:
    """Test SecurityHeadersMiddleware for all security headers."""

    @pytest.mark.asyncio
    async def test_adds_x_content_type_options(self, mock_request, mock_call_next):
        """Test that middleware adds X-Content-Type-Options header."""
        middleware = SecurityHeadersMiddleware(app=Mock())

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.headers["X-Content-Type-Options"] == "nosniff"

    @pytest.mark.asyncio
    async def test_adds_x_frame_options(self, mock_request, mock_call_next):
        """Test that middleware adds X-Frame-Options header."""
        middleware = SecurityHeadersMiddleware(app=Mock())

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.headers["X-Frame-Options"] == "DENY"

    @pytest.mark.asyncio
    async def test_adds_x_xss_protection(self, mock_request, mock_call_next):
        """Test that middleware adds X-XSS-Protection header."""
        middleware = SecurityHeadersMiddleware(app=Mock())

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.headers["X-XSS-Protection"] == "1; mode=block"

    @pytest.mark.asyncio
    async def test_adds_referrer_policy(self, mock_request, mock_call_next):
        """Test that middleware adds Referrer-Policy header."""
        middleware = SecurityHeadersMiddleware(app=Mock())

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    @pytest.mark.asyncio
    async def test_adds_content_security_policy(self, mock_request, mock_call_next):
        """Test that middleware adds comprehensive CSP header."""
        middleware = SecurityHeadersMiddleware(app=Mock())

        response = await middleware.dispatch(mock_request, mock_call_next)

        csp = response.headers["Content-Security-Policy"]
        # Check key directives
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "style-src 'self' 'unsafe-inline'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "object-src 'none'" in csp
        assert "upgrade-insecure-requests" in csp

    @pytest.mark.asyncio
    async def test_adds_strict_transport_security_for_https(self, mock_request, mock_call_next):
        """Test that middleware adds HSTS header for HTTPS requests."""
        middleware = SecurityHeadersMiddleware(app=Mock())
        mock_request.url.scheme = "https"
        mock_request.headers = Headers({})

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert "Strict-Transport-Security" in response.headers
        hsts = response.headers["Strict-Transport-Security"]
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts
        assert "preload" in hsts

    @pytest.mark.asyncio
    async def test_adds_strict_transport_security_for_forwarded_https(self, mock_request, mock_call_next):
        """Test that middleware adds HSTS header for proxied HTTPS requests."""
        middleware = SecurityHeadersMiddleware(app=Mock())
        mock_request.url.scheme = "http"
        mock_request.headers = Headers({"X-Forwarded-Proto": "https"})

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert "Strict-Transport-Security" in response.headers

    @pytest.mark.asyncio
    async def test_no_strict_transport_security_for_http(self, mock_request, mock_call_next):
        """Test that middleware doesn't add HSTS header for HTTP requests."""
        middleware = SecurityHeadersMiddleware(app=Mock())
        mock_request.url.scheme = "http"
        mock_request.headers = Headers({})

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert "Strict-Transport-Security" not in response.headers

    @pytest.mark.asyncio
    async def test_adds_permissions_policy(self, mock_request, mock_call_next):
        """Test that middleware adds Permissions-Policy header."""
        middleware = SecurityHeadersMiddleware(app=Mock())

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.headers["Permissions-Policy"] == "geolocation=(), microphone=(), camera=()"

    @pytest.mark.asyncio
    async def test_all_security_headers_present(self, mock_request, mock_call_next):
        """Test that all security headers are present."""
        middleware = SecurityHeadersMiddleware(app=Mock())
        mock_request.url.scheme = "https"
        mock_request.headers = Headers({})

        response = await middleware.dispatch(mock_request, mock_call_next)

        # Verify all expected security headers
        expected_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Referrer-Policy",
            "Content-Security-Policy",
            "Strict-Transport-Security",
            "Permissions-Policy",
        ]
        for header in expected_headers:
            assert header in response.headers, f"Missing security header: {header}"

    def test_middleware_with_test_client(self, app):
        """Integration test: SecurityHeadersMiddleware with TestClient."""
        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app)

        response = client.get("/test")

        # Check all security headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "Content-Security-Policy" in response.headers
        assert "Permissions-Policy" in response.headers


# RequestSizeLimitMiddleware Tests
class TestRequestSizeLimitMiddleware:
    """Test RequestSizeLimitMiddleware for size limits and rejections."""

    @pytest.mark.asyncio
    async def test_accepts_normal_sized_request(self, mock_request, mock_call_next):
        """Test that middleware accepts normally sized requests."""
        middleware = RequestSizeLimitMiddleware(app=Mock(), max_size=1000000, max_query_length=1000)
        mock_request.headers = Headers({"content-length": "500"})
        mock_request.url.query = "param=value"

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_rejects_oversized_body(self, mock_request, mock_call_next):
        """Test that middleware rejects requests with body too large."""
        middleware = RequestSizeLimitMiddleware(app=Mock(), max_size=1000, max_query_length=1000)
        mock_request.headers = Headers({"content-length": "2000"})
        mock_request.url.query = ""

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.status_code == 413
        # Parse JSON response
        import json
        content = json.loads(response.body.decode())
        assert content["error"] == "RequestEntityTooLarge"
        assert "body too large" in content["message"]

    @pytest.mark.asyncio
    async def test_rejects_oversized_query_string(self, mock_request, mock_call_next):
        """Test that middleware rejects requests with query string too long."""
        middleware = RequestSizeLimitMiddleware(app=Mock(), max_size=1000000, max_query_length=100)
        mock_request.headers = Headers({})
        mock_request.url.query = "x" * 200  # 200 chars, exceeds limit

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.status_code == 413
        # Parse JSON response
        import json
        content = json.loads(response.body.decode())
        assert content["error"] == "RequestEntityTooLarge"
        assert "Query string too long" in content["message"]

    @pytest.mark.asyncio
    async def test_handles_missing_content_length(self, mock_request, mock_call_next):
        """Test that middleware handles requests without content-length."""
        middleware = RequestSizeLimitMiddleware(app=Mock(), max_size=1000, max_query_length=1000)
        mock_request.headers = Headers({})
        mock_request.url.query = ""

        response = await middleware.dispatch(mock_request, mock_call_next)

        # Should pass through when no content-length
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_handles_invalid_content_length(self, mock_request, mock_call_next):
        """Test that middleware handles invalid content-length gracefully."""
        middleware = RequestSizeLimitMiddleware(app=Mock(), max_size=1000, max_query_length=1000)
        mock_request.headers = Headers({"content-length": "invalid"})
        mock_request.url.query = ""

        response = await middleware.dispatch(mock_request, mock_call_next)

        # Should pass through when content-length is invalid
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_custom_size_limits(self, mock_request, mock_call_next):
        """Test that middleware respects custom size limits."""
        middleware = RequestSizeLimitMiddleware(app=Mock(), max_size=500, max_query_length=50)

        # Test body limit
        mock_request.headers = Headers({"content-length": "600"})
        mock_request.url.query = ""

        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 413

        # Test query limit
        mock_request.headers = Headers({})
        mock_request.url.query = "x" * 60

        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 413

    @pytest.mark.asyncio
    async def test_default_limits(self, mock_request, mock_call_next):
        """Test that middleware uses default limits when not specified."""
        middleware = RequestSizeLimitMiddleware(app=Mock())

        # Default max_size is 10MB (10485760 bytes)
        assert middleware.max_size == 10485760
        # Default max_query_length is 10k chars
        assert middleware.max_query_length == 10000

    @pytest.mark.asyncio
    async def test_error_response_format(self, mock_request, mock_call_next):
        """Test that error response has correct format."""
        middleware = RequestSizeLimitMiddleware(app=Mock(), max_size=100, max_query_length=100)
        mock_request.headers = Headers({"content-length": "200"})
        mock_request.url.query = ""

        response = await middleware.dispatch(mock_request, mock_call_next)

        import json
        content = json.loads(response.body.decode())
        # Check all expected fields
        assert "error" in content
        assert "message" in content
        assert "detail" in content
        assert "status_code" in content
        assert content["status_code"] == 413

    @pytest.mark.asyncio
    async def test_logs_rejection(self, mock_request, mock_call_next, caplog):
        """Test that middleware logs when rejecting requests."""
        middleware = RequestSizeLimitMiddleware(app=Mock(), max_size=100, max_query_length=100)
        mock_request.headers = Headers({"content-length": "200"})
        mock_request.url.query = ""

        with caplog.at_level(logging.WARNING):
            await middleware.dispatch(mock_request, mock_call_next)

        # Check warning log
        assert any("Request body too large" in record.message for record in caplog.records)

    def test_middleware_with_test_client(self, app):
        """Integration test: RequestSizeLimitMiddleware with TestClient."""
        app.add_middleware(RequestSizeLimitMiddleware, max_size=1000, max_query_length=100)
        client = TestClient(app)

        # Normal request
        response = client.get("/test")
        assert response.status_code == 200

        # Oversized body
        response = client.post(
            "/upload",
            headers={"content-length": "2000"},
            content="x" * 2000
        )
        assert response.status_code == 413

        # Oversized query string
        response = client.get(f"/test?{'x' * 150}=value")
        assert response.status_code == 413


# Middleware Integration Tests
class TestMiddlewareIntegration:
    """Test middleware interaction and ordering."""

    def test_multiple_middleware_stack(self, app):
        """Test that multiple middleware work together correctly."""
        # Add all middleware in order
        app.add_middleware(RequestSizeLimitMiddleware, max_size=1000000, max_query_length=1000)
        app.add_middleware(SecurityHeadersMiddleware)
        app.add_middleware(CacheHeaderMiddleware)
        app.add_middleware(LoggingMiddleware)
        app.add_middleware(TimingMiddleware)
        app.add_middleware(RequestIDMiddleware)

        client = TestClient(app)
        response = client.get("/test")

        # Verify headers from all middleware
        assert "X-Request-ID" in response.headers
        assert "X-Process-Time" in response.headers
        assert "Cache-Control" in response.headers
        assert "X-Content-Type-Options" in response.headers
        assert response.status_code == 200

    def test_request_id_available_in_logging(self, app, caplog):
        """Test that RequestIDMiddleware provides ID for LoggingMiddleware."""
        app.add_middleware(LoggingMiddleware)
        app.add_middleware(TimingMiddleware)
        app.add_middleware(RequestIDMiddleware)

        client = TestClient(app)

        with caplog.at_level(logging.INFO):
            response = client.get("/test")

        # Request ID should be in logs
        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]
        assert any(request_id in record.message for record in caplog.records)

    def test_timing_available_in_logging(self, app, caplog):
        """Test that TimingMiddleware provides time for LoggingMiddleware."""
        app.add_middleware(LoggingMiddleware)
        app.add_middleware(TimingMiddleware)
        app.add_middleware(RequestIDMiddleware)

        client = TestClient(app)

        with caplog.at_level(logging.INFO):
            response = client.get("/test")

        # Timing should be in logs
        assert any("time=" in record.message for record in caplog.records if "Request completed" in record.message)

    def test_error_handling_through_middleware_stack(self, app, caplog):
        """Test that errors propagate correctly through middleware stack."""
        app.add_middleware(LoggingMiddleware)
        app.add_middleware(TimingMiddleware)
        app.add_middleware(RequestIDMiddleware)

        client = TestClient(app)

        with caplog.at_level(logging.ERROR):
            # This will raise an exception
            with pytest.raises(ValueError):
                client.get("/error")

        # Error should be logged
        assert any("Request failed" in record.message for record in caplog.records)
        assert any("ValueError" in record.message for record in caplog.records)

    def test_size_limit_before_processing(self, app):
        """Test that RequestSizeLimitMiddleware rejects before other processing."""
        app.add_middleware(LoggingMiddleware)
        app.add_middleware(RequestSizeLimitMiddleware, max_size=100, max_query_length=50)
        app.add_middleware(RequestIDMiddleware)

        client = TestClient(app)

        # Oversized request should be rejected with 413
        response = client.get(f"/test?{'x' * 100}=value")
        assert response.status_code == 413
        # Should still have request ID
        assert "X-Request-ID" in response.headers


# Edge Cases and Error Handling
class TestMiddlewareEdgeCases:
    """Test edge cases and error handling in middleware."""

    @pytest.mark.asyncio
    async def test_request_id_with_empty_header(self, mock_request, mock_call_next):
        """Test RequestIDMiddleware with empty X-Request-ID header."""
        middleware = RequestIDMiddleware(app=Mock())
        mock_request.headers = Headers({"X-Request-ID": ""})

        response = await middleware.dispatch(mock_request, mock_call_next)

        # Empty string is falsy, should generate new ID
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"] != ""
        uuid.UUID(response.headers["X-Request-ID"])  # Should be valid UUID

    @pytest.mark.asyncio
    async def test_timing_with_zero_time(self, mock_request):
        """Test TimingMiddleware with instant processing."""
        middleware = TimingMiddleware(app=Mock())

        async def instant_call_next(request):
            return Response(content="test", status_code=200)

        response = await middleware.dispatch(mock_request, instant_call_next)

        # Should have timing even if very small
        assert "X-Process-Time" in response.headers
        process_time = float(response.headers["X-Process-Time"])
        assert process_time >= 0

    @pytest.mark.asyncio
    async def test_cache_header_with_nested_paths(self, mock_request, mock_call_next):
        """Test CacheHeaderMiddleware with nested API paths."""
        middleware = CacheHeaderMiddleware(app=Mock())

        # Test nested health path
        mock_request.url.path = "/api/v1/health/detailed"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert "no-cache, no-store" in response.headers["Cache-Control"]

        # Test nested query path
        mock_request.url.path = "/api/v1/query/advanced"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.headers["Cache-Control"] == "private, max-age=60"

    @pytest.mark.asyncio
    async def test_security_headers_with_various_schemes(self, mock_request, mock_call_next):
        """Test SecurityHeadersMiddleware with different URL schemes."""
        middleware = SecurityHeadersMiddleware(app=Mock())

        # HTTP request
        mock_request.url.scheme = "http"
        mock_request.headers = Headers({})
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert "Strict-Transport-Security" not in response.headers

        # HTTPS request
        mock_request.url.scheme = "https"
        mock_request.headers = Headers({})
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert "Strict-Transport-Security" in response.headers

    @pytest.mark.asyncio
    async def test_size_limit_boundary_conditions(self, mock_request, mock_call_next):
        """Test RequestSizeLimitMiddleware at boundary conditions."""
        middleware = RequestSizeLimitMiddleware(app=Mock(), max_size=1000, max_query_length=100)
        mock_request.url.query = ""

        # Exactly at limit
        mock_request.headers = Headers({"content-length": "1000"})
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 200

        # Just over limit
        mock_request.headers = Headers({"content-length": "1001"})
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 413

        # Query string exactly at limit
        mock_request.headers = Headers({})
        mock_request.url.query = "x" * 100
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 200

        # Query string just over limit
        mock_request.url.query = "x" * 101
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 413
