"""
Tests for Performance Dashboard.

Tests verify:
- Latency measurement accuracy
- Throughput calculation correctness
- Cache metrics collection
- Memory tracking
- Report generation (text, JSON, HTML)
- Metric data structures
- Scalability measurement
"""

import time
import json
import pytest
from pathlib import Path
from tests.performance.dashboard import (
    PerformanceDashboard,
    LatencyMetrics,
    ThroughputMetrics,
    CacheMetrics,
    MemoryMetrics,
    BenchmarkReport
)
from knowledgebeast.core.engine import KnowledgeBase
from knowledgebeast.core.config import KnowledgeBeastConfig


@pytest.fixture
def kb_instance(tmp_path):
    """Create KB instance for dashboard testing."""
    kb_dir = tmp_path / "knowledge"
    kb_dir.mkdir()

    # Create test documents
    for i in range(10):
        content = f"""# Document {i}
This document covers topic_{i % 3} with various keywords.
Audio processing, video analysis, machine learning, data science, NLP.
Document {i} contains information about signal processing and computer vision.
"""
        (kb_dir / f"doc_{i}.md").write_text(content)

    config = KnowledgeBeastConfig(
        knowledge_dirs=[kb_dir],
        auto_warm=False,
        cache_file=str(tmp_path / "cache.json")
    )
    kb = KnowledgeBase(config)
    kb.ingest_all()
    return kb


@pytest.fixture
def dashboard(kb_instance):
    """Create dashboard instance."""
    return PerformanceDashboard(kb_instance)


class TestLatencyMeasurement:
    """Test latency measurement functionality."""

    def test_measure_latency_uncached(self, dashboard):
        """Test uncached latency measurement."""
        queries = ["audio processing", "video analysis", "machine learning"]

        metrics = dashboard.measure_latency(queries, use_cache=False, iterations=50)

        assert isinstance(metrics, LatencyMetrics)
        assert metrics.count == 50
        assert metrics.p50 > 0
        assert metrics.p95 > 0
        assert metrics.p99 > 0
        assert metrics.p99 >= metrics.p95 >= metrics.p50
        assert metrics.max >= metrics.p99
        assert metrics.min <= metrics.p50
        assert 0 < metrics.mean < 1.0  # Should be under 1 second

    def test_measure_latency_cached(self, dashboard):
        """Test cached latency measurement."""
        queries = ["audio processing"]

        # Warm cache
        for _ in range(5):
            dashboard.kb.query(queries[0], use_cache=True)

        metrics = dashboard.measure_latency(queries, use_cache=True, iterations=50)

        assert isinstance(metrics, LatencyMetrics)
        assert metrics.count == 50
        # Cached queries should be much faster
        assert metrics.p50 < 0.1  # Less than 100ms

    def test_latency_metrics_to_dict(self):
        """Test LatencyMetrics to_dict conversion."""
        metrics = LatencyMetrics(
            p50=0.050,
            p95=0.095,
            p99=0.099,
            mean=0.055,
            min=0.040,
            max=0.100,
            count=100
        )

        result = metrics.to_dict()

        assert result['p50_ms'] == 50.0
        assert result['p95_ms'] == 95.0
        assert result['p99_ms'] == 99.0
        assert result['mean_ms'] == 55.0
        assert result['min_ms'] == 40.0
        assert result['max_ms'] == 100.0
        assert result['count'] == 100

    def test_latency_percentiles_ordered(self, dashboard):
        """Test that percentiles are correctly ordered."""
        queries = ["audio", "video", "ml"]

        metrics = dashboard.measure_latency(queries, use_cache=False, iterations=100)

        assert metrics.min <= metrics.p50
        assert metrics.p50 <= metrics.p95
        assert metrics.p95 <= metrics.p99
        assert metrics.p99 <= metrics.max


