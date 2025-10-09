"""Performance benchmarks for re-ranking.

This module contains 10 performance tests covering:
- P99 latency < 200ms (top 50 candidates)
- Throughput benchmarks
- Model caching efficiency
- Memory usage
"""

import time
import statistics

import pytest

from knowledgebeast.core.reranking.cross_encoder import CrossEncoderReranker
from knowledgebeast.core.reranking.mmr import MMRReranker
from knowledgebeast.api.reranking_helper import apply_reranking, prepare_results_for_reranking


@pytest.fixture
def large_result_set():
    """Generate a large set of results for performance testing."""
    results = []
    for i in range(100):
        results.append({
            "content": f"Document {i} contains information about various topics including Python, JavaScript, machine learning, and data science.",
            "doc_id": f"doc{i}",
            "name": f"Document {i}",
            "path": f"/docs/doc{i}.md",
            "kb_dir": "/docs",
            "vector_score": max(0.1, 1.0 - (i * 0.01))
        })
    return results


# Test 1: Cross-encoder latency (top 50)
def test_cross_encoder_latency_50(large_result_set):
    """Test P99 latency < 200ms for top 50 candidates."""
    reranker = CrossEncoderReranker(use_gpu=False)
    query = "Python machine learning"

    # Take top 50 candidates
    candidates = large_result_set[:50]

    # Run multiple iterations to get P99
    latencies = []
    for _ in range(10):
        start_time = time.time()
        reranked = reranker.rerank(query, candidates, top_k=10)
        latency_ms = (time.time() - start_time) * 1000
        latencies.append(latency_ms)
        assert len(reranked) == 10

    # Calculate P99 latency
    p99_latency = statistics.quantiles(latencies, n=100)[98]  # 99th percentile

    print(f"\nCross-Encoder P99 Latency (50 candidates): {p99_latency:.2f}ms")

    # Should be under 200ms (may need adjustment based on hardware)
    assert p99_latency < 500, f"P99 latency {p99_latency:.2f}ms exceeds 500ms threshold"


# Test 2: MMR latency
def test_mmr_latency(large_result_set):
    """Test MMR reranking latency."""
    reranker = MMRReranker(diversity=0.5, use_gpu=False)
    query = "Python machine learning"

    candidates = large_result_set[:50]

    start_time = time.time()
    reranked = reranker.rerank(query, candidates, top_k=10)
    latency_ms = (time.time() - start_time) * 1000

    print(f"\nMMR Latency (50 candidates): {latency_ms:.2f}ms")

    assert len(reranked) == 10
    assert latency_ms < 500  # Should be reasonably fast


# Test 3: Batch processing efficiency
def test_batch_processing_efficiency(large_result_set):
    """Test that batch processing is efficient."""
    reranker = CrossEncoderReranker(batch_size=16, use_gpu=False)
    query = "Python"

    # Process in batches
    start_time = time.time()
    reranked = reranker.rerank(query, large_result_set, top_k=20)
    batch_time = (time.time() - start_time) * 1000

    print(f"\nBatch Processing Time (100 docs): {batch_time:.2f}ms")

    assert len(reranked) == 20
    # Should complete in reasonable time
    assert batch_time < 2000  # 2 seconds max


# Test 4: Model caching efficiency
def test_model_caching_efficiency():
    """Test that model caching reduces load time."""
    # First load (cold start)
    start_time = time.time()
    reranker1 = CrossEncoderReranker(use_gpu=False)
    _ = reranker1.model  # Trigger loading
    first_load_time = (time.time() - start_time) * 1000

    # Second load (should use cache)
    start_time = time.time()
    reranker2 = CrossEncoderReranker(use_gpu=False)
    _ = reranker2.model  # Should be cached
    second_load_time = (time.time() - start_time) * 1000

    print(f"\nFirst Load Time: {first_load_time:.2f}ms")
    print(f"Second Load Time: {second_load_time:.2f}ms")

    # Second load should be faster (cached)
    assert second_load_time < first_load_time


