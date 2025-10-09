"""Vector store implementation using ChromaDB for persistent vector search.

This module provides the VectorStore class for managing vector embeddings
with ChromaDB, including collection CRUD operations and similarity search.

Features:
- Circuit breaker protection for all ChromaDB operations
- Automatic retry with exponential backoff for transient failures
- Graceful degradation when ChromaDB is unavailable
- Comprehensive metrics and health monitoring
"""

import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import chromadb
import numpy as np
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from knowledgebeast.core.circuit_breaker import CircuitBreaker, CircuitBreakerError
from knowledgebeast.core.retry_logic import chromadb_retry
from knowledgebeast.utils.observability import get_tracer

logger = logging.getLogger(__name__)


class VectorStore:
    """Thread-safe vector store using ChromaDB for persistent storage.

    Provides a high-level interface for storing and querying vector embeddings
    with metadata, supporting both in-memory and persistent storage modes.

    Features:
    - Persistent storage with ChromaDB
    - Collection management (create, get, delete, list)
    - Batch operations for performance
    - Metadata filtering
    - Similarity search with configurable metrics
    - Thread-safe operations

    Attributes:
        persist_directory: Path to persistent storage (None for in-memory)
        client: ChromaDB client instance
        collection_name: Active collection name
        collection: Active ChromaDB collection
        stats: Operation statistics
    """

    def __init__(
        self,
        persist_directory: Optional[Union[str, Path]] = None,
        collection_name: str = "default",
        embedding_function: Optional[Any] = None,
        enable_circuit_breaker: bool = True,
        circuit_breaker_threshold: int = 5,
    ) -> None:
        """Initialize the vector store.

        Args:
            persist_directory: Directory for persistent storage (None for in-memory)
            collection_name: Name of the collection to use
            embedding_function: Custom embedding function (optional)
            enable_circuit_breaker: Enable circuit breaker protection (default: True)
            circuit_breaker_threshold: Failures before opening circuit (default: 5)
        """
        self.persist_directory = Path(persist_directory) if persist_directory else None
        self._lock = threading.RLock()

        # Circuit breaker for fault tolerance
        self.circuit_breaker = CircuitBreaker(
            name="chromadb",
            failure_threshold=circuit_breaker_threshold,
            failure_window=60,  # 60 second window
            recovery_timeout=30,  # 30 second recovery
            expected_exception=Exception,
        ) if enable_circuit_breaker else None

        # Initialize ChromaDB client with retry
        self.client = self._initialize_client()

        # Statistics
        self.stats = {
            "total_documents": 0,
            "total_queries": 0,
            "total_collections": 0,
            "total_adds": 0,
            "total_deletes": 0,
            "circuit_breaker_opens": 0,
            "circuit_breaker_errors": 0,
        }

        # Create or get collection
        self.collection_name = collection_name
        self.collection = self._get_or_create_collection(
            collection_name, embedding_function
        )

        # Update stats
        try:
            with self._lock:
                self.stats["total_documents"] = self._safe_count()
                self.stats["total_collections"] = len(self._safe_list_collections())
        except Exception as e:
            logger.warning(f"Failed to initialize stats: {e}")

    def _initialize_client(self) -> chromadb.Client:
        """Initialize ChromaDB client with retry logic.

        Returns:
            ChromaDB client instance

        Raises:
            Exception: If client initialization fails after retries
        """
        @chromadb_retry(max_attempts=3, initial_wait=1.0)
        def create_client() -> chromadb.Client:
            if self.persist_directory:
                self.persist_directory.mkdir(parents=True, exist_ok=True)
                settings = Settings(
                    persist_directory=str(self.persist_directory),
                    anonymized_telemetry=False,
                )
                return chromadb.PersistentClient(settings=settings)
            else:
                return chromadb.Client()

        return create_client()

    def _execute_with_protection(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
            Exception: Original exception from function
        """
        if self.circuit_breaker:
            try:
                return self.circuit_breaker.call(func, *args, **kwargs)
            except CircuitBreakerError:
                with self._lock:
                    self.stats["circuit_breaker_errors"] += 1
                    # Check if circuit just opened
                    cb_stats = self.circuit_breaker.get_stats()
                    if cb_stats["state"] == "open":
                        self.stats["circuit_breaker_opens"] += 1
                raise
        else:
            return func(*args, **kwargs)

    def _safe_count(self) -> int:
        """Get collection count with retry logic.

        Returns:
            Document count, or 0 on failure
        """
        @chromadb_retry(max_attempts=3)
        def count_docs():
            return self.collection.count()

        try:
            return self._execute_with_protection(count_docs)
        except Exception as e:
            logger.warning(f"Failed to count documents: {e}")
            return 0

    def _safe_list_collections(self) -> List:
        """List collections with retry logic.

        Returns:
            List of collections, or empty list on failure
        """
        @chromadb_retry(max_attempts=3)
        def list_colls():
            return self.client.list_collections()

        try:
            return self._execute_with_protection(list_colls)
        except Exception as e:
            logger.warning(f"Failed to list collections: {e}")
            return []

    def _get_or_create_collection(
        self,
        name: str,
        embedding_function: Optional[Any] = None,
    ) -> Any:
        """Get existing collection or create new one with retry logic.

        Args:
            name: Collection name
            embedding_function: Custom embedding function

        Returns:
            ChromaDB collection
        """
        @chromadb_retry(max_attempts=3, initial_wait=1.0)
        def get_or_create():
            try:
                return self.client.get_collection(
                    name=name,
                    embedding_function=embedding_function,
                )
            except Exception:
                return self.client.create_collection(
                    name=name,
                    embedding_function=embedding_function,
                    metadata={"created_at": time.time()},
                )

        return self._execute_with_protection(get_or_create)

    def add(
        self,
        ids: Union[str, List[str]],
        embeddings: Union[np.ndarray, List[np.ndarray]],
        documents: Optional[Union[str, List[str]]] = None,
        metadatas: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
    ) -> None:
        """Add embeddings to the collection.

        Args:
            ids: Single ID or list of IDs
            embeddings: Single embedding or list of embeddings
            documents: Optional document texts
            metadatas: Optional metadata dictionaries

        Raises:
            ValueError: If inputs have mismatched lengths
        """
        # Normalize inputs to lists
        if isinstance(ids, str):
            ids = [ids]
        if isinstance(embeddings, np.ndarray) and embeddings.ndim == 1:
            embeddings = [embeddings]
        if isinstance(documents, str):
            documents = [documents]
        if isinstance(metadatas, dict):
            metadatas = [metadatas]

        # Convert numpy arrays to lists for ChromaDB
        embeddings_list = [
            emb.tolist() if isinstance(emb, np.ndarray) else emb
            for emb in embeddings
        ]

        # Validate lengths
        if len(ids) != len(embeddings_list):
            raise ValueError("Number of ids must match number of embeddings")
        if documents is not None and len(documents) != len(ids):
            raise ValueError("Number of documents must match number of ids")
        if metadatas is not None and len(metadatas) != len(ids):
            raise ValueError("Number of metadatas must match number of ids")

        # Add to collection
        with self._lock:
            self.collection.add(
                ids=ids,
                embeddings=embeddings_list,
                documents=documents,
                metadatas=metadatas,
            )
            self.stats["total_adds"] += len(ids)
            self.stats["total_documents"] = self.collection.count()

    def query(
        self,
        query_embeddings: Union[np.ndarray, List[np.ndarray]],
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Query the collection for similar vectors with circuit breaker protection.

        Args:
            query_embeddings: Query embedding(s)
            n_results: Number of results to return
            where: Metadata filter
            where_document: Document text filter
            include: Fields to include in results

        Returns:
            Dictionary with 'ids', 'distances', 'embeddings', 'metadatas', 'documents'

        Raises:
            CircuitBreakerError: If circuit breaker is open
        """
        tracer = get_tracer()
        with tracer.start_as_current_span("vector_store.query") as span:
            # Normalize query embeddings
            if isinstance(query_embeddings, np.ndarray) and query_embeddings.ndim == 1:
                query_embeddings = [query_embeddings]

            # Add span attributes
            span.set_attribute("vector_store.collection", self.collection_name)
            span.set_attribute("vector_store.n_results", n_results)
            span.set_attribute("vector_store.num_queries", len(query_embeddings))
            span.set_attribute("vector_store.has_where_filter", where is not None)
            span.set_attribute("vector_store.has_document_filter", where_document is not None)

            # Convert numpy arrays to lists
            query_list = [
                emb.tolist() if isinstance(emb, np.ndarray) else emb
                for emb in query_embeddings
            ]

            # Default includes
            if include is None:
                include = ["distances", "metadatas", "documents"]

            with self._lock:
                self.stats["total_queries"] += 1
                results = self.collection.query(
                    query_embeddings=query_list,
                    n_results=n_results,
                    where=where,
                    where_document=where_document,
                    include=include,
                )

            # Add result statistics to span
            if results and "ids" in results:
                span.set_attribute("vector_store.results_returned", len(results["ids"][0]))

            return results

    def get(
        self,
        ids: Optional[Union[str, List[str]]] = None,
        where: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get documents by IDs or filter.

        Args:
            ids: Document IDs to retrieve
            where: Metadata filter
            limit: Maximum number of results
            offset: Number of results to skip
            include: Fields to include in results

        Returns:
            Dictionary with requested fields
        """
        if isinstance(ids, str):
            ids = [ids]

        if include is None:
            include = ["embeddings", "metadatas", "documents"]

        with self._lock:
            return self.collection.get(
                ids=ids,
                where=where,
                limit=limit,
                offset=offset,
                include=include,
            )

    def delete(
        self,
        ids: Optional[Union[str, List[str]]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Delete documents from collection.

        Args:
            ids: Document IDs to delete
            where: Metadata filter for deletion
        """
        if isinstance(ids, str):
            ids = [ids]

        with self._lock:
            # Get count before deletion
            if ids:
                delete_count = len(ids)
            else:
                # Query to get count
                to_delete = self.collection.get(where=where, limit=None)
                delete_count = len(to_delete["ids"])

            self.collection.delete(ids=ids, where=where)
            self.stats["total_deletes"] += delete_count
            self.stats["total_documents"] = self.collection.count()

    def update(
        self,
        ids: Union[str, List[str]],
        embeddings: Optional[Union[np.ndarray, List[np.ndarray]]] = None,
        documents: Optional[Union[str, List[str]]] = None,
        metadatas: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
    ) -> None:
        """Update existing documents.

        Args:
            ids: Document IDs to update
            embeddings: New embeddings (optional)
            documents: New document texts (optional)
            metadatas: New metadata (optional)
        """
        if isinstance(ids, str):
            ids = [ids]
        if isinstance(embeddings, np.ndarray) and embeddings.ndim == 1:
            embeddings = [embeddings]
        if isinstance(documents, str):
            documents = [documents]
        if isinstance(metadatas, dict):
            metadatas = [metadatas]

        # Convert embeddings to lists
        if embeddings is not None:
            embeddings = [
                emb.tolist() if isinstance(emb, np.ndarray) else emb
                for emb in embeddings
            ]

        with self._lock:
            self.collection.update(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )

    def count(self) -> int:
        """Get number of documents in collection.

        Returns:
            Document count
        """
        with self._lock:
            return self.collection.count()

    def create_collection(
        self,
        name: str,
        embedding_function: Optional[Any] = None,
    ) -> None:
        """Create a new collection.

        Args:
            name: Collection name
            embedding_function: Custom embedding function

        Raises:
            ValueError: If collection already exists
        """
        with self._lock:
            try:
                self.client.create_collection(
                    name=name,
                    embedding_function=embedding_function,
                    metadata={"created_at": time.time()},
                )
                self.stats["total_collections"] = len(self.client.list_collections())
            except Exception as e:
                raise ValueError(f"Collection '{name}' already exists") from e

    def get_collection(self, name: str) -> None:
        """Switch to an existing collection.

        Args:
            name: Collection name

        Raises:
            ValueError: If collection doesn't exist
        """
        with self._lock:
            try:
                self.collection = self.client.get_collection(name=name)
                self.collection_name = name
                self.stats["total_documents"] = self.collection.count()
            except Exception as e:
                raise ValueError(f"Collection '{name}' not found") from e

    def delete_collection(self, name: str) -> None:
        """Delete a collection.

        Args:
            name: Collection name
        """
        with self._lock:
            self.client.delete_collection(name=name)
            self.stats["total_collections"] = len(self.client.list_collections())

            # If deleted current collection, switch to default
            if name == self.collection_name:
                self.collection = self._get_or_create_collection("default")
                self.collection_name = "default"
                self.stats["total_documents"] = self.collection.count()

    def list_collections(self) -> List[str]:
        """List all collection names.

        Returns:
            List of collection names
        """
        with self._lock:
            collections = self.client.list_collections()
            return [col.name for col in collections]

    def peek(self, limit: int = 10) -> Dict[str, Any]:
        """Peek at first documents in collection.

        Args:
            limit: Number of documents to return

        Returns:
            Dictionary with document data
        """
        with self._lock:
            return self.collection.peek(limit=limit)

    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics including circuit breaker status.

        Returns:
            Dictionary with statistics and reliability metrics
        """
        with self._lock:
            stats = {
                **self.stats,
                "current_collection": self.collection_name,
                "persist_directory": str(self.persist_directory) if self.persist_directory else None,
            }

            # Add circuit breaker stats if enabled
            if self.circuit_breaker:
                stats["circuit_breaker"] = self.circuit_breaker.get_stats()

            return stats

    def get_health(self) -> Dict[str, Any]:
        """Get health status of vector store.

        Returns:
            Dictionary with health information
        """
        try:
            # Test connectivity with timeout
            count = self._safe_count()
            circuit_state = self.circuit_breaker.state.value if self.circuit_breaker else "disabled"

            return {
                "status": "healthy" if circuit_state != "open" else "degraded",
                "chromadb_available": circuit_state != "open",
                "circuit_breaker_state": circuit_state,
                "document_count": count,
                "collection": self.collection_name,
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "chromadb_available": False,
                "circuit_breaker_state": self.circuit_breaker.state.value if self.circuit_breaker else "disabled",
                "error": str(e),
            }

    def reset(self) -> None:
        """Reset the current collection (delete all documents)."""
        with self._lock:
            # Delete and recreate collection
            self.client.delete_collection(name=self.collection_name)
            self.collection = self._get_or_create_collection(self.collection_name)
            self.stats["total_documents"] = 0

    def __repr__(self) -> str:
        """Return string representation of vector store."""
        return (
            f"VectorStore(collection={self.collection_name}, "
            f"documents={self.count()}, "
            f"persist={self.persist_directory is not None})"
        )
