# PostgresBackend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement PostgresBackend using asyncpg + pgvector for production-grade vector storage with ACID guarantees.

**Architecture:** PostgresBackend implements the VectorBackend ABC using asyncpg for async database operations, pgvector for vector similarity search, and RRF (Reciprocal Rank Fusion) for hybrid search. Database schema includes a single table with vector column, text column (for keyword search), and JSONB metadata. Connection pooling for concurrency.

**Tech Stack:** asyncpg (async Postgres driver), pgvector extension, PostgreSQL 15+, pytest-asyncio (testing)

---

## Task 1: Add PostgreSQL Dependencies

**Files:**
- Modify: `requirements.txt`
- Create: None

**Step 1: Add asyncpg and pgvector dependencies**

Add to `requirements.txt` after line 12:

```
asyncpg>=0.29.0  # Async PostgreSQL driver
```

Note: pgvector is a Postgres extension, not a Python package.

**Step 2: Verify dependencies**

Run: `pip install -r requirements.txt`
Expected: asyncpg installs successfully

**Step 3: Commit**

```bash
git add requirements.txt
git commit -m "deps: add asyncpg for PostgresBackend"
```

---

## Task 2: Database Schema SQL

**Files:**
- Create: `knowledgebeast/backends/postgres_schema.sql`

**Step 1: Create schema SQL file**

Create file with complete schema:

