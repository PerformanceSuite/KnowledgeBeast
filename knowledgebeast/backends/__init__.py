"""Vector backend abstraction layer.

This module provides pluggable backends for vector storage and search,
supporting multiple implementations (ChromaDB, Postgres+pgvector, etc.)

Available backends:
- ChromaDBBackend: Legacy backend using ChromaDB (default)
- PostgresBackend: New backend using pgvector + ParadeDB (v3.0+)
"""

from knowledgebeast.backends.base import VectorBackend
from knowledgebeast.backends.chromadb import ChromaDBBackend
from knowledgebeast.backends.postgres import PostgresBackend

__all__ = [
    "VectorBackend",
    "ChromaDBBackend",
    "PostgresBackend",
]
