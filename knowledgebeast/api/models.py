"""Pydantic models for KnowledgeBeast API requests and responses.

All models use Pydantic v2 syntax with comprehensive validation,
field descriptions, and examples for OpenAPI documentation.
"""

import re
from typing import Any, Dict, List, Optional
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, field_validator, ValidationError


# ============================================================================
# Request Models
# ============================================================================

class QueryRequest(BaseModel):
    """Request model for querying the knowledge base (legacy, without pagination metadata)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "How do I use librosa for audio analysis?",
                "use_cache": True,
                "limit": 10,
                "offset": 0
            }
        }
    )

    query: str = Field(
        ...,
        description="Search query string",
        min_length=1,
        max_length=1000,
        examples=["audio processing best practices"]
    )
    use_cache: bool = Field(
        default=True,
        description="Whether to use cached results if available"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results to return (1-100)"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of results to skip for pagination"
    )


class PaginatedQueryRequest(BaseModel):
    """Request model for querying the knowledge base with pagination support."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "How do I use librosa for audio analysis?",
                "use_cache": True,
                "page": 1,
                "page_size": 10
            }
        }
    )

    query: str = Field(
        ...,
        description="Search query string",
        min_length=1,
        max_length=1000,
        examples=["audio processing best practices"]
    )
    use_cache: bool = Field(
        default=True,
        description="Whether to use cached results if available"
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Page number (1-indexed)"
    )
    page_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of results per page (1-100)"
    )

    @field_validator('query')
    @classmethod
    def sanitize_paginated_query(cls, v: str) -> str:
        """Sanitize query string to prevent injection attacks."""
        # Remove potentially dangerous characters
        dangerous_chars = ['<', '>', ';', '&', '|', '$', '`', '\n', '\r']
        for char in dangerous_chars:
            if char in v:
                raise ValueError(f"Query contains invalid character: {char}")

        # Strip whitespace
        v = v.strip()

        # Ensure not empty after stripping
        if not v:
            raise ValueError("Query cannot be empty or only whitespace")

        return v


class IngestRequest(BaseModel):
    """Request model for ingesting a single document."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_path": "/path/to/document.md",
                "metadata": {
                    "category": "audio",
                    "tags": ["librosa", "tutorial"]
                }
            }
        }
    )

    file_path: str = Field(
        ...,
        description="Absolute path to the document file",
        examples=["/knowledge-base/audio/librosa-guide.md"]
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata to attach to the document"
    )

    @field_validator('file_path')
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        """Validate file path to prevent path traversal attacks."""
        # Convert to Path object
        try:
            path = Path(v).resolve()
        except Exception as e:
            raise ValueError(f"Invalid file path: {e}")

        # Check for path traversal attempts
        if '..' in v:
            raise ValueError("Path traversal detected: '..' not allowed")

        # Ensure it's a valid file extension
        allowed_extensions = {'.md', '.txt', '.pdf', '.docx', '.html', '.htm'}
        if path.suffix.lower() not in allowed_extensions:
            raise ValueError(f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}")

        # Check file exists
        if not path.exists():
            raise ValueError(f"File does not exist: {path}")

        # Check it's a file (not directory)
        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")

        return str(path)


class BatchIngestRequest(BaseModel):
    """Request model for batch ingestion of multiple documents."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_paths": [
                    "/knowledge-base/audio/doc1.md",
                    "/knowledge-base/audio/doc2.md"
                ],
                "metadata": {"batch": "audio-docs"}
            }
        }
    )

    file_paths: List[str] = Field(
        ...,
        description="List of absolute paths to document files",
        min_length=1,
        max_length=100
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata to attach to all documents"
    )


class WarmRequest(BaseModel):
    """Request model for triggering knowledge base warming."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "force_rebuild": False
            }
        }
    )

    force_rebuild: bool = Field(
        default=False,
        description="Force rebuild of the index before warming"
    )


class CollectionRequest(BaseModel):
    """Request model for collection operations."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "my-collection"
            }
        }
    )

    name: str = Field(
        ...,
        description="Collection name",
        min_length=1,
        max_length=100,
        pattern="^[a-zA-Z0-9_-]+$"
    )


# ============================================================================
# Response Models
# ============================================================================

