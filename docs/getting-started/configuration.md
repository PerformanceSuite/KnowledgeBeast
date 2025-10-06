# Configuration Guide

KnowledgeBeast provides flexible configuration options via Python API, CLI options, and environment variables.

## Configuration Methods

### 1. Python API Configuration

```python
from pathlib import Path
from knowledgebeast import KnowledgeBeast, KnowledgeBeastConfig

config = KnowledgeBeastConfig(
    data_dir=Path("./data"),
    collection_name="my_collection",
    embedding_model="all-MiniLM-L6-v2",
    chunk_size=1000,
    chunk_overlap=200,
    cache_size=100,
    heartbeat_interval=60.0,
    log_level="INFO"
)

kb = KnowledgeBeast(config)
```

### 2. CLI Configuration

```bash
# Most commands accept --data-dir
knowledgebeast query "question" --data-dir ./custom-data

# Some commands have specific options
knowledgebeast serve --host 0.0.0.0 --port 8080
knowledgebeast heartbeat start --interval 300
```

### 3. Environment Variables

Set environment variables with `KB_` prefix:

```bash
# Knowledge directories (comma-separated)
export KB_KNOWLEDGE_DIRS="./docs,./papers"

# Cache settings
export KB_CACHE_FILE="./.cache/knowledge.pkl"
export KB_MAX_CACHE_SIZE=200

# Heartbeat interval (seconds)
export KB_HEARTBEAT_INTERVAL=300

# Auto-warm on initialization
export KB_AUTO_WARM=true
```

## Configuration Options

### Core Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `data_dir` | Path | `./data` | Directory for storing data and indexes |
| `collection_name` | str | `knowledge_base` | ChromaDB collection name |
| `embedding_model` | str | `all-MiniLM-L6-v2` | Sentence-transformers model for embeddings |

### Document Processing

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `chunk_size` | int | 1000 | Maximum chunk size in characters |
| `chunk_overlap` | int | 200 | Overlap between chunks in characters |

### Caching

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `cache_size` | int | 100 | Maximum number of cached queries (LRU) |
| `cache_file` | Path | `.knowledge_cache.pkl` | Path to persistent cache file |

### Monitoring

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `heartbeat_interval` | float | 60.0 | Heartbeat interval in seconds |
| `log_level` | str | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

## Embedding Models

