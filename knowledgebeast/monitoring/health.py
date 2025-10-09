"""Project health monitoring system.

Provides comprehensive health metrics and alerting for KnowledgeBeast projects.
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class ProjectHealthMonitor:
    """Monitor project health metrics and generate alerts.

    Tracks:
    - Query latency (avg, p95, p99)
    - Error rates
    - Cache performance
    - Document counts
    - Last activity

    Generates alerts for:
    - High query latency
    - High error rates
    - Low cache hit rates
    - Stale projects
    """

    def __init__(self, project_manager):
        """Initialize health monitor.

        Args:
            project_manager: ProjectManager instance
        """
        self.pm = project_manager

        # Query metrics per project (project_id -> deque of latencies)
        self._query_latencies: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

        # Error counts per project
        self._error_counts: Dict[str, int] = defaultdict(int)

        # Total query counts per project
        self._query_counts: Dict[str, int] = defaultdict(int)

        # Last query timestamps per project
        self._last_queries: Dict[str, datetime] = {}

        # Cache hit/miss tracking per project
        self._cache_hits: Dict[str, int] = defaultdict(int)
        self._cache_misses: Dict[str, int] = defaultdict(int)

        logger.info("ProjectHealthMonitor initialized")

    def record_query(
        self,
        project_id: str,
        latency_ms: float,
        success: bool,
        cache_hit: bool = False
    ) -> None:
        """Record query metrics for health tracking.

        Args:
            project_id: Project identifier
            latency_ms: Query latency in milliseconds
            success: Whether query succeeded
            cache_hit: Whether query was served from cache
        """
        # Record latency
        self._query_latencies[project_id].append(latency_ms)

        # Update counts
        self._query_counts[project_id] += 1

        if not success:
            self._error_counts[project_id] += 1

        if cache_hit:
            self._cache_hits[project_id] += 1
        else:
            self._cache_misses[project_id] += 1

        # Update last query timestamp
        self._last_queries[project_id] = datetime.utcnow()

        logger.debug(
            f"Recorded query for project {project_id}: "
            f"latency={latency_ms:.2f}ms, success={success}, cache_hit={cache_hit}"
        )

    def get_project_health(self, project_id: str) -> Dict[str, Any]:
        """Get comprehensive health status for a project.

        Args:
            project_id: Project identifier

        Returns:
            Dictionary with health status, metrics, and alerts
        """
        # Verify project exists
        project = self.pm.get_project(project_id)
        if not project:
            return {
                "project_id": project_id,
                "status": "not_found",
                "error": "Project not found",
                "timestamp": datetime.utcnow().isoformat()
            }

        # Get query latency statistics
        latencies = list(self._query_latencies[project_id])
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            p95_latency = self._percentile(latencies, 95)
            p99_latency = self._percentile(latencies, 99)
        else:
            avg_latency = 0
            p95_latency = 0
            p99_latency = 0

        # Calculate error rate
        total_queries = self._query_counts[project_id]
        error_count = self._error_counts[project_id]
        error_rate = error_count / total_queries if total_queries > 0 else 0

        # Calculate cache hit rate
        total_cache_queries = self._cache_hits[project_id] + self._cache_misses[project_id]
        cache_hit_rate = (
            self._cache_hits[project_id] / total_cache_queries
            if total_cache_queries > 0
            else 0
        )

        # Get document count
        collection = self.pm.get_collection(project_id)
        doc_count = collection.count() if collection else 0

        # Calculate time since last query
        last_query = self._last_queries.get(project_id)
        minutes_since_last = None
        if last_query:
            minutes_since_last = (datetime.utcnow() - last_query).total_seconds() / 60

        # Determine health status and generate alerts
        status = "healthy"
        alerts = []

        # High average latency alert
        if avg_latency > 500:
            status = "degraded"
            alerts.append({
                "severity": "warning",
                "message": f"High average query latency: {avg_latency:.0f}ms",
                "threshold": "500ms",
                "current": f"{avg_latency:.0f}ms"
            })

        # Very high P95 latency alert
        if p95_latency > 1000:
            status = "degraded"
            alerts.append({
                "severity": "warning",
                "message": f"High P95 query latency: {p95_latency:.0f}ms",
                "threshold": "1000ms",
                "current": f"{p95_latency:.0f}ms"
            })

        # Critical P99 latency alert
        if p99_latency > 2000:
            status = "unhealthy"
            alerts.append({
                "severity": "error",
                "message": f"Critical P99 query latency: {p99_latency:.0f}ms",
                "threshold": "2000ms",
                "current": f"{p99_latency:.0f}ms"
            })

        # High error rate alert
        if error_rate > 0.05:
            status = "unhealthy"
            alerts.append({
                "severity": "error",
                "message": f"High error rate: {error_rate*100:.1f}%",
                "threshold": "5%",
                "current": f"{error_rate*100:.1f}%"
            })

        # Low cache hit rate info
        if total_cache_queries > 10 and cache_hit_rate < 0.5:
            alerts.append({
                "severity": "info",
                "message": f"Low cache hit rate: {cache_hit_rate*100:.1f}%",
                "threshold": "50%",
                "current": f"{cache_hit_rate*100:.1f}%",
                "suggestion": "Consider cache warming or check query patterns"
            })

        # Stale project warning
        if minutes_since_last and minutes_since_last > 60:
            alerts.append({
                "severity": "info",
                "message": f"Project inactive for {minutes_since_last:.0f} minutes",
                "last_activity": last_query.isoformat() if last_query else None
            })

        # No documents warning
        if doc_count == 0:
            alerts.append({
                "severity": "warning",
                "message": "Project has no documents",
                "suggestion": "Ingest documents to enable queries"
            })

        return {
            "project_id": project_id,
            "project_name": project.name,
            "status": status,
            "metrics": {
                "document_count": doc_count,
                "total_queries": total_queries,
                "avg_query_latency_ms": round(avg_latency, 2),
                "p95_query_latency_ms": round(p95_latency, 2),
                "p99_query_latency_ms": round(p99_latency, 2),
                "error_rate": round(error_rate, 4),
                "error_count": error_count,
                "cache_hit_rate": round(cache_hit_rate, 4),
                "cache_hits": self._cache_hits[project_id],
                "cache_misses": self._cache_misses[project_id],
                "last_query_minutes_ago": round(minutes_since_last, 2) if minutes_since_last else None
            },
            "alerts": alerts,
            "timestamp": datetime.utcnow().isoformat()
        }

    def get_all_projects_health(self) -> Dict[str, Any]:
        """Get health status for all projects.

        Returns:
            Dictionary with summary and per-project health statuses
        """
        projects = self.pm.list_projects()

        health_statuses = [
            self.get_project_health(p.project_id)
            for p in projects
        ]

        # Filter out not_found projects
        health_statuses = [h for h in health_statuses if h.get("status") != "not_found"]

        # Aggregate stats
        total_projects = len(health_statuses)
        healthy = sum(1 for h in health_statuses if h['status'] == 'healthy')
        degraded = sum(1 for h in health_statuses if h['status'] == 'degraded')
        unhealthy = sum(1 for h in health_statuses if h['status'] == 'unhealthy')

        # Calculate aggregate metrics
        total_queries = sum(h['metrics']['total_queries'] for h in health_statuses)
        total_errors = sum(h['metrics']['error_count'] for h in health_statuses)
        total_docs = sum(h['metrics']['document_count'] for h in health_statuses)

        # Calculate average latencies across all projects
        all_latencies = []
        for project_id in self._query_latencies:
            all_latencies.extend(self._query_latencies[project_id])

        if all_latencies:
            avg_latency_all = sum(all_latencies) / len(all_latencies)
            p95_latency_all = self._percentile(all_latencies, 95)
            p99_latency_all = self._percentile(all_latencies, 99)
        else:
            avg_latency_all = 0
            p95_latency_all = 0
            p99_latency_all = 0

        return {
            "summary": {
                "total_projects": total_projects,
                "healthy": healthy,
                "degraded": degraded,
                "unhealthy": unhealthy,
                "total_queries": total_queries,
                "total_errors": total_errors,
                "total_documents": total_docs,
                "avg_latency_ms": round(avg_latency_all, 2),
                "p95_latency_ms": round(p95_latency_all, 2),
                "p99_latency_ms": round(p99_latency_all, 2),
            },
            "projects": health_statuses,
            "timestamp": datetime.utcnow().isoformat()
        }

    def reset_metrics(self, project_id: str) -> None:
        """Reset metrics for a project.

        Args:
            project_id: Project identifier
        """
        if project_id in self._query_latencies:
            self._query_latencies[project_id].clear()
        self._error_counts[project_id] = 0
        self._query_counts[project_id] = 0
        if project_id in self._last_queries:
            del self._last_queries[project_id]
        self._cache_hits[project_id] = 0
        self._cache_misses[project_id] = 0

        logger.info(f"Reset metrics for project: {project_id}")

    def reset_all_metrics(self) -> None:
        """Reset metrics for all projects."""
        self._query_latencies.clear()
        self._error_counts.clear()
        self._query_counts.clear()
        self._last_queries.clear()
        self._cache_hits.clear()
        self._cache_misses.clear()

        logger.info("Reset all metrics")

    @staticmethod
    def _percentile(values: List[float], percentile: float) -> float:
        """Calculate percentile of values.

        Args:
            values: List of values
            percentile: Percentile to calculate (0-100)

        Returns:
            Percentile value
        """
        if not values:
            return 0

        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))
        index = min(index, len(sorted_values) - 1)
        return sorted_values[index]
