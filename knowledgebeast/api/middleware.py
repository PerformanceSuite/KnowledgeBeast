"""Custom middleware for KnowledgeBeast API.

Provides:
- Request ID tracking for distributed tracing
- Timing middleware for performance monitoring
- Request/response logging
"""

import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add unique request ID to each request.

    Adds X-Request-ID header to both request and response for tracing.
    If client provides X-Request-ID, it will be used; otherwise a new UUID is generated.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add request ID.

        Args:
            request: Incoming request
            call_next: Next middleware/endpoint to call

        Returns:
            Response with X-Request-ID header
        """
        # Get or generate request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Store in request state for access by endpoints
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Middleware to measure and log request processing time.

    Adds X-Process-Time header to response with processing time in seconds.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and measure timing.

        Args:
            request: Incoming request
            call_next: Next middleware/endpoint to call

        Returns:
            Response with X-Process-Time header
        """
        # Record start time
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate processing time
        process_time = time.time() - start_time

        # Add timing header (in seconds, 4 decimal places)
        response.headers["X-Process-Time"] = f"{process_time:.4f}"

        # Store in request state for logging middleware
        request.state.process_time = process_time

        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all requests and responses.

    Logs:
    - Request method, path, query params
    - Response status code
    - Processing time
    - Request ID
    - Client IP
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log details.

        Args:
            request: Incoming request
            call_next: Next middleware/endpoint to call

        Returns:
            Response from next handler
        """
        # Get client info
        client_ip = request.client.host if request.client else "unknown"

        # Get request ID (set by RequestIDMiddleware)
        request_id = getattr(request.state, "request_id", "unknown")

        # Build query string
        query_string = f"?{request.url.query}" if request.url.query else ""

        # Log request
        logger.info(
            f"Request started: {request.method} {request.url.path}{query_string} "
            f"[client={client_ip}] [request_id={request_id}]"
        )

        try:
            # Process request
            response = await call_next(request)

            # Get processing time (set by TimingMiddleware)
            process_time = getattr(request.state, "process_time", 0)

            # Log response
            logger.info(
                f"Request completed: {request.method} {request.url.path} "
                f"[status={response.status_code}] [time={process_time:.4f}s] "
                f"[request_id={request_id}]"
            )

            return response

        except Exception as e:
            # Log error
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"[error={type(e).__name__}: {str(e)}] [request_id={request_id}]",
                exc_info=True
            )
            raise


class CacheHeaderMiddleware(BaseHTTPMiddleware):
    """Middleware to add cache control headers.

    Adds appropriate cache headers based on endpoint and response.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add cache headers.

        Args:
            request: Incoming request
            call_next: Next middleware/endpoint to call

        Returns:
            Response with cache headers
        """
        response = await call_next(request)

        # Add cache headers based on path
        path = request.url.path

        if path.startswith("/api/v1/health"):
            # Health endpoints: no cache
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        elif path.startswith("/api/v1/query"):
            # Query endpoints: short cache (1 minute)
            response.headers["Cache-Control"] = "private, max-age=60"

        elif path.startswith("/api/v1/stats"):
            # Stats endpoints: short cache (30 seconds)
            response.headers["Cache-Control"] = "private, max-age=30"

        else:
            # Default: no cache for API endpoints
            response.headers["Cache-Control"] = "no-cache"

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers.

    Adds standard security headers to all responses.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add security headers.

        Args:
            request: Incoming request
            call_next: Next middleware/endpoint to call

        Returns:
            Response with security headers
        """
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Note: HTTPS/TLS headers should be handled by reverse proxy (nginx, etc)

        return response
