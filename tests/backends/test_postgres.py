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
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        # Mock the context manager for pool.acquire()
        mock_pool.acquire = MagicMock(return_value=MagicMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock()
        ))

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


@pytest.mark.asyncio
async def test_postgres_add_documents():
    """PostgresBackend should add documents to database."""
    with patch('knowledgebeast.backends.postgres.asyncpg') as mock_asyncpg:
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire = MagicMock(return_value=MagicMock(
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
        mock_pool.acquire = MagicMock(return_value=MagicMock(
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
        mock_pool.acquire = MagicMock(return_value=MagicMock(
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

        mock_pool.acquire = MagicMock(return_value=MagicMock(
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


@pytest.mark.asyncio
async def test_postgres_delete_documents():
    """PostgresBackend should delete documents by IDs or metadata filter."""
    with patch('knowledgebeast.backends.postgres.asyncpg') as mock_asyncpg:
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 2")
        mock_pool.acquire = MagicMock(return_value=MagicMock(
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
        result = await backend.delete_documents(ids=["doc1", "doc2"])

        assert result == 2
        assert mock_conn.execute.called

        await backend.close()