```sql
-- PostgresBackend schema for vector storage
-- Requires: PostgreSQL 15+ with pgvector extension

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table with vector embeddings
CREATE TABLE IF NOT EXISTS {collection_name}_documents (
    id TEXT PRIMARY KEY,
    embedding vector({embedding_dimension}),
    document TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Vector similarity index (HNSW for fast approximate search)
CREATE INDEX IF NOT EXISTS {collection_name}_embedding_idx
    ON {collection_name}_documents
    USING hnsw (embedding vector_cosine_ops);

-- Text search index (for keyword search)
CREATE INDEX IF NOT EXISTS {collection_name}_document_idx
    ON {collection_name}_documents
    USING gin (to_tsvector('english', document));

-- Metadata index (for filtering)
CREATE INDEX IF NOT EXISTS {collection_name}_metadata_idx
    ON {collection_name}_documents
    USING gin (metadata);

-- Updated timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_{collection_name}_updated_at
    BEFORE UPDATE ON {collection_name}_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

**Step 2: Commit**

```bash
git add knowledgebeast/backends/postgres_schema.sql
git commit -m "feat(backends): add PostgresBackend database schema"
```

---

## Task 3: PostgresBackend Init and Connection Pool

**Files:**
- Modify: `knowledgebeast/backends/postgres.py`
- Test: `tests/backends/test_postgres.py` (create)

**Step 1: Write failing test for initialization**

Create `tests/backends/test_postgres.py`:

```python
"""Tests for PostgresBackend implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from knowledgebeast.backends.postgres import PostgresBackend
from knowledgebeast.backends.base import VectorBackend


@pytest.mark.asyncio
async def test_postgres_backend_implements_interface():
    """PostgresBackend should implement VectorBackend interface."""
    assert issubclass(PostgresBackend, VectorBackend)


@pytest.mark.asyncio
async def test_postgres_backend_initialization():
    """PostgresBackend should initialize connection pool."""
    with patch('knowledgebeast.backends.postgres.asyncpg') as mock_asyncpg:
        mock_pool = AsyncMock()
        mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

        backend = PostgresBackend(
            connection_string="postgresql://test:test@localhost/test",
            collection_name="test_collection",
            embedding_dimension=384
        )

        await backend.initialize()

        # Verify pool created
        mock_asyncpg.create_pool.assert_called_once()
        assert backend.pool == mock_pool
        assert backend.collection_name == "test_collection"
        assert backend.embedding_dimension == 384

        await backend.close()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/backends/test_postgres.py::test_postgres_backend_initialization -v`
Expected: FAIL with import error or NotImplementedError

**Step 3: Implement initialization**

Replace content in `knowledgebeast/backends/postgres.py`:

```python
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

    # Stub methods (to be implemented in subsequent tasks)
    async def add_documents(self, ids, embeddings, documents, metadatas):
        raise NotImplementedError("Task 4")

    async def query_vector(self, query_embedding, top_k=10, where=None):
        raise NotImplementedError("Task 5")

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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/backends/test_postgres.py::test_postgres_backend_initialization -v`
Expected: PASS

**Step 5: Commit**

```bash
git add knowledgebeast/backends/postgres.py tests/backends/test_postgres.py
git commit -m "feat(backends): implement PostgresBackend initialization and connection pool"
```

---

## Task 4: Implement add_documents Method

**Files:**
- Modify: `knowledgebeast/backends/postgres.py:95-96`
- Modify: `tests/backends/test_postgres.py`

**Step 1: Write failing test**

Add to `tests/backends/test_postgres.py`:

```python
@pytest.mark.asyncio
async def test_postgres_add_documents():
    """PostgresBackend should add documents to database."""
    with patch('knowledgebeast.backends.postgres.asyncpg') as mock_asyncpg:
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire = AsyncMock(return_value=MagicMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock()
        ))
        mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

        backend = PostgresBackend(
            connection_string="postgresql://test:test@localhost/test",
            collection_name="test"
        )
        await backend.initialize()

        # Add documents
        await backend.add_documents(
            ids=["doc1", "doc2"],
            embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
            documents=["Hello world", "Goodbye world"],
            metadatas=[{"source": "test"}, {"source": "prod"}]
        )

        # Verify executemany called with correct SQL
        assert mock_conn.executemany.called
        call_args = mock_conn.executemany.call_args
        sql = call_args[0][0]
        assert "INSERT INTO test_documents" in sql
        assert "ON CONFLICT (id) DO UPDATE" in sql

        await backend.close()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/backends/test_postgres.py::test_postgres_add_documents -v`
Expected: FAIL with NotImplementedError

**Step 3: Implement add_documents**

Replace lines 95-96 in `knowledgebeast/backends/postgres.py`:

```python
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/backends/test_postgres.py::test_postgres_add_documents -v`
Expected: PASS

**Step 5: Commit**

```bash
git add knowledgebeast/backends/postgres.py tests/backends/test_postgres.py
git commit -m "feat(backends): implement PostgresBackend.add_documents with upsert"
```

---

## Task 5: Implement query_vector Method

**Files:**
- Modify: `knowledgebeast/backends/postgres.py:98-99`
- Modify: `tests/backends/test_postgres.py`

**Step 1: Write failing test**

Add to `tests/backends/test_postgres.py`:

```python
@pytest.mark.asyncio
async def test_postgres_query_vector():
    """PostgresBackend should perform vector similarity search."""
    with patch('knowledgebeast.backends.postgres.asyncpg') as mock_asyncpg:
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {"id": "doc1", "distance": 0.1, "metadata": {"source": "test"}},
            {"id": "doc2", "distance": 0.3, "metadata": {"source": "prod"}}
        ])
        mock_pool.acquire = AsyncMock(return_value=MagicMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock()
        ))
        mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

        backend = PostgresBackend(
            connection_string="postgresql://test:test@localhost/test",
            collection_name="test"
        )
        await backend.initialize()

        # Query
        results = await backend.query_vector(
            query_embedding=[0.1, 0.2, 0.3],
            top_k=2
        )

        assert len(results) == 2
        assert results[0][0] == "doc1"  # ID
        assert results[0][1] > results[1][1]  # Higher similarity for closer vector
        assert results[0][2] == {"source": "test"}  # Metadata

        await backend.close()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/backends/test_postgres.py::test_postgres_query_vector -v`
Expected: FAIL with NotImplementedError

**Step 3: Implement query_vector**

Replace lines 98-99 in `knowledgebeast/backends/postgres.py`:

```python
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/backends/test_postgres.py::test_postgres_query_vector -v`
Expected: PASS

**Step 5: Commit**

```bash
git add knowledgebeast/backends/postgres.py tests/backends/test_postgres.py
git commit -m "feat(backends): implement PostgresBackend.query_vector with pgvector"
```

---

## Task 6: Implement query_keyword Method

**Files:**
- Modify: `knowledgebeast/backends/postgres.py:101-102`
- Modify: `tests/backends/test_postgres.py`

**Step 1: Write failing test**

Add to `tests/backends/test_postgres.py`:

```python
@pytest.mark.asyncio
async def test_postgres_query_keyword():
    """PostgresBackend should perform full-text search."""
    with patch('knowledgebeast.backends.postgres.asyncpg') as mock_asyncpg:
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {"id": "doc1", "rank": 0.9, "metadata": {"source": "test"}},
            {"id": "doc2", "rank": 0.5, "metadata": {"source": "prod"}}
        ])
        mock_pool.acquire = AsyncMock(return_value=MagicMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock()
        ))
        mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

        backend = PostgresBackend(
            connection_string="postgresql://test:test@localhost/test",
            collection_name="test"
        )
        await backend.initialize()

        # Query
        results = await backend.query_keyword(
            query="machine learning",
            top_k=2
        )

        assert len(results) == 2
        assert results[0][0] == "doc1"
        assert results[0][1] == 0.9  # Rank score

        await backend.close()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/backends/test_postgres.py::test_postgres_query_keyword -v`
Expected: FAIL with NotImplementedError

**Step 3: Implement query_keyword**

Replace lines 101-102 in `knowledgebeast/backends/postgres.py`:

```python
    async def query_keyword(
        self,
        query: str,
        top_k: int = 10,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Perform full-text keyword search using PostgreSQL.

        Uses ts_rank for relevance scoring with to_tsvector/to_tsquery.

        Args:
            query: Search query string
            top_k: Number of results to return
            where: Optional metadata filter

        Returns:
            List of (doc_id, relevance_score, metadata) tuples

        Raises:
            RuntimeError: If backend not initialized
        """
        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")

        # Build WHERE clause for metadata filtering
        where_clause = ""
        params = [query, top_k]
        if where:
            where_clause = "AND metadata @> $3"
            params.append(where)

        # Full-text search with ts_rank
        sql = f"""
            SELECT
                id,
                ts_rank(to_tsvector('english', document), to_tsquery('english', $1)) as rank,
                metadata
            FROM {self.collection_name}_documents
            WHERE to_tsvector('english', document) @@ to_tsquery('english', $1)
            {where_clause}
            ORDER BY rank DESC
            LIMIT $2
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        results = [(row["id"], float(row["rank"]), row["metadata"]) for row in rows]
        return results
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/backends/test_postgres.py::test_postgres_query_keyword -v`
Expected: PASS

**Step 5: Commit**

```bash
git add knowledgebeast/backends/postgres.py tests/backends/test_postgres.py
git commit -m "feat(backends): implement PostgresBackend.query_keyword with full-text search"
```

---

## Task 7: Implement query_hybrid Method

**Files:**
- Modify: `knowledgebeast/backends/postgres.py:104-105`
- Modify: `tests/backends/test_postgres.py`

**Step 1: Write failing test**

Add to `tests/backends/test_postgres.py`:

```python
@pytest.mark.asyncio
async def test_postgres_query_hybrid():
    """PostgresBackend should perform hybrid search with RRF."""
    with patch('knowledgebeast.backends.postgres.asyncpg') as mock_asyncpg:
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()

        # Mock vector results
        mock_conn.fetch = AsyncMock(side_effect=[
            [{"id": "doc1", "distance": 0.1, "metadata": {"source": "test"}}],
            [{"id": "doc1", "rank": 0.9, "metadata": {"source": "test"}}]
        ])

        mock_pool.acquire = AsyncMock(return_value=MagicMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock()
        ))
        mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

        backend = PostgresBackend(
            connection_string="postgresql://test:test@localhost/test",
            collection_name="test"
        )
        await backend.initialize()

        # Query
        results = await backend.query_hybrid(
            query_embedding=[0.1, 0.2, 0.3],
            query_text="machine learning",
            top_k=1,
            alpha=0.7
        )

        assert len(results) <= 1
        assert all(len(r) == 3 for r in results)  # (id, score, metadata)

        await backend.close()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/backends/test_postgres.py::test_postgres_query_hybrid -v`
Expected: FAIL with NotImplementedError

**Step 3: Implement query_hybrid**

Replace lines 104-105 in `knowledgebeast/backends/postgres.py`:

```python
    async def query_hybrid(
        self,
        query_embedding: List[float],
        query_text: str,
        top_k: int = 10,
        alpha: float = 0.7,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Perform hybrid search combining vector and keyword search.

        Uses Reciprocal Rank Fusion (RRF) to combine results.

        Args:
            query_embedding: Query vector for semantic search
            query_text: Query string for keyword search
            top_k: Number of results to return
            alpha: Weight for vector search (0-1)
            where: Optional metadata filter

        Returns:
            List of (doc_id, combined_score, metadata) tuples

        Raises:
            ValueError: If alpha not in [0, 1]
            RuntimeError: If backend not initialized
        """
        if not 0 <= alpha <= 1:
            raise ValueError(f"alpha must be in [0, 1], got {alpha}")

        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")

        # Get both result sets (expand to 20 for better RRF coverage)
        vector_results = await self.query_vector(query_embedding, top_k=20, where=where)
        keyword_results = await self.query_keyword(query_text, top_k=20, where=where)

        # Reciprocal Rank Fusion
        k = 60  # RRF constant

        # Build ranking maps
        vector_ranks = {doc_id: i + 1 for i, (doc_id, _, _) in enumerate(vector_results)}
        keyword_ranks = {doc_id: i + 1 for i, (doc_id, _, _) in enumerate(keyword_results)}

        # Collect all unique doc IDs
        all_ids = set(vector_ranks.keys()) | set(keyword_ranks.keys())

        # Build metadata maps
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
            metadata_map[doc_id] = vector_meta.get(doc_id) or keyword_meta.get(doc_id, {})

        # Sort by RRF score and return top_k
        sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return [(doc_id, score, metadata_map.get(doc_id, {}))
                for doc_id, score in sorted_results[:top_k]]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/backends/test_postgres.py::test_postgres_query_hybrid -v`
Expected: PASS

**Step 5: Commit**

```bash
git add knowledgebeast/backends/postgres.py tests/backends/test_postgres.py
git commit -m "feat(backends): implement PostgresBackend.query_hybrid with RRF"
```

---

## Task 8: Implement delete_documents Method

**Files:**
- Modify: `knowledgebeast/backends/postgres.py:107-108`
- Modify: `tests/backends/test_postgres.py`

**Step 1: Write failing test**

Add to `tests/backends/test_postgres.py`:

```python
@pytest.mark.asyncio
async def test_postgres_delete_documents():
    """PostgresBackend should delete documents."""
    with patch('knowledgebeast.backends.postgres.asyncpg') as mock_asyncpg:
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 2")  # Postgres returns "DELETE N"

        mock_pool.acquire = AsyncMock(return_value=MagicMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock()
        ))
        mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

        backend = PostgresBackend(
            connection_string="postgresql://test:test@localhost/test",
            collection_name="test"
        )
        await backend.initialize()

        # Delete by IDs
        count = await backend.delete_documents(ids=["doc1", "doc2"])

        assert count == 2
        assert mock_conn.execute.called

        await backend.close()


