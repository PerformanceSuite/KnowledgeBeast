"""
Performance tests for parallel document ingestion.

Benchmarks measure:
- Sequential vs parallel ingestion speedup
- Scalability with increasing workers
- Thread safety during parallel processing
- Performance with varying document counts
"""

import time
import statistics
from pathlib import Path
import pytest
from knowledgebeast.core.engine import KnowledgeBase
from knowledgebeast.core.config import KnowledgeBeastConfig


@pytest.fixture
def large_kb_dir(tmp_path):
    """Create a large knowledge base with 100+ documents."""
    kb_dir = tmp_path / "knowledge"
    kb_dir.mkdir()

    # Create 150 test documents with varied content
    for i in range(150):
        content = f"""# Document {i}

## Overview
This is test document number {i} for performance testing.

## Topics
- Topic A{i % 10}: Information about topic A{i % 10}
- Topic B{i % 7}: Details on topic B{i % 7}
- Topic C{i % 5}: Analysis of topic C{i % 5}

## Content
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Document {i} covers
various aspects of knowledge base ingestion and indexing. This includes
discussion of audio processing, video analysis, machine learning, data science,
natural language processing, signal processing, and computer vision.

### Section 1
Performance characteristics matter when dealing with large knowledge bases.
Sequential processing can become a bottleneck with hundreds of documents.
Parallel processing using ThreadPoolExecutor can provide significant speedups.

### Section 2
Thread safety is critical when implementing parallel ingestion. We use the
atomic swap pattern to ensure consistency. Documents are processed independently
and results are merged before the final atomic index update.

### Section 3
Additional content for document {i} to ensure sufficient text for indexing.
Keywords: doc{i}, test{i % 20}, category{i % 8}, group{i % 12}

## Conclusion
Document {i} concludes with a summary of the main points discussed above.
This content ensures each document has sufficient text for meaningful testing.
"""
        (kb_dir / f"doc_{i:03d}.md").write_text(content)

    return kb_dir


@pytest.fixture
def small_kb_dir(tmp_path):
    """Create a small knowledge base with 20 documents."""
    kb_dir = tmp_path / "knowledge_small"
    kb_dir.mkdir()

    for i in range(20):
        content = f"""# Small Document {i}
This is a smaller test document for baseline comparisons.
Topic: category_{i % 5}
Keywords: small, test, doc{i}
"""
        (kb_dir / f"small_doc_{i:02d}.md").write_text(content)

    return kb_dir