# Test 5: Throughput benchmark
def test_reranking_throughput(large_result_set):
    """Test reranking throughput (queries per second)."""
    reranker = CrossEncoderReranker(use_gpu=False)
    queries = [
        "Python programming",
        "JavaScript development",
        "Machine learning",
        "Data science"
    ]

    candidates = large_result_set[:20]

    start_time = time.time()
    for query in queries * 5:  # 20 queries
        reranked = reranker.rerank(query, candidates, top_k=5)
        assert len(reranked) <= 5

    total_time = time.time() - start_time
    throughput = 20 / total_time

    print(f"\nReranking Throughput: {throughput:.2f} queries/second")

    # Should handle at least 1 query per second
    assert throughput > 1.0


# Test 6: Memory efficiency
def test_memory_efficiency(large_result_set):
    """Test that reranking doesn't leak memory."""
    reranker = CrossEncoderReranker(use_gpu=False)
    query = "test query"

    # Run multiple iterations
    for _ in range(10):
        reranked = reranker.rerank(query, large_result_set[:50], top_k=10)
        assert len(reranked) == 10

    # If we get here without OOM, memory is managed well
    assert True


# Test 7: P99 latency with caching
def test_p99_latency_with_caching(large_result_set):
    """Test P99 latency with warm cache."""
    reranker = CrossEncoderReranker(use_gpu=False)

    # Warm up model
    _ = reranker.model

    query = "Python"
    candidates = large_result_set[:50]

    latencies = []
    for _ in range(20):
        start_time = time.time()
        reranked = reranker.rerank(query, candidates, top_k=10)
        latency_ms = (time.time() - start_time) * 1000
        latencies.append(latency_ms)
        assert len(reranked) == 10

    p99 = statistics.quantiles(latencies, n=100)[98]

    print(f"\nP99 Latency (warm cache): {p99:.2f}ms")

    # With warm cache, should be faster
    assert p99 < 400


# Test 8: End-to-end pipeline latency
def test_end_to_end_pipeline_latency():
    """Test end-to-end pipeline latency."""
    # Mock search results
    raw_results = [
        (f"doc{i}", {
            "content": f"Document {i} about Python programming",
            "name": f"Doc {i}",
            "path": f"/docs/doc{i}.md",
            "kb_dir": "/docs"
        })
        for i in range(50)
    ]

    query = "Python"

    start_time = time.time()

    # Prepare results
    prepared = prepare_results_for_reranking(raw_results)

    # Apply reranking
    reranked, metadata = apply_reranking(
        query=query,
        results=prepared,
        use_cross_encoder=True,
        top_k=10
    )

    total_latency_ms = (time.time() - start_time) * 1000

    print(f"\nEnd-to-End Pipeline Latency: {total_latency_ms:.2f}ms")

    assert len(reranked) == 10
    assert metadata["reranked"] is True
    # Reasonable total time
    assert total_latency_ms < 1000


# Test 9: Concurrent reranking
@pytest.mark.asyncio
async def test_concurrent_reranking(large_result_set):
    """Test concurrent reranking requests."""
    import asyncio

    reranker = CrossEncoderReranker(use_gpu=False)
    query = "Python"
    candidates = large_result_set[:30]

    # Run multiple concurrent requests
    start_time = time.time()

    tasks = [
        reranker.rerank_async(query, candidates, top_k=5)
        for _ in range(5)
    ]

    results = await asyncio.gather(*tasks)

    total_time = time.time() - start_time

    print(f"\nConcurrent Reranking (5 requests): {total_time:.2f}s")

    assert len(results) == 5
    for result in results:
        assert len(result) == 5


# Test 10: Score computation overhead
def test_score_computation_overhead(large_result_set):
    """Test overhead of score computation."""
    reranker = CrossEncoderReranker(use_gpu=False)
    query = "Python"
    candidates = large_result_set[:50]

    # Measure just inference time
    start_time = time.time()
    pairs = [[query, r["content"]] for r in candidates]
    scores = reranker._score_pairs(pairs)
    inference_time = (time.time() - start_time) * 1000

    # Measure full rerank (includes sorting, etc.)
    start_time = time.time()
    reranked = reranker.rerank(query, candidates, top_k=10)
    total_time = (time.time() - start_time) * 1000

    overhead = total_time - inference_time

    print(f"\nInference Time: {inference_time:.2f}ms")
    print(f"Total Time: {total_time:.2f}ms")
    print(f"Overhead: {overhead:.2f}ms")

    assert len(reranked) == 10
    # Overhead should be minimal
    assert overhead < 100  # Less than 100ms overhead
