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
    rerank: bool = Field(
        default=False,
        description="Whether to apply re-ranking to improve relevance"
    )
    rerank_top_k: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Number of candidates to re-rank (must be >= limit)"
    )
    diversity: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Diversity parameter for MMR (0-1, higher = more relevance, lower = more diversity)"
    )

    @field_validator('query')
    @classmethod
    def sanitize_query(cls, v: str) -> str:
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
    rerank: bool = Field(
        default=False,
        description="Whether to apply re-ranking to improve relevance"
    )
    rerank_top_k: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Number of candidates to re-rank before pagination"
    )
    diversity: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Diversity parameter for MMR (0-1)"
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
        """Validate file path to prevent path traversal attacks.

        Note: File existence is checked in the route handler, not here,
        to allow proper 404 error responses instead of 422 validation errors.
        """
        # Check for path traversal attempts
        if '..' in v:
            raise ValueError("Path traversal detected: '..' not allowed")

        # Convert to Path object for extension checking
        try:
            path = Path(v)
        except Exception as e:
            raise ValueError(f"Invalid file path: {e}")

        # Ensure it's a valid file extension
        allowed_extensions = {'.md', '.txt', '.pdf', '.docx', '.html', '.htm'}
        if path.suffix.lower() not in allowed_extensions:
            raise ValueError(f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}")

        return v


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
    vector_score: Optional[float] = Field(None, description="Original vector similarity score (0-1)")
    rerank_score: Optional[float] = Field(None, description="Re-ranking relevance score (0-1)")
    final_score: Optional[float] = Field(None, description="Final combined score (0-1)")
    rank: Optional[int] = Field(None, description="Result rank position (1-indexed)")


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
                        "kb_dir": "/knowledge-base",
                        "vector_score": 0.87,
                        "rerank_score": 0.95,
                        "final_score": 0.95,
                        "rank": 1
                    }
                ],
                "count": 1,
                "cached": True,
                "query": "librosa audio analysis",
                "metadata": {
                    "reranked": True,
                    "rerank_model": "ms-marco-MiniLM-L-6-v2",
                    "rerank_duration_ms": 45
                }
            }
        }
    )

    results: List[QueryResult] = Field(..., description="List of matching documents")
    count: int = Field(..., description="Number of results returned")
    cached: bool = Field(..., description="Whether results were served from cache")
    query: str = Field(..., description="Original query string")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata (e.g., reranking info)"
    )


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


# ============================================================================
# Project API Models (v2)
# ============================================================================

class ProjectCreate(BaseModel):
    """Request model for creating a new project."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Audio ML Project",
                "description": "Audio processing and machine learning knowledge base",
                "embedding_model": "all-MiniLM-L6-v2",
                "metadata": {
                    "owner": "user@example.com",
                    "tags": ["audio", "ml"]
                }
            }
        }
    )

    name: str = Field(
        ...,
        description="Project name (must be unique)",
        min_length=1,
        max_length=100,
        pattern="^[a-zA-Z0-9_\\- ]+$"
    )
    description: str = Field(
        default="",
        description="Project description",
        max_length=500
    )
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Embedding model for this project"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional project metadata"
    )

    @field_validator('name')
    @classmethod
    def sanitize_project_name(cls, v: str) -> str:
        """Sanitize and validate project name."""
        v = v.strip()
        if not v:
            raise ValueError("Project name cannot be empty or only whitespace")
        return v


class ProjectUpdate(BaseModel):
    """Request model for updating a project."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Updated Project Name",
                "description": "Updated description",
                "embedding_model": "all-MiniLM-L6-v2",
                "metadata": {"updated": True}
            }
        }
    )

    name: Optional[str] = Field(
        None,
        description="New project name",
        min_length=1,
        max_length=100,
        pattern="^[a-zA-Z0-9_\\- ]+$"
    )
    description: Optional[str] = Field(
        None,
        description="New description",
        max_length=500
    )
    embedding_model: Optional[str] = Field(
        None,
        description="New embedding model"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="New metadata"
    )


