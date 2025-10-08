# Vector Performance Tuning Guide

Optimization strategies for maximizing KnowledgeBeast performance.

## Quick Wins

### 1. Batch Embedding (5-10x faster)

```python
# Slow
for doc in documents:
    embedding = engine.embed(doc)
    store.add(ids=id, embeddings=embedding, documents=doc)

# Fast
embeddings = engine.embed_batch(documents, batch_size=32)
store.add(ids=ids, embeddings=embeddings, documents=documents)
```

### 2. Increase Embedding Cache

```python
# Default
engine = EmbeddingEngine(cache_size=100)

# Optimized
engine = EmbeddingEngine(cache_size=2000)  # 95%+ hit rate
```

### 3. Use Lighter Model

```python
# 384-dim, 10ms latency
engine = EmbeddingEngine(model_name="all-MiniLM-L6-v2")

# 768-dim, 25ms latency (only if quality critical)
engine = EmbeddingEngine(model_name="all-mpnet-base-v2")
```

## Latency Optimization

### Target P99 < 100ms

```python
import time
import numpy as np

def measure_latency(engine, queries, iterations=100):
    latencies = []
    for _ in range(iterations):
        query = queries[np.random.randint(len(queries))]
        start = time.time()
        results = engine.search_hybrid(query, top_k=10)
        latencies.append((time.time() - start) * 1000)

    return {
        'p50': np.percentile(latencies, 50),
        'p95': np.percentile(latencies, 95),
        'p99': np.percentile(latencies, 99)
    }

stats = measure_latency(engine, test_queries)
print(f"P99: {stats['p99']:.2f}ms")  # Target: < 100ms
```

### Optimizations

1. **Cache warming**: Pre-populate embedding cache
2. **Batch queries**: Group similar queries
3. **Index optimization**: Keep documents < 50k
4. **Reduce top_k**: Only request what you need

## Throughput Optimization

### Target > 500 queries/sec (10 workers)

```python
import threading
from collections import defaultdict

def benchmark_throughput(engine, num_threads=10, queries_per_thread=100):
    completed = defaultdict(int)
    lock = threading.Lock()

    def worker(thread_id):
        for i in range(queries_per_thread):
            engine.search_hybrid(f"query {i}", top_k=5)
            with lock:
                completed[thread_id] += 1

    threads = []
    start = time.time()

    for i in range(num_threads):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    elapsed = time.time() - start
    total_queries = num_threads * queries_per_thread
    throughput = total_queries / elapsed

    print(f"{num_threads} threads: {throughput:.0f} queries/sec")
    return throughput

throughput = benchmark_throughput(engine, num_threads=10)
assert throughput > 500, "Throughput below target"
```

## Memory Optimization

### Cache Size Tuning

```python
# Monitor cache utilization
stats = engine.get_stats()
print(f"Cache utilization: {stats['cache_utilization']:.1%}")

# If utilization > 95%, increase capacity
if stats['cache_utilization'] > 0.95:
    engine = EmbeddingEngine(cache_size=stats['cache_capacity'] * 2)
```

### Model Selection by Memory

| Model | Memory | Latency |
|-------|--------|---------|
| all-MiniLM-L6-v2 | ~90MB | 10ms |
| all-mpnet-base-v2 | ~420MB | 25ms |

## Search Quality vs Performance

### Alpha Tuning

```python
# Faster (more keyword, less embedding)
results = engine.search_hybrid(query, alpha=0.3, top_k=10)

# Slower but higher quality (more vector, less keyword)
results = engine.search_hybrid(query, alpha=0.9, top_k=10)

# Recommended: alpha=0.7 (balanced)
```

### MMR Performance Impact

```python
# Standard search (faster)
results = engine.search_hybrid(query, top_k=10)

# MMR (10-20% slower, better diversity)
results = engine.search_with_mmr(query, lambda_param=0.5, top_k=10)
```

## ChromaDB Optimization

### Collection Size

```python
# Optimal: < 50k documents per collection
# If larger, consider:
# 1. Multiple collections
# 2. Archiving old documents
# 3. Horizontal scaling

count = store.count()
if count > 50000:
    print("Consider splitting collection")
```

### Query Optimization

```python
# Metadata filtering (pre-filter before similarity)
results = store.query(
    query_embeddings=emb,
    where={'category': 'tutorial'},  # Pre-filter
    n_results=10
)
```

## Monitoring

### Key Metrics

```python
def print_performance_report(engine):
    stats = engine.get_stats()
    print("\nPerformance Report:")
    print(f"  Cache hit rate: {stats['cache_hit_rate']:.1%}")
    print(f"  Cache utilization: {stats['cache_utilization']:.1%}")
    print(f"  Total queries: {stats['total_queries']}")
    print(f"  Embeddings generated: {stats['embeddings_generated']}")

print_performance_report(engine)
```

### Performance Targets

| Metric | Target | Action if Below |
|--------|--------|-----------------|
| Cache hit rate | > 90% | Increase cache_size |
| P99 latency | < 100ms | Use lighter model or batch queries |
| Throughput (10 workers) | > 500 q/s | Check thread contention |
| NDCG@10 | > 0.85 | Tune alpha parameter |

## Advanced Optimizations

### GPU Acceleration

```python
# Use GPU for embeddings (if available)
engine = EmbeddingEngine(
    model_name="all-MiniLM-L6-v2",
    device='cuda'  # or 'mps' for Apple Silicon
)
```

### Parallel Ingestion

```python
from concurrent.futures import ThreadPoolExecutor

def ingest_batch(doc_batch):
    embeddings = engine.embed_batch([d['content'] for d in doc_batch])
    # Add to store...

# Parallel processing
with ThreadPoolExecutor(max_workers=4) as executor:
    batch_size = 100
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        executor.submit(ingest_batch, batch)
```

## Troubleshooting

### Slow Queries

1. Check cache hit rate (should be > 90%)
2. Reduce top_k
3. Use lighter embedding model
4. Profile with `cProfile`

### High Memory Usage

1. Reduce cache_size
2. Use MiniLM (384-dim) instead of MPNet (768-dim)
3. Clear caches periodically
4. Monitor with `memory_profiler`

### Low Throughput

1. Check thread contention
2. Increase worker count
3. Use batch operations
4. Profile with threading tools

## Benchmarking

See [BENCHMARK_REPORT.md](../../BENCHMARK_REPORT.md) for detailed performance results.