class QueryResult(BaseModel):
    """Model for a single query result."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "doc_id": "knowledge-base/audio/librosa.md",
                "content": "Librosa is a Python package for music and audio analysis...",
                "name": "Librosa Guide",
                "path": "/Users/user/knowledge-base/audio/librosa.md",
                "kb_dir": "/Users/user/knowledge-base"
            }
        }
    )

    doc_id: str = Field(..., description="Document ID/path")
    content: str = Field(..., description="Document content")
    name: str = Field(..., description="Document name")
    path: str = Field(..., description="Full file path")
    kb_dir: str = Field(..., description="Knowledge base directory")


class QueryResponse(BaseModel):
    """Response model for query endpoint (legacy, without pagination metadata)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "results": [
                    {
                        "doc_id": "knowledge-base/audio/librosa.md",
                        "content": "Librosa guide...",
                        "name": "Librosa Guide",
                        "path": "/path/to/librosa.md",
                        "kb_dir": "/knowledge-base"
                    }
                ],
                "count": 1,
                "cached": True,
                "query": "librosa audio analysis"
            }
        }
    )

    results: List[QueryResult] = Field(..., description="List of matching documents")
    count: int = Field(..., description="Number of results returned")
    cached: bool = Field(..., description="Whether results were served from cache")
    query: str = Field(..., description="Original query string")


class PaginationMetadata(BaseModel):
    """Pagination metadata for query results."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_results": 42,
                "total_pages": 5,
                "current_page": 1,
                "page_size": 10,
                "has_next": True,
                "has_previous": False
            }
        }
    )

    total_results: int = Field(..., description="Total number of results across all pages")
    total_pages: int = Field(..., description="Total number of pages")
    current_page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of results per page")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_previous: bool = Field(..., description="Whether there is a previous page")


class PaginatedQueryResponse(BaseModel):
    """Response model for paginated query endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "results": [
                    {
                        "doc_id": "knowledge-base/audio/librosa.md",
                        "content": "Librosa guide...",
                        "name": "Librosa Guide",
                        "path": "/path/to/librosa.md",
                        "kb_dir": "/knowledge-base"
                    }
                ],
                "count": 10,
                "cached": True,
                "query": "librosa audio analysis",
                "pagination": {
                    "total_results": 42,
                    "total_pages": 5,
                    "current_page": 1,
                    "page_size": 10,
                    "has_next": True,
                    "has_previous": False
                }
            }
        }
    )

    results: List[QueryResult] = Field(..., description="List of matching documents for current page")
    count: int = Field(..., description="Number of results in current page")
    cached: bool = Field(..., description="Whether results were served from cache")
    query: str = Field(..., description="Original query string")
    pagination: PaginationMetadata = Field(..., description="Pagination metadata")


class IngestResponse(BaseModel):
    """Response model for document ingestion."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "file_path": "/knowledge-base/doc.md",
                "doc_id": "knowledge-base/doc.md",
                "message": "Successfully ingested document"
            }
        }
    )

    success: bool = Field(..., description="Whether ingestion succeeded")
    file_path: str = Field(..., description="Path to ingested file")
    doc_id: str = Field(..., description="Generated document ID")
    message: str = Field(..., description="Status message")


class BatchIngestResponse(BaseModel):
    """Response model for batch ingestion."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "total_files": 10,
                "successful": 9,
                "failed": 1,
                "failed_files": ["/path/to/failed.md"],
                "message": "Batch ingestion completed: 9/10 successful"
            }
        }
    )

    success: bool = Field(..., description="Overall success status")
    total_files: int = Field(..., description="Total number of files processed")
    successful: int = Field(..., description="Number of successful ingestions")
    failed: int = Field(..., description="Number of failed ingestions")
    failed_files: List[str] = Field(
        default_factory=list,
        description="List of files that failed to ingest"
    )
    message: str = Field(..., description="Summary message")


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "version": "0.1.0",
                "kb_initialized": True,
                "timestamp": "2025-10-05T12:00:00Z"
            }
        }
    )

    status: str = Field(..., description="Health status (healthy/degraded/unhealthy)")
    version: str = Field(..., description="KnowledgeBeast version")
    kb_initialized: bool = Field(..., description="Whether knowledge base is initialized")
    timestamp: str = Field(..., description="Response timestamp (ISO 8601)")