class ProjectResponse(BaseModel):
    """Response model for project data."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "project_id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Audio ML Project",
                "description": "Audio processing knowledge base",
                "collection_name": "kb_project_550e8400-e29b-41d4-a716-446655440000",
                "embedding_model": "all-MiniLM-L6-v2",
                "created_at": "2025-10-07T12:00:00",
                "updated_at": "2025-10-07T12:00:00",
                "metadata": {"owner": "user@example.com"}
            }
        }
    )

    project_id: str = Field(..., description="Unique project identifier")
    name: str = Field(..., description="Project name")
    description: str = Field(..., description="Project description")
    collection_name: str = Field(..., description="ChromaDB collection name")
    embedding_model: str = Field(..., description="Embedding model")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    metadata: Dict[str, Any] = Field(..., description="Project metadata")


class ProjectListResponse(BaseModel):
    """Response model for listing projects."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "projects": [
                    {
                        "project_id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "Audio ML Project",
                        "description": "Audio processing",
                        "collection_name": "kb_project_550e8400-e29b-41d4-a716-446655440000",
                        "embedding_model": "all-MiniLM-L6-v2",
                        "created_at": "2025-10-07T12:00:00",
                        "updated_at": "2025-10-07T12:00:00",
                        "metadata": {}
                    }
                ],
                "count": 1
            }
        }
    )

    projects: List[ProjectResponse] = Field(..., description="List of projects")
    count: int = Field(..., description="Number of projects")


class ProjectQueryRequest(BaseModel):
    """Request model for project-scoped query."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "audio processing techniques",
                "use_cache": True,
                "limit": 10
            }
        }
    )

    query: str = Field(
        ...,
        description="Search query string",
        min_length=1,
        max_length=1000
    )
    use_cache: bool = Field(
        default=True,
        description="Whether to use cached results"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results (1-100)"
    )
    rerank: bool = Field(
        default=False,
        description="Whether to apply re-ranking to improve relevance"
    )
    rerank_top_k: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Number of candidates to re-rank before limiting results"
    )
    diversity: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Diversity parameter for MMR (0-1)"
    )

    @field_validator('query')
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        """Sanitize query string."""
        dangerous_chars = ['<', '>', ';', '&', '|', '$', '`', '\n', '\r']
        for char in dangerous_chars:
            if char in v:
                raise ValueError(f"Query contains invalid character: {char}")
        v = v.strip()
        if not v:
            raise ValueError("Query cannot be empty or only whitespace")
        return v


class ProjectIngestRequest(BaseModel):
    """Request model for project-scoped document ingestion."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_path": "/path/to/document.md",
                "content": "Document content here...",
                "metadata": {"category": "audio"}
            }
        }
    )

    file_path: Optional[str] = Field(
        None,
        description="Path to document file (if ingesting from file)"
    )
    content: Optional[str] = Field(
        None,
        description="Document content (if ingesting directly)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Document metadata"
    )

    @field_validator('file_path')
    @classmethod
    def validate_file_path_optional(cls, v: Optional[str]) -> Optional[str]:
        """Validate file path if provided."""
        if v is None:
            return None

        try:
            path = Path(v).resolve()
        except Exception as e:
            raise ValueError(f"Invalid file path: {e}")

        if '..' in v:
            raise ValueError("Path traversal detected: '..' not allowed")

        allowed_extensions = {'.md', '.txt', '.pdf', '.docx', '.html', '.htm'}
        if path.suffix.lower() not in allowed_extensions:
            raise ValueError(f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}")

        return str(path)


class ProjectDeleteResponse(BaseModel):
    """Response model for project deletion."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "project_id": "550e8400-e29b-41d4-a716-446655440000",
                "message": "Project deleted successfully"
            }
        }
    )

    success: bool = Field(..., description="Whether deletion succeeded")
    project_id: str = Field(..., description="Deleted project ID")
    message: str = Field(..., description="Status message")


class ProjectExportResponse(BaseModel):
    """Response model for project export."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "project_id": "550e8400-e29b-41d4-a716-446655440000",
                "export_path": "/tmp/project_export_1234567890.zip",
                "document_count": 42,
                "file_size_bytes": 1048576,
                "message": "Project exported successfully"
            }
        }
    )

    success: bool = Field(..., description="Whether export succeeded")
    project_id: str = Field(..., description="Exported project ID")
    export_path: str = Field(..., description="Path to export ZIP file")
    document_count: int = Field(..., description="Number of documents exported")
    file_size_bytes: int = Field(..., description="Export file size in bytes")
    message: str = Field(..., description="Status message")