KnowledgeBeast uses [sentence-transformers](https://www.sbert.net/) for embeddings. You can choose from various models:

### Recommended Models

#### all-MiniLM-L6-v2 (Default)
- **Size**: 80MB
- **Dimensions**: 384
- **Speed**: Very Fast
- **Use case**: General purpose, balanced performance

```python
config = KnowledgeBeastConfig(
    embedding_model="all-MiniLM-L6-v2"
)
```

#### all-mpnet-base-v2
- **Size**: 420MB
- **Dimensions**: 768
- **Speed**: Fast
- **Use case**: Higher quality embeddings, technical content

```python
config = KnowledgeBeastConfig(
    embedding_model="all-mpnet-base-v2"
)
```

#### multi-qa-mpnet-base-dot-v1
- **Size**: 420MB
- **Dimensions**: 768
- **Speed**: Fast
- **Use case**: Question-answering, semantic search

```python
config = KnowledgeBeastConfig(
    embedding_model="multi-qa-mpnet-base-dot-v1"
)
```

### Model Performance Comparison

| Model | Size | Speed | Quality | Use Case |
|-------|------|-------|---------|----------|
| all-MiniLM-L6-v2 | 80MB | ⚡⚡⚡ | ⭐⭐⭐ | General purpose |
| all-mpnet-base-v2 | 420MB | ⚡⚡ | ⭐⭐⭐⭐ | Technical docs |
| multi-qa-mpnet-base-dot-v1 | 420MB | ⚡⚡ | ⭐⭐⭐⭐ | Q&A systems |

## Chunk Size Optimization

The `chunk_size` and `chunk_overlap` parameters affect retrieval quality:

### Small Chunks (500-800 characters)
- **Pros**: More precise results, better for specific queries
- **Cons**: More chunks to store, may miss context
- **Use case**: Code snippets, FAQs, definitions

```python
config = KnowledgeBeastConfig(
    chunk_size=500,
    chunk_overlap=100
)
```

### Medium Chunks (1000-1500 characters) - Default
- **Pros**: Balanced context and precision
- **Cons**: Moderate storage
- **Use case**: General documentation, articles

```python
config = KnowledgeBeastConfig(
    chunk_size=1000,
    chunk_overlap=200
)
```

### Large Chunks (2000-3000 characters)
- **Pros**: Better context, fewer chunks
- **Cons**: Less precise results, larger storage
- **Use case**: Long-form content, books, research papers

```python
config = KnowledgeBeastConfig(
    chunk_size=2000,
    chunk_overlap=400
)
```

## Cache Configuration

### Cache Size

Set based on your query patterns:

```python
# Small cache (low memory usage)
config = KnowledgeBeastConfig(cache_size=50)

# Medium cache (default)
config = KnowledgeBeastConfig(cache_size=100)

# Large cache (frequent repeated queries)
config = KnowledgeBeastConfig(cache_size=500)
```

### Persistent Cache

Enable persistent cache across sessions:

```python
config = KnowledgeBeastConfig(
    cache_file=Path("./.cache/knowledge.pkl")
)
```

Disable persistent cache:

```python
config = KnowledgeBeastConfig(
    cache_file=None
)
```

## Logging Configuration

### Log Levels

```python
# Minimal logging
config = KnowledgeBeastConfig(log_level="WARNING")

# Standard logging (default)
config = KnowledgeBeastConfig(log_level="INFO")

# Verbose logging (development)
config = KnowledgeBeastConfig(log_level="DEBUG")
```

### Custom Logging

```python
import logging
from knowledgebeast.utils.logging import setup_logging

# Configure custom logging
setup_logging(
    level="DEBUG",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    log_file="./logs/knowledgebeast.log"
)
```

## Complete Configuration Example

```python
from pathlib import Path
from knowledgebeast import KnowledgeBeast, KnowledgeBeastConfig

# Production configuration
config = KnowledgeBeastConfig(
    # Core settings
    data_dir=Path("./production-data"),
    collection_name="production_knowledge",

    # High-quality embeddings
    embedding_model="all-mpnet-base-v2",

    # Optimized for long-form content
    chunk_size=1500,
    chunk_overlap=300,

    # Large cache for production
    cache_size=500,
    cache_file=Path("./.cache/prod-cache.pkl"),

    # Monitoring
    heartbeat_interval=300.0,
    log_level="INFO"
)

with KnowledgeBeast(config) as kb:
    # Your application logic
    pass
```

## Environment-Based Configuration

```python
import os
from pathlib import Path
from knowledgebeast import KnowledgeBeastConfig

# Load configuration based on environment
env = os.getenv("ENVIRONMENT", "development")

if env == "production":
    config = KnowledgeBeastConfig(
        data_dir=Path("/var/lib/knowledgebeast"),
        cache_size=1000,
        log_level="WARNING"
    )
elif env == "development":
    config = KnowledgeBeastConfig(
        data_dir=Path("./dev-data"),
        cache_size=50,
        log_level="DEBUG"
    )
else:  # testing
    config = KnowledgeBeastConfig(
        data_dir=Path("./test-data"),
        cache_size=10,
        log_level="ERROR"
    )
```

## Configuration Validation

KnowledgeBeast validates configuration on initialization:

```python
# This will raise ValueError
config = KnowledgeBeastConfig(
    cache_size=0  # Must be positive
)

# This will raise ValueError
config = KnowledgeBeastConfig(
    heartbeat_interval=5  # Must be at least 10 seconds
)
```

## Next Steps

- [Python API Guide](../guides/python-api.md)
- [Performance Tuning](../architecture/performance.md)
- [Production Checklist](../deployment/production-checklist.md)