class TestParallelIngestionPerformance:
    """Test parallel ingestion performance characteristics."""

    def test_sequential_baseline(self, large_kb_dir, tmp_path):
        """Establish baseline with sequential processing (1 worker)."""
        config = KnowledgeBeastConfig(
            knowledge_dirs=[large_kb_dir],
            auto_warm=False,
            verbose=False,
            cache_file=str(tmp_path / "cache_seq.json"),
            max_workers=1  # Sequential processing
        )

        kb = KnowledgeBase(config)

        start = time.time()
        kb.ingest_all()
        elapsed = time.time() - start

        stats = kb.get_stats()

        print(f"\nSequential Ingestion (1 worker):")
        print(f"  Documents: {stats['total_documents']}")
        print(f"  Terms: {stats['total_terms']}")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Throughput: {stats['total_documents']/elapsed:.2f} docs/sec")

        assert stats['total_documents'] == 150
        assert stats['total_terms'] > 0

        # Store for comparison
        return elapsed

    def test_parallel_4_workers(self, large_kb_dir, tmp_path):
        """Test with 4 parallel workers."""
        config = KnowledgeBeastConfig(
            knowledge_dirs=[large_kb_dir],
            auto_warm=False,
            verbose=False,
            cache_file=str(tmp_path / "cache_parallel_4.json"),
            max_workers=4
        )

        kb = KnowledgeBase(config)

        start = time.time()
        kb.ingest_all()
        elapsed = time.time() - start

        stats = kb.get_stats()

        print(f"\nParallel Ingestion (4 workers):")
        print(f"  Documents: {stats['total_documents']}")
        print(f"  Terms: {stats['total_terms']}")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Throughput: {stats['total_documents']/elapsed:.2f} docs/sec")

        assert stats['total_documents'] == 150
        assert stats['total_terms'] > 0

        return elapsed

    def test_parallel_8_workers(self, large_kb_dir, tmp_path):
        """Test with 8 parallel workers."""
        config = KnowledgeBeastConfig(
            knowledge_dirs=[large_kb_dir],
            auto_warm=False,
            verbose=False,
            cache_file=str(tmp_path / "cache_parallel_8.json"),
            max_workers=8
        )

        kb = KnowledgeBase(config)

        start = time.time()
        kb.ingest_all()
        elapsed = time.time() - start

        stats = kb.get_stats()

        print(f"\nParallel Ingestion (8 workers):")
        print(f"  Documents: {stats['total_documents']}")
        print(f"  Terms: {stats['total_terms']}")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Throughput: {stats['total_documents']/elapsed:.2f} docs/sec")

        assert stats['total_documents'] == 150
        assert stats['total_terms'] > 0

        return elapsed

    def test_speedup_comparison(self, large_kb_dir, tmp_path):
        """Compare speedup from sequential to parallel processing."""
        results = {}

        for workers in [1, 2, 4, 8]:
            config = KnowledgeBeastConfig(
                knowledge_dirs=[large_kb_dir],
                auto_warm=False,
                verbose=False,
                cache_file=str(tmp_path / f"cache_{workers}w.json"),
                max_workers=workers
            )

            kb = KnowledgeBase(config)

            start = time.time()
            kb.ingest_all()
            elapsed = time.time() - start

            stats = kb.get_stats()
            results[workers] = {
                'time': elapsed,
                'throughput': stats['total_documents'] / elapsed,
                'docs': stats['total_documents'],
                'terms': stats['total_terms']
            }

        # Calculate speedups relative to sequential (1 worker)
        baseline = results[1]['time']

        print(f"\nSpeedup Analysis:")
        print(f"  {'Workers':<10} {'Time (s)':<12} {'Throughput':<15} {'Speedup':<10}")
        print(f"  {'-'*50}")

        for workers, data in results.items():
            speedup = baseline / data['time']
            print(f"  {workers:<10} {data['time']:<12.2f} {data['throughput']:<15.2f} {speedup:<10.2f}x")

        # Verify we get some speedup with parallel workers
        # Note: Actual speedup depends on I/O characteristics and CPU count
        # With Docling converter being CPU-heavy, speedup may be modest
        speedup_4 = baseline / results[4]['time']
        speedup_8 = baseline / results[8]['time']

        # We should see at least 1.2x speedup with 4 workers (20% improvement)
        # This is conservative given I/O overhead and GIL constraints
        assert speedup_4 > 1.2, f"Expected at least 1.2x speedup with 4 workers, got {speedup_4:.2f}x"

        # Document performance improvement
        print(f"\n  Performance improvements:")
        print(f"    4 workers: {speedup_4:.2f}x speedup")
        print(f"    8 workers: {speedup_8:.2f}x speedup")
        print(f"  Target achieved: {speedup_4:.2f}x speedup with 4 workers (> 1.2x)")


class TestParallelIngestionCorrectness:
    """Test correctness of parallel ingestion."""

    def test_document_count_consistency(self, large_kb_dir, tmp_path):
        """Verify all documents are ingested correctly."""
        config = KnowledgeBeastConfig(
            knowledge_dirs=[large_kb_dir],
            auto_warm=False,
            verbose=False,
            cache_file=str(tmp_path / "cache_consistency.json"),
            max_workers=8
        )

        kb = KnowledgeBase(config)
        kb.ingest_all()

        stats = kb.get_stats()

        # All 150 documents should be ingested
        assert stats['total_documents'] == 150, f"Expected 150 docs, got {stats['total_documents']}"

        # Verify index is built correctly
        assert stats['total_terms'] > 0, "Index should contain terms"

        # Check a few sample documents
        results = kb.query("Document 0")
        assert len(results) > 0, "Should find Document 0"

        results = kb.query("Document 100")
        assert len(results) > 0, "Should find Document 100"

    def test_index_integrity(self, large_kb_dir, tmp_path):
        """Verify index integrity after parallel ingestion."""
        config = KnowledgeBeastConfig(
            knowledge_dirs=[large_kb_dir],
            auto_warm=False,
            verbose=False,
            cache_file=str(tmp_path / "cache_integrity.json"),
            max_workers=8
        )

        kb = KnowledgeBase(config)
        kb.ingest_all()

        # Test various queries
        test_queries = [
            ("audio processing", True),
            ("video analysis", True),
            ("machine learning", True),
            ("nonexistent_keyword_xyz", False),
        ]

        for query, should_find in test_queries:
            results = kb.query(query)
            if should_find:
                assert len(results) > 0, f"Should find results for '{query}'"
            else:
                assert len(results) == 0, f"Should not find results for '{query}'"

    def test_parallel_vs_sequential_equivalence(self, small_kb_dir, tmp_path):
        """Verify parallel and sequential produce same results."""
        # Sequential
        config_seq = KnowledgeBeastConfig(
            knowledge_dirs=[small_kb_dir],
            auto_warm=False,
            verbose=False,
            cache_file=str(tmp_path / "cache_seq_equiv.json"),
            max_workers=1
        )
        kb_seq = KnowledgeBase(config_seq)
        kb_seq.ingest_all()
        stats_seq = kb_seq.get_stats()

        # Parallel
        config_par = KnowledgeBeastConfig(
            knowledge_dirs=[small_kb_dir],
            auto_warm=False,
            verbose=False,
            cache_file=str(tmp_path / "cache_par_equiv.json"),
            max_workers=4
        )
        kb_par = KnowledgeBase(config_par)
        kb_par.ingest_all()
        stats_par = kb_par.get_stats()

        # Same number of documents
        assert stats_seq['total_documents'] == stats_par['total_documents']

        # Same number of terms (index should be identical)
        assert stats_seq['total_terms'] == stats_par['total_terms']

        # Query results should be equivalent
        for query in ["small", "test", "category_1", "doc5"]:
            results_seq = kb_seq.query(query)
            results_par = kb_par.query(query)

            # Same number of results
            assert len(results_seq) == len(results_par), f"Query '{query}' returned different counts"

            # Same document IDs (order may differ)
            doc_ids_seq = {doc_id for doc_id, _ in results_seq}
            doc_ids_par = {doc_id for doc_id, _ in results_par}
            assert doc_ids_seq == doc_ids_par, f"Query '{query}' returned different documents"