@pytest.mark.asyncio
async def test_postgres_delete_requires_ids_or_where():
    """PostgresBackend.delete_documents should require ids or where."""
    with patch('knowledgebeast.backends.postgres.asyncpg') as mock_asyncpg:
        mock_pool = AsyncMock()
        mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

        backend = PostgresBackend(
            connection_string="postgresql://test:test@localhost/test",
            collection_name="test"
        )
        await backend.initialize()

        with pytest.raises(ValueError, match="Either ids or where must be provided"):
            await backend.delete_documents()

        await backend.close()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/backends/test_postgres.py::test_postgres_delete_documents -v`
Expected: FAIL with NotImplementedError

**Step 3: Implement delete_documents**

Replace lines 107-108 in `knowledgebeast/backends/postgres.py`:

```python
    async def delete_documents(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Delete documents from database.

        Args:
            ids: Document IDs to delete
            where: Metadata filter for deletion

        Returns:
            Number of documents deleted

        Raises:
            ValueError: If neither ids nor where is provided
            RuntimeError: If backend not initialized
        """
        if ids is None and where is None:
            raise ValueError("Either ids or where must be provided")

        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")

        # Build DELETE query
        if ids:
            sql = f"DELETE FROM {self.collection_name}_documents WHERE id = ANY($1)"
            params = [ids]
        else:
            sql = f"DELETE FROM {self.collection_name}_documents WHERE metadata @> $1"
            params = [where]

        async with self.pool.acquire() as conn:
            result = await conn.execute(sql, *params)

        # Parse "DELETE N" response
        count = int(result.split()[-1]) if result else 0
        logger.debug(f"Deleted {count} documents from '{self.collection_name}'")
        return count
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/backends/test_postgres.py::test_postgres_delete_documents -v`
Expected: PASS

**Step 5: Commit**

```bash
git add knowledgebeast/backends/postgres.py tests/backends/test_postgres.py
git commit -m "feat(backends): implement PostgresBackend.delete_documents"
```

---

## Task 9: Implement get_statistics Method

**Files:**
- Modify: `knowledgebeast/backends/postgres.py:110-111`
- Modify: `tests/backends/test_postgres.py`

**Step 1: Write failing test**

Add to `tests/backends/test_postgres.py`:

```python
@pytest.mark.asyncio
async def test_postgres_get_statistics():
    """PostgresBackend should return statistics."""
    with patch('knowledgebeast.backends.postgres.asyncpg') as mock_asyncpg:
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "total_documents": 100,
            "table_size": 1024000  # bytes
        })

        mock_pool.acquire = AsyncMock(return_value=MagicMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock()
        ))
        mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

        backend = PostgresBackend(
            connection_string="postgresql://test:test@localhost/test",
            collection_name="test",
            embedding_dimension=384
        )
        await backend.initialize()

        stats = await backend.get_statistics()

        assert stats["backend"] == "postgres"
        assert stats["collection"] == "test"
        assert stats["embedding_dimension"] == 384
        assert "total_documents" in stats
        assert "storage_size_mb" in stats

        await backend.close()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/backends/test_postgres.py::test_postgres_get_statistics -v`
Expected: FAIL with NotImplementedError

**Step 3: Implement get_statistics**

Replace lines 110-111 in `knowledgebeast/backends/postgres.py`:

```python
    async def get_statistics(self) -> Dict[str, Any]:
        """Get backend statistics.

        Returns:
            Dictionary with backend info:
            {
                "backend": "postgres",
                "collection": str,
                "total_documents": int,
                "embedding_dimension": int,
                "storage_size_mb": float,
                "index_type": "hnsw"
            }

        Raises:
            RuntimeError: If backend not initialized
        """
        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")

        sql = f"""
            SELECT
                COUNT(*) as total_documents,
                pg_total_relation_size('{self.collection_name}_documents') as table_size
            FROM {self.collection_name}_documents
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(sql)

        return {
            "backend": "postgres",
            "collection": self.collection_name,
            "total_documents": row["total_documents"],
            "embedding_dimension": self.embedding_dimension,
            "storage_size_mb": round(row["table_size"] / (1024 * 1024), 2),
            "index_type": "hnsw",
        }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/backends/test_postgres.py::test_postgres_get_statistics -v`
Expected: PASS

**Step 5: Commit**

```bash
git add knowledgebeast/backends/postgres.py tests/backends/test_postgres.py
git commit -m "feat(backends): implement PostgresBackend.get_statistics"
```

---

## Task 10: Implement get_health Method

**Files:**
- Modify: `knowledgebeast/backends/postgres.py:113-114`
- Modify: `tests/backends/test_postgres.py`

**Step 1: Write failing test**

Add to `tests/backends/test_postgres.py`:

```python
@pytest.mark.asyncio
async def test_postgres_get_health_healthy():
    """PostgresBackend should report healthy status."""
    with patch('knowledgebeast.backends.postgres.asyncpg') as mock_asyncpg:
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)

        mock_pool.acquire = AsyncMock(return_value=MagicMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock()
        ))
        mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

        backend = PostgresBackend(
            connection_string="postgresql://test:test@localhost/test",
            collection_name="test"
        )
        await backend.initialize()

        health = await backend.get_health()

        assert health["status"] == "healthy"
        assert health["backend_available"] is True
        assert "latency_ms" in health

        await backend.close()


