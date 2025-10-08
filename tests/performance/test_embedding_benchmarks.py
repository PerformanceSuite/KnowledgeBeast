"""Performance benchmarks for embeddings and vector operations."""

import time
from statistics import mean, median

import numpy as np
import pytest

from knowledgebeast.core.embeddings import EmbeddingEngine
from knowledgebeast.core.vector_store import VectorStore


class TestEmbeddingPerformance:
    """Test embedding generation performance."""

    def test_single_embedding_latency(self):
        """Test latency for single embedding generation."""
        engine = EmbeddingEngine()

        # Warm up
        engine.embed("warm up text")

        # Measure latency
        latencies = []
        for _ in range(100):
            start = time.time()
            engine.embed("Test text for performance measurement", use_cache=False)
            latency = (time.time() - start) * 1000  # Convert to ms
            latencies.append(latency)

        p50 = median(latencies)
        p95 = np.percentile(latencies, 95)
        p99 = np.percentile(latencies, 99)

        print(f"\nSingle embedding latency:")
        print(f"  P50: {p50:.2f}ms")
        print(f"  P95: {p95:.2f}ms")
        print(f"  P99: {p99:.2f}ms")

        # P99 should be under 100ms for single embedding
        assert p99 < 100, f"P99 latency {p99:.2f}ms exceeds 100ms"

    def test_batch_embedding_throughput(self):
        """Test throughput for batch embedding."""
        engine = EmbeddingEngine()

        # Warm up
        engine.embed(["warm up"] * 10)

        # Measure throughput
        batch_sizes = [10, 50, 100, 200]
        results = {}

        for batch_size in batch_sizes:
            texts = [f"Document {i}" for i in range(batch_size)]

            start = time.time()
            engine.embed(texts, use_cache=False)
            elapsed = time.time() - start

            throughput = batch_size / elapsed

            results[batch_size] = {
                "throughput": throughput,
                "latency_per_item": (elapsed / batch_size) * 1000
            }

            print(f"\nBatch size {batch_size}:")
            print(f"  Throughput: {throughput:.2f} embeddings/sec")
            print(f"  Latency per item: {results[batch_size]['latency_per_item']:.2f}ms")

        # Larger batches should have better throughput
        assert results[100]["throughput"] > results[10]["throughput"]

    def test_cache_hit_latency(self):
        """Test latency for cache hits."""
        engine = EmbeddingEngine()

        # Populate cache
        text = "Cached text for performance test"
        engine.embed(text, use_cache=True)

        # Measure cache hit latency
        latencies = []
        for _ in range(1000):
            start = time.time()
            engine.embed(text, use_cache=True)
            latency = (time.time() - start) * 1000
            latencies.append(latency)

        p50 = median(latencies)
        p99 = np.percentile(latencies, 99)

        print(f"\nCache hit latency:")
        print(f"  P50: {p50:.2f}ms")
        print(f"  P99: {p99:.2f}ms")

        # Cache hits should be very fast (< 10ms P99)
        assert p99 < 10, f"Cache hit P99 {p99:.2f}ms exceeds 10ms"

    def test_different_model_performance(self):
        """Test performance comparison across models."""
        models = [
            "all-MiniLM-L6-v2",
            "all-mpnet-base-v2",
        ]

        results = {}

        for model_name in models:
            engine = EmbeddingEngine(model_name=model_name)

            # Warm up
            engine.embed("warm up")

            # Measure
            text = "Performance test text for model comparison"
            latencies = []

            for _ in range(20):
                start = time.time()
                engine.embed(text, use_cache=False)
                latency = (time.time() - start) * 1000
                latencies.append(latency)

            results[model_name] = {
                "mean_latency": mean(latencies),
                "p95_latency": np.percentile(latencies, 95)
            }

        print(f"\nModel performance comparison:")
        for model, metrics in results.items():
            print(f"  {model}:")
            print(f"    Mean: {metrics['mean_latency']:.2f}ms")
            print(f"    P95: {metrics['p95_latency']:.2f}ms")

        # MiniLM should be faster than mpnet
        assert results["all-MiniLM-L6-v2"]["mean_latency"] < results["all-mpnet-base-v2"]["mean_latency"]