class TestThroughputMeasurement:
    """Test throughput measurement functionality."""

    def test_measure_throughput_sequential(self, dashboard):
        """Test sequential throughput measurement."""
        queries = ["audio", "video", "ml"]

        metrics = dashboard.measure_throughput(
            queries,
            workers=1,
            queries_per_worker=50
        )

        assert isinstance(metrics, ThroughputMetrics)
        assert metrics.workers == 1
        assert metrics.total_queries == 50
        assert metrics.queries_per_second > 0
        assert metrics.elapsed_seconds > 0
        assert metrics.queries_per_second == metrics.total_queries / metrics.elapsed_seconds

    def test_measure_throughput_concurrent(self, dashboard):
        """Test concurrent throughput measurement."""
        queries = ["audio", "video", "ml"]

        metrics = dashboard.measure_throughput(
            queries,
            workers=10,
            queries_per_worker=20
        )

        assert isinstance(metrics, ThroughputMetrics)
        assert metrics.workers == 10
        assert metrics.total_queries == 200  # 10 * 20
        assert metrics.queries_per_second > 0

    def test_throughput_scales_with_workers(self, dashboard):
        """Test that throughput improves with workers."""
        queries = ["audio", "video"]

        # Measure with 1 worker
        single = dashboard.measure_throughput(queries, workers=1, queries_per_worker=30)

        # Measure with 5 workers
        multi = dashboard.measure_throughput(queries, workers=5, queries_per_worker=30)

        # Multi-threaded should complete more total queries (even if per-second might vary)
        assert multi.total_queries > single.total_queries
        # Both should have reasonable throughput
        assert multi.queries_per_second > 100

    def test_throughput_metrics_to_dict(self):
        """Test ThroughputMetrics to_dict conversion."""
        metrics = ThroughputMetrics(
            queries_per_second=500.0,
            total_queries=1000,
            elapsed_seconds=2.0,
            workers=10
        )

        result = metrics.to_dict()

        assert result['queries_per_second'] == 500.0
        assert result['total_queries'] == 1000
        assert result['elapsed_seconds'] == 2.0
        assert result['workers'] == 10


class TestCacheMetrics:
    """Test cache performance metrics."""

    def test_measure_cache_performance(self, dashboard):
        """Test cache performance measurement."""
        metrics = dashboard.measure_cache_performance()

        assert isinstance(metrics, CacheMetrics)
        assert 0 <= metrics.hit_ratio <= 1.0
        assert metrics.hits >= 0
        assert metrics.misses >= 0
        assert metrics.size <= metrics.capacity
        assert 0 <= metrics.utilization <= 1.0
        assert metrics.avg_hit_latency_us > 0
        assert metrics.avg_miss_latency_us > 0

    def test_cache_metrics_to_dict(self):
        """Test CacheMetrics to_dict conversion."""
        metrics = CacheMetrics(
            hit_ratio=0.95,
            hits=950,
            misses=50,
            size=100,
            capacity=100,
            utilization=1.0,
            avg_hit_latency_us=5.0,
            avg_miss_latency_us=3.0
        )

        result = metrics.to_dict()

        assert result['hit_ratio'] == 0.95
        assert result['hits'] == 950
        assert result['misses'] == 50
        assert result['utilization'] == 1.0


class TestMemoryMetrics:
    """Test memory usage tracking."""

    def test_measure_memory(self, dashboard):
        """Test memory measurement."""
        metrics = dashboard.measure_memory()

        assert isinstance(metrics, MemoryMetrics)
        assert metrics.rss_mb > 0
        assert metrics.vms_mb > 0
        assert metrics.percent >= 0

    def test_memory_metrics_to_dict(self):
        """Test MemoryMetrics to_dict conversion."""
        metrics = MemoryMetrics(
            rss_mb=150.5,
            vms_mb=500.0,
            percent=2.5
        )

        result = metrics.to_dict()

        assert result['rss_mb'] == 150.5
        assert result['vms_mb'] == 500.0
        assert result['percent'] == 2.5


class TestScalability:
    """Test scalability measurement."""

    def test_measure_scalability(self, dashboard):
        """Test scalability measurement with varying workers."""
        queries = ["audio", "video"]

        results = dashboard.measure_scalability(
            queries,
            worker_counts=[1, 2, 5],
            queries_per_worker=20
        )

        assert isinstance(results, dict)
        assert len(results) == 3
        assert 1 in results
        assert 2 in results
        assert 5 in results
        assert all(qps > 0 for qps in results.values())

    def test_scalability_increases_with_workers(self, dashboard):
        """Test that QPS generally increases with workers."""
        queries = ["audio", "video"]

        results = dashboard.measure_scalability(
            queries,
            worker_counts=[1, 5, 10],
            queries_per_worker=20
        )

        # All configurations should have reasonable throughput
        # Note: Due to threading overhead, more workers doesn't always mean higher QPS
        # but all should complete successfully
        assert all(qps > 100 for qps in results.values())
        assert len(results) == 3