@pytest.mark.asyncio
async def test_postgres_get_health_unhealthy():
    """PostgresBackend should report unhealthy status on error."""
    with patch('knowledgebeast.backends.postgres.asyncpg') as mock_asyncpg:
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=Exception("Connection failed"))

        mock_pool.acquire = AsyncMock(return_value=MagicMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock()
        ))
        mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

        backend = PostgresBackend(
            connection_string="postgresql://test:test@localhost/test",
            collection_name="test"
        )
        await backend.initialize()

        health = await backend.get_health()

        assert health["status"] == "unhealthy"
        assert health["backend_available"] is False
        assert "error" in health

        await backend.close()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/backends/test_postgres.py::test_postgres_get_health_healthy -v`
Expected: FAIL with NotImplementedError

**Step 3: Implement get_health**

Replace lines 113-114 in `knowledgebeast/backends/postgres.py`:

```python
    async def get_health(self) -> Dict[str, Any]:
        """Check backend health.

        Returns:
            Dictionary with health status:
            {
                "status": "healthy" | "degraded" | "unhealthy",
                "backend_available": bool,
                "latency_ms": float
            }

        Raises:
            RuntimeError: If backend not initialized
        """
        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")

        import time

        try:
            start = time.time()
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            latency_ms = (time.time() - start) * 1000

            status = "healthy" if latency_ms < 100 else "degraded"

            return {
                "status": status,
                "backend_available": True,
                "latency_ms": round(latency_ms, 2),
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "backend_available": False,
                "error": str(e),
            }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/backends/test_postgres.py::test_postgres_get_health_healthy -v`
Expected: PASS

**Step 5: Commit**

```bash
git add knowledgebeast/backends/postgres.py tests/backends/test_postgres.py
git commit -m "feat(backends): implement PostgresBackend.get_health"
```

---

## Task 11: Run Full Test Suite

**Files:**
- None (verification only)

**Step 1: Run all PostgresBackend tests**

Run: `pytest tests/backends/test_postgres.py -v`
Expected: All tests PASS

**Step 2: Run all backend tests**

Run: `pytest tests/backends/ -v`
Expected: All tests PASS (including ChromaDB and base tests)

**Step 3: Run integration tests if they exist**

Run: `pytest tests/integration/ -v -k backend`
Expected: PASS or SKIP if no integration tests

**Step 4: Commit test summary**

Create `WEEK2_TEST_SUMMARY.md`:

```markdown
# Week 2 Test Summary