class ProjectImportRequest(BaseModel):
    """Request model for project import."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "new_name": "Restored Project",
                "overwrite": False
            }
        }
    )

    new_name: Optional[str] = Field(
        None,
        description="Optional new name for imported project",
        min_length=1,
        max_length=100
    )
    overwrite: bool = Field(
        default=False,
        description="Whether to overwrite existing project with same name"
    )


class ProjectImportResponse(BaseModel):
    """Response model for project import."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "project_id": "550e8400-e29b-41d4-a716-446655440000",
                "project_name": "Restored Project",
                "document_count": 42,
                "message": "Project imported successfully"
            }
        }
    )

    success: bool = Field(..., description="Whether import succeeded")
    project_id: str = Field(..., description="Imported project ID")
    project_name: str = Field(..., description="Imported project name")
    document_count: int = Field(..., description="Number of documents imported")
    message: str = Field(..., description="Status message")


# ============================================================================
# Multi-Modal API Models
# ============================================================================

class MultiModalUploadRequest(BaseModel):
    """Request model for multi-modal document upload."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_path": "/path/to/document.pdf",
                "file_type": "pdf",
                "extract_images": True,
                "use_ocr": False,
                "generate_embeddings": True,
                "metadata": {"category": "research"}
            }
        }
    )

    file_path: str = Field(
        ...,
        description="Path to file to process"
    )
    file_type: Optional[str] = Field(
        None,
        description="File type override (auto-detected if not provided)"
    )
    extract_images: bool = Field(
        default=False,
        description="Extract images from PDFs"
    )
    use_ocr: bool = Field(
        default=False,
        description="Use OCR for text extraction from images/scanned PDFs"
    )
    generate_embeddings: bool = Field(
        default=True,
        description="Generate CLIP embeddings for images"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata"
    )

    @field_validator('file_path')
    @classmethod
    def validate_multimodal_file_path(cls, v: str) -> str:
        """Validate file path for multi-modal upload."""
        if '..' in v:
            raise ValueError("Path traversal detected: '..' not allowed")

        try:
            path = Path(v)
        except Exception as e:
            raise ValueError(f"Invalid file path: {e}")

        # Multimodal supported extensions
        allowed_extensions = {
            '.pdf', '.md', '.txt', '.docx', '.html', '.htm',  # Documents
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp',  # Images
            '.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs'  # Code
        }

        if path.suffix.lower() not in allowed_extensions:
            raise ValueError(
                f"Unsupported file type: {path.suffix}. "
                f"Supported: {', '.join(sorted(allowed_extensions))}"
            )

        return v


class MultiModalUploadResponse(BaseModel):
    """Response model for multi-modal document upload."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "document_id": "doc_123",
                "file_type": "pdf",
                "file_path": "/path/to/document.pdf",
                "chunks_created": 15,
                "images_extracted": 3,
                "has_embeddings": True,
                "processing_time_ms": 1250,
                "metadata": {"pages": 10}
            }
        }
    )

    success: bool = Field(..., description="Whether upload succeeded")
    document_id: str = Field(..., description="Generated document ID")
    file_type: str = Field(..., description="Detected/specified file type")
    file_path: str = Field(..., description="Path to processed file")
    chunks_created: int = Field(..., description="Number of text chunks created")
    images_extracted: int = Field(
        default=0,
        description="Number of images extracted (PDFs only)"
    )
    has_embeddings: bool = Field(
        default=False,
        description="Whether embeddings were generated"
    )
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    metadata: Dict[str, Any] = Field(..., description="Document metadata")


class MultiModalQueryRequest(BaseModel):
    """Request model for multi-modal search."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "machine learning algorithms",
                "modalities": ["text", "image", "code"],
                "code_language": "python",
                "use_cache": True,
                "limit": 10
            }
        }
    )

    query: str = Field(
        ...,
        description="Search query (text or image path for image search)",
        min_length=1,
        max_length=1000
    )
    modalities: Optional[List[str]] = Field(
        default=None,
        description="Filter by modalities: text, image, code"
    )
    code_language: Optional[str] = Field(
        None,
        description="Filter code files by language (e.g., 'python', 'javascript')"
    )
    use_cache: bool = Field(
        default=True,
        description="Whether to use cached results"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results"
    )

    @field_validator('modalities')
    @classmethod
    def validate_modalities(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate modality filters."""
        if v is None:
            return None

        allowed_modalities = {'text', 'image', 'code', 'document'}
        for modality in v:
            if modality not in allowed_modalities:
                raise ValueError(
                    f"Invalid modality: {modality}. "
                    f"Allowed: {', '.join(sorted(allowed_modalities))}"
                )

        return v

    @field_validator('query')
    @classmethod
    def sanitize_multimodal_query(cls, v: str) -> str:
        """Sanitize query string."""
        dangerous_chars = ['<', '>', ';', '&', '|', '$', '`', '\n', '\r']
        for char in dangerous_chars:
            if char in v:
                raise ValueError(f"Query contains invalid character: {char}")
        v = v.strip()
        if not v:
            raise ValueError("Query cannot be empty or only whitespace")
        return v


