"""
Performance Benchmarking Dashboard for KnowledgeBeast.

This module provides comprehensive performance monitoring and benchmarking
capabilities including:
- Query latency measurements (P50, P95, P99)
- Throughput analysis (queries/second)
- Cache performance metrics
- Concurrent performance testing
- Memory usage tracking
- Visual report generation (ASCII graphs, HTML, JSON)

Usage:
    python -m tests.performance.dashboard
    knowledgebeast benchmark [--output report.html]
"""

import time
import json
import statistics
import psutil
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

from knowledgebeast.core.engine import KnowledgeBase
from knowledgebeast.core.config import KnowledgeBeastConfig
from knowledgebeast.core.cache import LRUCache


@dataclass
class LatencyMetrics:
    """Latency measurement metrics."""
    p50: float
    p95: float
    p99: float
    mean: float
    min: float
    max: float
    count: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with millisecond values."""
        return {
            'p50_ms': round(self.p50 * 1000, 2),
            'p95_ms': round(self.p95 * 1000, 2),
            'p99_ms': round(self.p99 * 1000, 2),
            'mean_ms': round(self.mean * 1000, 2),
            'min_ms': round(self.min * 1000, 2),
            'max_ms': round(self.max * 1000, 2),
            'count': self.count
        }


@dataclass
class ThroughputMetrics:
    """Throughput measurement metrics."""
    queries_per_second: float
    total_queries: int
    elapsed_seconds: float
    workers: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class CacheMetrics:
    """Cache performance metrics."""
    hit_ratio: float
    hits: int
    misses: int
    size: int
    capacity: int
    utilization: float
    avg_hit_latency_us: float
    avg_miss_latency_us: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class MemoryMetrics:
    """Memory usage metrics."""
    rss_mb: float
    vms_mb: float
    percent: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class BenchmarkReport:
    """Complete benchmark report."""
    timestamp: str
    system_info: Dict[str, Any]
    query_latency: Dict[str, Any]
    cached_query_latency: Dict[str, Any]
    throughput_sequential: Dict[str, Any]
    throughput_concurrent: List[Dict[str, Any]]
    cache_performance: Dict[str, Any]
    memory_usage: Dict[str, Any]
    scalability: Dict[str, List[float]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class PerformanceDashboard:
    """
    Comprehensive performance monitoring dashboard.

    Measures and reports:
    - Query latency (P50, P95, P99)
    - Throughput (queries/second)
    - Cache performance (hit ratio, latency)
    - Concurrent performance (1, 10, 50, 100 workers)
    - Memory usage during operations
    """

    def __init__(self, kb: KnowledgeBase):
        """
        Initialize dashboard with knowledge base instance.

        Args:
            kb: KnowledgeBase instance to benchmark
        """
        self.kb = kb
        self.process = psutil.Process(os.getpid())

    def measure_latency(self, queries: List[str], use_cache: bool = False,
                       iterations: int = 100) -> LatencyMetrics:
        """
        Measure query latency.

        Args:
            queries: List of queries to test
            use_cache: Whether to use cache
            iterations: Number of iterations per query

        Returns:
            LatencyMetrics with P50, P95, P99, etc.
        """
        latencies = []

        for _ in range(iterations):
            query = queries[_ % len(queries)]
            start = time.perf_counter()
            self.kb.query(query, use_cache=use_cache)
            latency = time.perf_counter() - start
            latencies.append(latency)

        if len(latencies) == 0:
            return LatencyMetrics(0, 0, 0, 0, 0, 0, 0)

        sorted_latencies = sorted(latencies)
        count = len(sorted_latencies)

        return LatencyMetrics(
            p50=statistics.median(sorted_latencies),
            p95=sorted_latencies[int(count * 0.95)] if count > 20 else sorted_latencies[-1],
            p99=sorted_latencies[int(count * 0.99)] if count > 100 else sorted_latencies[-1],
            mean=statistics.mean(sorted_latencies),
            min=min(sorted_latencies),
            max=max(sorted_latencies),
            count=count
        )

    def measure_throughput(self, queries: List[str], workers: int = 1,
                          queries_per_worker: int = 100,
                          use_cache: bool = True) -> ThroughputMetrics:
        """
        Measure query throughput.

        Args:
            queries: List of queries to test
            workers: Number of concurrent workers
            queries_per_worker: Queries each worker should execute
            use_cache: Whether to use cache

        Returns:
            ThroughputMetrics with queries/second
        """
        def worker(worker_id: int) -> int:
            """Worker function."""
            for i in range(queries_per_worker):
                query = queries[i % len(queries)]
                self.kb.query(query, use_cache=use_cache)
            return queries_per_worker

        start = time.perf_counter()

        if workers == 1:
            total = worker(0)
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(worker, i) for i in range(workers)]
                totals = [f.result() for f in as_completed(futures)]
                total = sum(totals)

        elapsed = time.perf_counter() - start
        qps = total / elapsed if elapsed > 0 else 0

        return ThroughputMetrics(
            queries_per_second=qps,
            total_queries=total,
            elapsed_seconds=elapsed,
            workers=workers
        )

    def measure_cache_performance(self) -> CacheMetrics:
        """
        Measure cache performance metrics.

        Returns:
            CacheMetrics with hit ratio, latency, etc.
        """
        cache = LRUCache[str, list](capacity=100)

        # Populate cache
        for i in range(100):
            cache.put(f"key_{i}", [f"value_{j}" for j in range(10)])

        # Measure hit latency
        hit_latencies = []
        hits = 0
        for _ in range(1000):
            start = time.perf_counter()
            result = cache.get("key_50")
            if result is not None:
                hits += 1
            hit_latencies.append(time.perf_counter() - start)

        # Measure miss latency
        miss_latencies = []
        misses = 0
        for _ in range(1000):
            start = time.perf_counter()
            result = cache.get("nonexistent_key")
            if result is None:
                misses += 1
            miss_latencies.append(time.perf_counter() - start)

        stats = cache.stats()

        return CacheMetrics(
            hit_ratio=hits / (hits + misses) if (hits + misses) > 0 else 0,
            hits=hits,
            misses=misses,
            size=stats['size'],
            capacity=stats['capacity'],
            utilization=stats['utilization'],
            avg_hit_latency_us=statistics.mean(hit_latencies) * 1_000_000,
            avg_miss_latency_us=statistics.mean(miss_latencies) * 1_000_000
        )

    def measure_memory(self) -> MemoryMetrics:
        """
        Measure current memory usage.

        Returns:
            MemoryMetrics with RSS, VMS, and percentage
        """
        mem_info = self.process.memory_info()
        mem_percent = self.process.memory_percent()

        return MemoryMetrics(
            rss_mb=mem_info.rss / (1024 * 1024),
            vms_mb=mem_info.vms / (1024 * 1024),
            percent=mem_percent
        )

    def measure_scalability(self, queries: List[str],
                           worker_counts: List[int] = None,
                           queries_per_worker: int = 50) -> Dict[int, float]:
        """
        Measure scalability with increasing worker counts.

        Args:
            queries: List of queries to test
            worker_counts: List of worker counts to test
            queries_per_worker: Queries per worker

        Returns:
            Dictionary mapping worker count to throughput
        """
        if worker_counts is None:
            worker_counts = [1, 2, 5, 10, 20, 50]

        results = {}
        for workers in worker_counts:
            metrics = self.measure_throughput(
                queries,
                workers=workers,
                queries_per_worker=queries_per_worker
            )
            results[workers] = metrics.queries_per_second

        return results

    def run_full_benchmark(self, test_queries: List[str] = None) -> BenchmarkReport:
        """
        Run complete benchmark suite.

        Args:
            test_queries: Optional list of queries to use for testing

        Returns:
            Complete BenchmarkReport
        """
        if test_queries is None:
            test_queries = [
                "audio processing",
                "video analysis",
                "machine learning",
                "data science",
                "NLP natural language"
            ]

        # Warm up cache
        for query in test_queries:
            self.kb.query(query, use_cache=True)

        print("Running comprehensive benchmarks...")
        print("=" * 60)

        # System info
        import platform
        system_info = {
            'platform': platform.system(),
            'platform_version': platform.version(),
            'python_version': platform.python_version(),
            'processor': platform.processor(),
            'cpu_count': psutil.cpu_count(),
            'total_memory_gb': round(psutil.virtual_memory().total / (1024**3), 2)
        }

        # Query latency (uncached)
        print("\n1. Measuring query latency (uncached)...")
        query_latency = self.measure_latency(test_queries, use_cache=False, iterations=100)
        print(f"   P50: {query_latency.p50*1000:.2f}ms | P95: {query_latency.p95*1000:.2f}ms | P99: {query_latency.p99*1000:.2f}ms")

        # Query latency (cached)
        print("\n2. Measuring query latency (cached)...")
        cached_latency = self.measure_latency(test_queries, use_cache=True, iterations=100)
        print(f"   P50: {cached_latency.p50*1000:.2f}ms | P95: {cached_latency.p95*1000:.2f}ms | P99: {cached_latency.p99*1000:.2f}ms")

        # Sequential throughput
        print("\n3. Measuring sequential throughput...")
        seq_throughput = self.measure_throughput(test_queries, workers=1, queries_per_worker=100)
        print(f"   {seq_throughput.queries_per_second:.2f} queries/sec")

        # Concurrent throughput
        print("\n4. Measuring concurrent throughput...")
        concurrent_throughput = []
        for workers in [10, 50]:
            metrics = self.measure_throughput(test_queries, workers=workers, queries_per_worker=50)
            concurrent_throughput.append(metrics.to_dict())
            print(f"   {workers} workers: {metrics.queries_per_second:.2f} queries/sec")

        # Cache performance
        print("\n5. Measuring cache performance...")
        cache_perf = self.measure_cache_performance()
        print(f"   Hit ratio: {cache_perf.hit_ratio*100:.1f}% | Hit latency: {cache_perf.avg_hit_latency_us:.2f}μs")

        # Memory usage
        print("\n6. Measuring memory usage...")
        memory = self.measure_memory()
        print(f"   RSS: {memory.rss_mb:.2f}MB | Percent: {memory.percent:.2f}%")

        # Scalability
        print("\n7. Measuring scalability...")
        scalability = self.measure_scalability(test_queries, worker_counts=[1, 2, 5, 10, 20])
        scalability_data = {
            'worker_counts': list(scalability.keys()),
            'throughput': list(scalability.values())
        }
        for workers, qps in scalability.items():
            print(f"   {workers:2d} workers: {qps:7.2f} queries/sec")

        print("\n" + "=" * 60)
        print("Benchmark complete!")

        return BenchmarkReport(
            timestamp=datetime.now().isoformat(),
            system_info=system_info,
            query_latency=query_latency.to_dict(),
            cached_query_latency=cached_latency.to_dict(),
            throughput_sequential=seq_throughput.to_dict(),
            throughput_concurrent=concurrent_throughput,
            cache_performance=cache_perf.to_dict(),
            memory_usage=memory.to_dict(),
            scalability=scalability_data
        )

    def generate_ascii_report(self, report: BenchmarkReport) -> str:
        """
        Generate ASCII text report.

        Args:
            report: BenchmarkReport to format

        Returns:
            Formatted ASCII report string
        """
        lines = []
        lines.append("=" * 70)
        lines.append("KNOWLEDGEBEAST PERFORMANCE BENCHMARK REPORT")
        lines.append("=" * 70)
        lines.append(f"Timestamp: {report.timestamp}")
        lines.append("")

        # System Info
        lines.append("SYSTEM INFORMATION")
        lines.append("-" * 70)
        for key, value in report.system_info.items():
            lines.append(f"  {key:20s}: {value}")
        lines.append("")

        # Query Latency
        lines.append("QUERY LATENCY (Uncached)")
        lines.append("-" * 70)
        for key, value in report.query_latency.items():
            lines.append(f"  {key:20s}: {value}")
        lines.append("")

        lines.append("QUERY LATENCY (Cached)")
        lines.append("-" * 70)
        for key, value in report.cached_query_latency.items():
            lines.append(f"  {key:20s}: {value}")
        lines.append("")

        # Throughput
        lines.append("THROUGHPUT - Sequential")
        lines.append("-" * 70)
        for key, value in report.throughput_sequential.items():
            lines.append(f"  {key:20s}: {value}")
        lines.append("")

        lines.append("THROUGHPUT - Concurrent")
        lines.append("-" * 70)
        for metrics in report.throughput_concurrent:
            lines.append(f"  Workers: {metrics['workers']}")
            lines.append(f"    QPS: {metrics['queries_per_second']:.2f}")
            lines.append(f"    Total Queries: {metrics['total_queries']}")
            lines.append(f"    Elapsed: {metrics['elapsed_seconds']:.2f}s")
        lines.append("")

        # Cache Performance
        lines.append("CACHE PERFORMANCE")
        lines.append("-" * 70)
        for key, value in report.cache_performance.items():
            lines.append(f"  {key:20s}: {value}")
        lines.append("")

        # Memory Usage
        lines.append("MEMORY USAGE")
        lines.append("-" * 70)
        for key, value in report.memory_usage.items():
            lines.append(f"  {key:20s}: {value}")
        lines.append("")

        # Scalability
        lines.append("SCALABILITY")
        lines.append("-" * 70)
        workers = report.scalability['worker_counts']
        throughput = report.scalability['throughput']
        for w, t in zip(workers, throughput):
            lines.append(f"  {w:2d} workers: {t:7.2f} queries/sec")
        lines.append("")

        # ASCII Graph
        lines.append("SCALABILITY GRAPH")
        lines.append("-" * 70)
        max_qps = max(throughput)
        scale = 50 / max_qps if max_qps > 0 else 1
        for w, t in zip(workers, throughput):
            bar = "#" * int(t * scale)
            lines.append(f"  {w:2d} workers: {bar} {t:.0f} qps")
        lines.append("")

        lines.append("=" * 70)
        lines.append("END OF REPORT")
        lines.append("=" * 70)

        return "\n".join(lines)

    def generate_html_report(self, report: BenchmarkReport) -> str:
        """
        Generate HTML report with charts.

        Args:
            report: BenchmarkReport to format

        Returns:
            HTML string
        """
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>KnowledgeBeast Performance Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
        }}
        .section {{
            background: white;
            padding: 20px;
            margin: 20px 0;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ecf0f1;
        }}
        th {{
            background: #3498db;
            color: white;
            font-weight: 600;
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        .metric {{
            display: inline-block;
            padding: 8px 16px;
            margin: 5px;
            background: #e8f4f8;
            border-radius: 4px;
            border-left: 4px solid #3498db;
        }}
        .metric-value {{
            font-weight: bold;
            color: #2c3e50;
        }}
        .timestamp {{
            color: #7f8c8d;
            font-size: 0.9em;
        }}
        .chart {{
            margin: 20px 0;
        }}
        .bar {{
            background: linear-gradient(90deg, #3498db, #2980b9);
            height: 30px;
            margin: 5px 0;
            border-radius: 4px;
            display: flex;
            align-items: center;
            padding: 0 10px;
            color: white;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <h1>KnowledgeBeast Performance Benchmark Report</h1>
    <p class="timestamp">Generated: {report.timestamp}</p>

    <div class="section">
        <h2>System Information</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            {''.join(f'<tr><td>{k.replace("_", " ").title()}</td><td>{v}</td></tr>' for k, v in report.system_info.items())}
        </table>
    </div>

    <div class="section">
        <h2>Query Latency</h2>
        <h3>Uncached Queries</h3>
        <div class="metric">P50: <span class="metric-value">{report.query_latency['p50_ms']:.2f}ms</span></div>
        <div class="metric">P95: <span class="metric-value">{report.query_latency['p95_ms']:.2f}ms</span></div>
        <div class="metric">P99: <span class="metric-value">{report.query_latency['p99_ms']:.2f}ms</span></div>
        <div class="metric">Mean: <span class="metric-value">{report.query_latency['mean_ms']:.2f}ms</span></div>

        <h3>Cached Queries</h3>
        <div class="metric">P50: <span class="metric-value">{report.cached_query_latency['p50_ms']:.2f}ms</span></div>
        <div class="metric">P95: <span class="metric-value">{report.cached_query_latency['p95_ms']:.2f}ms</span></div>
        <div class="metric">P99: <span class="metric-value">{report.cached_query_latency['p99_ms']:.2f}ms</span></div>
        <div class="metric">Mean: <span class="metric-value">{report.cached_query_latency['mean_ms']:.2f}ms</span></div>
    </div>

    <div class="section">
        <h2>Throughput</h2>
        <h3>Sequential</h3>
        <div class="metric">QPS: <span class="metric-value">{report.throughput_sequential['queries_per_second']:.2f}</span></div>

        <h3>Concurrent</h3>
        <table>
            <tr><th>Workers</th><th>QPS</th><th>Total Queries</th><th>Elapsed (s)</th></tr>
            {''.join(f'<tr><td>{m["workers"]}</td><td>{m["queries_per_second"]:.2f}</td><td>{m["total_queries"]}</td><td>{m["elapsed_seconds"]:.2f}</td></tr>' for m in report.throughput_concurrent)}
        </table>
    </div>

    <div class="section">
        <h2>Cache Performance</h2>
        <div class="metric">Hit Ratio: <span class="metric-value">{report.cache_performance['hit_ratio']*100:.1f}%</span></div>
        <div class="metric">Hit Latency: <span class="metric-value">{report.cache_performance['avg_hit_latency_us']:.2f}μs</span></div>
        <div class="metric">Miss Latency: <span class="metric-value">{report.cache_performance['avg_miss_latency_us']:.2f}μs</span></div>
        <div class="metric">Utilization: <span class="metric-value">{report.cache_performance['utilization']*100:.1f}%</span></div>
    </div>

    <div class="section">
        <h2>Memory Usage</h2>
        <div class="metric">RSS: <span class="metric-value">{report.memory_usage['rss_mb']:.2f} MB</span></div>
        <div class="metric">VMS: <span class="metric-value">{report.memory_usage['vms_mb']:.2f} MB</span></div>
        <div class="metric">Percent: <span class="metric-value">{report.memory_usage['percent']:.2f}%</span></div>
    </div>

    <div class="section">
        <h2>Scalability</h2>
        <div class="chart">
"""
        # Add scalability chart
        workers = report.scalability['worker_counts']
        throughput = report.scalability['throughput']
        max_qps = max(throughput) if throughput else 1

        for w, t in zip(workers, throughput):
            width = (t / max_qps * 100) if max_qps > 0 else 0
            html += f'            <div class="bar" style="width: {width}%">{w} workers: {t:.0f} qps</div>\n'

        html += """        </div>
    </div>

</body>
</html>"""
        return html


