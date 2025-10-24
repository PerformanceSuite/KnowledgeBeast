# Backend Abstraction Layer

KnowledgeBeast v3.0 introduces a pluggable backend architecture, allowing you to choose between different vector storage implementations.

## Available Backends

### ChromaDBBackend (Default)

Legacy backend using ChromaDB for vector storage.

**Pros:**
- Backward compatible with v2.x
- Easy setup (no external database)
- Good for development and small-scale deployments

**Cons:**
- Separate service (not integrated with main database)
- Limited multi-tenancy support
- Slower at scale compared to Postgres

**Usage:**

```python
from knowledgebeast.backends import ChromaDBBackend

backend = ChromaDBBackend(
    persist_directory="./chroma_db",
    collection_name="my_kb",
    enable_circuit_breaker=True
)

engine = HybridQueryEngine(repository, backend=backend)
```

### PostgresBackend (v3.0-beta, Week 2)

New backend using PostgreSQL with pgvector and ParadeDB extensions.

**Pros:**
- Unified database (no separate service)
- Production-grade reliability (ACID, replication, backups)
- Better multi-tenancy (schemas/tables)
- Faster at scale (optimized indexes)

**Cons:**
- Requires Postgres 15+ with extensions
- More complex setup

**Usage (coming in Week 2):**

```python
from knowledgebeast.backends import PostgresBackend

backend = PostgresBackend(
    connection_string="postgresql://user:pass@localhost/kb",
    collection_name="my_kb",
    embedding_dimension=384
)

await backend.initialize()  # Create tables/indexes

engine = HybridQueryEngine(repository, backend=backend)
```

## Migration Guide

### From v2.x to v3.0 (ChromaDB)

No changes required! Your existing code works as-is:

```python
# v2.x code
engine = HybridQueryEngine(repository)

# Still works in v3.0 (legacy mode)
engine = HybridQueryEngine(repository)
```

To explicitly use ChromaDBBackend:

```python
# v3.0 with explicit backend
from knowledgebeast.backends import ChromaDBBackend

backend = ChromaDBBackend(persist_directory="./chroma_db")
engine = HybridQueryEngine(repository, backend=backend)
```

### From ChromaDB to Postgres (Week 2)

Migration utility will be provided in v3.0-beta:

```bash
kb-migrate chromadb postgres \
  --chromadb-dir ./chroma_db \
  --postgres-url postgresql://user:pass@localhost/kb \
  --collection my_kb
```

## Backend Interface

All backends implement the `VectorBackend` abstract base class:

```python
class VectorBackend(ABC):
    @abstractmethod
    async def add_documents(self, ids, embeddings, documents, metadatas): ...

    @abstractmethod
    async def query_vector(self, query_embedding, top_k, where): ...

    @abstractmethod
    async def query_keyword(self, query, top_k, where): ...

    @abstractmethod
    async def query_hybrid(self, query_embedding, query_text, top_k, alpha, where): ...

    @abstractmethod
    async def delete_documents(self, ids, where): ...

    @abstractmethod
    async def get_statistics(self): ...

    @abstractmethod
    async def get_health(self): ...

    @abstractmethod
    async def close(self): ...
```

See `knowledgebeast/backends/base.py` for full documentation.

## Custom Backends

You can implement your own backend by subclassing `VectorBackend`:

```python
from knowledgebeast.backends.base import VectorBackend

class MyCustomBackend(VectorBackend):
    async def add_documents(self, ...):
        # Your implementation
        pass

    # Implement all abstract methods
    ...
```

## Roadmap

- **Week 1 (Current)**: Backend abstraction + ChromaDBBackend
- **Week 2**: PostgresBackend implementation
- **Week 3**: Migration utility + benchmarks
- **Week 4**: Production deployment + documentation
- **v4.0**: Deprecate ChromaDBBackend (Postgres only)
