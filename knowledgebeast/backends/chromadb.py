"""ChromaDB backend implementation for backward compatibility.

This backend wraps the existing VectorStore class to provide
compatibility with the new backend abstraction layer.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from knowledgebeast.backends.base import VectorBackend
from knowledgebeast.core.vector_store import VectorStore

logger = logging.getLogger(__name__)


class ChromaDBBackend(VectorBackend):
    """ChromaDB backend for legacy compatibility.

    Wraps the existing VectorStore implementation to provide
    the new VectorBackend interface while maintaining all
    existing functionality and behavior.

    This backend will be the default in v3.0 for backward
    compatibility. Users can opt-in to PostgresBackend for
    new features.

    Attributes:
        vector_store: Underlying VectorStore instance
        collection_name: Active collection name
    """

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: str = "default",
        enable_circuit_breaker: bool = True,
        circuit_breaker_threshold: int = 5,
    ) -> None:
        """Initialize ChromaDB backend.

        Args:
            persist_directory: Directory for persistent storage (None for in-memory)
            collection_name: Collection name (default: "default")
            enable_circuit_breaker: Enable circuit breaker protection
            circuit_breaker_threshold: Failures before opening circuit
        """
        self.collection_name = collection_name
        self.persist_directory = persist_directory

        # Initialize underlying VectorStore
        self.vector_store = VectorStore(
            persist_directory=persist_directory,
            collection_name=collection_name,
            enable_circuit_breaker=enable_circuit_breaker,
            circuit_breaker_threshold=circuit_breaker_threshold,
        )

        logger.info(f"Initialized ChromaDBBackend with collection '{collection_name}'")

    async def add_documents(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        """Add documents to ChromaDB collection.

        Wraps VectorStore.add() with async interface.
        """
        # VectorStore.add is synchronous, but we wrap it for async compatibility
        self.vector_store.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    async def query_vector(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Perform vector similarity search.

        Wraps VectorStore.query() with async interface.
        """
        results = self.vector_store.query(
            query_embeddings=query_embedding,
            n_results=top_k,
            where=where,
        )

        # Convert ChromaDB results to standard format
        # ChromaDB returns: {"ids": [[...]], "distances": [[...]], "metadatas": [[...]]}
        output = []
        if results and "ids" in results:
            ids = results["ids"][0]
            distances = results["distances"][0]
            metadatas = results.get("metadatas", [[{}] * len(ids)])[0]

            for doc_id, distance, metadata in zip(ids, distances, metadatas):
                # Convert distance to similarity score (lower distance = higher similarity)
                similarity = 1.0 / (1.0 + distance)
                output.append((doc_id, similarity, metadata or {}))

        return output

    async def query_keyword(
        self,
        query: str,
        top_k: int = 10,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Perform keyword search.

        ChromaDB doesn't have built-in BM25, so we use document filtering
        with where_document parameter for basic keyword matching.

        Note: This is a simplified implementation. Full BM25 search
        requires the QueryEngine or PostgresBackend (with ParadeDB).
        """
        # Use where_document for simple text matching
        results = self.vector_store.collection.get(
            where=where,
            where_document={"$contains": query},
            limit=top_k,
            include=["metadatas", "documents"]
        )

        # Convert to standard format with simple relevance score
        output = []
        if results and "ids" in results:
            for i, doc_id in enumerate(results["ids"]):
                # Simple relevance: count of query terms in document
                doc_text = results["documents"][i] if "documents" in results else ""
                score = sum(1 for term in query.lower().split() if term in doc_text.lower())
                metadata = results["metadatas"][i] if "metadatas" in results else {}
                output.append((doc_id, float(score), metadata))

        # Sort by score descending
        output.sort(key=lambda x: x[1], reverse=True)
        return output[:top_k]

    async def query_hybrid(
        self,
        query_embedding: List[float],
        query_text: str,
        top_k: int = 10,
        alpha: float = 0.7,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Perform hybrid search combining vector and keyword.

        Uses Reciprocal Rank Fusion to combine results.
        """
        if not 0 <= alpha <= 1:
            raise ValueError(f"alpha must be in [0, 1], got {alpha}")

        # Get vector and keyword results
        vector_results = await self.query_vector(query_embedding, top_k=20, where=where)
        keyword_results = await self.query_keyword(query_text, top_k=20, where=where)

        # Reciprocal Rank Fusion (RRF)
        # Score = alpha * (1 / (k + rank_vector)) + (1 - alpha) * (1 / (k + rank_keyword))
        k = 60  # RRF constant

        # Build ranking maps
        vector_ranks = {doc_id: i + 1 for i, (doc_id, _, _) in enumerate(vector_results)}
        keyword_ranks = {doc_id: i + 1 for i, (doc_id, _, _) in enumerate(keyword_results)}

        # Collect all unique doc IDs
        all_ids = set(vector_ranks.keys()) | set(keyword_ranks.keys())

        # Build metadata maps once - O(n)
        vector_meta = {doc_id: meta for doc_id, _, meta in vector_results}
        keyword_meta = {doc_id: meta for doc_id, _, meta in keyword_results}

        # Compute RRF scores
        rrf_scores = {}
        metadata_map = {}

        for doc_id in all_ids:
            vec_rank = vector_ranks.get(doc_id, 1000)  # Large rank if not found
            key_rank = keyword_ranks.get(doc_id, 1000)

            rrf_score = (
                alpha * (1.0 / (k + vec_rank)) +
                (1 - alpha) * (1.0 / (k + key_rank))
            )
            rrf_scores[doc_id] = rrf_score

            # Get metadata from either result (O(1) lookup)
            metadata_map[doc_id] = vector_meta.get(doc_id) or keyword_meta.get(doc_id, {})

        # Sort by RRF score and return top_k
        sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return [(doc_id, score, metadata_map.get(doc_id, {}))
                for doc_id, score in sorted_results[:top_k]]

    async def delete_documents(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Delete documents from collection."""
        if ids is None and where is None:
            raise ValueError("Either ids or where must be provided")

        # Get count before deletion
        if ids:
            delete_count = len(ids)
        else:
            results = self.vector_store.collection.get(where=where, limit=None)
            delete_count = len(results.get("ids", []))

        # Delete
        self.vector_store.delete(ids=ids, where=where)

        return delete_count

    async def get_statistics(self) -> Dict[str, Any]:
        """Get backend statistics."""
        stats = self.vector_store.get_stats()

        return {
            "backend": "chromadb",
            "collection": self.collection_name,
            "total_documents": stats.get("total_documents", 0),
            "embedding_dimension": 384,  # Default for sentence-transformers
            "persist_directory": self.persist_directory,
            "circuit_breaker": stats.get("circuit_breaker", {}),
        }

    async def get_health(self) -> Dict[str, Any]:
        """Check backend health."""
        health = self.vector_store.get_health()

        return {
            "status": health.get("status", "unknown"),
            "backend_available": health.get("chromadb_available", False),
            "circuit_breaker_state": health.get("circuit_breaker_state", "disabled"),
            "document_count": health.get("document_count", 0),
        }

    async def close(self) -> None:
        """Close backend connections.

        ChromaDB client doesn't require explicit closing,
        but we provide this for interface compliance.
        """
        logger.info(f"Closing ChromaDBBackend for collection '{self.collection_name}'")
        # VectorStore doesn't have a close method, but we could add cleanup here if needed
