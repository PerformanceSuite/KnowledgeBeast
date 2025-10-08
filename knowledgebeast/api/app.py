"""FastAPI application factory for KnowledgeBeast.

Production-ready FastAPI application with:
- Lifespan management for KB initialization and cleanup
- CORS middleware for cross-origin requests
- Comprehensive error handling
- Request logging and timing
- OpenAPI documentation customization
- Rate limiting support
- Health monitoring
"""

import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Union

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from knowledgebeast import __description__, __version__
from knowledgebeast.api.middleware import (
    LoggingMiddleware,
    RequestIDMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
    TimingMiddleware,
)
from knowledgebeast.api.models import ErrorResponse
from knowledgebeast.api.routes import cleanup_executor, cleanup_heartbeat, get_kb_instance, router, router_v2

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from knowledgebeast.core.constants import (
    DEFAULT_RATE_LIMIT_PER_MINUTE,
    DEFAULT_RATE_LIMIT_STORAGE,
    ENV_PREFIX,
    HTTP_404_MESSAGE,
    HTTP_500_MESSAGE,
    HTTP_500_DETAIL,
    HTTP_422_MESSAGE
)

# Rate limiting configuration
RATE_LIMIT_PER_MINUTE = int(os.getenv(f'{ENV_PREFIX}RATE_LIMIT_PER_MINUTE', str(DEFAULT_RATE_LIMIT_PER_MINUTE)))
RATE_LIMIT_STORAGE = os.getenv(f'{ENV_PREFIX}RATE_LIMIT_STORAGE', DEFAULT_RATE_LIMIT_STORAGE)

# CORS configuration - restrict origins for security
def get_allowed_origins() -> list:
    """Get allowed CORS origins from environment.

    Returns:
        List of allowed origin strings. Defaults to localhost for development.
    """
    origins_env = os.getenv(f'{ENV_PREFIX}ALLOWED_ORIGINS', '')

    if origins_env:
        # Parse comma-separated origins
        origins = [origin.strip() for origin in origins_env.split(',') if origin.strip()]
        if origins:
            logger.info(f"CORS configured with {len(origins)} allowed origins")
            return origins

    # Default to localhost for development
    default_origins = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8080"
    ]
    logger.warning("No KB_ALLOWED_ORIGINS configured, using development defaults")
    return default_origins

# Security configuration
MAX_REQUEST_SIZE = int(os.getenv(f'{ENV_PREFIX}MAX_REQUEST_SIZE', '10485760'))  # 10MB default
MAX_QUERY_LENGTH = int(os.getenv(f'{ENV_PREFIX}MAX_QUERY_LENGTH', '10000'))  # 10k chars default

