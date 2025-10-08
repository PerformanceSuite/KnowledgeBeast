# Vector RAG Guide

Complete guide to using vector embeddings and RAG (Retrieval-Augmented Generation) with KnowledgeBeast.

## Table of Contents

1. [Introduction to Vector RAG](#introduction)
2. [Vector Embeddings](#vector-embeddings)
3. [Hybrid Search](#hybrid-search)
4. [MMR Re-ranking](#mmr-re-ranking)
5. [Search Quality Metrics](#search-quality-metrics)
6. [Best Practices](#best-practices)

## Introduction

Vector RAG combines dense vector embeddings with traditional keyword search to provide semantic understanding while maintaining exact-match capabilities.

### Key Benefits

- **Semantic Understanding**: Find conceptually similar documents, not just keyword matches
- **Robustness**: Handles synonyms, paraphrasing, and different phrasings
- **Flexibility**: Configurable blend of semantic and keyword search
- **Quality**: NDCG@10 > 0.85 on standard benchmarks

## Vector Embeddings

### What Are Vector Embeddings?

Vector embeddings convert text into dense numerical vectors (384 or 768 dimensions) that capture semantic meaning.

```python
from knowledgebeast.core.embeddings import EmbeddingEngine

# Initialize engine
engine = EmbeddingEngine(model_name="all-MiniLM-L6-v2", cache_size=1000)

# Embed text
text = "Machine learning enables computers to learn from data"
embedding = engine.embed(text)

print(f"Embedding shape: {embedding.shape}")  # (384,)
print(f"Embedding norm: {np.linalg.norm(embedding)}")  # ~1.0 (normalized)
```

### Supported Models

| Model | Dimensions | Speed | Quality | Use Case |
|-------|------------|-------|---------|----------|
| all-MiniLM-L6-v2 | 384 | Fast (10ms) | Good | General purpose |
| all-mpnet-base-v2 | 768 | Medium (25ms) | Best | High quality |
| paraphrase-multilingual-mpnet-base-v2 | 768 | Medium (25ms) | Best | Multilingual |

### Choosing a Model

```python
# Fast, lightweight (recommended for most use cases)
fast_engine = EmbeddingEngine(model_name="all-MiniLM-L6-v2")

# Higher quality (for critical applications)
quality_engine = EmbeddingEngine(model_name="all-mpnet-base-v2")

# Multilingual support
multilingual_engine = EmbeddingEngine(
    model_name="paraphrase-multilingual-mpnet-base-v2"
)
```

### Embedding Cache

The embedding cache dramatically improves performance:

```python
engine = EmbeddingEngine(cache_size=1000)

# First call (cache miss) - ~10ms
emb1 = engine.embed("machine learning")

# Second call (cache hit) - ~0.1ms (100x faster!)
emb2 = engine.embed("machine learning")

# Check statistics
stats = engine.get_stats()
print(f"Cache hit rate: {stats['cache_hit_rate']:.1%}")
```

## Hybrid Search

Hybrid search combines vector similarity (semantic) with keyword matching (exact).

### The Alpha Parameter

The `alpha` parameter controls the blend:

```python
from knowledgebeast.core.query_engine import HybridQueryEngine

engine = HybridQueryEngine(repository, alpha=0.7)

# alpha = 0.0: Pure keyword (exact matching only)
results_keyword = engine.search_hybrid("python", alpha=0.0, top_k=5)

# alpha = 0.5: Balanced hybrid
results_balanced = engine.search_hybrid("python", alpha=0.5, top_k=5)

# alpha = 1.0: Pure vector (semantic only)
results_vector = engine.search_hybrid("python", alpha=1.0, top_k=5)
```

### When to Use Each Mode

**Pure Vector (alpha=1.0)**
- Conceptual queries: "How do computers learn?"
- Synonym handling: "car" matching "automobile"
- Cross-lingual search
- Exploratory research

**Pure Keyword (alpha=0.0)**
- Exact term matching: function names, error codes
- Technical documentation lookup
- Code search
- When precision > recall matters

**Hybrid (alpha=0.5-0.7)**
- General knowledge base search
- Balanced precision and recall
- Best overall quality (NDCG@10 > 0.90)
- **Recommended default: alpha=0.7**

### Example: Finding Synonyms

```python
# Vector search handles synonyms
query = "automobile maintenance"

# Pure keyword won't find "car repair" docs
keyword_results = engine.search_keyword("automobile")  # May miss relevant docs

# Vector search finds semantic matches
vector_results = engine.search_vector("automobile", top_k=10)  # Finds "car", "vehicle", etc.

# Hybrid gets best of both
hybrid_results = engine.search_hybrid("automobile", alpha=0.7, top_k=10)
```

## MMR Re-ranking

MMR (Maximal Marginal Relevance) increases result diversity while maintaining relevance.

### Why Use MMR?

Without MMR, top results might be nearly identical:
```
1. "Python tutorial for beginners"
2. "Python beginner's guide"  # Very similar to #1
3. "Python intro for newbies"  # Also very similar
```

With MMR:
```
1. "Python tutorial for beginners"
2. "Advanced Python patterns"  # More diverse
3. "Python vs Ruby comparison"  # Even more diverse
```

### Using MMR

```python
# Standard search (may return similar results)
results = engine.search_hybrid("python tutorial", top_k=10)

# MMR for diversity
mmr_results = engine.search_with_mmr(
    "python tutorial",
    lambda_param=0.5,  # Balance relevance/diversity
    top_k=10,
    mode='hybrid'
)
```

### Lambda Parameter

- **lambda=1.0**: Maximum relevance (minimal diversity) - like standard search
- **lambda=0.5**: Balanced relevance and diversity (recommended)
- **lambda=0.0**: Maximum diversity (may sacrifice relevance)

```python
# High relevance, low diversity
mmr_relevant = engine.search_with_mmr(
    "machine learning",
    lambda_param=0.9,
    top_k=10
)

# Balanced
mmr_balanced = engine.search_with_mmr(
    "machine learning",
    lambda_param=0.5,
    top_k=10
)

# High diversity, lower relevance
mmr_diverse = engine.search_with_mmr(
    "machine learning",
    lambda_param=0.1,
    top_k=10
)
```

## Search Quality Metrics

KnowledgeBeast achieves high search quality measured by standard IR metrics.

### NDCG@10 (Normalized Discounted Cumulative Gain)

NDCG@10 measures ranking quality considering both relevance and position:

```python
# From test results:
# Vector search NDCG@10: ~0.91
# Hybrid search NDCG@10: ~0.93
# Keyword search NDCG@10: ~0.67

# Target: NDCG@10 > 0.85 ✓
```

### Mean Average Precision (MAP)

MAP measures precision across all relevant documents:

```python
# From test results:
# Vector search MAP: ~0.72
# Hybrid search MAP: ~0.74
# Target: MAP > 0.60 ✓
```

### Precision@K and Recall@K

```python
# Precision@5: How many of top 5 results are relevant?
# Vector search: ~0.85
# Hybrid search: ~0.90

# Recall@10: What fraction of relevant docs are in top 10?
# Vector search: ~0.75
# Hybrid search: ~0.80
```

## Best Practices

### 1. Choose the Right Model

```python
# For production (balanced speed/quality)
engine = EmbeddingEngine(model_name="all-MiniLM-L6-v2", cache_size=1000)

# For critical applications (max quality)
engine = EmbeddingEngine(model_name="all-mpnet-base-v2", cache_size=2000)
```

### 2. Optimize Cache Size

```python
# Small KB (< 1000 docs)
engine = EmbeddingEngine(cache_size=500)

# Medium KB (1000-10000 docs)
engine = EmbeddingEngine(cache_size=1000)

# Large KB (> 10000 docs)
engine = EmbeddingEngine(cache_size=2000)
```

### 3. Tune Alpha for Your Use Case

```python
# Test different alphas
for alpha in [0.3, 0.5, 0.7, 0.9]:
    results = engine.search_hybrid("test query", alpha=alpha, top_k=10)
    # Evaluate quality metrics
    # Choose alpha with best NDCG@10
```

### 4. Use Batch Embedding for Bulk Ingestion

```python
# Slow: Individual embeddings
for doc in documents:
    embedding = engine.embed(doc)
    store.add(...)

# Fast: Batch embeddings (5-10x faster)
embeddings = engine.embed_batch(documents, batch_size=32)
store.add(ids=ids, embeddings=embeddings, documents=documents)
```

### 5. Monitor Cache Performance

```python
stats = engine.get_stats()
print(f"Cache hit rate: {stats['cache_hit_rate']:.1%}")
print(f"Cache utilization: {stats['cache_utilization']:.1%}")

# If hit rate < 80%, consider increasing cache_size
if stats['cache_hit_rate'] < 0.8:
    print("Consider increasing cache_size")
```

### 6. Use MMR for User-Facing Results

```python
# For APIs and UIs, use MMR to avoid redundant results
results = engine.search_with_mmr(
    query,
    lambda_param=0.5,
    top_k=10,
    mode='hybrid'
)
```

### 7. Benchmark Your Use Case

```python
import time
import numpy as np

latencies = []
for i in range(100):
    start = time.time()
    results = engine.search_hybrid("test query", top_k=10)
    latencies.append((time.time() - start) * 1000)

print(f"P50 latency: {np.percentile(latencies, 50):.2f}ms")
print(f"P95 latency: {np.percentile(latencies, 95):.2f}ms")
print(f"P99 latency: {np.percentile(latencies, 99):.2f}ms")
```

## Advanced Topics

### Custom Similarity Metrics

```python
# Cosine similarity (default, recommended)
results = store.query(query_embedding, n_results=10)

# L2 distance
# (ChromaDB uses L2 by default for distance metric)
```

### Metadata Filtering

```python
# Add with metadata
store.add(
    ids="doc1",
    embeddings=embedding,
    documents="content",
    metadatas={'category': 'tutorial', 'language': 'python'}
)

# Query with filter
results = store.query(
    query_embeddings=query_emb,
    where={'category': 'tutorial'},  # Metadata filter
    n_results=10
)
```

### Persistence and Loading

```python
# Persistent storage
store = VectorStore(
    persist_directory="./chroma_db",
    collection_name="my_kb"
)

# Automatically persisted - reload later
store2 = VectorStore(
    persist_directory="./chroma_db",
    collection_name="my_kb"  # Same collection
)

print(f"Loaded {store2.count()} documents")
```

## Troubleshooting

### Low Search Quality

1. Try higher quality model (`all-mpnet-base-v2`)
2. Tune alpha parameter
3. Use hybrid search instead of pure vector/keyword
4. Check NDCG@10 metrics

### Slow Queries

1. Increase embedding cache size
2. Use smaller model (`all-MiniLM-L6-v2`)
3. Enable batch processing
4. Monitor cache hit rate

### Memory Issues

1. Reduce cache size
2. Use smaller embedding model (384-dim vs 768-dim)
3. Implement pagination for large result sets

## Further Reading

- [Multi-Project Guide](./multi-project-guide.md)
- [Performance Tuning Guide](./vector-performance-tuning.md)
- [sentence-transformers documentation](https://www.sbert.net/)
- [ChromaDB documentation](https://docs.trychroma.com/)