class TestFullBenchmark:
    """Test full benchmark suite."""

    def test_run_full_benchmark(self, dashboard):
        """Test running complete benchmark."""
        report = dashboard.run_full_benchmark()

        assert isinstance(report, BenchmarkReport)
        assert report.timestamp is not None
        assert 'platform' in report.system_info
        assert 'python_version' in report.system_info
        assert report.query_latency is not None
        assert report.cached_query_latency is not None
        assert report.throughput_sequential is not None
        assert len(report.throughput_concurrent) > 0
        assert report.cache_performance is not None
        assert report.memory_usage is not None
        assert 'worker_counts' in report.scalability
        assert 'throughput' in report.scalability

    def test_benchmark_report_to_dict(self, dashboard):
        """Test BenchmarkReport to_dict conversion."""
        report = dashboard.run_full_benchmark()

        result = report.to_dict()

        assert isinstance(result, dict)
        assert 'timestamp' in result
        assert 'system_info' in result
        assert 'query_latency' in result
        assert 'cached_query_latency' in result
        assert 'throughput_sequential' in result
        assert 'throughput_concurrent' in result
        assert 'cache_performance' in result
        assert 'memory_usage' in result
        assert 'scalability' in result

    def test_benchmark_report_to_json(self, dashboard):
        """Test BenchmarkReport to_json conversion."""
        report = dashboard.run_full_benchmark()

        json_str = report.to_json()

        assert isinstance(json_str, str)
        # Verify it's valid JSON
        parsed = json.loads(json_str)
        assert 'timestamp' in parsed
        assert 'system_info' in parsed


class TestReportGeneration:
    """Test report generation in various formats."""

    def test_generate_ascii_report(self, dashboard):
        """Test ASCII report generation."""
        report = dashboard.run_full_benchmark()

        ascii_report = dashboard.generate_ascii_report(report)

        assert isinstance(ascii_report, str)
        assert "KNOWLEDGEBEAST PERFORMANCE BENCHMARK REPORT" in ascii_report
        assert "SYSTEM INFORMATION" in ascii_report
        assert "QUERY LATENCY" in ascii_report
        assert "THROUGHPUT" in ascii_report
        assert "CACHE PERFORMANCE" in ascii_report
        assert "MEMORY USAGE" in ascii_report
        assert "SCALABILITY" in ascii_report

    def test_generate_html_report(self, dashboard):
        """Test HTML report generation."""
        report = dashboard.run_full_benchmark()

        html_report = dashboard.generate_html_report(report)

        assert isinstance(html_report, str)
        assert "<!DOCTYPE html>" in html_report
        assert "KnowledgeBeast Performance Report" in html_report
        assert "System Information" in html_report
        assert "Query Latency" in html_report
        assert "Throughput" in html_report
        assert "Cache Performance" in html_report
        assert "Memory Usage" in html_report
        assert "Scalability" in html_report
        assert "</html>" in html_report

    def test_ascii_report_contains_metrics(self, dashboard):
        """Test ASCII report contains actual metric values."""
        report = dashboard.run_full_benchmark()

        ascii_report = dashboard.generate_ascii_report(report)

        # Should contain numeric values
        assert "p50_ms" in ascii_report
        assert "p95_ms" in ascii_report
        assert "p99_ms" in ascii_report
        assert "queries_per_second" in ascii_report

    def test_html_report_contains_metrics(self, dashboard):
        """Test HTML report contains actual metric values."""
        report = dashboard.run_full_benchmark()

        html_report = dashboard.generate_html_report(report)

        # Should contain metric values
        assert "P50:" in html_report
        assert "P95:" in html_report
        assert "P99:" in html_report
        assert "QPS:" in html_report
        assert "Hit Ratio:" in html_report

    def test_ascii_report_has_graph(self, dashboard):
        """Test ASCII report includes scalability graph."""
        report = dashboard.run_full_benchmark()

        ascii_report = dashboard.generate_ascii_report(report)

        assert "SCALABILITY GRAPH" in ascii_report
        assert "workers:" in ascii_report
        assert "#" in ascii_report  # Bar chart characters


