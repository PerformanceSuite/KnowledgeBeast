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
    """Middleware to add comprehensive security headers.

    Adds standard security headers to all responses including:
    - X-Content-Type-Options: Prevent MIME sniffing
    - X-Frame-Options: Prevent clickjacking
    - X-XSS-Protection: Enable browser XSS protection
    - Content-Security-Policy: Restrict resource loading
    - Strict-Transport-Security: Force HTTPS (when enabled)
    - Referrer-Policy: Control referrer information
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add security headers.

        Args:
            request: Incoming request
            call_next: Next middleware/endpoint to call

        Returns:
            Response with comprehensive security headers
        """
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Enable browser XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content Security Policy - restrict resource loading
        # For API: only allow same-origin and explicitly deny unsafe operations
        csp_directives = [
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self' 'unsafe-inline'",  # Allow inline styles for web UI
            "img-src 'self' data: https:",
            "font-src 'self' data:",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "object-src 'none'",
            "upgrade-insecure-requests"
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        # Strict Transport Security - force HTTPS (when not in development)
        # Check if request is secure or if we're behind a proxy
        is_secure = request.url.scheme == "https" or request.headers.get("X-Forwarded-Proto") == "https"
        if is_secure:
            # max-age: 1 year, includeSubDomains, preload
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        # Permissions Policy - restrict browser features
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce request size limits.

    Prevents DoS attacks by limiting:
    - Total request body size
    - Query string length
    """

    def __init__(self, app: ASGIApp, max_size: int = 10485760, max_query_length: int = 10000):
        """Initialize request size limit middleware.

        Args:
            app: ASGI application
            max_size: Maximum request body size in bytes (default: 10MB)
            max_query_length: Maximum query string length (default: 10k chars)
        """
        super().__init__(app)
        self.max_size = max_size
        self.max_query_length = max_query_length

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and enforce size limits.

        Args:
            request: Incoming request
            call_next: Next middleware/endpoint to call

        Returns:
            Response from next handler or 413 error

        Raises:
            HTTPException: If request exceeds size limits
        """
        # Check query string length
        if request.url.query and len(request.url.query) > self.max_query_length:
            logger.warning(
                f"Request query string too long: {len(request.url.query)} > {self.max_query_length}"
            )
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=413,
                content={
                    "error": "RequestEntityTooLarge",
                    "message": "Query string too long",
                    "detail": f"Maximum query length is {self.max_query_length} characters",
                    "status_code": 413
                }
            )

        # Check content-length header if present
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                content_length_int = int(content_length)
                if content_length_int > self.max_size:
                    logger.warning(
                        f"Request body too large: {content_length_int} > {self.max_size}"
                    )
                    from fastapi.responses import JSONResponse
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": "RequestEntityTooLarge",
                            "message": "Request body too large",
                            "detail": f"Maximum request size is {self.max_size} bytes ({self.max_size // 1048576}MB)",
                            "status_code": 413
                        }
                    )
            except ValueError:
                pass  # Invalid content-length, let it through and fail later if needed

        # Process request
        response = await call_next(request)
        return response