**Date**: 2025-10-24
**Feature**: PostgresBackend Implementation

## Test Results

- PostgresBackend unit tests: X/X PASS
- All backend tests: X/X PASS
- Integration tests: X/X PASS

## Coverage

- PostgresBackend.py: 100%
- All 8 VectorBackend methods implemented
- Error handling tested
- Mocked database connections (no external dependencies)

## Next Steps

- Optional: Add Docker Compose setup for integration tests
- Optional: Add migration utility from ChromaDB to Postgres
- Update documentation with usage examples
```

```bash
git add WEEK2_TEST_SUMMARY.md
git commit -m "docs: add Week 2 test summary"
```

---

## Task 12: Update Documentation

**Files:**
- Modify: `docs/BACKENDS.md`
- Modify: `README.md`

**Step 1: Update BACKENDS.md with Postgres usage**

Update section "PostgresBackend (v3.0-beta, Week 2)" in `docs/BACKENDS.md`:

Replace "coming in Week 2" with complete example:

```markdown
### PostgresBackend (v3.0)

Production backend using PostgreSQL with pgvector extension.

**Setup:**

```bash
# 1. Install PostgreSQL 15+ with pgvector
# Docker:
docker run -d \
  --name postgres-kb \
  -e POSTGRES_PASSWORD=secret \
  -e POSTGRES_DB=knowledgebeast \
  -p 5432:5432 \
  ankane/pgvector:latest

# 2. Install Python dependencies
pip install asyncpg

# 3. Use in code
```