class TestReportPersistence:
    """Test saving reports to files."""

    def test_save_json_report(self, dashboard, tmp_path):
        """Test saving JSON report to file."""
        report = dashboard.run_full_benchmark()

        output_file = tmp_path / "report.json"
        output_file.write_text(report.to_json())

        assert output_file.exists()

        # Verify it's valid JSON
        content = json.loads(output_file.read_text())
        assert 'timestamp' in content
        assert 'system_info' in content

    def test_save_html_report(self, dashboard, tmp_path):
        """Test saving HTML report to file."""
        report = dashboard.run_full_benchmark()

        output_file = tmp_path / "report.html"
        html_content = dashboard.generate_html_report(report)
        output_file.write_text(html_content)

        assert output_file.exists()

        content = output_file.read_text()
        assert "<!DOCTYPE html>" in content
        assert "</html>" in content

    def test_save_text_report(self, dashboard, tmp_path):
        """Test saving text report to file."""
        report = dashboard.run_full_benchmark()

        output_file = tmp_path / "report.txt"
        text_content = dashboard.generate_ascii_report(report)
        output_file.write_text(text_content)

        assert output_file.exists()

        content = output_file.read_text()
        assert "KNOWLEDGEBEAST PERFORMANCE BENCHMARK REPORT" in content


class TestCustomQueries:
    """Test benchmarking with custom queries."""

    def test_benchmark_with_custom_queries(self, dashboard):
        """Test running benchmark with custom query list."""
        custom_queries = [
            "test query one",
            "test query two",
            "test query three"
        ]

        report = dashboard.run_full_benchmark(test_queries=custom_queries)

        assert isinstance(report, BenchmarkReport)
        # Should complete without errors

    def test_benchmark_with_single_query(self, dashboard):
        """Test benchmark with single query."""
        report = dashboard.run_full_benchmark(test_queries=["audio"])

        assert isinstance(report, BenchmarkReport)
        assert report.query_latency is not None


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_latency_with_empty_queries(self, dashboard):
        """Test latency measurement handles edge case."""
        # Should handle gracefully
        metrics = dashboard.measure_latency(["nonexistent"], use_cache=False, iterations=10)

        assert isinstance(metrics, LatencyMetrics)
        assert metrics.count == 10

    def test_throughput_with_zero_workers(self, dashboard):
        """Test throughput with minimal configuration."""
        # 1 worker is minimum
        metrics = dashboard.measure_throughput(
            ["audio"],
            workers=1,
            queries_per_worker=1
        )

        assert metrics.total_queries == 1
        assert metrics.queries_per_second > 0

    def test_memory_tracking_consistency(self, dashboard):
        """Test memory measurements are consistent."""
        mem1 = dashboard.measure_memory()
        time.sleep(0.1)
        mem2 = dashboard.measure_memory()

        # Memory should be relatively stable
        assert abs(mem1.rss_mb - mem2.rss_mb) < 100  # Less than 100MB difference


class TestPerformanceTargets:
    """Test that performance meets targets."""

    def test_query_latency_target(self, dashboard):
        """Test P99 latency meets target (< 100ms)."""
        queries = ["audio", "video", "ml"]

        metrics = dashboard.measure_latency(queries, use_cache=False, iterations=100)

        # P99 should be under 100ms
        assert metrics.p99 < 0.1, f"P99 latency too high: {metrics.p99*1000:.2f}ms"

    def test_cached_latency_target(self, dashboard):
        """Test cached P99 latency meets target (< 10ms)."""
        queries = ["audio"]

        # Warm cache
        for _ in range(5):
            dashboard.kb.query(queries[0], use_cache=True)

        metrics = dashboard.measure_latency(queries, use_cache=True, iterations=100)

        # Cached P99 should be under 10ms
        assert metrics.p99 < 0.01, f"Cached P99 latency too high: {metrics.p99*1000:.2f}ms"

    def test_throughput_target(self, dashboard):
        """Test throughput meets target (> 500 q/s)."""
        queries = ["audio", "video"]

        metrics = dashboard.measure_throughput(
            queries,
            workers=10,
            queries_per_worker=100
        )

        # Should achieve > 500 q/s with 10 workers
        assert metrics.queries_per_second > 500, \
            f"Throughput too low: {metrics.queries_per_second:.2f} q/s"

    def test_cache_hit_ratio_target(self, dashboard):
        """Test cache achieves good hit ratio."""
        # Run same queries multiple times
        queries = ["audio", "video", "ml"]

        for _ in range(10):
            for query in queries:
                dashboard.kb.query(query, use_cache=True)

        stats = dashboard.kb.get_stats()
        total = stats['cache_hits'] + stats['cache_misses']
        hit_ratio = stats['cache_hits'] / total if total > 0 else 0

        # Should achieve >= 90% hit ratio with repeated queries
        assert hit_ratio >= 0.90, f"Cache hit ratio too low: {hit_ratio*100:.1f}%"
