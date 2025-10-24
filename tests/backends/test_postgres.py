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