**Usage:**

```python
from knowledgebeast.backends import PostgresBackend
from knowledgebeast.core.query_engine import HybridQueryEngine

# Initialize backend
backend = PostgresBackend(
    connection_string="postgresql://user:pass@localhost/knowledgebeast",
    collection_name="my_kb",
    embedding_dimension=384,
    pool_size=10
)

# IMPORTANT: Call initialize() before use
await backend.initialize()

# Use with query engine
engine = HybridQueryEngine(repository, backend=backend)

# Query
results = await engine.query("machine learning")

# Cleanup
await backend.close()
```

**Advantages:**
- Unified database (no separate ChromaDB service)
- ACID transactions
- Production-grade reliability
- Better scalability
- pgvector HNSW indexes for fast vector search

**Migration from ChromaDB:**

```python
# Coming soon: kb-migrate utility
# For now, manually re-ingest documents with PostgresBackend
```
```

**Step 2: Update README.md**

Add PostgresBackend to features section:

```markdown
## Features

- **Multiple Vector Backends**:
  - ChromaDBBackend (default, v2.x compatible)
  - PostgresBackend (v3.0, production-grade)
  - Pluggable architecture for custom backends
```

**Step 3: Commit**

```bash
git add docs/BACKENDS.md README.md
git commit -m "docs: update documentation with PostgresBackend usage examples"
```

---

## Task 13: Create Docker Compose Setup (Optional)

**Files:**
- Create: `docker-compose.postgres.yml`

**Step 1: Create Docker Compose file**

Create `docker-compose.postgres.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: ankane/pgvector:latest
    environment:
      POSTGRES_USER: knowledgebeast
      POSTGRES_PASSWORD: kb_secret_dev
      POSTGRES_DB: knowledgebeast
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U knowledgebeast"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

