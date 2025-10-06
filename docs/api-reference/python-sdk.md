# Python SDK Reference

Complete API reference for KnowledgeBeast Python SDK.

## KnowledgeBeast Class

Main class for knowledge base operations.

### Constructor

```python
KnowledgeBeast(config: KnowledgeBeastConfig = None)
```

**Parameters:**
- `config` (optional): Configuration object

**Example:**
```python
kb = KnowledgeBeast()
```

### Methods

#### query(query_text, n_results=5, use_cache=True)

Search the knowledge base.

**Returns:** List of results with text, metadata, and distance.

#### ingest_document(file_path, metadata=None)

Ingest a document.

**Returns:** Number of chunks ingested.

#### get_stats()

Get statistics.

**Returns:** Dict with documents count, cache stats, etc.

#### clear()

Clear all documents.

#### shutdown()

Cleanup resources.

## KnowledgeBeastConfig Class

Configuration for KnowledgeBeast.

### Constructor

```python
KnowledgeBeastConfig(
    data_dir=Path("./data"),
    collection_name="knowledge_base",
    embedding_model="all-MiniLM-L6-v2",
    chunk_size=1000,
    chunk_overlap=200,
    cache_size=100,
    heartbeat_interval=60.0,
    log_level="INFO"
)
```

See [Configuration Guide](../getting-started/configuration.md) for details.

## LRUCache Class

LRU cache for query results.

Located in `knowledgebeast/core/cache.py`.

## KnowledgeBaseHeartbeat Class

Background heartbeat monitoring.

Located in `knowledgebeast/core/heartbeat.py`.
