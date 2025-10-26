"""Abstract base class for vector storage backends.

This module defines the VectorBackend interface that all backend
implementations must follow. This enables swapping between ChromaDB,
Postgres+pgvector, or other vector stores without changing application code.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


class VectorBackend(ABC):
    """Abstract base class for vector storage backends.

    All backend implementations (ChromaDB, Postgres, etc.) must implement
    these methods to provide a consistent interface for vector operations.

    Design Principles:
    - Async-first: All I/O operations are async for better performance
    - Type-safe: Full type hints for IDE support and type checking
    - Minimal interface: Only essential operations required
    - Metadata support: Store and query document metadata
    - Hybrid search: Support both vector and keyword search

    Thread Safety:
        Implementations should be thread-safe and support concurrent queries.
        Initialization/close operations may require synchronization.
    """

    @abstractmethod
    async def add_documents(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        """Add documents with their embeddings to the vector store.

        Args:
            ids: Unique document identifiers
            embeddings: Document embedding vectors
            documents: Raw document text content
            metadatas: Document metadata (e.g., source, timestamp, tags)

        Raises:
            ValueError: If input lists have mismatched lengths
            RuntimeError: If backend is not initialized or connection failed
        """
        pass

    @abstractmethod
    async def query_vector(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Perform vector similarity search.

        Uses cosine similarity (or backend-specific distance metric)
        to find documents semantically similar to the query embedding.

        Args:
            query_embedding: Query vector (same dimension as documents)
            top_k: Number of results to return (default: 10)
            where: Optional metadata filters (e.g., {"source": "docs"})

        Returns:
            List of (doc_id, similarity_score, metadata) tuples,
            sorted by similarity (highest first)

        Raises:
            RuntimeError: If backend is not initialized
        """
        pass

    @abstractmethod
    async def query_keyword(
        self,
        query: str,
        top_k: int = 10,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Perform keyword/BM25 search.

        Uses traditional text search (BM25, TF-IDF, or backend-specific)
        to find documents with matching keywords.

        Args:
            query: Search query string
            top_k: Number of results to return (default: 10)
            where: Optional metadata filters

        Returns:
            List of (doc_id, relevance_score, metadata) tuples,
            sorted by relevance (highest first)

        Raises:
            RuntimeError: If backend is not initialized
        """
        pass

    @abstractmethod
    async def query_hybrid(
        self,
        query_embedding: List[float],
        query_text: str,
        top_k: int = 10,
        alpha: float = 0.7,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Perform hybrid search combining vector and keyword search.

        Uses Reciprocal Rank Fusion (RRF) or weighted score combination
        to merge results from vector and keyword search.

        Args:
            query_embedding: Query vector for semantic search
            query_text: Query string for keyword search
            top_k: Number of results to return (default: 10)
            alpha: Weight for vector search (0-1, default 0.7)
                   alpha=1.0: pure vector search
                   alpha=0.0: pure keyword search
                   alpha=0.7: balanced hybrid (recommended)
            where: Optional metadata filters

        Returns:
            List of (doc_id, combined_score, metadata) tuples,
            sorted by combined score (highest first)

        Raises:
            ValueError: If alpha not in [0, 1]
            RuntimeError: If backend is not initialized
        """
        pass

    @abstractmethod
    async def delete_documents(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Delete documents from the vector store.

        Args:
            ids: Document IDs to delete (if specified)
            where: Metadata filter for deletion (if specified)
                   At least one of ids or where must be provided

        Returns:
            Number of documents deleted

        Raises:
            ValueError: If neither ids nor where is provided
            RuntimeError: If backend is not initialized
        """
        pass

    @abstractmethod
    async def get_statistics(self) -> Dict[str, Any]:
        """Get backend statistics and metadata.

        Returns:
            Dictionary with backend info:
            {
                "backend": "chromadb" | "postgres",
                "collection": "collection_name",
                "total_documents": 1234,
                "embedding_dimension": 384,
                "storage_size_mb": 567.8,  # optional
                "index_type": "ivfflat" | "hnsw",  # optional
            }
        """
        pass

    @abstractmethod
    async def get_health(self) -> Dict[str, Any]:
        """Check backend health and availability.

        Returns:
            Dictionary with health status:
            {
                "status": "healthy" | "degraded" | "unhealthy",
                "backend_available": True | False,
                "latency_ms": 12.3,  # optional
                "error": "error message",  # if unhealthy
            }
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close backend connections and cleanup resources.

        Should be called when shutting down to properly release
        database connections, file handles, etc.

        After calling close(), the backend should not be used.
        """
        pass