# ============================================================================
# Project API Key Management Models (v2 Security)
# ============================================================================

class APIKeyCreate(BaseModel):
    """Request model for creating a project API key."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Mobile App Key",
                "scopes": ["read"],
                "expires_days": 90
            }
        }
    )

    name: str = Field(
        ...,
        description="Human-readable key name",
        min_length=1,
        max_length=100
    )
    scopes: List[str] = Field(
        default=["read", "write"],
        description="Permission scopes: read, write, admin"
    )
    expires_days: Optional[int] = Field(
        default=None,
        ge=1,
        le=365,
        description="Key expiration in days (None = never expires)"
    )

    @field_validator('name')
    @classmethod
    def sanitize_key_name(cls, v: str) -> str:
        """Sanitize key name."""
        v = v.strip()
        if not v:
            raise ValueError("Key name cannot be empty or only whitespace")
        return v

    @field_validator('scopes')
    @classmethod
    def validate_scopes(cls, v: List[str]) -> List[str]:
        """Validate permission scopes."""
        valid_scopes = {"read", "write", "admin"}
        invalid_scopes = set(v) - valid_scopes
        if invalid_scopes:
            raise ValueError(
                f"Invalid scopes: {invalid_scopes}. "
                f"Valid scopes: {valid_scopes}"
            )
        if not v:
            raise ValueError("At least one scope is required")
        return v


class APIKeyResponse(BaseModel):
    """Response model for API key creation (includes raw key ONCE)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "key_id": "key_abc123xyz",
                "api_key": "kb_vL9x2K8pQ7mR4nS6tU0wY1zA3bC5dE7fG9h",
                "project_id": "proj_123",
                "name": "Mobile App Key",
                "scopes": ["read"],
                "created_at": "2025-10-09T12:00:00",
                "expires_at": "2026-01-09T12:00:00"
            }
        }
    )

    key_id: str = Field(..., description="Unique key identifier (for revocation)")
    api_key: str = Field(..., description="Raw API key (ONLY shown once!)")
    project_id: str = Field(..., description="Project this key grants access to")
    name: str = Field(..., description="Key name")
    scopes: List[str] = Field(..., description="Permission scopes")
    created_at: str = Field(..., description="Creation timestamp")
    expires_at: Optional[str] = Field(None, description="Expiration timestamp")


class APIKeyInfo(BaseModel):
    """Model for API key metadata (NO raw key included)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "key_id": "key_abc123xyz",
                "name": "Mobile App Key",
                "scopes": ["read"],
                "created_at": "2025-10-09T12:00:00",
                "expires_at": "2026-01-09T12:00:00",
                "revoked": False,
                "last_used_at": "2025-10-09T14:30:00",
                "created_by": "admin@example.com"
            }
        }
    )

    key_id: str = Field(..., description="Unique key identifier")
    name: str = Field(..., description="Key name")
    scopes: List[str] = Field(..., description="Permission scopes")
    created_at: str = Field(..., description="Creation timestamp")
    expires_at: Optional[str] = Field(None, description="Expiration timestamp")
    revoked: bool = Field(..., description="Whether key is revoked")
    last_used_at: Optional[str] = Field(None, description="Last usage timestamp")
    created_by: Optional[str] = Field(None, description="Creator username/email")


class APIKeyListResponse(BaseModel):
    """Response model for listing project API keys."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "project_id": "proj_123",
                "api_keys": [
                    {
                        "key_id": "key_abc123",
                        "name": "Mobile App",
                        "scopes": ["read"],
                        "created_at": "2025-10-09T12:00:00",
                        "expires_at": None,
                        "revoked": False,
                        "last_used_at": "2025-10-09T14:30:00",
                        "created_by": "admin@example.com"
                    }
                ],
                "count": 1
            }
        }
    )

    project_id: str = Field(..., description="Project identifier")
    api_keys: List[APIKeyInfo] = Field(..., description="List of API keys")
    count: int = Field(..., description="Number of keys")


class APIKeyRevokeResponse(BaseModel):
    """Response model for API key revocation."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "key_id": "key_abc123",
                "message": "API key revoked successfully"
            }
        }
    )

    success: bool = Field(..., description="Whether revocation succeeded")
    key_id: str = Field(..., description="Revoked key ID")
    message: str = Field(..., description="Status message")
