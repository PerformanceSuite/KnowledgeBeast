"""API routes for KnowledgeBeast.

Provides 12 production-ready endpoints:
1. GET /health - Health check
2. GET /stats - KB statistics
3. POST /query - Search knowledge base
4. POST /ingest - Add single document
5. POST /batch-ingest - Add multiple documents
6. POST /warm - Trigger warming
7. POST /cache/clear - Clear cache
8. GET /heartbeat/status - Heartbeat status
9. POST /heartbeat/start - Start heartbeat
10. POST /heartbeat/stop - Stop heartbeat
11. GET /collections - List collections
12. GET /collections/{name} - Get collection info
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from knowledgebeast import __version__
from knowledgebeast.api.auth import get_api_key
from knowledgebeast.api.models import (
    APIKeyCreate,
    APIKeyInfo,
    APIKeyListResponse,
    APIKeyResponse,
    APIKeyRevokeResponse,
    BatchIngestRequest,
    BatchIngestResponse,
    CacheClearResponse,
    CollectionInfo,
    CollectionsResponse,
    HealthResponse,
    HeartbeatActionResponse,
    HeartbeatStatusResponse,
    IngestRequest,
    IngestResponse,
    MultiModalQueryRequest,
    MultiModalUploadRequest,
    MultiModalUploadResponse,
    PaginatedQueryRequest,
    PaginatedQueryResponse,
    PaginationMetadata,
    ProjectCreate,
    ProjectDeleteResponse,
    ProjectIngestRequest,
    ProjectListResponse,
    ProjectQueryRequest,
    ProjectResponse,
    ProjectUpdate,
    QueryRequest,
    QueryResponse,
    QueryResult,
    StatsResponse,
    WarmRequest,
    WarmResponse,
)
from knowledgebeast.core.config import KnowledgeBeastConfig
from knowledgebeast.core.engine import KnowledgeBase
from knowledgebeast.core.heartbeat import KnowledgeBaseHeartbeat
from knowledgebeast.core.project_manager import ProjectManager
from knowledgebeast.utils.metrics import (
    measure_project_query,
    record_project_cache_hit,
    record_project_cache_miss,
    record_project_error,
    record_project_ingest,
)

logger = logging.getLogger(__name__)

# Initialize routers
router = APIRouter()  # V1 routes (legacy)
router_v2 = APIRouter()  # V2 routes (projects)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Thread pool executor for blocking operations
_executor: Optional[ThreadPoolExecutor] = None


def get_executor() -> ThreadPoolExecutor:
    """Get or create the thread pool executor.

    Returns:
        ThreadPoolExecutor instance
    """
    global _executor

    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="kb-worker")
        logger.debug("Created new thread pool executor")

    return _executor

# Global instances (singleton pattern)
_kb_instance: Optional[KnowledgeBase] = None
_heartbeat_instance: Optional[KnowledgeBaseHeartbeat] = None
_project_manager_instance: Optional[ProjectManager] = None


def get_kb_instance() -> KnowledgeBase:
    """Get or create the singleton KnowledgeBase instance.

    Returns:
        KnowledgeBase instance

    Raises:
        HTTPException: If initialization fails
    """
    global _kb_instance

    if _kb_instance is None:
        try:
            logger.info("Initializing KnowledgeBase instance...")
            config = KnowledgeBeastConfig()
            _kb_instance = KnowledgeBase(config=config)
            logger.info("KnowledgeBase initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize KnowledgeBase: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize knowledge base: {str(e)}",
            )

    return _kb_instance


def get_heartbeat_instance() -> Optional[KnowledgeBaseHeartbeat]:
    """Get the heartbeat instance if it exists.

    Returns:
        KnowledgeBaseHeartbeat instance or None
    """
    return _heartbeat_instance


def get_project_manager() -> ProjectManager:
    """Get or create the singleton ProjectManager instance.

    Returns:
        ProjectManager instance

    Raises:
        HTTPException: If initialization fails
    """
    global _project_manager_instance

    if _project_manager_instance is None:
        try:
            logger.info("Initializing ProjectManager instance...")
            _project_manager_instance = ProjectManager(
                storage_path="./kb_projects.db",
                chroma_path="./chroma_db",
                cache_capacity=100
            )
            logger.info("ProjectManager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ProjectManager: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize project manager: {str(e)}",
            )

    return _project_manager_instance


def cleanup_heartbeat() -> None:
    """Cleanup heartbeat instance if running."""
    global _heartbeat_instance

    if _heartbeat_instance and _heartbeat_instance.is_running():
        logger.info("Stopping heartbeat...")
        _heartbeat_instance.stop()
        _heartbeat_instance = None


def cleanup_executor() -> None:
    """Cleanup thread pool executor."""
    global _executor

    if _executor:
        logger.info("Shutting down thread pool executor...")
        _executor.shutdown(wait=True, cancel_futures=False)
        _executor = None  # Reset to None after shutdown
        logger.info("Thread pool executor shutdown complete")


# ============================================================================
# Health Endpoints
# ============================================================================


@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Health check",
    description="Check API health status and basic system information",
)
@limiter.limit("100/minute")
async def health_check(request: Request, api_key: str = Depends(get_api_key)) -> HealthResponse:
    """Health check endpoint with deep system checks.

    Checks:
    - KB initialization
    - Cache file accessibility
    - Knowledge directories accessibility
    - Memory usage (if psutil available)

    Returns:
        Health status, version, and initialization state
    """
    kb_initialized = False
    cache_readable = False
    dirs_accessible = False
    issues = []

    try:
        kb = get_kb_instance()
        kb_initialized = True

        # Check cache file accessibility
        try:
            cache_path = Path(kb.config.cache_file)
            if cache_path.exists():
                cache_readable = cache_path.is_file() and cache_path.stat().st_size >= 0
            else:
                cache_readable = True  # Cache doesn't exist yet, but that's ok
        except Exception as e:
            issues.append(f"Cache check failed: {str(e)}")
            logger.warning(f"Health check - cache accessibility issue: {e}")

        # Check knowledge directories accessibility
        try:
            accessible_dirs = 0
            for kb_dir in kb.config.knowledge_dirs:
                if kb_dir.exists() and kb_dir.is_dir():
                    accessible_dirs += 1
            dirs_accessible = accessible_dirs > 0
            if not dirs_accessible:
                issues.append("No accessible knowledge directories")
        except Exception as e:
            issues.append(f"Directory check failed: {str(e)}")
            logger.warning(f"Health check - directory accessibility issue: {e}")

        # Optional: Check memory usage if psutil available
        try:
            import psutil

            process = psutil.Process()
            mem_info = process.memory_info()
            mem_mb = mem_info.rss / 1024 / 1024
            if mem_mb > 1000:  # Warn if over 1GB
                issues.append(f"High memory usage: {mem_mb:.1f}MB")
                logger.warning(f"Health check - high memory usage: {mem_mb:.1f}MB")
        except ImportError:
            pass  # psutil not available, skip memory check
        except Exception as e:
            logger.debug(f"Memory check failed: {e}")

    except Exception as e:
        issues.append(f"KB initialization failed: {str(e)}")
        logger.error(f"Health check - KB initialization issue: {e}")

    # Determine overall health status
    if kb_initialized and cache_readable and dirs_accessible:
        status = "healthy"
    elif kb_initialized:
        status = "degraded"
    else:
        status = "unhealthy"

    response = HealthResponse(
        status=status,
        version=__version__,
        kb_initialized=kb_initialized,
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )

    # Add issues to response if any (add as extra field if needed)
    if issues and hasattr(response, "__dict__"):
        response.__dict__["issues"] = issues

    return response


@router.get(
    "/stats",
    response_model=StatsResponse,
    tags=["health"],
    summary="Get statistics",
    description="Get detailed knowledge base statistics and performance metrics",
)
@limiter.limit("60/minute")
async def get_stats(request: Request, api_key: str = Depends(get_api_key)) -> StatsResponse:
    """Get knowledge base statistics.

    Returns:
        Detailed statistics about queries, cache, documents, etc.

    Raises:
        HTTPException: If KB not initialized
    """
    try:
        kb = get_kb_instance()

        # Execute in thread pool (non-blocking)
        loop = asyncio.get_event_loop()
        stats = await loop.run_in_executor(get_executor(), kb.get_stats)

        return StatsResponse(**stats)

    except Exception as e:
        logger.error(f"Stats error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}",
        )


# ============================================================================
# Query Endpoints
# ============================================================================


@router.post(
    "/query",
    response_model=QueryResponse,
    tags=["query"],
    summary="Query knowledge base",
    description="Search the knowledge base for relevant documents",
)
@limiter.limit("30/minute")
async def query_knowledge_base(
    request: Request, query_request: QueryRequest, api_key: str = Depends(get_api_key)
) -> QueryResponse:
    """Query the knowledge base for relevant documents.

    Args:
        query_request: Query request with search terms and options

    Returns:
        List of matching documents with metadata

    Raises:
        HTTPException: If query fails
    """
    try:
        kb = get_kb_instance()

        # Check if cached before query
        cache_key = kb._generate_cache_key(query_request.query)
        was_cached = cache_key in kb.query_cache._cache

        # Execute query in thread pool (non-blocking)
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            get_executor(),
            lambda: kb.query(query_request.query, use_cache=query_request.use_cache)
        )

        # Convert results to QueryResult models
        query_results = [
            QueryResult(
                doc_id=doc_id,
                content=doc["content"],
                name=doc["name"],
                path=doc["path"],
                kb_dir=doc["kb_dir"],
            )
            for doc_id, doc in results
        ]

        return QueryResponse(
            results=query_results,
            count=len(query_results),
            cached=was_cached,
            query=query_request.query,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Query error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Query failed: {str(e)}"
        )


@router.post(
    "/query/paginated",
    response_model=PaginatedQueryResponse,
    tags=["query"],
    summary="Query knowledge base with pagination",
    description="Search the knowledge base for relevant documents with pagination support",
)
@limiter.limit("30/minute")
async def query_knowledge_base_paginated(
    request: Request, query_request: PaginatedQueryRequest, api_key: str = Depends(get_api_key)
) -> PaginatedQueryResponse:
    """Query the knowledge base for relevant documents with pagination.

    Args:
        query_request: Paginated query request with search terms and pagination options

    Returns:
        Paginated list of matching documents with metadata

    Raises:
        HTTPException: If query fails or invalid page requested
    """
    try:
        kb = get_kb_instance()

        # Check if cached before query
        cache_key = kb._generate_cache_key(query_request.query)
        was_cached = cache_key in kb.query_cache._cache

        # Execute query in thread pool (non-blocking) - get ALL results
        loop = asyncio.get_event_loop()
        all_results = await loop.run_in_executor(
            get_executor(),
            kb.query,
            query_request.query,
            query_request.use_cache
        )

        # Calculate pagination metadata
        total_results = len(all_results)
        page_size = query_request.page_size
        current_page = query_request.page
        total_pages = (total_results + page_size - 1) // page_size if total_results > 0 else 1

        # Validate page number
        if current_page > total_pages and total_results > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Page {current_page} exceeds total pages {total_pages}"
            )

        # Calculate slice indices for current page
        start_idx = (current_page - 1) * page_size
        end_idx = start_idx + page_size

        # Slice results for current page
        page_results = all_results[start_idx:end_idx]

        # Convert results to QueryResult models
        query_results = [
            QueryResult(
                doc_id=doc_id,
                content=doc["content"],
                name=doc["name"],
                path=doc["path"],
                kb_dir=doc["kb_dir"],
            )
            for doc_id, doc in page_results
        ]

        # Build pagination metadata
        pagination = PaginationMetadata(
            total_results=total_results,
            total_pages=total_pages,
            current_page=current_page,
            page_size=page_size,
            has_next=current_page < total_pages,
            has_previous=current_page > 1
        )

        return PaginatedQueryResponse(
            results=query_results,
            count=len(query_results),
            cached=was_cached,
            query=query_request.query,
            pagination=pagination
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Paginated query error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Paginated query failed: {str(e)}"
        )


# ============================================================================
# Ingest Endpoints
# ============================================================================


@router.post(
    "/ingest",
    response_model=IngestResponse,
    tags=["ingest"],
    summary="Ingest single document",
    description="Add a single document to the knowledge base",
)
@limiter.limit("20/minute")
async def ingest_document(
    request: Request, ingest_request: IngestRequest, api_key: str = Depends(get_api_key)
) -> IngestResponse:
    """Ingest a single document into the knowledge base.

    Args:
        ingest_request: Ingestion request with file path and metadata

    Returns:
        Ingestion status and document ID

    Raises:
        HTTPException: If file not found or ingestion fails
    """
    try:
        kb = get_kb_instance()
        file_path = Path(ingest_request.file_path)

        # Validate file exists
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found: {file_path}"
            )

        if not file_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Path is not a file: {file_path}"
            )

        # Note: Current KnowledgeBase engine uses ingest_all() for directory ingestion
        # For single file, we need to rebuild the index to include the new file
        # This is a limitation that could be improved in the future

        logger.warning(
            "Single file ingestion triggers full index rebuild. "
            "Consider batch ingestion for better performance."
        )

        # Trigger rebuild to include new file (execute in thread pool)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(get_executor(), kb.rebuild_index)

        # Generate doc_id (similar to how engine does it)
        doc_id = str(file_path)

        return IngestResponse(
            success=True,
            file_path=str(file_path),
            doc_id=doc_id,
            message=f"Successfully ingested {file_path.name}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ingestion error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ingestion failed: {str(e)}"
        )


@router.post(
    "/batch-ingest",
    response_model=BatchIngestResponse,
    tags=["ingest"],
    summary="Batch ingest documents",
    description="Add multiple documents to the knowledge base in a single operation",
)
@limiter.limit("10/minute")
async def batch_ingest_documents(
    request: Request, batch_request: BatchIngestRequest, api_key: str = Depends(get_api_key)
) -> BatchIngestResponse:
    """Batch ingest multiple documents.

    Args:
        batch_request: Batch ingestion request with file paths

    Returns:
        Batch ingestion status with success/failure counts

    Raises:
        HTTPException: If batch ingestion fails
    """
    try:
        kb = get_kb_instance()

        failed_files = []
        successful = 0

        # Validate all files exist first
        for file_path_str in batch_request.file_paths:
            file_path = Path(file_path_str)
            if not file_path.exists() or not file_path.is_file():
                failed_files.append(file_path_str)
            else:
                successful += 1

        # Rebuild index to include all files (execute in thread pool)
        if successful > 0:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(get_executor(), kb.rebuild_index)

        total_files = len(batch_request.file_paths)
        failed = len(failed_files)

        return BatchIngestResponse(
            success=failed == 0,
            total_files=total_files,
            successful=successful,
            failed=failed,
            failed_files=failed_files,
            message=f"Batch ingestion completed: {successful}/{total_files} successful",
        )

    except Exception as e:
        logger.error(f"Batch ingestion error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch ingestion failed: {str(e)}",
        )


# ============================================================================
# Management Endpoints
# ============================================================================


@router.post(
    "/warm",
    response_model=WarmResponse,
    tags=["management"],
    summary="Warm knowledge base",
    description="Trigger knowledge base warming to reduce query latency",
)
@limiter.limit("10/minute")
async def warm_knowledge_base(
    request: Request, warm_request: WarmRequest, api_key: str = Depends(get_api_key)
) -> WarmResponse:
    """Trigger knowledge base warming.

    Args:
        warm_request: Warming request with options

    Returns:
        Warming status and metrics

    Raises:
        HTTPException: If warming fails
    """
    try:
        kb = get_kb_instance()

        start_time = time.time()

        loop = asyncio.get_event_loop()

        # Rebuild if requested (execute in thread pool)
        if warm_request.force_rebuild:
            await loop.run_in_executor(get_executor(), kb.rebuild_index)

        # Warm up (execute in thread pool)
        await loop.run_in_executor(get_executor(), kb.warm_up)

        warm_time = time.time() - start_time

        return WarmResponse(
            success=True,
            warm_time=warm_time,
            queries_executed=kb.stats.get("warm_queries", 0),
            documents_loaded=len(kb.documents),
            message=f"Knowledge base warmed in {warm_time:.2f}s",
        )

    except Exception as e:
        logger.error(f"Warming error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Warming failed: {str(e)}"
        )


@router.post(
    "/cache/clear",
    response_model=CacheClearResponse,
    tags=["management"],
    summary="Clear query cache",
    description="Clear all cached query results",
)
@limiter.limit("20/minute")
async def clear_cache(request: Request, api_key: str = Depends(get_api_key)) -> CacheClearResponse:
    """Clear query cache.

    Returns:
        Cache clear status and count

    Raises:
        HTTPException: If cache clear fails
    """
    try:
        kb = get_kb_instance()

        # Get count before clearing
        cleared_count = len(kb.query_cache)

        # Clear cache
        kb.clear_cache()

        return CacheClearResponse(
            success=True,
            cleared_count=cleared_count,
            message=f"Cache cleared: {cleared_count} entries removed",
        )

    except Exception as e:
        logger.error(f"Cache clear error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cache clear failed: {str(e)}",
        )


# ============================================================================
# Heartbeat Endpoints
# ============================================================================


@router.get(
    "/heartbeat/status",
    response_model=HeartbeatStatusResponse,
    tags=["heartbeat"],
    summary="Get heartbeat status",
    description="Get current heartbeat status and metrics",
)
@limiter.limit("60/minute")
async def get_heartbeat_status(
    request: Request, api_key: str = Depends(get_api_key)
) -> HeartbeatStatusResponse:
    """Get heartbeat status.

    Returns:
        Heartbeat running status and metrics
    """
    global _heartbeat_instance

    if _heartbeat_instance is None:
        return HeartbeatStatusResponse(
            running=False, interval=0, heartbeat_count=0, last_heartbeat=None
        )

    return HeartbeatStatusResponse(
        running=_heartbeat_instance.is_running(),
        interval=_heartbeat_instance.interval,
        heartbeat_count=_heartbeat_instance.heartbeat_count,
        last_heartbeat=None,  # Could add timestamp tracking in heartbeat class
    )


@router.post(
    "/heartbeat/start",
    response_model=HeartbeatActionResponse,
    tags=["heartbeat"],
    summary="Start heartbeat",
    description="Start background heartbeat for continuous KB monitoring",
)
@limiter.limit("10/minute")
async def start_heartbeat(
    request: Request, api_key: str = Depends(get_api_key)
) -> HeartbeatActionResponse:
    """Start heartbeat monitoring.

    Returns:
        Action status

    Raises:
        HTTPException: If start fails
    """
    global _heartbeat_instance

    try:
        kb = get_kb_instance()

        if _heartbeat_instance and _heartbeat_instance.is_running():
            return HeartbeatActionResponse(
                success=True, message="Heartbeat already running", running=True
            )

        # Create and start heartbeat
        _heartbeat_instance = KnowledgeBaseHeartbeat(kb=kb, interval=kb.config.heartbeat_interval)
        _heartbeat_instance.start()

        return HeartbeatActionResponse(
            success=True, message="Heartbeat started successfully", running=True
        )

    except Exception as e:
        logger.error(f"Heartbeat start error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start heartbeat: {str(e)}",
        )


@router.post(
    "/heartbeat/stop",
    response_model=HeartbeatActionResponse,
    tags=["heartbeat"],
    summary="Stop heartbeat",
    description="Stop background heartbeat monitoring",
)
@limiter.limit("10/minute")
async def stop_heartbeat(
    request: Request, api_key: str = Depends(get_api_key)
) -> HeartbeatActionResponse:
    """Stop heartbeat monitoring.

    Returns:
        Action status
    """
    global _heartbeat_instance

    try:
        if _heartbeat_instance is None or not _heartbeat_instance.is_running():
            return HeartbeatActionResponse(
                success=True, message="Heartbeat not running", running=False
            )

        _heartbeat_instance.stop()
        _heartbeat_instance = None

        return HeartbeatActionResponse(
            success=True, message="Heartbeat stopped successfully", running=False
        )

    except Exception as e:
        logger.error(f"Heartbeat stop error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop heartbeat: {str(e)}",
        )


# ============================================================================
# Collection Endpoints
# ============================================================================


@router.get(
    "/collections",
    response_model=CollectionsResponse,
    tags=["collections"],
    summary="List collections",
    description="Get list of all knowledge base collections",
)
@limiter.limit("60/minute")
async def list_collections(
    request: Request, api_key: str = Depends(get_api_key)
) -> CollectionsResponse:
    """List all collections.

    Returns:
        List of collections with metadata

    Note:
        Current implementation has a single collection.
        Multi-collection support could be added in the future.
    """
    try:
        kb = get_kb_instance()

        # Current implementation has a single default collection
        collection = CollectionInfo(
            name="default",
            document_count=len(kb.documents),
            term_count=len(kb.index),
            cache_size=len(kb.query_cache),
        )

        return CollectionsResponse(collections=[collection], count=1)

    except Exception as e:
        logger.error(f"List collections error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list collections: {str(e)}",
        )


@router.get(
    "/collections/{name}",
    response_model=CollectionInfo,
    tags=["collections"],
    summary="Get collection info",
    description="Get detailed information about a specific collection",
)
@limiter.limit("60/minute")
async def get_collection_info(
    request: Request, name: str, api_key: str = Depends(get_api_key)
) -> CollectionInfo:
    """Get collection information.

    Args:
        name: Collection name

    Returns:
        Collection information

    Raises:
        HTTPException: If collection not found
    """
    try:
        kb = get_kb_instance()

        # Only "default" collection exists in current implementation
        if name != "default":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Collection not found: {name}"
            )

        return CollectionInfo(
            name="default",
            document_count=len(kb.documents),
            term_count=len(kb.index),
            cache_size=len(kb.query_cache),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get collection error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get collection info: {str(e)}",
        )


# ============================================================================
# Project Endpoints (API v2)
# ============================================================================


@router_v2.post(
    "",
    response_model=ProjectResponse,
    tags=["projects"],
    summary="Create new project",
    description="Create a new isolated project with its own knowledge base",
    status_code=201
)
@limiter.limit("10/minute")
async def create_project(
    request: Request,
    project_data: ProjectCreate,
    api_key: str = Depends(get_api_key)
) -> ProjectResponse:
    """Create a new project.

    Args:
        project_data: Project creation data

    Returns:
        Created project details

    Raises:
        HTTPException: If project creation fails or name already exists
    """
    try:
        pm = get_project_manager()

        # Create project in thread pool
        loop = asyncio.get_event_loop()
        project = await loop.run_in_executor(
            get_executor(),
            pm.create_project,
            project_data.name,
            project_data.description,
            project_data.embedding_model,
            project_data.metadata
        )

        # Record project creation metric
        from knowledgebeast.utils.observability import project_creations_total
        project_creations_total.inc()

        return ProjectResponse(**project.to_dict())

    except ValueError as e:
        from knowledgebeast.utils.observability import project_errors_total
        project_errors_total.labels(project_id="unknown", error_type="ValidationError").inc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Create project error: {e}", exc_info=True)
        from knowledgebeast.utils.observability import project_errors_total
        project_errors_total.labels(project_id="unknown", error_type="CreateError").inc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create project: {str(e)}"
        )


@router_v2.get(
    "",
    response_model=ProjectListResponse,
    tags=["projects"],
    summary="List all projects",
    description="Get list of all projects",
)
@limiter.limit("60/minute")
async def list_projects(
    request: Request,
    api_key: str = Depends(get_api_key)
) -> ProjectListResponse:
    """List all projects.

    Returns:
        List of all projects

    Raises:
        HTTPException: If listing fails
    """
    try:
        pm = get_project_manager()

        # List projects in thread pool
        loop = asyncio.get_event_loop()
        projects = await loop.run_in_executor(get_executor(), pm.list_projects)

        project_responses = [ProjectResponse(**p.to_dict()) for p in projects]

        return ProjectListResponse(
            projects=project_responses,
            count=len(project_responses)
        )

    except Exception as e:
        logger.error(f"List projects error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list projects: {str(e)}"
        )


@router_v2.get(
    "/{project_id}",
    response_model=ProjectResponse,
    tags=["projects"],
    summary="Get project details",
    description="Get detailed information about a specific project",
)
@limiter.limit("60/minute")
async def get_project(
    request: Request,
    project_id: str,
    api_key: str = Depends(get_api_key)
) -> ProjectResponse:
    """Get project details.

    Args:
        project_id: Project identifier

    Returns:
        Project details

    Raises:
        HTTPException: If project not found
    """
    try:
        pm = get_project_manager()

        # Get project in thread pool
        loop = asyncio.get_event_loop()
        project = await loop.run_in_executor(get_executor(), pm.get_project, project_id)

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project not found: {project_id}"
            )

        return ProjectResponse(**project.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get project error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get project: {str(e)}"
        )


@router_v2.put(
    "/{project_id}",
    response_model=ProjectResponse,
    tags=["projects"],
    summary="Update project",
    description="Update project metadata",
)
@limiter.limit("20/minute")
async def update_project(
    request: Request,
    project_id: str,
    update_data: ProjectUpdate,
    api_key: str = Depends(get_api_key)
) -> ProjectResponse:
    """Update project metadata.

    Args:
        project_id: Project identifier
        update_data: Update data

    Returns:
        Updated project details

    Raises:
        HTTPException: If project not found or update fails
    """
    try:
        pm = get_project_manager()

        # Update project in thread pool
        loop = asyncio.get_event_loop()
        project = await loop.run_in_executor(
            get_executor(),
            pm.update_project,
            project_id,
            update_data.name,
            update_data.description,
            update_data.embedding_model,
            update_data.metadata
        )

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project not found: {project_id}"
            )

        # Record project update
        from knowledgebeast.utils.observability import project_updates_total
        project_updates_total.inc()

        return ProjectResponse(**project.to_dict())

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Update project error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update project: {str(e)}"
        )


@router_v2.delete(
    "/{project_id}",
    response_model=ProjectDeleteResponse,
    tags=["projects"],
    summary="Delete project",
    description="Delete a project and all its resources",
)
@limiter.limit("10/minute")
async def delete_project(
    request: Request,
    project_id: str,
    api_key: str = Depends(get_api_key)
) -> ProjectDeleteResponse:
    """Delete a project.

    Args:
        project_id: Project identifier

    Returns:
        Deletion status

    Raises:
        HTTPException: If project not found or deletion fails
    """
    try:
        pm = get_project_manager()

        # Delete project in thread pool
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(get_executor(), pm.delete_project, project_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project not found: {project_id}"
            )

        # Record project deletion
        from knowledgebeast.utils.observability import project_deletions_total
        project_deletions_total.inc()

        return ProjectDeleteResponse(
            success=True,
            project_id=project_id,
            message=f"Project {project_id} deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete project error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete project: {str(e)}"
        )


@router_v2.post(
    "/{project_id}/query",
    response_model=QueryResponse,
    tags=["projects"],
    summary="Project-scoped query",
    description="Search within a specific project's knowledge base",
)
@limiter.limit("30/minute")
async def project_query(
    request: Request,
    project_id: str,
    query_request: ProjectQueryRequest,
    api_key: str = Depends(get_api_key)
) -> QueryResponse:
    """Query a specific project's knowledge base.

    Args:
        project_id: Project identifier
        query_request: Query request

    Returns:
        Query results

    Raises:
        HTTPException: If project not found or query fails
    """
    try:
        pm = get_project_manager()

        # Verify project exists
        loop = asyncio.get_event_loop()
        project = await loop.run_in_executor(get_executor(), pm.get_project, project_id)

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project not found: {project_id}"
            )

        # Get project cache and check for cached results
        cache = pm.get_project_cache(project_id)
        cache_key = f"{query_request.query}:{query_request.limit}"

        cached_results = cache.get(cache_key) if query_request.use_cache else None
        if cached_results is not None:
            logger.debug(f"Cache hit for project {project_id} query: {query_request.query}")
            record_project_cache_hit(project_id)
            return QueryResponse(
                results=cached_results,
                count=len(cached_results),
                cached=True,
                query=query_request.query
            )

        # Record cache miss
        record_project_cache_miss(project_id)

        # Get ChromaDB collection for this project
        collection = await loop.run_in_executor(get_executor(), pm.get_project_collection, project_id)

        if not collection:
            record_project_error(project_id, "CollectionError")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get collection for project: {project_id}"
            )

        # Execute vector search using ChromaDB's native query
        # ChromaDB automatically handles embedding generation for the query text
        def query_collection():
            result = collection.query(
                query_texts=[query_request.query],
                n_results=min(query_request.limit, 100)  # Cap at 100 results
            )
            return result

        # Measure query duration
        with measure_project_query(project_id):
            chroma_results = await loop.run_in_executor(get_executor(), query_collection)

        # Convert ChromaDB results to QueryResult format
        query_results = []

        # ChromaDB returns: {'ids': [[...]], 'documents': [[...]], 'metadatas': [[...]], 'distances': [[...]]}
        ids = chroma_results.get('ids', [[]])[0]
        documents = chroma_results.get('documents', [[]])[0]
        metadatas = chroma_results.get('metadatas', [[]])[0]
        distances = chroma_results.get('distances', [[]])[0]

        for i, doc_id in enumerate(ids):
            content = documents[i] if i < len(documents) else ""
            metadata = metadatas[i] if i < len(metadatas) else {}

            query_results.append(QueryResult(
                doc_id=doc_id,
                content=content,
                name=metadata.get('name', 'Unknown'),
                path=metadata.get('path', ''),
                kb_dir=metadata.get('kb_dir', ''),
            ))

        # Cache results if caching enabled
        if query_request.use_cache:
            cache.put(cache_key, query_results)

        return QueryResponse(
            results=query_results,
            count=len(query_results),
            cached=False,
            query=query_request.query
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Project query error: {e}", exc_info=True)
        record_project_error(project_id, "QueryError")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query project: {str(e)}"
        )


@router_v2.post(
    "/{project_id}/ingest",
    response_model=IngestResponse,
    tags=["projects"],
    summary="Project-scoped ingestion",
    description="Ingest documents into a specific project",
)
@limiter.limit("20/minute")
async def project_ingest(
    request: Request,
    project_id: str,
    ingest_request: ProjectIngestRequest,
    api_key: str = Depends(get_api_key)
) -> IngestResponse:
    """Ingest documents into a specific project.

    Args:
        project_id: Project identifier
        ingest_request: Ingestion request

    Returns:
        Ingestion status

    Raises:
        HTTPException: If project not found or ingestion fails
    """
    try:
        pm = get_project_manager()

        # Verify project exists
        loop = asyncio.get_event_loop()
        project = await loop.run_in_executor(get_executor(), pm.get_project, project_id)

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project not found: {project_id}"
            )

        # Validate request has either file_path or content
        if not ingest_request.file_path and not ingest_request.content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either file_path or content must be provided"
            )

        # Get ChromaDB collection for this project
        collection = await loop.run_in_executor(get_executor(), pm.get_project_collection, project_id)

        if not collection:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get collection for project: {project_id}"
            )

        # Prepare document content and metadata
        if ingest_request.content:
            # Direct content ingestion
            doc_content = ingest_request.content
            doc_id = f"doc_{int(time.time() * 1000)}"
            file_path = "inline_content"
        else:
            # File-based ingestion
            file_path_obj = Path(ingest_request.file_path)
            if not file_path_obj.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File not found: {ingest_request.file_path}"
                )

            # Read file content
            try:
                with open(file_path_obj, 'r', encoding='utf-8') as f:
                    doc_content = f.read()
                file_path = str(file_path_obj)
                doc_id = str(file_path_obj)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to read file: {str(e)}"
                )

        # Prepare metadata
        doc_metadata = ingest_request.metadata or {}
        doc_metadata.update({
            'name': Path(file_path).name,
            'path': file_path,
            'kb_dir': str(Path(file_path).parent) if ingest_request.file_path else '',
            'ingested_at': datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        })

        # Add document to ChromaDB collection
        # ChromaDB automatically generates embeddings using the collection's embedding function
        def add_to_collection():
            collection.add(
                documents=[doc_content],
                ids=[doc_id],
                metadatas=[doc_metadata]
            )

        await loop.run_in_executor(get_executor(), add_to_collection)

        # Record successful ingestion
        record_project_ingest(project_id, "success")
        logger.info(f"Ingested document into project {project_id}: {doc_id}")

        return IngestResponse(
            success=True,
            file_path=file_path,
            doc_id=doc_id,
            message=f"Document successfully ingested into project {project.name}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Project ingest error: {e}", exc_info=True)
        record_project_ingest(project_id, "error")
        record_project_error(project_id, "IngestError")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest into project: {str(e)}"
        )


# ============================================================================
# Project API Key Management Endpoints (v2 Security)
# ============================================================================


@router_v2.post(
    "/{project_id}/api-keys",
    response_model=APIKeyResponse,
    tags=["projects", "security"],
    summary="Create project API key",
    description="Generate a new API key for project-scoped access",
    status_code=201
)
@limiter.limit("10/minute")
async def create_project_api_key(
    request: Request,
    project_id: str,
    key_data: APIKeyCreate,
    api_key: str = Depends(get_api_key)
) -> APIKeyResponse:
    """Create a new API key for a project.

    Args:
        project_id: Project identifier
        key_data: API key creation parameters

    Returns:
        Created API key (raw key shown ONLY here!)

    Raises:
        HTTPException: If project not found or key creation fails

    Note:
        The raw API key is returned only once in the response.
        Store it securely - it cannot be retrieved again.
    """
    try:
        pm = get_project_manager()

        # Verify project exists
        loop = asyncio.get_event_loop()
        project = await loop.run_in_executor(get_executor(), pm.get_project, project_id)

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project not found: {project_id}"
            )

        # Create API key
        from knowledgebeast.api.project_auth_middleware import get_auth_manager
        auth_manager = get_auth_manager()

        key_info = await loop.run_in_executor(
            get_executor(),
            auth_manager.create_api_key,
            project_id,
            key_data.name,
            key_data.scopes,
            key_data.expires_days,
            None  # created_by (could extract from global API key if needed)
        )

        logger.info(
            f"Created API key for project {project_id}: "
            f"{key_info['name']} (scopes: {key_info['scopes']})"
        )

        return APIKeyResponse(**key_info)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Create API key error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create API key: {str(e)}"
        )


@router_v2.get(
    "/{project_id}/api-keys",
    response_model=APIKeyListResponse,
    tags=["projects", "security"],
    summary="List project API keys",
    description="Get all API keys for a project (no raw keys included)"
)
@limiter.limit("60/minute")
async def list_project_api_keys(
    request: Request,
    project_id: str,
    api_key: str = Depends(get_api_key)
) -> APIKeyListResponse:
    """List all API keys for a project.

    Args:
        project_id: Project identifier

    Returns:
        List of API key metadata (no raw keys)

    Raises:
        HTTPException: If project not found

    Note:
        Raw API keys are never included in this response.
        Only metadata like name, scopes, and usage timestamps.
    """
    try:
        pm = get_project_manager()

        # Verify project exists
        loop = asyncio.get_event_loop()
        project = await loop.run_in_executor(get_executor(), pm.get_project, project_id)

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project not found: {project_id}"
            )

        # List API keys
        from knowledgebeast.api.project_auth_middleware import get_auth_manager
        auth_manager = get_auth_manager()

        keys = await loop.run_in_executor(
            get_executor(),
            auth_manager.list_project_keys,
            project_id
        )

        # Convert to APIKeyInfo models
        from knowledgebeast.api.models import APIKeyInfo
        api_keys = [APIKeyInfo(**key_data) for key_data in keys]

        return APIKeyListResponse(
            project_id=project_id,
            api_keys=api_keys,
            count=len(api_keys)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List API keys error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list API keys: {str(e)}"
        )


@router_v2.delete(
    "/{project_id}/api-keys/{key_id}",
    response_model=APIKeyRevokeResponse,
    tags=["projects", "security"],
    summary="Revoke project API key",
    description="Revoke an API key to immediately disable access"
)
@limiter.limit("20/minute")
async def revoke_project_api_key(
    request: Request,
    project_id: str,
    key_id: str,
    api_key: str = Depends(get_api_key)
) -> APIKeyRevokeResponse:
    """Revoke a project API key.

    Args:
        project_id: Project identifier
        key_id: API key ID to revoke

    Returns:
        Revocation status

    Raises:
        HTTPException: If project or key not found

    Note:
        Revoked keys are soft-deleted (audit trail preserved).
        The key will be immediately invalid for all requests.
    """
    try:
        pm = get_project_manager()

        # Verify project exists
        loop = asyncio.get_event_loop()
        project = await loop.run_in_executor(get_executor(), pm.get_project, project_id)

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project not found: {project_id}"
            )

        # Revoke API key
        from knowledgebeast.api.project_auth_middleware import get_auth_manager
        auth_manager = get_auth_manager()

        success = await loop.run_in_executor(
            get_executor(),
            auth_manager.revoke_api_key,
            key_id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"API key not found: {key_id}"
            )

        logger.info(f"Revoked API key {key_id} for project {project_id}")

        return APIKeyRevokeResponse(
            success=True,
            key_id=key_id,
            message=f"API key {key_id} revoked successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Revoke API key error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke API key: {str(e)}"
        )