class TestVectorStorePerformance:
    """Test vector store performance."""

    def test_add_latency(self):
        """Test latency for adding documents."""
        store = VectorStore()

        # Single document add
        latencies = []
        for i in range(100):
            embedding = np.random.rand(384).astype(np.float32)

            start = time.time()
            store.add(ids=f"doc{i}", embeddings=embedding)
            latency = (time.time() - start) * 1000
            latencies.append(latency)

        p50 = median(latencies)
        p95 = np.percentile(latencies, 95)

        print(f"\nSingle document add latency:")
        print(f"  P50: {p50:.2f}ms")
        print(f"  P95: {p95:.2f}ms")

        # Should be fast
        assert p95 < 50, f"Add P95 {p95:.2f}ms exceeds 50ms"

    def test_batch_add_throughput(self):
        """Test throughput for batch adds."""
        store = VectorStore()

        batch_sizes = [10, 50, 100]
        results = {}

        for batch_size in batch_sizes:
            embeddings = [np.random.rand(384).astype(np.float32) for _ in range(batch_size)]
            ids = [f"doc_{batch_size}_{i}" for i in range(batch_size)]

            start = time.time()
            store.add(ids=ids, embeddings=embeddings)
            elapsed = time.time() - start

            throughput = batch_size / elapsed
            results[batch_size] = throughput

            print(f"\nBatch add (size {batch_size}):")
            print(f"  Throughput: {throughput:.2f} docs/sec")

        # Batch operations should be efficient
        assert results[100] > 100, "Batch add throughput should exceed 100 docs/sec"

    def test_query_latency(self):
        """Test query latency."""
        store = VectorStore()

        # Add documents
        num_docs = 1000
        embeddings = [np.random.rand(384).astype(np.float32) for _ in range(num_docs)]
        store.add(
            ids=[f"doc{i}" for i in range(num_docs)],
            embeddings=embeddings
        )

        # Measure query latency
        latencies = []
        for _ in range(100):
            query_embedding = np.random.rand(384).astype(np.float32)

            start = time.time()
            store.query(query_embeddings=query_embedding, n_results=10)
            latency = (time.time() - start) * 1000
            latencies.append(latency)

        p50 = median(latencies)
        p95 = np.percentile(latencies, 95)
        p99 = np.percentile(latencies, 99)

        print(f"\nQuery latency (1000 docs):")
        print(f"  P50: {p50:.2f}ms")
        print(f"  P95: {p95:.2f}ms")
        print(f"  P99: {p99:.2f}ms")

        # P99 should be under 100ms
        assert p99 < 100, f"Query P99 {p99:.2f}ms exceeds 100ms"

    def test_query_scalability(self):
        """Test query performance with increasing dataset size."""
        dataset_sizes = [100, 500, 1000, 2000]
        results = {}

        for size in dataset_sizes:
            store = VectorStore(collection_name=f"test_{size}")

            # Add documents
            embeddings = [np.random.rand(384).astype(np.float32) for _ in range(size)]
            store.add(
                ids=[f"doc{i}" for i in range(size)],
                embeddings=embeddings
            )

            # Measure query latency
            latencies = []
            for _ in range(20):
                query_embedding = np.random.rand(384).astype(np.float32)

                start = time.time()
                store.query(query_embeddings=query_embedding, n_results=10)
                latency = (time.time() - start) * 1000
                latencies.append(latency)

            results[size] = median(latencies)

            print(f"\nQuery latency with {size} documents:")
            print(f"  Median: {results[size]:.2f}ms")

        # Latency should scale sub-linearly
        # 10x data shouldn't mean 10x latency
        latency_ratio = results[1000] / results[100]
        data_ratio = 10

        print(f"\nScalability ratio: {latency_ratio:.2f}x latency for {data_ratio}x data")
        assert latency_ratio < data_ratio, "Query latency scaling too linear"

    def test_concurrent_query_throughput(self):
        """Test concurrent query throughput."""
        import concurrent.futures

        store = VectorStore()

        # Add documents
        num_docs = 500
        embeddings = [np.random.rand(384).astype(np.float32) for _ in range(num_docs)]
        store.add(
            ids=[f"doc{i}" for i in range(num_docs)],
            embeddings=embeddings
        )

        def run_query():
            query_embedding = np.random.rand(384).astype(np.float32)
            store.query(query_embeddings=query_embedding, n_results=10)

        # Measure throughput with different worker counts
        worker_counts = [1, 5, 10]
        results = {}

        for num_workers in worker_counts:
            num_queries = 100

            start = time.time()
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = [executor.submit(run_query) for _ in range(num_queries)]
                concurrent.futures.wait(futures)
            elapsed = time.time() - start

            throughput = num_queries / elapsed
            results[num_workers] = throughput

            print(f"\nConcurrent queries ({num_workers} workers):")
            print(f"  Throughput: {throughput:.2f} queries/sec")

        # More workers should increase throughput
        assert results[10] > results[1]


