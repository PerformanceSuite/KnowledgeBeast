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
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator, Union

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from knowledgebeast import __version__, __description__
from knowledgebeast.api.middleware import (
    RequestIDMiddleware,
    TimingMiddleware,
    LoggingMiddleware
)
from knowledgebeast.api.routes import router, get_kb_instance, cleanup_heartbeat
from knowledgebeast.api.models import ErrorResponse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


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
            }
        ],
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,  # Hide schemas section by default
            "docExpansion": "list",  # Expand only tags
            "filter": True,  # Enable search filter
        }
    )

    # Add CORS middleware
    # NOTE: Configure origins appropriately for production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: Restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time"]
    )

    # Add custom middleware (order matters - first added is outermost)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # Add rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Include routers with API versioning
    app.include_router(router, prefix="/api/v1")

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
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                error="NotFound",
                message="The requested resource was not found",
                detail=str(exc) if str(exc) else None,
                status_code=404
            ).model_dump()
        )

    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle 500 Internal Server errors."""
        logger.error(f"Internal server error: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="InternalServerError",
                message="An internal server error occurred",
                detail="Please contact support if this persists",
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
        detail = "; ".join([
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
            for err in errors
        ])

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                error="ValidationError",
                message="Request validation failed",
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

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=type(exc).__name__,
                message="An unexpected error occurred",
                detail=str(exc) if str(exc) else None,
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
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi": "/openapi.json",
        "api_v1": "/api/v1",
        "timestamp": datetime.utcnow().isoformat() + "Z"
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