def main():
    """Main entry point for standalone benchmarking."""
    import argparse

    parser = argparse.ArgumentParser(description='KnowledgeBeast Performance Benchmark')
    parser.add_argument('--output', '-o', help='Output file path (JSON or HTML)')
    parser.add_argument('--format', '-f', choices=['json', 'html', 'text'], default='text',
                       help='Output format')
    parser.add_argument('--data-dir', default='./data', help='Data directory')

    args = parser.parse_args()

    # Setup test KB
    from pathlib import Path
    import tempfile

    # Create test data
    with tempfile.TemporaryDirectory() as tmpdir:
        kb_dir = Path(tmpdir) / "knowledge"
        kb_dir.mkdir()

        # Create test documents
        for i in range(10):
            content = f"""# Document {i}
This document covers topic_{i % 3} with various keywords.
Audio processing, video analysis, machine learning, data science, NLP.
Document {i} contains information about signal processing and computer vision.
"""
            (kb_dir / f"doc_{i}.md").write_text(content)

        # Initialize KB
        config = KnowledgeBeastConfig(
            knowledge_dirs=[kb_dir],
            auto_warm=True,
            cache_file=str(Path(tmpdir) / "cache.json")
        )
        kb = KnowledgeBase(config)
        kb.ingest_all()

        # Run benchmark
        dashboard = PerformanceDashboard(kb)
        report = dashboard.run_full_benchmark()

        # Output results
        if args.format == 'json' or (args.output and args.output.endswith('.json')):
            output = report.to_json()
        elif args.format == 'html' or (args.output and args.output.endswith('.html')):
            output = dashboard.generate_html_report(report)
        else:
            output = dashboard.generate_ascii_report(report)

        if args.output:
            Path(args.output).write_text(output)
            print(f"\nReport saved to: {args.output}")
        else:
            print("\n" + output)


if __name__ == '__main__':
    main()
