"""Tests for project health monitoring endpoints."""

import pytest
import tempfile
import shutil
from pathlib import Path

from knowledgebeast.core.project_manager import ProjectManager
from knowledgebeast.monitoring.health import ProjectHealthMonitor


@pytest.fixture
def temp_storage():
    """Create temporary storage for tests."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def pm(temp_storage):
    """Create ProjectManager instance."""
    pm = ProjectManager(
        storage_path=str(temp_storage / "test_projects.db"),
        chroma_path=str(temp_storage / "test_chroma"),
        cache_capacity=100
    )
    yield pm
    pm.close()


@pytest.fixture
def health_monitor(pm):
    """Create ProjectHealthMonitor instance."""
    return ProjectHealthMonitor(pm)


def test_record_query(health_monitor, pm):
    """Test recording query metrics."""
    # Create project
    project = pm.create_project("test_project")

    # Record some queries
    health_monitor.record_query(project.project_id, 50.0, True, False)
    health_monitor.record_query(project.project_id, 75.0, True, True)
    health_monitor.record_query(project.project_id, 100.0, False, False)

    # Check metrics were recorded
    assert project.project_id in health_monitor._query_latencies
    assert len(health_monitor._query_latencies[project.project_id]) == 3
    assert health_monitor._query_counts[project.project_id] == 3
    assert health_monitor._error_counts[project.project_id] == 1
    assert health_monitor._cache_hits[project.project_id] == 1
    assert health_monitor._cache_misses[project.project_id] == 2


def test_get_project_health_healthy(health_monitor, pm):
    """Test getting health status for healthy project."""
    # Create project
    project = pm.create_project("healthy_project")

    # Record good queries
    for _ in range(10):
        health_monitor.record_query(project.project_id, 50.0, True, True)

    # Get health
    health = health_monitor.get_project_health(project.project_id)

    assert health['status'] == 'healthy'
    assert health['project_id'] == project.project_id
    assert health['metrics']['total_queries'] == 10
    assert health['metrics']['error_rate'] == 0
    assert health['metrics']['avg_query_latency_ms'] == 50.0
    # May have "no documents" alert since we didn't ingest any
    assert all(alert['severity'] != 'error' for alert in health['alerts'])


def test_get_project_health_degraded(health_monitor, pm):
    """Test getting health status for degraded project."""
    # Create project
    project = pm.create_project("degraded_project")

    # Record slow queries
    for _ in range(10):
        health_monitor.record_query(project.project_id, 600.0, True, False)

    # Get health
    health = health_monitor.get_project_health(project.project_id)

    assert health['status'] == 'degraded'
    assert health['metrics']['avg_query_latency_ms'] == 600.0
    assert len(health['alerts']) > 0
    assert any('latency' in alert['message'].lower() for alert in health['alerts'])


def test_get_project_health_unhealthy(health_monitor, pm):
    """Test getting health status for unhealthy project."""
    # Create project
    project = pm.create_project("unhealthy_project")

    # Record many failed queries
    for _ in range(10):
        health_monitor.record_query(project.project_id, 100.0, False, False)

    # Get health
    health = health_monitor.get_project_health(project.project_id)

    assert health['status'] == 'unhealthy'
    assert health['metrics']['error_rate'] == 1.0
    assert len(health['alerts']) > 0
    assert any('error rate' in alert['message'].lower() for alert in health['alerts'])


def test_get_project_health_low_cache_hit(health_monitor, pm):
    """Test alert for low cache hit rate."""
    # Create project
    project = pm.create_project("low_cache_project")

    # Record queries with low cache hit rate (need > 10 queries for alert)
    for _ in range(15):
        health_monitor.record_query(project.project_id, 100.0, True, False)
    for _ in range(5):
        health_monitor.record_query(project.project_id, 100.0, True, True)

    # Get health
    health = health_monitor.get_project_health(project.project_id)

    # Cache hit rate is 25%, should trigger info alert
    cache_hit_rate = health['metrics']['cache_hit_rate']
    assert cache_hit_rate < 0.5
    assert any('cache hit rate' in alert['message'].lower() for alert in health['alerts'])


def test_get_project_health_not_found(health_monitor):
    """Test getting health for non-existent project."""
    health = health_monitor.get_project_health("nonexistent")

    assert health['status'] == 'not_found'
    assert 'error' in health


def test_get_all_projects_health(health_monitor, pm):
    """Test getting health for all projects."""
    # Create multiple projects
    project1 = pm.create_project("project1")
    project2 = pm.create_project("project2")
    project3 = pm.create_project("project3")

    # Record different query patterns
    for _ in range(5):
        health_monitor.record_query(project1.project_id, 50.0, True, True)
    for _ in range(5):
        health_monitor.record_query(project2.project_id, 600.0, True, False)
    for _ in range(5):
        health_monitor.record_query(project3.project_id, 100.0, False, False)

    # Get all health
    all_health = health_monitor.get_all_projects_health()

    assert 'summary' in all_health
    assert 'projects' in all_health
    assert all_health['summary']['total_projects'] == 3
    assert all_health['summary']['healthy'] >= 1
    assert all_health['summary']['total_queries'] == 15


def test_latency_percentiles(health_monitor, pm):
    """Test latency percentile calculations."""
    # Create project
    project = pm.create_project("percentile_project")

    # Record queries with different latencies
    latencies = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    for latency in latencies:
        health_monitor.record_query(project.project_id, latency, True, False)

    # Get health
    health = health_monitor.get_project_health(project.project_id)

    assert health['metrics']['avg_query_latency_ms'] == 55.0
    # P95 should be around 95-100 (9.5th item in sorted list)
    assert 90 <= health['metrics']['p95_query_latency_ms'] <= 100
    # P99 should be around 99-100 (9.9th item in sorted list)
    assert 95 <= health['metrics']['p99_query_latency_ms'] <= 100


def test_rolling_window(health_monitor, pm):
    """Test that query latencies use rolling window."""
    # Create project
    project = pm.create_project("rolling_project")

    # Record more than 100 queries (max window size)
    for i in range(150):
        health_monitor.record_query(project.project_id, 100.0, True, False)

    # Should only keep last 100
    assert len(health_monitor._query_latencies[project.project_id]) == 100


def test_reset_metrics(health_monitor, pm):
    """Test resetting metrics for a project."""
    # Create project
    project = pm.create_project("reset_project")

    # Record some queries
    for _ in range(10):
        health_monitor.record_query(project.project_id, 50.0, True, False)

    # Reset metrics
    health_monitor.reset_metrics(project.project_id)

    # Check metrics cleared
    assert len(health_monitor._query_latencies.get(project.project_id, [])) == 0
    assert health_monitor._query_counts[project.project_id] == 0
    assert health_monitor._error_counts[project.project_id] == 0


def test_reset_all_metrics(health_monitor, pm):
    """Test resetting all metrics."""
    # Create projects
    project1 = pm.create_project("project1")
    project2 = pm.create_project("project2")

    # Record queries
    health_monitor.record_query(project1.project_id, 50.0, True, False)
    health_monitor.record_query(project2.project_id, 75.0, True, False)

    # Reset all
    health_monitor.reset_all_metrics()

    # Check all cleared
    assert len(health_monitor._query_latencies) == 0
    assert len(health_monitor._query_counts) == 0


def test_cache_hit_tracking(health_monitor, pm):
    """Test cache hit/miss tracking."""
    # Create project
    project = pm.create_project("cache_project")

    # Record mix of cache hits and misses
    health_monitor.record_query(project.project_id, 10.0, True, True)
    health_monitor.record_query(project.project_id, 50.0, True, False)
    health_monitor.record_query(project.project_id, 10.0, True, True)
    health_monitor.record_query(project.project_id, 10.0, True, True)

    # Get health
    health = health_monitor.get_project_health(project.project_id)

    assert health['metrics']['cache_hits'] == 3
    assert health['metrics']['cache_misses'] == 1
    assert health['metrics']['cache_hit_rate'] == 0.75


def test_inactive_project_alert(health_monitor, pm):
    """Test alert for inactive project."""
    # Create project
    project = pm.create_project("inactive_project")

    # Record a query
    health_monitor.record_query(project.project_id, 50.0, True, False)

    # Manually set last query time to 61 minutes ago
    from datetime import datetime, timedelta
    health_monitor._last_queries[project.project_id] = datetime.utcnow() - timedelta(minutes=61)

    # Get health
    health = health_monitor.get_project_health(project.project_id)

    # Should have inactive alert
    assert any('inactive' in alert['message'].lower() for alert in health['alerts'])


def test_no_documents_alert(health_monitor, pm):
    """Test alert for project with no documents."""
    # Create project (no documents ingested)
    project = pm.create_project("empty_project")

    # Get health
    health = health_monitor.get_project_health(project.project_id)

    # Should have no documents alert
    assert any('no documents' in alert['message'].lower() for alert in health['alerts'])


def test_aggregate_metrics(health_monitor, pm):
    """Test aggregate metrics across projects."""
    # Create projects
    project1 = pm.create_project("project1")
    project2 = pm.create_project("project2")

    # Record queries
    for _ in range(10):
        health_monitor.record_query(project1.project_id, 50.0, True, False)
    for _ in range(5):
        health_monitor.record_query(project2.project_id, 100.0, False, False)

    # Get all health
    all_health = health_monitor.get_all_projects_health()

    summary = all_health['summary']
    assert summary['total_queries'] == 15
    assert summary['total_errors'] == 5
    assert 0 < summary['avg_latency_ms'] < 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