# Initialize rate limiter with configurable defaults
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{RATE_LIMIT_PER_MINUTE}/minute"],
    storage_uri=RATE_LIMIT_STORAGE
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager for startup and shutdown events.

    Handles:
    - Knowledge base initialization on startup
    - Heartbeat cleanup on shutdown
    - Resource cleanup

    Args:
        app: FastAPI application instance

    Yields:
        None during application lifetime
    """
    # Startup
    logger.info("Starting KnowledgeBeast API server...")
    logger.info(f"Version: {__version__}")

    try:
        # Initialize knowledge base (lazy initialization on first request)
        logger.info("Knowledge base will be initialized on first request")

        yield  # Application is running

    finally:
        # Shutdown
        logger.info("Shutting down KnowledgeBeast API server...")

        # Cleanup heartbeat if running
        try:
            cleanup_heartbeat()
            logger.info("Heartbeat cleanup completed")
        except Exception as e:
            logger.error(f"Error during heartbeat cleanup: {e}")

        # Cleanup thread pool executor
        try:
            cleanup_executor()
            logger.info("Executor cleanup completed")
        except Exception as e:
            logger.error(f"Error during executor cleanup: {e}")

        # Cleanup KB instance if exists
        try:
            kb = get_kb_instance()
            if kb:
                logger.info(f"Final stats: {kb.get_stats()}")
        except Exception as e:
            logger.error(f"Error getting final stats: {e}")

        logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Configures:
    - OpenAPI documentation
    - CORS middleware
    - Custom middleware (request ID, timing, logging)
    - Rate limiting
    - Error handlers
    - API routes

    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title="KnowledgeBeast API",
        description=__description__,
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        # Customize OpenAPI schema
        openapi_tags=[
            {
                "name": "health",
                "description": "Health check and system status endpoints"
            },
            {
                "name": "query",
                "description": "Knowledge base query operations"
            },
            {
                "name": "ingest",
                "description": "Document ingestion operations"
            },
            {
                "name": "management",
                "description": "Cache, warming, and maintenance operations"
            },
            {
                "name": "heartbeat",
                "description": "Heartbeat monitoring and control"
            },
            {
                "name": "collections",
                "description": "Collection management operations"
            },
            {
                "name": "projects",
                "description": "Multi-project management operations (API v2)"
            }
        ],
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,  # Hide schemas section by default
            "docExpansion": "list",  # Expand only tags
            "filter": True,  # Enable search filter
        }
    )

    # Add CORS middleware with restricted origins
    allowed_origins = get_allowed_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],  # Only required methods
        allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
        expose_headers=["X-Request-ID", "X-Process-Time"]
    )

    # Add custom middleware (order matters - first added is outermost)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware, max_size=MAX_REQUEST_SIZE, max_query_length=MAX_QUERY_LENGTH)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # Add rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Include routers with API versioning
    # V1 routes (legacy)
    app.include_router(router, prefix="/api/v1")
    # V2 routes (multi-project API)
    app.include_router(router_v2, prefix="/api/v2/projects")

    # Mount static files for web UI
    static_dir = Path(__file__).parent.parent / "web" / "static"
    if static_dir.exists():
        app.mount("/ui", StaticFiles(directory=str(static_dir), html=True), name="ui")
        logger.info(f"Web UI mounted at /ui (serving from {static_dir})")
    else:
        logger.warning(f"Static directory not found: {static_dir}")

    # Register error handlers
    register_error_handlers(app)

    logger.info("FastAPI application created and configured")
    return app


def register_error_handlers(app: FastAPI) -> None:
    """Register custom error handlers for the application.

    Handles:
    - 404 Not Found errors
    - 500 Internal Server errors
    - Validation errors
    - Generic exceptions

    Args:
        app: FastAPI application instance
    """

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle 404 Not Found errors."""
        # Don't expose internal details in error message
        error_detail = str(exc) if str(exc) and not "/" in str(exc) else None
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                error="NotFound",
                message=HTTP_404_MESSAGE,
                detail=error_detail,
                status_code=404
            ).model_dump()
        )

    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle 500 Internal Server errors."""
        logger.error(f"Internal server error: {exc}", exc_info=True)
        # Never expose internal paths or stack traces to users
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="InternalServerError",
                message=HTTP_500_MESSAGE,
                detail=HTTP_500_DETAIL,
                status_code=500
            ).model_dump()
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError
    ) -> JSONResponse:
        """Handle request validation errors."""
        errors = exc.errors()
        # Sanitize error details to avoid exposing internal paths
        detail = "; ".join([
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
            for err in errors
        ])

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                error="ValidationError",
                message=HTTP_422_MESSAGE,
                detail=detail,
                status_code=422
            ).model_dump()
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request,
        exc: Exception
    ) -> JSONResponse:
        """Handle generic exceptions."""
        logger.error(f"Unhandled exception: {exc}", exc_info=True)

        # Don't expose internal details - sanitize error message
        error_msg = str(exc)
        # Remove any file paths from error message
        if "/" in error_msg or "\\" in error_msg:
            error_detail = HTTP_500_DETAIL
        else:
            error_detail = error_msg if error_msg else HTTP_500_DETAIL

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=type(exc).__name__,
                message="An unexpected error occurred",
                detail=error_detail,
                status_code=500
            ).model_dump()
        )


# Create default app instance
app = create_app()


# Root endpoint (outside versioned API)
@app.get("/", tags=["root"])
async def root() -> dict:
    """Root endpoint with API information.

    Returns:
        API information and links
    """
    return {
        "name": "KnowledgeBeast API",
        "version": __version__,
        "description": __description__,
        "web_ui": "/ui",
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi": "/openapi.json",
        "api_v1": "/api/v1",
        "api_v2": "/api/v2/projects",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }


if __name__ == "__main__":
    import uvicorn

    # Run with hot reload for development
    uvicorn.run(
        "knowledgebeast.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