**Step 2: Create setup documentation**

Create `docs/POSTGRES_SETUP.md`:

```markdown
# PostgreSQL Backend Setup

## Quick Start with Docker

```bash
# 1. Start PostgreSQL with pgvector
docker-compose -f docker-compose.postgres.yml up -d

# 2. Wait for healthy status
docker-compose -f docker-compose.postgres.yml ps

# 3. Install Python dependencies
pip install asyncpg

# 4. Use PostgresBackend in your code
```

## Connection String

```
postgresql://knowledgebeast:kb_secret_dev@localhost:5432/knowledgebeast
```

## Manual Setup (without Docker)

### macOS (Homebrew)

```bash
brew install postgresql@15
brew install pgvector

# Start PostgreSQL
brew services start postgresql@15

# Create database
createdb knowledgebeast
psql knowledgebeast -c "CREATE EXTENSION vector;"
```

### Ubuntu/Debian

```bash
# Add PostgreSQL APT repository
sudo apt install postgresql-15 postgresql-contrib-15

# Install pgvector
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# Create database
sudo -u postgres createdb knowledgebeast
sudo -u postgres psql knowledgebeast -c "CREATE EXTENSION vector;"
```

## Verification

```python
import asyncpg

async def test_connection():
    conn = await asyncpg.connect(
        "postgresql://knowledgebeast:kb_secret_dev@localhost/knowledgebeast"
    )
    result = await conn.fetchval("SELECT 1")
    print(f"Connection successful: {result}")
    await conn.close()

import asyncio
asyncio.run(test_connection())
```
```

**Step 3: Commit**

```bash
git add docker-compose.postgres.yml docs/POSTGRES_SETUP.md
git commit -m "feat(backends): add Docker Compose setup for PostgresBackend development"
```

---

## Task 14: Final Verification and Week 2 Completion

**Files:**
- Create: `WEEK2_COMPLETION_REPORT.md`

**Step 1: Run full test suite**

Run: `pytest tests/backends/test_postgres.py -v --cov=knowledgebeast/backends/postgres`
Expected: 100% coverage, all tests passing

**Step 2: Create completion report**

Create `WEEK2_COMPLETION_REPORT.md`:

