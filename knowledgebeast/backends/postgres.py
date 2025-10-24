"""Postgres backend implementation using pgvector.

This backend provides production-grade vector storage with:
- asyncpg for async database operations
- pgvector for vector similarity search
- ACID transactions and PostgreSQL reliability
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import asyncpg

from knowledgebeast.backends.base import VectorBackend

logger = logging.getLogger(__name__)


class PostgresBackend(VectorBackend):
    """Postgres backend using pgvector.

    Features:
    - pgvector for vector similarity search (cosine distance)
    - PostgreSQL full-text search for keyword search
    - Reciprocal Rank Fusion for hybrid search
    - ACID transactions and production reliability
    - Connection pooling for concurrency
    """

    def __init__(
        self,
        connection_string: str,
        collection_name: str = "default",
        embedding_dimension: int = 384,
        pool_size: int = 10,
        pool_min_size: int = 2,
    ):
        """Initialize Postgres backend.

        Args:
            connection_string: PostgreSQL connection string
                (e.g., "postgresql://user:pass@localhost/dbname")
            collection_name: Collection/table name prefix
            embedding_dimension: Embedding vector dimension (default: 384)
            pool_size: Maximum connection pool size (default: 10)
            pool_min_size: Minimum connection pool size (default: 2)
        """
        self.connection_string = connection_string
        self.collection_name = collection_name
        self.embedding_dimension = embedding_dimension
        self.pool_size = pool_size
        self.pool_min_size = pool_min_size
        self.pool: Optional[asyncpg.Pool] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database connection pool and schema.

        Must be called before using the backend.
        Creates connection pool and sets up database schema.
        """
        if self._initialized:
            return

        # Create connection pool
        self.pool = await asyncpg.create_pool(
            self.connection_string,
            min_size=self.pool_min_size,
            max_size=self.pool_size,
            command_timeout=60,
        )

        # Create schema
        await self._create_schema()

        self._initialized = True
        logger.info(
            f"Initialized PostgresBackend: collection='{self.collection_name}', "
            f"dimension={self.embedding_dimension}"
        )

    async def _create_schema(self) -> None:
        """Create database schema from SQL template."""
        # Read schema SQL
        schema_path = Path(__file__).parent / "postgres_schema.sql"
        schema_sql = schema_path.read_text()

        # Replace template variables
        schema_sql = schema_sql.replace("{collection_name}", self.collection_name)
        schema_sql = schema_sql.replace("{embedding_dimension}", str(self.embedding_dimension))

        # Execute schema creation
        async with self.pool.acquire() as conn:
            await conn.execute(schema_sql)

        logger.info(f"Created schema for collection '{self.collection_name}'")

    async def add_documents(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        """Add documents with embeddings to Postgres.

        Uses INSERT ... ON CONFLICT DO UPDATE for upsert behavior.

        Args:
            ids: Document IDs
            embeddings: Embedding vectors
            documents: Document text content
            metadatas: Document metadata (stored as JSONB)

        Raises:
            ValueError: If input lists have mismatched lengths
            RuntimeError: If backend not initialized
        """
        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")

        if not (len(ids) == len(embeddings) == len(documents) == len(metadatas)):
            raise ValueError("All input lists must have the same length")

        # Prepare data for bulk insert
        records = [
            (doc_id, embedding, document, metadata)
            for doc_id, embedding, document, metadata in zip(ids, embeddings, documents, metadatas)
        ]

        # Upsert SQL (insert or update on conflict)
        sql = f"""
            INSERT INTO {self.collection_name}_documents (id, embedding, document, metadata)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (id) DO UPDATE SET
                embedding = EXCLUDED.embedding,
                document = EXCLUDED.document,
                metadata = EXCLUDED.metadata
        """

        async with self.pool.acquire() as conn:
            await conn.executemany(sql, records)

        logger.debug(f"Added {len(ids)} documents to '{self.collection_name}'")

    async def query_vector(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Perform vector similarity search using pgvector.

        Uses cosine distance for similarity (lower distance = higher similarity).

        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            where: Optional metadata filter (e.g., {"source": "docs"})

        Returns:
            List of (doc_id, similarity_score, metadata) tuples

        Raises:
            RuntimeError: If backend not initialized
        """
        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")

        # Build WHERE clause for metadata filtering
        where_clause = ""
        params = [query_embedding, top_k]
        if where:
            # Simple equality filter: metadata @> '{"key": "value"}'
            where_clause = "WHERE metadata @> $3"
            params.append(where)

        # Query with cosine distance (pgvector operator: <=>)
        sql = f"""
            SELECT id, embedding <=> $1 as distance, metadata
            FROM {self.collection_name}_documents
            {where_clause}
            ORDER BY distance
            LIMIT $2
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        # Convert distance to similarity score
        results = []
        for row in rows:
            # Similarity = 1 / (1 + distance)
            similarity = 1.0 / (1.0 + row["distance"])
            results.append((row["id"], similarity, row["metadata"]))

        return results

    async def query_keyword(self, query, top_k=10, where=None):
        raise NotImplementedError("Task 6")

    async def query_hybrid(self, query_embedding, query_text, top_k=10, alpha=0.7, where=None):
        raise NotImplementedError("Task 7")

    async def delete_documents(self, ids=None, where=None):
        raise NotImplementedError("Task 8")

    async def get_statistics(self):
        raise NotImplementedError("Task 9")

    async def get_health(self):
        raise NotImplementedError("Task 10")

    async def close(self) -> None:
        """Close connection pool and cleanup resources."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            self._initialized = False
            logger.info(f"Closed PostgresBackend for collection '{self.collection_name}'")
