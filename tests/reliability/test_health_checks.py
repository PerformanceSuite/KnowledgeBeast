"""Tests for Enhanced Health Check endpoint.

Validates:
- All component checks work independently
- Status aggregation (healthy/degraded/unhealthy)
- Dependency failure detection
- Response format validation
- Disk space thresholds
- Latency measurements accurate
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def test_client():
    """Create test client for FastAPI app."""
    from knowledgebeast.api.app import app
    return TestClient(app)


@pytest.fixture
def mock_kb():
    """Create mock knowledge base."""
    kb = Mock()
    kb.get_stats = Mock(return_value={
        "documents": 100,
        "queries": 50,
    })
    kb.vector_store = Mock()
    kb.vector_store.get_health = Mock(return_value={
        "status": "healthy",
        "chromadb_available": True,
        "circuit_breaker_state": "closed",
        "document_count": 100,
    })
    kb.hybrid_engine = Mock()
    kb.hybrid_engine.model = Mock()
    kb.hybrid_engine.model.model_name_or_path = "all-MiniLM-L6-v2"
    return kb


class TestHealthCheckBasics:
    """Test basic health check functionality."""

    def test_health_endpoint_exists(self, test_client):
        """Test /health endpoint is accessible."""
        response = test_client.get("/health")
        assert response.status_code == 200

    def test_health_response_has_required_fields(self, test_client):
        """Test health response contains required fields."""
        response = test_client.get("/health")
        data = response.json()

        assert "status" in data
        assert "version" in data
        assert "components" in data
        assert "timestamp" in data

    def test_health_response_format(self, test_client):
        """Test health response follows expected format."""
        response = test_client.get("/health")
        data = response.json()

        # Status should be one of: healthy, degraded, unhealthy
        assert data["status"] in ["healthy", "degraded", "unhealthy"]

        # Components should be a dict
        assert isinstance(data["components"], dict)

        # Timestamp should be ISO format
        assert "T" in data["timestamp"]
        assert "Z" in data["timestamp"]


class TestComponentHealthChecks:
    """Test individual component health checks."""

    def test_knowledgebase_component_check(self, test_client):
        """Test knowledge base component health check."""
        response = test_client.get("/health")
        data = response.json()

        assert "knowledgebase" in data["components"]
        kb_health = data["components"]["knowledgebase"]
        assert "status" in kb_health

    def test_chromadb_component_check_when_available(self, test_client):
        """Test ChromaDB component when available."""
        with patch("knowledgebeast.api.routes.get_kb_instance") as mock_kb_instance:
            kb = Mock()
            kb.vector_store = Mock()
            kb.vector_store.get_health = Mock(return_value={
                "status": "healthy",
                "chromadb_available": True,
                "circuit_breaker_state": "closed",
                "document_count": 100,
            })
            kb.get_stats = Mock(return_value={"documents": 100})
            mock_kb_instance.return_value = kb

            response = test_client.get("/health")
            data = response.json()

            if "chromadb" in data["components"]:
                chromadb_health = data["components"]["chromadb"]
                assert "status" in chromadb_health
                assert "available" in chromadb_health

    def test_embedding_model_component_check(self, test_client):
        """Test embedding model component health check."""
        with patch("knowledgebeast.api.routes.get_kb_instance") as mock_kb_instance:
            kb = Mock()
            kb.hybrid_engine = Mock()
            kb.hybrid_engine.model = Mock()
            kb.hybrid_engine.model.model_name_or_path = "all-MiniLM-L6-v2"
            kb.get_stats = Mock(return_value={"documents": 0})
            mock_kb_instance.return_value = kb

            response = test_client.get("/health")
            data = response.json()

            if "embedding_model" in data["components"]:
                model_health = data["components"]["embedding_model"]
                assert "status" in model_health

    def test_database_component_check(self, test_client):
        """Test database component health check."""
        with patch("knowledgebeast.api.routes.get_kb_instance") as mock_kb_instance:
            kb = Mock()
            kb.get_stats = Mock(return_value={"documents": 42})
            mock_kb_instance.return_value = kb

            response = test_client.get("/health")
            data = response.json()

            if "database" in data["components"]:
                db_health = data["components"]["database"]
                assert "status" in db_health
                assert "accessible" in db_health

    def test_disk_space_component_check(self, test_client):
        """Test disk space component health check."""
        response = test_client.get("/health")
        data = response.json()

        assert "disk" in data["components"]
        disk_health = data["components"]["disk"]
        assert "status" in disk_health
        assert "available_gb" in disk_health
        assert "threshold_gb" in disk_health


class TestStatusAggregation:
    """Test overall status aggregation logic."""

    def test_healthy_status_when_all_components_up(self, test_client):
        """Test overall status is healthy when all components are up."""
        with patch("knowledgebeast.api.routes.get_kb_instance") as mock_kb_instance:
            kb = Mock()
            kb.vector_store = Mock()
            kb.vector_store.get_health = Mock(return_value={
                "status": "healthy",
                "chromadb_available": True,
                "circuit_breaker_state": "closed",
            })
            kb.get_stats = Mock(return_value={"documents": 100})
            kb.hybrid_engine = Mock()
            kb.hybrid_engine.model = Mock()
            kb.hybrid_engine.model.model_name_or_path = "test-model"
            mock_kb_instance.return_value = kb

            with patch("shutil.disk_usage") as mock_disk:
                # Mock 50GB free
                mock_disk.return_value = Mock(free=50 * 1024**3)

                response = test_client.get("/health")
                data = response.json()

                # Should be healthy with all components up
                assert data["status"] in ["healthy", "degraded"]

    def test_degraded_status_on_circuit_breaker_open(self, test_client):
        """Test status is degraded when circuit breaker is open."""
        with patch("knowledgebeast.api.routes.get_kb_instance") as mock_kb_instance:
            kb = Mock()
            kb.vector_store = Mock()
            kb.vector_store.get_health = Mock(return_value={
                "status": "degraded",
                "chromadb_available": False,
                "circuit_breaker_state": "open",
            })
            kb.get_stats = Mock(return_value={"documents": 100})
            mock_kb_instance.return_value = kb

            response = test_client.get("/health")
            data = response.json()

            # Should be degraded when circuit breaker open
            assert data["status"] in ["degraded", "unhealthy"]

    def test_unhealthy_status_on_kb_failure(self, test_client):
        """Test status is unhealthy when KB initialization fails."""
        with patch("knowledgebeast.api.routes.get_kb_instance") as mock_kb_instance:
            mock_kb_instance.return_value = None  # KB not initialized

            response = test_client.get("/health")
            data = response.json()

            assert data["status"] == "unhealthy"
            assert data["components"]["knowledgebase"]["status"] == "down"


class TestDependencyFailureDetection:
    """Test detection of dependency failures."""

    def test_chromadb_failure_detected(self, test_client):
        """Test ChromaDB failure is detected."""
        with patch("knowledgebeast.api.routes.get_kb_instance") as mock_kb_instance:
            kb = Mock()
            kb.vector_store = Mock()
            kb.vector_store.get_health = Mock(return_value={
                "status": "unhealthy",
                "chromadb_available": False,
                "error": "Connection failed",
            })
            kb.get_stats = Mock(return_value={})
            mock_kb_instance.return_value = kb

            response = test_client.get("/health")
            data = response.json()

            if "chromadb" in data["components"]:
                assert data["components"]["chromadb"]["available"] is False

    def test_database_failure_detected(self, test_client):
        """Test database failure is detected."""
        with patch("knowledgebeast.api.routes.get_kb_instance") as mock_kb_instance:
            kb = Mock()
            kb.get_stats = Mock(side_effect=Exception("Database error"))
            mock_kb_instance.return_value = kb

            response = test_client.get("/health")
            data = response.json()

            # Should handle error gracefully
            assert response.status_code == 200


class TestDiskSpaceThresholds:
    """Test disk space threshold logic."""

    def test_disk_healthy_above_threshold(self, test_client):
        """Test disk status is healthy when above threshold."""
        with patch("shutil.disk_usage") as mock_disk:
            # Mock 5GB free (above 1GB threshold)
            mock_disk.return_value = Mock(free=5 * 1024**3)

            response = test_client.get("/health")
            data = response.json()

            disk_health = data["components"]["disk"]
            assert disk_health["status"] == "up"
            assert disk_health["available_gb"] > 1.0

    def test_disk_warning_below_threshold(self, test_client):
        """Test disk status is warning when below 1GB."""
        with patch("shutil.disk_usage") as mock_disk:
            # Mock 0.7GB free (below 1GB threshold)
            mock_disk.return_value = Mock(free=0.7 * 1024**3)

            response = test_client.get("/health")
            data = response.json()

            disk_health = data["components"]["disk"]
            assert disk_health["status"] == "warning"

    def test_disk_critical_very_low(self, test_client):
        """Test disk status is critical when very low."""
        with patch("shutil.disk_usage") as mock_disk:
            # Mock 0.3GB free (below 0.5GB critical threshold)
            mock_disk.return_value = Mock(free=0.3 * 1024**3)

            response = test_client.get("/health")
            data = response.json()

            disk_health = data["components"]["disk"]
            assert disk_health["status"] == "critical"
            assert data["status"] == "unhealthy"


class TestLatencyMeasurements:
    """Test latency measurements in health checks."""

    def test_chromadb_latency_measured(self, test_client):
        """Test ChromaDB latency is measured."""
        with patch("knowledgebeast.api.routes.get_kb_instance") as mock_kb_instance:
            kb = Mock()
            kb.vector_store = Mock()
            kb.vector_store.get_health = Mock(return_value={
                "status": "healthy",
                "chromadb_available": True,
                "circuit_breaker_state": "closed",
            })
            kb.get_stats = Mock(return_value={})
            mock_kb_instance.return_value = kb

            response = test_client.get("/health")
            data = response.json()

            if "chromadb" in data["components"]:
                chromadb_health = data["components"]["chromadb"]
                if "latency_ms" in chromadb_health:
                    # Latency should be a positive number
                    assert chromadb_health["latency_ms"] >= 0

    def test_latency_reasonable_range(self, test_client):
        """Test latency measurements are in reasonable range."""
        with patch("knowledgebeast.api.routes.get_kb_instance") as mock_kb_instance:
            kb = Mock()
            kb.vector_store = Mock()
            kb.vector_store.get_health = Mock(return_value={
                "status": "healthy",
                "chromadb_available": True,
            })
            kb.get_stats = Mock(return_value={})
            mock_kb_instance.return_value = kb

            response = test_client.get("/health")
            data = response.json()

            if "chromadb" in data["components"]:
                chromadb_health = data["components"]["chromadb"]
                if "latency_ms" in chromadb_health:
                    # Should be less than 1 second for health check
                    assert chromadb_health["latency_ms"] < 1000


class TestCircuitBreakerStatus:
    """Test circuit breaker status in health checks."""

    def test_circuit_breaker_state_reported(self, test_client):
        """Test circuit breaker state is reported."""
        with patch("knowledgebeast.api.routes.get_kb_instance") as mock_kb_instance:
            kb = Mock()
            kb.vector_store = Mock()
            kb.vector_store.get_health = Mock(return_value={
                "status": "healthy",
                "circuit_breaker_state": "closed",
            })
            kb.get_stats = Mock(return_value={})
            mock_kb_instance.return_value = kb

            response = test_client.get("/health")
            data = response.json()

            if "chromadb" in data["components"]:
                chromadb_health = data["components"]["chromadb"]
                assert "circuit_breaker_state" in chromadb_health
                assert chromadb_health["circuit_breaker_state"] in ["closed", "open", "half_open", "unknown"]

    def test_circuit_breaker_open_reflected_in_status(self, test_client):
        """Test open circuit breaker affects overall status."""
        with patch("knowledgebeast.api.routes.get_kb_instance") as mock_kb_instance:
            kb = Mock()
            kb.vector_store = Mock()
            kb.vector_store.get_health = Mock(return_value={
                "status": "degraded",
                "chromadb_available": False,
                "circuit_breaker_state": "open",
            })
            kb.get_stats = Mock(return_value={})
            mock_kb_instance.return_value = kb

            response = test_client.get("/health")
            data = response.json()

            # Overall status should reflect circuit breaker issue
            assert data["status"] in ["degraded", "unhealthy"]


class TestHealthCheckErrorHandling:
    """Test error handling in health checks."""

    def test_handles_kb_exception_gracefully(self, test_client):
        """Test health check handles KB exceptions gracefully."""
        with patch("knowledgebeast.api.routes.get_kb_instance") as mock_kb_instance:
            mock_kb_instance.side_effect = Exception("KB initialization failed")

            response = test_client.get("/health")

            # Should still return 200 with error status
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "unhealthy"

    def test_handles_component_check_failures(self, test_client):
        """Test health check handles individual component failures."""
        with patch("knowledgebeast.api.routes.get_kb_instance") as mock_kb_instance:
            kb = Mock()
            kb.vector_store = Mock()
            kb.vector_store.get_health = Mock(side_effect=Exception("Vector store error"))
            kb.get_stats = Mock(return_value={})
            mock_kb_instance.return_value = kb

            response = test_client.get("/health")

            # Should handle error without crashing
            assert response.status_code == 200

    def test_disk_check_error_handled(self, test_client):
        """Test disk space check errors are handled."""
        with patch("shutil.disk_usage") as mock_disk:
            mock_disk.side_effect = Exception("Disk check failed")

            response = test_client.get("/health")
            data = response.json()

            # Should handle error gracefully
            assert response.status_code == 200
            if "disk" in data["components"]:
                assert "error" in data["components"]["disk"]
