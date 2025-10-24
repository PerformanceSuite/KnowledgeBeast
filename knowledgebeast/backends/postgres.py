"""Postgres backend implementation using pgvector + ParadeDB.

This backend will be implemented in Week 2.
Currently a stub to establish the module structure.
"""

from typing import Any, Dict, List, Optional, Tuple
from knowledgebeast.backends.base import VectorBackend


class PostgresBackend(VectorBackend):
    """Postgres backend using pgvector + ParadeDB.

    Features (Week 2):
    - pgvector for vector similarity search
    - ParadeDB (pg_search) for BM25 keyword search
    - Reciprocal Rank Fusion for hybrid search
    - ACID transactions and production reliability

    Status: STUB - Implementation in Week 2
    """

    def __init__(
        self,
        connection_string: str,
        collection_name: str = "default",
        embedding_dimension: int = 384,
        pool_size: int = 10,
    ):
        """Initialize Postgres backend (stub).

        Args:
            connection_string: PostgreSQL connection string
            collection_name: Collection/table name
            embedding_dimension: Embedding vector dimension
            pool_size: Connection pool size
        """
        raise NotImplementedError(
            "PostgresBackend will be implemented in Week 2. "
            "Use ChromaDBBackend for now."
        )

    # All abstract methods raise NotImplementedError
    async def add_documents(self, ids, embeddings, documents, metadatas):
        raise NotImplementedError("PostgresBackend coming in Week 2")

    async def query_vector(self, query_embedding, top_k=10, where=None):
        raise NotImplementedError("PostgresBackend coming in Week 2")

    async def query_keyword(self, query, top_k=10, where=None):
        raise NotImplementedError("PostgresBackend coming in Week 2")

    async def query_hybrid(self, query_embedding, query_text, top_k=10, alpha=0.7, where=None):
        raise NotImplementedError("PostgresBackend coming in Week 2")

    async def delete_documents(self, ids=None, where=None):
        raise NotImplementedError("PostgresBackend coming in Week 2")

    async def get_statistics(self):
        raise NotImplementedError("PostgresBackend coming in Week 2")

    async def get_health(self):
        raise NotImplementedError("PostgresBackend coming in Week 2")

    async def close(self):
        raise NotImplementedError("PostgresBackend coming in Week 2")