class TestEndToEndPerformance:
    """Test end-to-end performance."""

    def test_embed_and_store_pipeline(self):
        """Test complete embedding and storage pipeline."""
        engine = EmbeddingEngine()
        store = VectorStore()

        # Generate documents
        num_docs = 100
        texts = [f"Document {i} with some content for testing" for i in range(num_docs)]

        # Measure end-to-end time
        start = time.time()

        # Embed in batches
        embeddings = engine.embed_batch(texts, batch_size=32)

        # Store in batches
        batch_size = 25
        for i in range(0, num_docs, batch_size):
            batch_end = min(i + batch_size, num_docs)
            store.add(
                ids=[f"doc{j}" for j in range(i, batch_end)],
                embeddings=embeddings[i:batch_end],
                documents=texts[i:batch_end]
            )

        elapsed = time.time() - start

        throughput = num_docs / elapsed

        print(f"\nEnd-to-end pipeline ({num_docs} docs):")
        print(f"  Total time: {elapsed:.2f}s")
        print(f"  Throughput: {throughput:.2f} docs/sec")

        # Should process at least 10 docs/sec
        assert throughput > 10, f"Pipeline throughput {throughput:.2f} docs/sec too slow"

    def test_search_accuracy_vs_speed(self):
        """Test search accuracy at different speeds."""
        engine = EmbeddingEngine()
        store = VectorStore()

        # Create documents with known relationships
        texts = [
            "Python programming language",
            "Python snake species",
            "Java programming language",
            "JavaScript web development",
            "C++ systems programming",
        ]

        embeddings = engine.embed(texts)
        store.add(
            ids=[f"doc{i}" for i in range(len(texts))],
            embeddings=embeddings,
            documents=texts
        )

        # Query for programming
        query = "software development programming"
        query_emb = engine.embed(query)

        # Measure query time and check accuracy
        start = time.time()
        results = store.query(query_embeddings=query_emb, n_results=3)
        query_time = (time.time() - start) * 1000

        # Top results should be programming-related
        top_docs = results["documents"][0]
        programming_count = sum(1 for doc in top_docs if "programming" in doc.lower())

        print(f"\nSearch accuracy test:")
        print(f"  Query time: {query_time:.2f}ms")
        print(f"  Programming docs in top 3: {programming_count}/3")

        # Should be fast and accurate
        assert query_time < 50, "Query too slow"
        assert programming_count >= 2, "Search accuracy too low"


class TestCacheEffectiveness:
    """Test cache effectiveness in real scenarios."""

    def test_cache_hit_rate_workload(self):
        """Test cache hit rate under realistic workload."""
        engine = EmbeddingEngine(cache_size=100)

        # Simulate workload with repeated queries
        common_queries = [f"Query {i}" for i in range(20)]
        rare_queries = [f"Rare query {i}" for i in range(80)]

        # Mix: 80% common, 20% rare
        queries = []
        for _ in range(500):
            if np.random.rand() < 0.8:
                queries.append(np.random.choice(common_queries))
            else:
                queries.append(np.random.choice(rare_queries))

        # Execute queries
        for query in queries:
            engine.embed(query, use_cache=True)

        stats = engine.get_stats()
        hit_rate = stats["cache_hit_rate"]

        print(f"\nCache effectiveness:")
        print(f"  Hit rate: {hit_rate*100:.1f}%")
        print(f"  Cache hits: {stats['cache_hits']}")
        print(f"  Cache misses: {stats['cache_misses']}")

        # Should have good hit rate for this workload
        assert hit_rate > 0.5, f"Cache hit rate {hit_rate*100:.1f}% too low"

    def test_cache_vs_nocache_performance(self):
        """Compare performance with and without caching."""
        text = "Repeated text for cache test"

        # Test with cache
        engine_cached = EmbeddingEngine()
        engine_cached.embed(text, use_cache=True)  # Warm up cache

        start = time.time()
        for _ in range(100):
            engine_cached.embed(text, use_cache=True)
        cached_time = time.time() - start

        # Test without cache
        engine_nocache = EmbeddingEngine()

        start = time.time()
        for _ in range(100):
            engine_nocache.embed(text, use_cache=False)
        nocache_time = time.time() - start

        speedup = nocache_time / cached_time

        print(f"\nCache performance comparison:")
        print(f"  With cache: {cached_time:.3f}s")
        print(f"  Without cache: {nocache_time:.3f}s")
        print(f"  Speedup: {speedup:.1f}x")

        # Cache should provide significant speedup
        assert speedup > 10, f"Cache speedup {speedup:.1f}x too low"


class TestMemoryEfficiency:
    """Test memory efficiency."""

    def test_cache_memory_bounds(self):
        """Test cache respects memory bounds."""
        cache_size = 100
        engine = EmbeddingEngine(cache_size=cache_size)

        # Add more items than cache capacity
        for i in range(cache_size * 2):
            engine.embed(f"Text {i}", use_cache=True)

        cache_stats = engine.cache.stats()

        print(f"\nCache memory bounds:")
        print(f"  Capacity: {cache_stats['capacity']}")
        print(f"  Size: {cache_stats['size']}")
        print(f"  Utilization: {cache_stats['utilization']*100:.1f}%")

        # Cache should not exceed capacity
        assert cache_stats['size'] <= cache_stats['capacity']
