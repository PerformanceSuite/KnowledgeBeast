"""Vector store implementation using ChromaDB for persistent vector search.

This module provides the VectorStore class for managing vector embeddings
with ChromaDB, including collection CRUD operations and similarity search.
"""

import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import chromadb
import numpy as np
from chromadb.config import Settings
from chromadb.utils import embedding_functions


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
    ) -> None:
        """Initialize the vector store.

        Args:
            persist_directory: Directory for persistent storage (None for in-memory)
            collection_name: Name of the collection to use
            embedding_function: Custom embedding function (optional)
        """
        self.persist_directory = Path(persist_directory) if persist_directory else None
        self._lock = threading.RLock()

        # Initialize ChromaDB client
        if self.persist_directory:
            self.persist_directory.mkdir(parents=True, exist_ok=True)
            settings = Settings(
                persist_directory=str(self.persist_directory),
                anonymized_telemetry=False,
            )
            self.client = chromadb.PersistentClient(settings=settings)
        else:
            self.client = chromadb.Client()

        # Statistics
        self.stats = {
            "total_documents": 0,
            "total_queries": 0,
            "total_collections": 0,
            "total_adds": 0,
            "total_deletes": 0,
        }

        # Create or get collection
        self.collection_name = collection_name
        self.collection = self._get_or_create_collection(
            collection_name, embedding_function
        )

        # Update stats
        with self._lock:
            self.stats["total_documents"] = self.collection.count()
            self.stats["total_collections"] = len(self.client.list_collections())

    def _get_or_create_collection(
        self,
        name: str,
        embedding_function: Optional[Any] = None,
    ) -> Any:
        """Get existing collection or create new one.

        Args:
            name: Collection name
            embedding_function: Custom embedding function

        Returns:
            ChromaDB collection
        """
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
        """Query the collection for similar vectors.

        Args:
            query_embeddings: Query embedding(s)
            n_results: Number of results to return
            where: Metadata filter
            where_document: Document text filter
            include: Fields to include in results

        Returns:
            Dictionary with 'ids', 'distances', 'embeddings', 'metadatas', 'documents'
        """
        # Normalize query embeddings
        if isinstance(query_embeddings, np.ndarray) and query_embeddings.ndim == 1:
            query_embeddings = [query_embeddings]

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
        """Get vector store statistics.

        Returns:
            Dictionary with statistics
        """
        with self._lock:
            return {
                **self.stats,
                "current_collection": self.collection_name,
                "persist_directory": str(self.persist_directory) if self.persist_directory else None,
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
