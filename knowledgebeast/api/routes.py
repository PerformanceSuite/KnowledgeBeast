"""API routes for KnowledgeBeast."""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from knowledgebeast import __version__
from knowledgebeast.api.models import (
    HealthResponse,
    IngestRequest,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    QueryResult,
    StatsResponse,
)
from knowledgebeast.core.engine import KnowledgeBeast

logger = logging.getLogger(__name__)

router = APIRouter()


def get_engine() -> KnowledgeBeast:
    """Get or create the global KnowledgeBeast engine instance."""
    if not hasattr(get_engine, "_engine"):
        get_engine._engine = KnowledgeBeast()
    return get_engine._engine


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint.
    
    Returns:
        Health status and version information
    """
    return HealthResponse(status="healthy", version=__version__)


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(request: IngestRequest) -> IngestResponse:
    """Ingest a document into the knowledge base.
    
    Args:
        request: Ingestion request with file path and metadata
        
    Returns:
        Ingestion response with status and chunk count
        
    Raises:
        HTTPException: If ingestion fails
    """
    try:
        engine = get_engine()
        file_path = Path(request.file_path)
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
        
        chunks = engine.ingest_document(file_path, request.metadata)
        
        return IngestResponse(
            success=True,
            chunks=chunks,
            message=f"Successfully ingested {chunks} chunks from {file_path.name}"
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Ingestion error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=QueryResponse)
async def query_knowledge_base(request: QueryRequest) -> QueryResponse:
    """Query the knowledge base.
    
    Args:
        request: Query request with query text and parameters
        
    Returns:
        Query response with results
        
    Raises:
        HTTPException: If query fails
    """
    try:
        engine = get_engine()
        
        # Check if results were cached before query
        cache_key = f"{request.query}:{request.n_results}"
        was_cached = cache_key in engine.cache
        
        results = engine.query(
            request.query,
            n_results=request.n_results,
            use_cache=request.use_cache
        )
        
        query_results = [
            QueryResult(
                text=r["text"],
                metadata=r["metadata"],
                distance=r["distance"]
            )
            for r in results
        ]
        
        return QueryResponse(results=query_results, cached=was_cached)
    except Exception as e:
        logger.error(f"Query error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    """Get knowledge base statistics.
    
    Returns:
        Statistics about the knowledge base
    """
    try:
        engine = get_engine()
        stats = engine.get_stats()
        
        return StatsResponse(
            total_documents=stats["total_documents"],
            cache_stats=stats["cache_stats"],
            heartbeat_running=stats["heartbeat_running"],
            collection_name=stats["collection_name"],
            embedding_model=stats["embedding_model"]
        )
    except Exception as e:
        logger.error(f"Stats error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear")
async def clear_knowledge_base() -> dict[str, str]:
    """Clear all documents from the knowledge base.
    
    Returns:
        Confirmation message
        
    Raises:
        HTTPException: If clearing fails
    """
    try:
        engine = get_engine()
        engine.clear()
        return {"message": "Knowledge base cleared successfully"}
    except Exception as e:
        logger.error(f"Clear error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
