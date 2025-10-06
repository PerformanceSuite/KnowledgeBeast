# Core Engine Architecture

The core engine (`knowledgebeast/core/engine.py`) is the heart of KnowledgeBeast.

## Class Hierarchy

```
KnowledgeBase (Main Engine)
├── Configuration (KnowledgeBeastConfig)
├── Vector Store (ChromaDB Collection)
├── Embeddings (SentenceTransformer)
├── Cache (LRUCache)
└── Heartbeat (KnowledgeBaseHeartbeat)
```

## Initialization

```python
def __init__(self, config: KnowledgeBeastConfig):
    self.config = config
    self.collection = self._init_chroma()
    self.embeddings = self._init_embeddings()
    self.cache = LRUCache(config.cache_size)
    self.heartbeat = None
```

## Document Ingestion

1. Load document with Docling
2. Split into chunks
3. Generate embeddings
4. Store in ChromaDB with metadata

## Query Processing

1. Generate query embedding
2. Check cache
3. Perform vector similarity search
4. Return top-k results
5. Update cache

## Resource Management

- Context manager support
- Automatic cleanup
- Thread-safe operations

For implementation details, see `knowledgebeast/core/engine.py`.
