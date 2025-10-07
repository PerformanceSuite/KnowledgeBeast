# Performance Tuning Guide

## Overview

This guide provides comprehensive performance optimization strategies for KnowledgeBeast. Following these recommendations will help you achieve optimal query performance, throughput, and resource utilization across different deployment scenarios.

**Performance Achievements:**
- 8x throughput improvement from lock optimization (Week 1)
- 2-4x speedup from parallel ingestion (Week 2)
- P99 query latency: ~80ms (uncached)
- P99 cached query: ~5ms
- Concurrent throughput: 800+ queries/sec (10 workers)

---

## Table of Contents

1. [Performance Metrics](#performance-metrics)
2. [Query Optimization](#query-optimization)
3. [Ingestion Optimization](#ingestion-optimization)
4. [Threading & Concurrency](#threading--concurrency)
5. [Caching Strategy](#caching-strategy)
6. [API Performance](#api-performance)
7. [Resource Management](#resource-management)
8. [Monitoring & Profiling](#monitoring--profiling)
9. [Troubleshooting](#troubleshooting)
10. [Configuration Examples](#configuration-examples)

---

## Performance Metrics

### Current Benchmarks

**Query Latency (P50/P95/P99):**
```
Uncached Queries:
  P50: ~40ms
  P95: ~70ms
  P99: ~80ms

Cached Queries:
  P50: ~2ms
  P95: ~4ms
  P99: ~5ms
```

**Throughput:**
```
Sequential:    500+ queries/sec
10 workers:    800+ queries/sec
50 workers:    600+ queries/sec
```

**Cache Performance:**
```
Hit Ratio:     > 90% (with repeated queries)
Hit Latency:   < 50μs
Miss Latency:  < 100μs
Utilization:   Auto-managed (LRU eviction)
```

**Memory Usage:**
```
Base:          ~500MB (model loading)
Per 1k docs:   ~200MB
Cache (100):   ~10MB
```

### Performance Targets

| Metric | Target | Purpose |
|--------|--------|---------|
| P99 Query Latency | < 100ms | User experience |
| P99 Cached Query | < 10ms | High responsiveness |
| Concurrent Throughput (10w) | > 500 q/s | Production load |
| Concurrent Throughput (50w) | > 300 q/s | Stress testing |
| Cache Hit Ratio | > 90% | Minimize redundant work |
| Data Corruption | 0% | Thread safety |

### Monitoring Tools

**Performance Dashboard:**
```bash
# Run comprehensive benchmarks
knowledgebeast benchmark --output report.html

# JSON output for CI/CD
knowledgebeast benchmark --format json --output metrics.json

# Text output to console
knowledgebeast benchmark --format text
```

**Key Metrics to Track:**
- Query latency percentiles (P50, P95, P99)
- Throughput (queries/second)
- Cache hit rate
- Memory usage (RSS, VMS)
- Lock contention (via throughput degradation)
- Worker scalability

---

## Query Optimization

### Index Structure Efficiency

**Inverted Index Design:**
```python
# KnowledgeBeast uses optimized inverted index
# Term -> [doc_id1, doc_id2, ...] mapping

# Efficient for:
# - Multi-term queries (intersection)
# - Relevance scoring (term frequency)
# - Fast lookups (O(1) term access)
```

**Optimization Strategies:**

1. **Use Specific Terms:**
   ```python
   # GOOD: Specific terms
   kb.query("audio processing fft algorithm")

   # LESS EFFICIENT: Generic terms
   kb.query("audio video")
   ```

2. **Query Complexity:**
   - Fewer terms = faster queries
   - More specific terms = better results
   - Balance specificity vs recall

3. **Term Normalization:**
   - All terms are lowercased automatically
   - Stemming not applied (exact match for precision)

### Cache Warming Strategies

**Automatic Cache Warming:**
```python
config = KnowledgeBeastConfig(
    knowledge_dirs=[Path("knowledge")],
    auto_warm=True,  # Enable automatic warming
    warming_queries=[
        "most common user queries",
        "key technical terms",
        "frequent search patterns"
    ]
)
kb = KnowledgeBase(config)
kb.ingest_all()  # Warming happens after ingestion
```

**Manual Cache Warming:**
```python
# Warm cache with production query patterns
common_queries = [
    "audio processing",
    "machine learning",
    "data analysis",
    # ... top 10-20 queries from analytics
]

for query in common_queries:
    kb.query(query, use_cache=True)  # IMPORTANT: use_cache=True

# Verify cache population
stats = kb.get_stats()
print(f"Cache warmed: {stats['cache_hits']} hits")
```

**Critical Cache Warming Rule:**
```python
# BAD: Cache never populated
kb.query("test", use_cache=False)

# GOOD: Cache populated for future use
kb.query("test", use_cache=True)
```

**Timing:**
- Warm cache after ingestion completes
- Re-warm after index rebuilds
- Update warming queries based on analytics
- Consider background warming during off-peak hours

### Query Result Caching

**LRU Cache Configuration:**
```python
config = KnowledgeBeastConfig(
    max_cache_size=100  # Default: 100 queries
)

# For high-traffic applications:
config = KnowledgeBeastConfig(
    max_cache_size=1000  # Larger cache
)
```

**Cache Key Generation:**
```python
# Cache key includes:
# - Normalized query terms (lowercase, sorted)
# - use_cache flag is NOT part of key (cached results used if available)

# These hit the same cache entry:
kb.query("Audio Processing")
kb.query("processing audio")
kb.query("AUDIO PROCESSING")
```

**Cache Invalidation:**
```python
# Cache automatically invalidated on ingestion
kb.ingest_all()  # Old cache cleared, new index built

# Manual cache management not needed (automatic LRU eviction)
```

### Pagination for Large Result Sets

**Current Implementation:**
```python
# KnowledgeBeast returns all matches sorted by relevance
results = kb.query("audio")
# Results: [(doc_id, doc_data), ...]

# For large result sets, implement client-side pagination:
page_size = 10
page = 0
paginated_results = results[page * page_size:(page + 1) * page_size]
```

**Recommended Approach:**
```python
def paginate_results(results, page=0, page_size=10):
    """Paginate query results."""
    start = page * page_size
    end = start + page_size
    return {
        'results': results[start:end],
        'total': len(results),
        'page': page,
        'page_size': page_size,
        'total_pages': (len(results) + page_size - 1) // page_size
    }

# Usage
results = kb.query("audio processing")
page_data = paginate_results(results, page=0, page_size=10)
```

---

## Ingestion Optimization

### Parallel Document Ingestion

**Worker Pool Configuration:**
```python
import multiprocessing

# Auto-detect CPU count (default)
config = KnowledgeBeastConfig(
    knowledge_dirs=[Path("knowledge")],
    max_workers=None  # Auto: uses CPU count
)

# Manual configuration
config = KnowledgeBeastConfig(
    max_workers=4  # Fixed worker count
)

# Environment variable
export KB_MAX_WORKERS=8
```

**Performance Characteristics:**

| Workers | Speedup | Use Case |
|---------|---------|----------|
| 1 | 1.0x | Baseline, debugging |
| 2 | 1.5-1.8x | Small datasets |
| 4 | 2.0-3.0x | Recommended default |
| 8 | 2.5-4.0x | Large datasets, high CPU |
| 16+ | 2.0-3.5x | Diminishing returns (I/O bound) |

**Optimal Worker Count:**
```python
# Rule of thumb: workers = CPU cores
# Adjust based on workload:

# CPU-bound converter: workers = CPU cores
config = KnowledgeBeastConfig(max_workers=multiprocessing.cpu_count())

# I/O-bound converter: workers = CPU cores * 2
config = KnowledgeBeastConfig(max_workers=multiprocessing.cpu_count() * 2)

# Memory-constrained: reduce workers
config = KnowledgeBeastConfig(max_workers=2)
```

### Batch Processing Strategies

**File Organization:**
```bash
# Organize files for efficient batch processing
knowledge/
  ├── category_a/  # Process by category
  │   ├── doc1.md
  │   └── doc2.md
  ├── category_b/
  │   ├── doc3.md
  │   └── doc4.md
  └── ...
```

**Incremental Ingestion:**
```python
# For very large knowledge bases, process in batches
import os
from pathlib import Path

def ingest_by_category(kb_base_dir):
    """Ingest documents category by category."""
    categories = [d for d in kb_base_dir.iterdir() if d.is_dir()]

    for category in categories:
        config = KnowledgeBeastConfig(
            knowledge_dirs=[category],
            max_workers=4
        )
        kb = KnowledgeBase(config)
        kb.ingest_all()
        print(f"Processed {category.name}: {kb.get_stats()['total_documents']} docs")
```

### File Format Considerations

**Supported Formats:**
- Markdown (.md) - Fastest, recommended
- Text (.txt) - Fast
- PDF (.pdf) - Slower (document parsing overhead)
- DOCX (.docx) - Slower (document parsing overhead)

**Optimization Tips:**
```python
# Convert complex documents to Markdown for faster ingestion
# Use parallel conversion tools:
# - pandoc for bulk conversion
# - docling for PDF/DOCX extraction

# Pre-process documents:
# 1. Extract text from PDFs offline
# 2. Save as .md or .txt
# 3. Ingest preprocessed files (faster)
```

**Ingestion Performance by Format:**

| Format | Relative Speed | Notes |
|--------|---------------|-------|
| .md | 1.0x | Baseline, fastest |
| .txt | 1.0x | Same as Markdown |
| .pdf | 0.3-0.5x | Docling overhead |
| .docx | 0.4-0.6x | Parsing overhead |

### Atomic Index Updates

**Thread-Safe Ingestion Pattern:**
```python
# KnowledgeBeast uses atomic swap pattern
# Old index remains available during rebuild

# Implementation (simplified):
def _build_index(self):
    # Build in local variables (no locks)
    new_documents = {}
    new_index = {}

    # Process files in parallel
    with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
        futures = {executor.submit(self._process_file, f): f for f in files}
        for future in as_completed(futures):
            doc_id, doc_data, terms = future.result()
            new_documents[doc_id] = doc_data
            # Build index...

    # Atomic swap with lock
    with self._lock:
        self.documents = new_documents
        self.index = new_index
```

**Benefits:**
- Zero downtime during index rebuilds
- Queries use old index during rebuild
- Atomic transition (no partial state)
- Thread-safe concurrent queries

---

## Threading & Concurrency

### Lock Contention Minimization

**Snapshot Pattern (Key Optimization):**
```python
# BEFORE: Lock held during entire search (slow)
with self._lock:
    matches = {}
    for term in search_terms:
        if term in self.index:
            for doc_id in self.index[term]:
                matches[doc_id] = matches.get(doc_id, 0) + 1
    # More processing...

# AFTER: Snapshot pattern (5-10x faster)
with self._lock:
    # Quick snapshot creation (<1ms)
    index_snapshot = {
        term: list(self.index.get(term, []))
        for term in search_terms
    }

# Process without lock (parallel execution)
matches = {}
for term, doc_ids in index_snapshot.items:
    for doc_id in doc_ids:
        matches[doc_id] = matches.get(doc_id, 0) + 1
```

**Performance Impact:**
- Lock held: <1ms (snapshot creation only)
- Parallel processing: Unlimited concurrent queries
- Throughput improvement: 5-10x
- Zero data corruption

**See Also:** `CLAUDE.md` for detailed threading best practices

### Thread Pool Sizing

**Query Workers:**
```python
# API server worker configuration
# Use uvicorn/gunicorn for production

# Development (single worker)
uvicorn knowledgebeast.api.app:app --workers 1

# Production (multiple workers)
uvicorn knowledgebeast.api.app:app --workers 4 --worker-class uvicorn.workers.UvicornWorker

# Calculate optimal workers:
# workers = (2 * CPU_cores) + 1
# For 4 cores: (2 * 4) + 1 = 9 workers
```

**Ingestion Workers:**
```python
# Set via config or environment variable
config = KnowledgeBeastConfig(
    max_workers=4  # Ingestion parallelism
)

# Or:
export KB_MAX_WORKERS=8
```

### Thread-Safe Components

**LRU Cache Thread Safety:**
```python
# Cache is fully thread-safe
cache = LRUCache[str, list](capacity=100)

# Safe from multiple threads:
cache.put(key, value)  # Thread-safe
cache.get(key)         # Thread-safe
cache.stats()          # Thread-safe

# Implementation uses threading.Lock() internally
# All operations are atomic
```

**KnowledgeBase Thread Safety:**
```python
# KnowledgeBase uses RLock (reentrant lock)
kb = KnowledgeBase(config)

# Safe concurrent operations:
# - Multiple concurrent queries (using snapshot pattern)
# - Query while ingestion in progress (old index)
# - Stats access from multiple threads
```

### Common Pitfalls to Avoid

**1. Lock Ordering Deadlocks:**
```python
# BAD: Nested locks (deadlock risk)
with self._lock:
    with self.cache._lock:
        # Danger!
        pass

# GOOD: Use thread-safe components
cached = self.query_cache.get(key)  # Cache handles locking
```

**2. Returning Mutable References:**
```python
# BAD: Returns shared data
with self._lock:
    return self.documents[doc_id]  # Can be modified by caller

# GOOD: Return deep copy
with self._lock:
    return dict(self.documents[doc_id])  # Safe copy
```

**3. Lock Held During I/O:**
```python
# BAD: Blocks all threads during I/O
with self._lock:
    result = self.converter.convert(file)  # Slow!
    self.documents[doc_id] = result

# GOOD: I/O without lock
result = self.converter.convert(file)  # No lock
with self._lock:
    self.documents[doc_id] = result  # Quick update
```

---

## Caching Strategy

### LRU Cache Sizing

**Default Configuration:**
```python
config = KnowledgeBeastConfig(
    max_cache_size=100  # 100 queries cached
)
```

**Sizing Guidelines:**

| Scenario | Cache Size | Rationale |
|----------|-----------|-----------|
| Development | 50-100 | Small dataset, frequent changes |
| Production (low traffic) | 100-500 | Normal usage patterns |
| Production (high traffic) | 500-2000 | Many unique queries |
| Analytics/Batch | 50 | Few repeated queries |

**Memory Calculation:**
```python
# Rough estimate:
# cache_memory = cache_size * avg_result_size

# Example:
# - cache_size: 1000
# - avg_result_size: 10KB
# - total: 1000 * 10KB = 10MB

# Monitor with:
import sys
stats = kb.get_stats()
print(f"Cache entries: {stats['cache_hits'] + stats['cache_misses']}")
```

**Environment Variable:**
```bash
export KB_MAX_CACHE_SIZE=1000
```

### Cache Eviction Policy

**LRU (Least Recently Used):**
- Automatic eviction when capacity reached
- Most recently accessed items retained
- No manual intervention required

**Eviction Characteristics:**
```python
cache = LRUCache[str, list](capacity=100)

# Fill cache
for i in range(100):
    cache.put(f"key_{i}", f"value_{i}")

# Add one more (triggers eviction)
cache.put("key_100", "value_100")
# key_0 evicted (least recently used)

# Access updates position
cache.get("key_1")  # Now most recently used
# key_1 won't be evicted next
```

### Multi-Level Caching

**Current Architecture:**
```
Query -> Check LRU Cache -> Index Search -> Document Retrieval
         (in-memory)        (in-memory)     (in-memory)
```

**Future Enhancement (Persistent Cache):**
```python
# Proposed multi-level caching
# L1: In-memory LRU (fast, volatile)
# L2: On-disk cache (slower, persistent)

# Not yet implemented
```

### Cache Warming Timing

**Best Practices:**

1. **After Ingestion:**
   ```python
   kb.ingest_all()
   # Warming queries automatically executed if auto_warm=True
   ```

2. **After Index Rebuild:**
   ```python
   kb.ingest_all()
   # Cache cleared, warming queries re-executed
   ```

3. **Scheduled Warming:**
   ```python
   # Warm cache during off-peak hours
   import schedule

   def warm_cache():
       for query in top_queries:
           kb.query(query, use_cache=True)

   schedule.every().day.at("02:00").do(warm_cache)
   ```

4. **On-Demand Warming:**
   ```python
   # API endpoint for manual warming
   @app.post("/api/v1/admin/warm-cache")
   async def warm_cache():
       # Execute warming queries
       return {"status": "cache warmed"}
   ```

---

## API Performance

### Worker Process Configuration

**Uvicorn (Development):**
```bash
# Single worker (development)
uvicorn knowledgebeast.api.app:app --host 0.0.0.0 --port 8000

# Multiple workers (production)
uvicorn knowledgebeast.api.app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker
```

**Gunicorn + Uvicorn (Production):**
```bash
gunicorn knowledgebeast.api.app:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --graceful-timeout 30 \
  --keep-alive 5
```

**Worker Count Formula:**
```python
# CPU-bound workloads:
workers = (2 * CPU_cores) + 1

# I/O-bound workloads:
workers = (2 * CPU_cores) * 2 + 1

# Example (4 cores):
# CPU-bound: (2 * 4) + 1 = 9 workers
# I/O-bound: ((2 * 4) * 2) + 1 = 17 workers
```

### Request Batching

**Current Implementation:**
```python
# Single query per request
POST /api/v1/query
{
  "query": "audio processing"
}

# For bulk queries, send multiple requests in parallel
# Client-side batching recommended
```

**Client-Side Batching:**
```python
import asyncio
import aiohttp

async def batch_query(queries):
    """Execute multiple queries in parallel."""
    async with aiohttp.ClientSession() as session:
        tasks = [
            session.post("http://localhost:8000/api/v1/query",
                        json={"query": q})
            for q in queries
        ]
        responses = await asyncio.gather(*tasks)
        return [await r.json() for r in responses]

# Usage
queries = ["audio", "video", "ml"]
results = asyncio.run(batch_query(queries))
```

### Connection Pooling

**Client Configuration:**
```python
import httpx

# Use connection pooling for better performance
client = httpx.Client(
    limits=httpx.Limits(
        max_connections=100,
        max_keepalive_connections=20
    ),
    timeout=httpx.Timeout(10.0)
)

# Reuse client for multiple requests
for query in queries:
    response = client.post("http://localhost:8000/api/v1/query",
                          json={"query": query})
    results = response.json()
```

**Server Configuration:**
```bash
# Keep-alive settings
gunicorn knowledgebeast.api.app:app \
  --keep-alive 5 \
  --timeout 120
```

### Middleware Optimization

**Performance-Critical Middleware:**

1. **Request ID Middleware:**
   - Minimal overhead (~10μs)
   - Essential for tracing

2. **Timing Middleware:**
   - Adds performance headers
   - Overhead: ~5μs

3. **Logging Middleware:**
   - Can impact performance under high load
   - Use appropriate log level (INFO in prod, DEBUG off)

4. **Security Headers:**
   - Minimal overhead (~20μs)
   - Required for production

**Optimization:**
```python
# Disable verbose logging in production
import logging
logging.getLogger("knowledgebeast.api").setLevel(logging.INFO)

# Or via environment
export LOG_LEVEL=INFO
```

**Middleware Ordering:**
```python
# Current order (optimized):
app.add_middleware(SecurityHeadersMiddleware)     # ~20μs
app.add_middleware(RequestSizeLimitMiddleware)    # ~10μs
app.add_middleware(CacheHeaderMiddleware)         # ~5μs
app.add_middleware(RequestIDMiddleware)           # ~10μs
app.add_middleware(TimingMiddleware)              # ~5μs
app.add_middleware(LoggingMiddleware)             # ~50μs (with I/O)

# Total overhead: ~100μs per request
```

---

## Resource Management

### Memory Configuration

**Memory Requirements:**

| Component | Memory Usage | Notes |
|-----------|-------------|-------|
| Base process | ~100MB | Python runtime |
| Document converter | ~400MB | Docling models |
| Index (1k docs) | ~200MB | Document + index data |
| Cache (100 entries) | ~10MB | Query results |
| **Total (small KB)** | **~710MB** | Minimum recommended |
| **Total (10k docs)** | **~2.5GB** | Production typical |

**Docker Memory Limits:**
```yaml
# docker-compose.yml
services:
  knowledgebeast:
    image: knowledgebeast:latest
    deploy:
      resources:
        limits:
          memory: 4G  # Recommended for production
        reservations:
          memory: 2G  # Minimum guaranteed
```

**Kubernetes Resource Limits:**
```yaml
# deployment.yaml
resources:
  requests:
    memory: "2Gi"
    cpu: "1000m"
  limits:
    memory: "4Gi"
    cpu: "2000m"
```

### Disk I/O Optimization

**File System Considerations:**
```bash
# Use fast local disk for knowledge base
# Avoid network file systems (NFS) if possible

# Mount SSD for optimal performance
/mnt/ssd/knowledge-base/

# Cache file on fast disk
export KB_CACHE_FILE=/mnt/ssd/.knowledge_cache.pkl
```

**I/O Patterns:**
```python
# Sequential reads during ingestion (fast)
# Random reads during queries (cached in memory)

# Optimize for:
# - Fast sequential read (ingestion)
# - Small random reads (cache misses)
```

### CPU Affinity

**Linux CPU Pinning:**
```bash
# Pin API workers to specific cores
taskset -c 0,1,2,3 uvicorn knowledgebeast.api.app:app --workers 4

# Or via systemd
[Service]
CPUAffinity=0 1 2 3
```

**Docker CPU Limits:**
```yaml
services:
  knowledgebeast:
    deploy:
      resources:
        limits:
          cpus: '4.0'
        reservations:
          cpus: '2.0'
```

### Container Resource Limits

**Production Docker Configuration:**
```yaml
version: '3.8'
services:
  knowledgebeast:
    image: knowledgebeast:latest
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '4.0'
        reservations:
          memory: 2G
          cpus: '2.0'
    environment:
      - KB_MAX_WORKERS=4
      - KB_MAX_CACHE_SIZE=500
      - LOG_LEVEL=INFO
    volumes:
      - ./knowledge:/app/knowledge:ro
      - cache-volume:/app/cache
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  cache-volume:
```

---

## Monitoring & Profiling

### Performance Dashboard Usage

**Run Full Benchmark Suite:**
```bash
# HTML report with graphs
knowledgebeast benchmark --output report.html

# Open in browser
open report.html
```

**JSON Output for CI/CD:**
```bash
# Generate JSON metrics
knowledgebeast benchmark --format json --output metrics.json

# Parse in CI pipeline
cat metrics.json | jq '.query_latency.p99_ms'
```

**Automated Benchmarking:**
```bash
#!/bin/bash
# run_benchmarks.sh

# Run benchmarks
knowledgebeast benchmark --format json --output metrics.json

# Check thresholds
P99=$(cat metrics.json | jq -r '.query_latency.p99_ms')
THROUGHPUT=$(cat metrics.json | jq -r '.throughput_concurrent[0].queries_per_second')

if (( $(echo "$P99 > 100" | bc -l) )); then
    echo "ERROR: P99 latency too high: ${P99}ms"
    exit 1
fi

if (( $(echo "$THROUGHPUT < 500" | bc -l) )); then
    echo "ERROR: Throughput too low: ${THROUGHPUT} q/s"
    exit 1
fi

echo "Performance benchmarks passed!"
```

### Benchmark Command

**Usage:**
```bash
# Basic benchmarks
knowledgebeast benchmark

# Custom output
knowledgebeast benchmark --output perf-report.html --format html

# JSON for automation
knowledgebeast benchmark --output metrics.json --format json

# Text to console
knowledgebeast benchmark --format text
```

**Benchmark Components:**
1. System information (CPU, memory, OS)
2. Query latency (uncached)
3. Query latency (cached)
4. Sequential throughput
5. Concurrent throughput (10, 50 workers)
6. Cache performance
7. Memory usage
8. Scalability analysis

### Profiling Tools

**cProfile (CPU Profiling):**
```python
import cProfile
import pstats
from pstats import SortKey

# Profile query execution
profiler = cProfile.Profile()
profiler.enable()

for _ in range(100):
    kb.query("audio processing")

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats(SortKey.CUMULATIVE)
stats.print_stats(20)  # Top 20 functions
```

**py-spy (Sampling Profiler):**
```bash
# Install
pip install py-spy

# Profile API server
py-spy top --pid <uvicorn_pid>

# Generate flamegraph
py-spy record --pid <uvicorn_pid> --output profile.svg --duration 60

# View flamegraph
open profile.svg
```

**Memory Profiling:**
```python
import tracemalloc

# Start tracing
tracemalloc.start()

# Run workload
kb.ingest_all()

# Get snapshot
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

print("[ Top 10 ]")
for stat in top_stats[:10]:
    print(stat)
```

### Metrics Collection

**Prometheus Integration (Future):**
```python
# Proposed metrics
# - knowledgebeast_queries_total (counter)
# - knowledgebeast_query_duration_seconds (histogram)
# - knowledgebeast_cache_hits_total (counter)
# - knowledgebeast_cache_misses_total (counter)
# - knowledgebeast_documents_total (gauge)
# - knowledgebeast_index_size_bytes (gauge)
```

**Current Metrics Access:**
```python
# Get stats via API
GET /api/v1/stats

# Response:
{
  "total_documents": 150,
  "total_terms": 5000,
  "queries": 1000,
  "cache_hits": 850,
  "cache_misses": 150,
  "last_access": "2025-10-06T12:00:00Z"
}

# Calculate metrics:
# - Cache hit ratio: cache_hits / (cache_hits + cache_misses)
# - Query rate: queries / uptime
```

---

## Troubleshooting

### Slow Query Diagnosis

**Symptoms:**
- Queries taking > 100ms
- High P99 latency
- User complaints

**Diagnostic Steps:**

1. **Check Cache Hit Rate:**
   ```python
   stats = kb.get_stats()
   hit_rate = stats['cache_hits'] / (stats['cache_hits'] + stats['cache_misses'])
   print(f"Cache hit rate: {hit_rate*100:.1f}%")

   # If < 80%, consider:
   # - Increasing cache size
   # - Warming cache with common queries
   # - Analyzing query patterns
   ```

2. **Profile Query Execution:**
   ```python
   import time

   start = time.perf_counter()
   results = kb.query("test query", use_cache=False)
   elapsed = time.perf_counter() - start

   print(f"Query time: {elapsed*1000:.2f}ms")
   print(f"Results: {len(results)} documents")
   ```

3. **Check Index Size:**
   ```python
   stats = kb.get_stats()
   print(f"Documents: {stats['total_documents']}")
   print(f"Terms: {stats['total_terms']}")

   # Large index (> 100k docs) may need optimization
   ```

4. **Analyze Query Complexity:**
   ```python
   # Simple query (fast)
   kb.query("audio")

   # Complex query (slower)
   kb.query("audio processing machine learning data science")

   # Too generic (many results)
   kb.query("the")  # Slow due to many matches
   ```

**Solutions:**
- Enable caching
- Warm cache with common queries
- Optimize query terms (fewer, more specific)
- Increase cache size
- Check for lock contention (see below)

### High Memory Usage

**Symptoms:**
- Process using > 4GB RAM
- OOM errors
- Slow performance (swapping)

**Diagnostic Steps:**

1. **Check Component Memory:**
   ```python
   import psutil
   import os

   process = psutil.Process(os.getpid())
   mem_info = process.memory_info()

   print(f"RSS: {mem_info.rss / 1024**2:.2f} MB")
   print(f"VMS: {mem_info.vms / 1024**2:.2f} MB")
   ```

2. **Profile Memory Usage:**
   ```python
   import tracemalloc

   tracemalloc.start()
   kb.ingest_all()
   snapshot = tracemalloc.take_snapshot()

   top_stats = snapshot.statistics('lineno')
   for stat in top_stats[:10]:
       print(stat)
   ```

3. **Check Document Count:**
   ```python
   stats = kb.get_stats()
   estimated_memory = stats['total_documents'] * 200 * 1024  # ~200KB per doc
   print(f"Estimated: {estimated_memory / 1024**2:.2f} MB")
   ```

**Solutions:**
- Reduce cache size
- Process documents in batches
- Limit ingestion workers
- Increase container memory limits
- Consider document size reduction (summarization)

### Thread Bottlenecks

**Symptoms:**
- Low concurrent throughput
- CPU usage < 50% with many workers
- High latency under load

**Diagnostic Steps:**

1. **Measure Concurrent Performance:**
   ```python
   from concurrent.futures import ThreadPoolExecutor
   import time

   def worker():
       kb.query("test query")

   workers = 20
   start = time.time()
   with ThreadPoolExecutor(max_workers=workers) as executor:
       futures = [executor.submit(worker) for _ in range(100)]
       for f in futures:
           f.result()
   elapsed = time.time() - start

   throughput = 100 / elapsed
   print(f"Throughput: {throughput:.2f} q/s")

   # If < 200 q/s with 20 workers, likely lock contention
   ```

2. **Check Lock Implementation:**
   ```python
   # Verify snapshot pattern is used
   # (see CLAUDE.md for details)

   # Lock should only be held during:
   # - Index snapshot creation (~1ms)
   # - Stats updates (~0.1ms)
   # - Document retrieval (~1ms)
   ```

3. **Profile with py-spy:**
   ```bash
   py-spy record --pid <pid> --output profile.svg --duration 30
   # Look for time spent in lock acquisition
   ```

**Solutions:**
- Verify snapshot pattern implementation
- Check for nested locks
- Ensure minimal lock scope
- Review thread-safe component usage

### Cache Inefficiency

**Symptoms:**
- Low cache hit rate (< 80%)
- High cache miss latency
- Cache not warming properly

**Diagnostic Steps:**

1. **Analyze Cache Stats:**
   ```python
   stats = kb.get_stats()
   hit_rate = stats['cache_hits'] / (stats['cache_hits'] + stats['cache_misses'])

   print(f"Cache hits: {stats['cache_hits']}")
   print(f"Cache misses: {stats['cache_misses']}")
   print(f"Hit rate: {hit_rate*100:.1f}%")
   ```

2. **Test Cache Warming:**
   ```python
   # Query before warming
   result1 = kb.query("test", use_cache=True)

   # Query again (should be cached)
   import time
   start = time.perf_counter()
   result2 = kb.query("test", use_cache=True)
   elapsed = time.perf_counter() - start

   print(f"Cached query time: {elapsed*1000:.2f}ms")
   # Should be < 10ms
   ```

3. **Check Query Variations:**
   ```python
   # These are different cache entries:
   kb.query("audio processing")
   kb.query("Audio Processing")  # Different case
   kb.query("processing audio")  # Different order

   # Note: KnowledgeBeast normalizes these, but check
   ```

**Solutions:**
- Increase cache size
- Use `use_cache=True` for warming
- Normalize queries before caching
- Analyze query patterns (unique vs repeated)
- Pre-warm common queries

---

## Configuration Examples

### Development (Small Dataset)

**Configuration:**
```python
# config_dev.py
from pathlib import Path
from knowledgebeast.core.config import KnowledgeBeastConfig

config = KnowledgeBeastConfig(
    knowledge_dirs=[Path("./knowledge")],
    cache_file=Path("./.knowledge_cache.pkl"),
    max_cache_size=50,  # Small cache
    heartbeat_interval=300,
    auto_warm=True,
    warming_queries=[
        "test query 1",
        "test query 2"
    ],
    max_workers=2,  # Limited parallelism
    verbose=True  # Verbose logging
)
```

**API Server:**
```bash
# Single worker for debugging
uvicorn knowledgebeast.api.app:app \
  --reload \
  --workers 1 \
  --log-level debug
```

**Resource Limits:**
```yaml
# docker-compose.dev.yml
services:
  knowledgebeast:
    image: knowledgebeast:latest
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
```

**Expected Performance:**
- Documents: < 1000
- Queries: 100-500 q/s (single worker)
- Memory: ~1GB
- Ingestion: Sequential (1 worker)

### Production (Large Dataset)

**Configuration:**
```python
# config_prod.py
from pathlib import Path
from knowledgebeast.core.config import KnowledgeBeastConfig

config = KnowledgeBeastConfig(
    knowledge_dirs=[
        Path("/data/knowledge/docs"),
        Path("/data/knowledge/manuals"),
        Path("/data/knowledge/guides")
    ],
    cache_file=Path("/data/cache/.knowledge_cache.pkl"),
    max_cache_size=1000,  # Large cache
    heartbeat_interval=300,
    auto_warm=True,
    warming_queries=[
        # Top 20 queries from analytics
        "common query 1",
        "common query 2",
        # ...
    ],
    max_workers=8,  # Parallel ingestion
    verbose=False  # Production logging
)
```

**API Server:**
```bash
# Multiple workers with Gunicorn
gunicorn knowledgebeast.api.app:app \
  --workers 9 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --graceful-timeout 30 \
  --keep-alive 5 \
  --access-logfile /var/log/knowledgebeast/access.log \
  --error-logfile /var/log/knowledgebeast/error.log \
  --log-level info
```

**Resource Limits:**
```yaml
# docker-compose.prod.yml
services:
  knowledgebeast:
    image: knowledgebeast:latest
    deploy:
      resources:
        limits:
          memory: 8G
          cpus: '8.0'
        reservations:
          memory: 4G
          cpus: '4.0'
    environment:
      - KB_MAX_WORKERS=8
      - KB_MAX_CACHE_SIZE=1000
      - LOG_LEVEL=INFO
    volumes:
      - /data/knowledge:/app/knowledge:ro
      - /data/cache:/app/cache
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
```

**Expected Performance:**
- Documents: 10k-100k
- Queries: 800+ q/s (10 workers)
- Memory: ~4-8GB
- Ingestion: Parallel (8 workers, 2-4x speedup)

### High-Throughput (Many Concurrent Users)

**Configuration:**
```python
# config_highload.py
from pathlib import Path
from knowledgebeast.core.config import KnowledgeBeastConfig

config = KnowledgeBeastConfig(
    knowledge_dirs=[Path("/data/knowledge")],
    cache_file=Path("/data/cache/.knowledge_cache.pkl"),
    max_cache_size=2000,  # Very large cache
    heartbeat_interval=300,
    auto_warm=True,
    warming_queries=[
        # Top 50 queries
        # ...
    ],
    max_workers=16,  # Maximum parallelism
    verbose=False
)
```

**API Server:**
```bash
# Many workers for high concurrency
gunicorn knowledgebeast.api.app:app \
  --workers 17 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --graceful-timeout 30 \
  --keep-alive 10 \
  --max-requests 1000 \
  --max-requests-jitter 100 \
  --worker-connections 1000
```

**Load Balancer:**
```nginx
# nginx.conf
upstream knowledgebeast {
    least_conn;
    server kb1:8000 max_fails=3 fail_timeout=30s;
    server kb2:8000 max_fails=3 fail_timeout=30s;
    server kb3:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;

    location /api/v1/ {
        proxy_pass http://knowledgebeast;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

**Resource Limits:**
```yaml
# docker-compose.highload.yml
services:
  knowledgebeast-1:
    image: knowledgebeast:latest
    deploy:
      resources:
        limits:
          memory: 12G
          cpus: '16.0'
        reservations:
          memory: 8G
          cpus: '8.0'
      replicas: 3
    environment:
      - KB_MAX_WORKERS=16
      - KB_MAX_CACHE_SIZE=2000
      - LOG_LEVEL=WARNING
```

**Expected Performance:**
- Documents: 100k+
- Queries: 2000+ q/s (3 instances, 17 workers each)
- Memory: ~12GB per instance
- Throughput: 6000+ q/s (aggregated)

---

## Summary

**Key Optimization Principles:**

1. **Enable Caching:** Always use `use_cache=True` for production
2. **Warm Cache:** Pre-warm with common queries
3. **Parallel Ingestion:** Use `max_workers=CPU_count` for faster ingestion
4. **Minimize Locks:** Snapshot pattern reduces contention 5-10x
5. **Monitor Performance:** Use `knowledgebeast benchmark` regularly
6. **Right-Size Resources:** Match configuration to workload

**Performance Checklist:**

- [ ] Cache enabled and warmed
- [ ] Appropriate cache size for workload
- [ ] Parallel ingestion configured
- [ ] Worker count optimized
- [ ] Resource limits set (memory, CPU)
- [ ] Monitoring/benchmarking in place
- [ ] Lock contention minimized
- [ ] API workers properly configured
- [ ] Logging level appropriate (INFO in prod)

**Next Steps:**

- Review [CLAUDE.md](../../CLAUDE.md) for threading details
- Run `knowledgebeast benchmark` to establish baseline
- Monitor performance in production
- Adjust configuration based on metrics

---

**Version:** 1.0.0
**Last Updated:** October 6, 2025
**Maintained by:** KnowledgeBeast Performance Team