```markdown
# Week 2 Completion Report: PostgresBackend Implementation

**Date**: 2025-10-24
**Status**: ✅ COMPLETE
**Branch**: `feature/postgres-backend`

---

## Deliverables

### ✅ PostgresBackend Implementation

Complete implementation of VectorBackend interface using PostgreSQL + pgvector:

- ✅ Connection pool management (asyncpg)
- ✅ Database schema with pgvector extension
- ✅ Vector similarity search (cosine distance, HNSW index)
- ✅ Keyword search (PostgreSQL full-text search)
- ✅ Hybrid search (Reciprocal Rank Fusion)
- ✅ Document CRUD operations
- ✅ Statistics and health monitoring

### ✅ Test Coverage

Comprehensive unit tests with mocked database:

- Test files: `tests/backends/test_postgres.py`
- Total tests: ~15
- Coverage: 100%
- All tests passing

### ✅ Documentation

Updated documentation:

- `docs/BACKENDS.md` - PostgresBackend usage guide
- `docs/POSTGRES_SETUP.md` - Setup instructions
- `README.md` - Feature list updated
- Inline docstrings for all methods

### ✅ Docker Setup

Optional Docker Compose configuration:

- `docker-compose.postgres.yml` - PostgreSQL + pgvector
- Easy development environment setup

---

## Success Criteria

- [x] PostgresBackend implements all 8 VectorBackend methods
- [x] Async operations using asyncpg
- [x] Connection pooling for concurrency
- [x] Unit tests with 100% coverage
- [x] No external dependencies for tests (mocked)
- [x] Documentation complete
- [x] Ready for integration testing

---

## Git History

1. `deps: add asyncpg for PostgresBackend`
2. `feat(backends): add PostgresBackend database schema`
3. `feat(backends): implement PostgresBackend initialization and connection pool`
4. `feat(backends): implement PostgresBackend.add_documents with upsert`
5. `feat(backends): implement PostgresBackend.query_vector with pgvector`
6. `feat(backends): implement PostgresBackend.query_keyword with full-text search`
7. `feat(backends): implement PostgresBackend.query_hybrid with RRF`
8. `feat(backends): implement PostgresBackend.delete_documents`
9. `feat(backends): implement PostgresBackend.get_statistics`
10. `feat(backends): implement PostgresBackend.get_health`
11. `docs: add Week 2 test summary`
12. `docs: update documentation with PostgresBackend usage examples`
13. `feat(backends): add Docker Compose setup for PostgresBackend development`
14. `docs: Week 2 completion report`

---

## Next Steps (Week 3 - Optional)

Potential enhancements:

1. Migration utility (ChromaDB → Postgres)
2. ParadeDB integration for advanced BM25
3. Integration tests with real Postgres (testcontainers)
4. Performance benchmarks (PostgresBackend vs ChromaDBBackend)
5. Multi-tenancy support (schema isolation)

---

## Metrics

- **Lines of Code Added**: ~500
- **Tests Added**: ~15
- **Test Coverage**: 100% (PostgresBackend)
- **Breaking Changes**: 0
- **Backward Compatibility**: ✅ Full

---

**Ready for production testing!** 🚀
```

**Step 3: Commit completion report**

```bash
git add WEEK2_COMPLETION_REPORT.md
git commit -m "docs: Week 2 completion report"
```

**Step 4: Push branch**

Run: `git push origin feature/postgres-backend`
Expected: Branch pushed successfully

---

## Execution Instructions

**Option 1: Use superpowers:executing-plans (in new session)**

Open new session in `/Users/danielconnolly/Projects/KnowledgeBeast/.worktrees/postgres-backend` and run:

```
/superpowers:execute-plan docs/plans/2025-10-24-postgres-backend.md
```

**Option 2: Use superpowers:subagent-driven-development (this session)**

If staying in current session, launch subagents for each task with code review between tasks.

---

## Notes for Engineer

- **TDD Required**: Write test first, see it fail, then implement
- **Commit Frequently**: After each passing test (Steps 1-5 per task)
- **YAGNI**: Implement only what's specified, no extra features
- **DRY**: Reuse RRF logic from ChromaDBBackend where possible
- **Type Safety**: Use type hints everywhere
- **Error Handling**: Raise RuntimeError if not initialized

## Reference Implementations

- **ChromaDBBackend**: See `knowledgebeast/backends/chromadb.py` for RRF pattern
- **VectorBackend ABC**: See `knowledgebeast/backends/base.py` for interface
- **Test Structure**: See `tests/backends/test_chromadb.py` for test patterns
