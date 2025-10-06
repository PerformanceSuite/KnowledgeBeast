# Python API Guide

Complete guide to using KnowledgeBeast in your Python applications.

## Table of Contents

- [Basic Usage](#basic-usage)
- [Configuration](#configuration)
- [Document Ingestion](#document-ingestion)
- [Querying](#querying)
- [Cache Management](#cache-management)
- [Heartbeat Monitoring](#heartbeat-monitoring)
- [Advanced Patterns](#advanced-patterns)

## Basic Usage

### Minimal Example

```python
from knowledgebeast import KnowledgeBeast

# Initialize with defaults
kb = KnowledgeBeast()

# Ingest a document
kb.ingest_document("document.pdf")

# Query
results = kb.query("machine learning")

# Process results
for result in results:
    print(result['text'])

# Cleanup
kb.shutdown()
```

### Context Manager (Recommended)

```python
from knowledgebeast import KnowledgeBeast

with KnowledgeBeast() as kb:
    kb.ingest_document("document.pdf")
    results = kb.query("machine learning")
    # Automatic cleanup on exit
```

## Configuration

### Using KnowledgeBeastConfig

```python
from pathlib import Path
from knowledgebeast import KnowledgeBeast, KnowledgeBeastConfig

# Create custom configuration
config = KnowledgeBeastConfig(
    data_dir=Path("./my-data"),
    collection_name="my_collection",
    embedding_model="all-mpnet-base-v2",
    chunk_size=1500,
    chunk_overlap=300,
    cache_size=200,
    heartbeat_interval=120.0,
    log_level="INFO"
)

# Initialize with config
kb = KnowledgeBeast(config)
```

### Environment-Based Configuration

```python
import os
from pathlib import Path
from knowledgebeast import KnowledgeBeast, KnowledgeBeastConfig

def get_config():
    env = os.getenv("ENV", "development")

    if env == "production":
        return KnowledgeBeastConfig(
            data_dir=Path("/var/lib/knowledgebeast"),
            cache_size=1000,
            log_level="WARNING",
            heartbeat_interval=300.0
        )
    else:
        return KnowledgeBeastConfig(
            data_dir=Path("./dev-data"),
            cache_size=50,
            log_level="DEBUG"
        )

with KnowledgeBeast(get_config()) as kb:
    # Your code here
    pass
```

## Document Ingestion

### Single Document

```python
# Ingest with automatic format detection
chunks = kb.ingest_document("document.pdf")
print(f"Ingested {chunks} chunks")

# With custom metadata
chunks = kb.ingest_document(
    "document.pdf",
    metadata={"author": "John Doe", "category": "ML"}
)
```

### Multiple Documents

```python
from pathlib import Path

documents = [
    Path("paper1.pdf"),
    Path("paper2.pdf"),
    Path("notes.md")
]

for doc in documents:
    try:
        chunks = kb.ingest_document(doc)
        print(f"✓ {doc.name}: {chunks} chunks")
    except Exception as e:
        print(f"✗ {doc.name}: {e}")
```

### Batch Ingestion with Progress

```python
from pathlib import Path
from tqdm import tqdm

def ingest_directory(kb, directory, pattern="**/*.pdf"):
    """Ingest all matching files from a directory."""
    files = list(Path(directory).glob(pattern))

    total_chunks = 0
    for file in tqdm(files, desc="Ingesting documents"):
        try:
            chunks = kb.ingest_document(file)
            total_chunks += chunks
        except Exception as e:
            print(f"Error ingesting {file}: {e}")

    return total_chunks

with KnowledgeBeast() as kb:
    total = ingest_directory(kb, "./papers")
    print(f"Total chunks ingested: {total}")
```

### Supported Document Formats

```python
# PDF documents
kb.ingest_document("research.pdf")

# Markdown files
kb.ingest_document("README.md")

# Text files
kb.ingest_document("notes.txt")

# Word documents
kb.ingest_document("report.docx")

# HTML files
kb.ingest_document("article.html")
```

## Querying

### Basic Query

```python
# Simple query
results = kb.query("machine learning")

# Specify number of results
results = kb.query("neural networks", n_results=10)

# Disable cache
results = kb.query("deep learning", use_cache=False)
```

### Processing Query Results

```python
results = kb.query("artificial intelligence", n_results=5)

for i, result in enumerate(results, 1):
    print(f"\n--- Result {i} ---")
    print(f"Text: {result['text'][:200]}...")
    print(f"Source: {result['metadata']['source']}")
    print(f"Distance: {result['distance']:.4f}")

    # Additional metadata (if provided during ingestion)
    if 'author' in result['metadata']:
        print(f"Author: {result['metadata']['author']}")
```

### Filtering Results

```python
def filter_by_distance(results, max_distance=0.5):
    """Filter results by distance threshold."""
    return [r for r in results if r['distance'] <= max_distance]

def filter_by_source(results, source_pattern):
    """Filter results by source filename pattern."""
    return [r for r in results if source_pattern in r['metadata']['source']]

# Usage
results = kb.query("machine learning", n_results=20)
high_quality = filter_by_distance(results, max_distance=0.3)
from_papers = filter_by_source(high_quality, "paper")

print(f"High-quality results from papers: {len(from_papers)}")
```

### Semantic Search Patterns

```python
class KnowledgeBaseSearch:
    """Advanced search wrapper."""

    def __init__(self, kb):
        self.kb = kb

    def precise_search(self, query, threshold=0.3):
        """Get only highly relevant results."""
        results = self.kb.query(query, n_results=50)
        return [r for r in results if r['distance'] <= threshold]

    def broad_search(self, query, threshold=0.7):
        """Get broader results including less similar matches."""
        return self.kb.query(query, n_results=20)

    def multi_query_search(self, queries):
        """Search with multiple query variations."""
        all_results = []
        seen_texts = set()

        for query in queries:
            results = self.kb.query(query, n_results=10)
            for result in results:
                text = result['text']
                if text not in seen_texts:
                    all_results.append(result)
                    seen_texts.add(text)

        # Sort by distance
        return sorted(all_results, key=lambda r: r['distance'])

# Usage
with KnowledgeBeast() as kb:
    search = KnowledgeBaseSearch(kb)

    # Precise search
    precise = search.precise_search("neural network architectures")

    # Broad search
    broad = search.broad_search("AI applications")

    # Multi-query search
    multi = search.multi_query_search([
        "machine learning algorithms",
        "ML models",
        "predictive analytics"
    ])
```

## Cache Management

### Cache Statistics

```python
# Get cache statistics
stats = kb.get_stats()
cache_stats = stats['cache_stats']

print(f"Cache size: {cache_stats['size']}")
print(f"Cache hits: {cache_stats['hits']}")
print(f"Cache misses: {cache_stats['misses']}")
print(f"Hit rate: {cache_stats['hit_rate']:.2%}")
```

### Manual Cache Control

```python
# Clear cache
cleared = kb.clear_cache()
print(f"Cleared {cleared} cached entries")

# Warm cache with common queries
common_queries = [
    "machine learning basics",
    "neural network training",
    "deep learning frameworks"
]

for query in common_queries:
    kb.query(query)  # Populate cache

print("Cache warmed")
```

### Cache Warming Strategy

```python
def warm_cache_from_file(kb, queries_file):
    """Warm cache with queries from a file."""
    with open(queries_file, 'r') as f:
        queries = [line.strip() for line in f if line.strip()]

    for query in queries:
        try:
            kb.query(query)
        except Exception as e:
            print(f"Error warming cache for '{query}': {e}")

    stats = kb.get_stats()
    print(f"Cache warmed with {len(queries)} queries")
    print(f"Cache size: {stats['cache_stats']['size']}")

with KnowledgeBeast() as kb:
    warm_cache_from_file(kb, "common_queries.txt")
```

## Heartbeat Monitoring

### Starting Heartbeat

```python
# Start heartbeat with custom interval
kb.start_heartbeat(interval=300)  # 5 minutes

# Check status
status = kb.get_heartbeat_status()
print(f"Heartbeat running: {status['running']}")
print(f"Heartbeat count: {status['count']}")

# Stop heartbeat
kb.stop_heartbeat()
```

### Custom Heartbeat Callback

```python
from knowledgebeast import KnowledgeBeast, KnowledgeBaseHeartbeat

def custom_heartbeat_callback():
    """Custom callback for heartbeat events."""
    stats = kb.get_stats()
    print(f"Heartbeat: {stats['total_documents']} documents indexed")

    # Custom monitoring logic
    cache_stats = stats['cache_stats']
    if cache_stats['hit_rate'] < 0.5:
        print("Warning: Low cache hit rate")

# Create custom heartbeat
heartbeat = KnowledgeBaseHeartbeat(
    kb,
    interval=60,
    callback=custom_heartbeat_callback
)

heartbeat.start()
# ... application runs ...
heartbeat.stop()
```

## Advanced Patterns

### Singleton Pattern

```python
class KnowledgeBaseManager:
    """Singleton manager for KnowledgeBeast instance."""
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = KnowledgeBeast()
        return cls._instance

    @classmethod
    def reset(cls):
        if cls._instance is not None:
            cls._instance.shutdown()
            cls._instance = None

# Usage
kb = KnowledgeBaseManager.get_instance()
results = kb.query("machine learning")
```

### Async Wrapper

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

class AsyncKnowledgeBeast:
    """Async wrapper for KnowledgeBeast."""

    def __init__(self, kb):
        self.kb = kb
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def query(self, query_text, n_results=5):
        """Async query method."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.kb.query,
            query_text,
            n_results
        )

    async def ingest_document(self, file_path):
        """Async ingestion method."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.kb.ingest_document,
            file_path
        )

    def shutdown(self):
        self.executor.shutdown(wait=True)
        self.kb.shutdown()

# Usage
async def main():
    kb = KnowledgeBeast()
    async_kb = AsyncKnowledgeBeast(kb)

    # Async queries
    results = await async_kb.query("machine learning")

    # Concurrent queries
    queries = ["AI", "ML", "DL"]
    results = await asyncio.gather(*[
        async_kb.query(q) for q in queries
    ])

    async_kb.shutdown()

asyncio.run(main())
```

### Question-Answering System

```python
class QASystem:
    """Question-answering system using KnowledgeBeast."""

    def __init__(self, kb, llm_client):
        self.kb = kb
        self.llm = llm_client

    def answer(self, question, n_context=3):
        """Answer question using RAG pattern."""
        # Retrieve relevant context
        results = self.kb.query(question, n_results=n_context)

        # Build context
        context = "\n\n".join([
            f"Source: {r['metadata']['source']}\n{r['text']}"
            for r in results
        ])

        # Generate answer using LLM
        prompt = f"""Answer the following question using the provided context.

Question: {question}

Context:
{context}

Answer:"""

        answer = self.llm.generate(prompt)
        return {
            "answer": answer,
            "sources": [r['metadata']['source'] for r in results],
            "context": results
        }

# Usage (pseudo-code)
with KnowledgeBeast() as kb:
    qa = QASystem(kb, llm_client)
    response = qa.answer("What is machine learning?")
    print(response["answer"])
    print(f"Sources: {response['sources']}")
```

### Document Versioning

```python
from datetime import datetime

class VersionedKnowledgeBase:
    """Knowledge base with document versioning."""

    def __init__(self, kb):
        self.kb = kb

    def ingest_versioned(self, file_path, version=None):
        """Ingest document with version metadata."""
        if version is None:
            version = datetime.now().isoformat()

        metadata = {
            "version": version,
            "ingested_at": datetime.now().isoformat(),
            "source": str(file_path)
        }

        return self.kb.ingest_document(file_path, metadata=metadata)

    def query_version(self, query, version=None, n_results=5):
        """Query specific version of documents."""
        results = self.kb.query(query, n_results=n_results * 2)

        if version:
            results = [
                r for r in results
                if r['metadata'].get('version') == version
            ][:n_results]

        return results

# Usage
with KnowledgeBeast() as kb:
    vkb = VersionedKnowledgeBase(kb)

    # Ingest with version
    vkb.ingest_versioned("document.pdf", version="v1.0")

    # Query specific version
    results = vkb.query_version("machine learning", version="v1.0")
```

## Error Handling

```python
from knowledgebeast import KnowledgeBeast

try:
    with KnowledgeBeast() as kb:
        # Ingestion errors
        try:
            kb.ingest_document("missing.pdf")
        except FileNotFoundError:
            print("Document not found")
        except Exception as e:
            print(f"Ingestion error: {e}")

        # Query errors
        try:
            results = kb.query("machine learning")
        except Exception as e:
            print(f"Query error: {e}")

except Exception as e:
    print(f"Initialization error: {e}")
```

## Best Practices

1. **Use Context Managers**: Always use `with` statement for automatic cleanup
2. **Batch Operations**: Ingest documents in batches for better performance
3. **Cache Warming**: Warm cache with common queries after ingestion
4. **Error Handling**: Always wrap operations in try-except blocks
5. **Resource Management**: Call `shutdown()` explicitly if not using context manager
6. **Configuration**: Use environment-based configuration for different deployments
7. **Monitoring**: Enable heartbeat for long-running applications

## Next Steps

- [CLI Usage Guide](cli-usage.md)
- [REST API Guide](rest-api.md)
- [Architecture Overview](../architecture/overview.md)
- [Performance Tuning](../architecture/performance.md)
