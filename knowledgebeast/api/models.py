"""Pydantic models for API requests and responses."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    """Request model for document ingestion."""
    
    file_path: str = Field(..., description="Path to the document to ingest")
    metadata: Optional[dict[str, Any]] = Field(None, description="Optional metadata")


class IngestResponse(BaseModel):
    """Response model for document ingestion."""
    
    success: bool = Field(..., description="Whether ingestion succeeded")
    chunks: int = Field(..., description="Number of chunks created")
    message: str = Field(..., description="Status message")


class QueryRequest(BaseModel):
    """Request model for knowledge base query."""
    
    query: str = Field(..., description="Query text", min_length=1)
    n_results: int = Field(5, description="Number of results to return", ge=1, le=100)
    use_cache: bool = Field(True, description="Whether to use cached results")


class QueryResult(BaseModel):
    """Model for a single query result."""
    
    text: str = Field(..., description="Retrieved text")
    metadata: dict[str, Any] = Field(..., description="Document metadata")
    distance: float = Field(..., description="Similarity distance")


class QueryResponse(BaseModel):
    """Response model for knowledge base query."""
    
    results: list[QueryResult] = Field(..., description="List of query results")
    cached: bool = Field(..., description="Whether results were cached")


class StatsResponse(BaseModel):
    """Response model for knowledge base statistics."""
    
    total_documents: int = Field(..., description="Total number of documents")
    cache_stats: dict[str, Any] = Field(..., description="Cache statistics")
    heartbeat_running: bool = Field(..., description="Whether heartbeat is running")
    collection_name: str = Field(..., description="ChromaDB collection name")
    embedding_model: str = Field(..., description="Embedding model name")


class HealthResponse(BaseModel):
    """Response model for health check."""
    
    status: str = Field(..., description="Health status")
    version: str = Field(..., description="KnowledgeBeast version")