class StatsResponse(BaseModel):
    """Response model for statistics endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "queries": 150,
                "cache_hits": 100,
                "cache_misses": 50,
                "cache_hit_rate": "66.7%",
                "warm_queries": 7,
                "last_warm_time": 2.5,
                "total_documents": 42,
                "total_terms": 1523,
                "documents": 42,
                "terms": 1523,
                "cached_queries": 25,
                "last_access_age": "5.2s ago",
                "knowledge_dirs": ["/knowledge-base"]
            }
        }
    )

    queries: int = Field(..., description="Total number of queries")
    cache_hits: int = Field(..., description="Number of cache hits")
    cache_misses: int = Field(..., description="Number of cache misses")
    cache_hit_rate: str = Field(..., description="Cache hit rate percentage")
    warm_queries: int = Field(..., description="Number of warming queries executed")
    last_warm_time: Optional[float] = Field(None, description="Last warming time in seconds")
    total_documents: int = Field(..., description="Total documents in knowledge base")
    total_terms: int = Field(..., description="Total indexed terms")
    documents: int = Field(..., description="Current document count")
    terms: int = Field(..., description="Current term count")
    cached_queries: int = Field(..., description="Number of cached queries")
    last_access_age: str = Field(..., description="Time since last access")
    knowledge_dirs: List[str] = Field(..., description="List of knowledge directories")
    total_queries: int = Field(..., description="Total queries (hits + misses)")


class HeartbeatStatusResponse(BaseModel):
    """Response model for heartbeat status endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "running": True,
                "interval": 300,
                "heartbeat_count": 12,
                "last_heartbeat": "30s ago"
            }
        }
    )

    running: bool = Field(..., description="Whether heartbeat is running")
    interval: int = Field(..., description="Heartbeat interval in seconds")
    heartbeat_count: int = Field(..., description="Number of heartbeats executed")
    last_heartbeat: Optional[str] = Field(
        None,
        description="Time since last heartbeat"
    )


class HeartbeatActionResponse(BaseModel):
    """Response model for heartbeat start/stop actions."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Heartbeat started successfully",
                "running": True
            }
        }
    )

    success: bool = Field(..., description="Whether action succeeded")
    message: str = Field(..., description="Action result message")
    running: bool = Field(..., description="Current heartbeat running status")


class CacheClearResponse(BaseModel):
    """Response model for cache clear endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "cleared_count": 25,
                "message": "Cache cleared: 25 entries removed"
            }
        }
    )

    success: bool = Field(..., description="Whether cache clear succeeded")
    cleared_count: int = Field(..., description="Number of cache entries cleared")
    message: str = Field(..., description="Status message")


class WarmResponse(BaseModel):
    """Response model for warming endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "warm_time": 2.5,
                "queries_executed": 7,
                "documents_loaded": 42,
                "message": "Knowledge base warmed in 2.5s"
            }
        }
    )

    success: bool = Field(..., description="Whether warming succeeded")
    warm_time: float = Field(..., description="Warming time in seconds")
    queries_executed: int = Field(..., description="Number of warming queries executed")
    documents_loaded: int = Field(..., description="Number of documents loaded")
    message: str = Field(..., description="Status message")


class CollectionInfo(BaseModel):
    """Model for collection information."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "knowledge-base",
                "document_count": 42,
                "term_count": 1523,
                "cache_size": 25
            }
        }
    )

    name: str = Field(..., description="Collection name")
    document_count: int = Field(..., description="Number of documents")
    term_count: int = Field(..., description="Number of indexed terms")
    cache_size: int = Field(..., description="Number of cached queries")


class CollectionsResponse(BaseModel):
    """Response model for collections list endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "collections": [
                    {
                        "name": "knowledge-base",
                        "document_count": 42,
                        "term_count": 1523,
                        "cache_size": 25
                    }
                ],
                "count": 1
            }
        }
    )

    collections: List[CollectionInfo] = Field(..., description="List of collections")
    count: int = Field(..., description="Number of collections")


class ErrorResponse(BaseModel):
    """Standard error response model."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "ValidationError",
                "message": "Query string cannot be empty",
                "detail": "Field 'query' is required and must be non-empty",
                "status_code": 400
            }
        }
    )

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    status_code: int = Field(..., description="HTTP status code")