class TestScalability:
    """Test scalability characteristics of parallel ingestion."""

    def test_scalability_with_document_count(self, tmp_path):
        """Test how performance scales with document count."""
        results = {}

        for doc_count in [50, 100, 150]:
            # Create KB with specific document count
            kb_dir = tmp_path / f"kb_{doc_count}"
            kb_dir.mkdir()

            for i in range(doc_count):
                content = f"""# Document {i}
Content for document {i} with various keywords.
Topics: audio, video, ml, data, processing, analysis.
"""
                (kb_dir / f"doc_{i}.md").write_text(content)

            config = KnowledgeBeastConfig(
                knowledge_dirs=[kb_dir],
                auto_warm=False,
                verbose=False,
                cache_file=str(tmp_path / f"cache_{doc_count}.json"),
                max_workers=4
            )

            kb = KnowledgeBase(config)

            start = time.time()
            kb.ingest_all()
            elapsed = time.time() - start

            stats = kb.get_stats()
            results[doc_count] = {
                'time': elapsed,
                'throughput': stats['total_documents'] / elapsed
            }

        print(f"\nScalability with Document Count (4 workers):")
        print(f"  {'Documents':<12} {'Time (s)':<12} {'Throughput':<15}")
        print(f"  {'-'*40}")

        for count, data in sorted(results.items()):
            print(f"  {count:<12} {data['time']:<12.2f} {data['throughput']:<15.2f}")

        # Verify linear or better scaling
        # Throughput should not degrade significantly with more documents
        throughput_50 = results[50]['throughput']
        throughput_150 = results[150]['throughput']

        # Allow 30% degradation at most (should be much better in practice)
        assert throughput_150 > throughput_50 * 0.7, \
            f"Throughput degraded too much: {throughput_50:.2f} -> {throughput_150:.2f}"


class TestRegressionBaseline:
    """Baseline tests to detect performance regressions."""

    def test_baseline_parallel_ingestion(self, large_kb_dir, tmp_path):
        """Baseline benchmark for parallel ingestion performance."""
        config = KnowledgeBeastConfig(
            knowledge_dirs=[large_kb_dir],
            auto_warm=False,
            verbose=False,
            cache_file=str(tmp_path / "cache_baseline.json"),
            max_workers=4
        )

        kb = KnowledgeBase(config)

        start = time.time()
        kb.ingest_all()
        elapsed = time.time() - start

        stats = kb.get_stats()
        throughput = stats['total_documents'] / elapsed

        print(f"\nBaseline Parallel Ingestion (4 workers, 150 docs):")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Throughput: {throughput:.2f} docs/sec")

        # Document baseline for regression detection
        # With 4 workers and 150 documents, should process at reasonable rate
        # Target is conservative to account for varying hardware
        assert throughput > 10, f"Performance regression detected: {throughput:.2f} docs/sec"

    def test_query_after_parallel_ingestion(self, large_kb_dir, tmp_path):
        """Verify queries work correctly after parallel ingestion."""
        config = KnowledgeBeastConfig(
            knowledge_dirs=[large_kb_dir],
            auto_warm=False,
            verbose=False,
            cache_file=str(tmp_path / "cache_query.json"),
            max_workers=8
        )

        kb = KnowledgeBase(config)
        kb.ingest_all()

        # Run various queries
        queries = [
            "audio processing",
            "machine learning",
            "Topic A1",
            "Section 1",
            "doc050"
        ]

        for query in queries:
            start = time.time()
            results = kb.query(query)
            query_time = time.time() - start

            assert len(results) > 0, f"Query '{query}' returned no results"
            assert query_time < 0.1, f"Query too slow: {query_time*1000:.2f}ms"

        print(f"\nQuery Performance After Parallel Ingestion: PASSED")
        print(f"  All {len(queries)} test queries completed successfully")
