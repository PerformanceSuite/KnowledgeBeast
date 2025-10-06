"""Tests for API routes."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

from knowledgebeast.api.app import app
from knowledgebeast import __version__


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_kb():
    """Create mock KnowledgeBase instance."""
    kb = Mock()
    kb.documents = {"doc1": {"content": "test", "name": "Test Doc", "path": "/test", "kb_dir": "/kb"}}
    kb.index = {"test": ["doc1"]}
    kb.query_cache = Mock()
    kb.query_cache.__len__ = Mock(return_value=5)
    kb.query_cache.__contains__ = Mock(return_value=False)
    kb.stats = {
        'queries': 100,
        'cache_hits': 60,
        'cache_misses': 40,
        'cache_hit_rate': '60.0%',
        'warm_queries': 7,
        'last_warm_time': 2.5,
        'total_documents': 42,
        'total_terms': 1523,
        'documents': 42,
        'terms': 1523,
        'cached_queries': 25,
        'last_access_age': '5.2s ago',
        'knowledge_dirs': ['/knowledge-base'],
        'total_queries': 100
    }
    kb.config = Mock()
    kb.config.heartbeat_interval = 300
    return kb


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_endpoint(self, client):
        """Test health endpoint returns 200."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "version" in data
        assert data["version"] == __version__

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_health_when_kb_initialized(self, mock_get_kb, client, mock_kb):
        """Test health status when KB initialized."""
        mock_get_kb.return_value = mock_kb

        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["kb_initialized"] is True

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_health_when_kb_not_initialized(self, mock_get_kb, client):
        """Test health status when KB fails to initialize."""
        mock_get_kb.side_effect = Exception("Init failed")

        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "degraded"
        assert data["kb_initialized"] is False


class TestStatsEndpoint:
    """Test statistics endpoint."""

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_stats_endpoint(self, mock_get_kb, client, mock_kb):
        """Test stats endpoint returns statistics."""
        mock_kb.get_stats.return_value = mock_kb.stats
        mock_get_kb.return_value = mock_kb

        response = client.get("/stats")
        assert response.status_code == 200

        data = response.json()
        assert "queries" in data
        assert "cache_hits" in data
        assert "cache_misses" in data
        assert "cache_hit_rate" in data
        assert data["queries"] == 100
        assert data["cache_hits"] == 60


class TestQueryEndpoint:
    """Test query endpoint."""

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_query_endpoint(self, mock_get_kb, client, mock_kb):
        """Test query endpoint returns results."""
        mock_kb.query.return_value = [
            ("doc1", {
                "content": "Test content",
                "name": "Test Doc",
                "path": "/path/to/doc",
                "kb_dir": "/kb"
            })
        ]
        mock_kb._generate_cache_key.return_value = "test_key"
        mock_get_kb.return_value = mock_kb

        response = client.post("/query", json={"query": "test query"})
        assert response.status_code == 200

        data = response.json()
        assert "results" in data
        assert "count" in data
        assert "cached" in data
        assert "query" in data
        assert data["count"] == 1
        assert data["query"] == "test query"

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_query_empty_string_error(self, mock_get_kb, client, mock_kb):
        """Test query with empty string returns 400."""
        mock_kb.query.side_effect = ValueError("Search terms cannot be empty")
        mock_get_kb.return_value = mock_kb

        response = client.post("/query", json={"query": ""})
        assert response.status_code == 400

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_query_with_cache_disabled(self, mock_get_kb, client, mock_kb):
        """Test query with caching disabled."""
        mock_kb.query.return_value = []
        mock_kb._generate_cache_key.return_value = "test_key"
        mock_get_kb.return_value = mock_kb

        response = client.post("/query", json={
            "query": "test",
            "use_cache": False
        })
        assert response.status_code == 200

        # Verify use_cache=False was passed to kb.query
        mock_kb.query.assert_called_with("test", use_cache=False)


class TestIngestEndpoint:
    """Test ingest endpoints."""

    @patch('knowledgebeast.api.routes.get_kb_instance')
    @patch('knowledgebeast.api.routes.Path')
    def test_ingest_endpoint_success(self, mock_path, mock_get_kb, client, mock_kb):
        """Test successful document ingestion."""
        # Mock Path operations
        mock_file = Mock()
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_file.name = "test.md"
        mock_path.return_value = mock_file

        mock_get_kb.return_value = mock_kb

        response = client.post("/ingest", json={
            "file_path": "/path/to/test.md"
        })
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "doc_id" in data

    @patch('knowledgebeast.api.routes.get_kb_instance')
    @patch('knowledgebeast.api.routes.Path')
    def test_ingest_file_not_found(self, mock_path, mock_get_kb, client, mock_kb):
        """Test ingestion with nonexistent file."""
        mock_file = Mock()
        mock_file.exists.return_value = False
        mock_path.return_value = mock_file

        mock_get_kb.return_value = mock_kb

        response = client.post("/ingest", json={
            "file_path": "/nonexistent/file.md"
        })
        assert response.status_code == 404

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_batch_ingest_endpoint(self, mock_get_kb, client, mock_kb):
        """Test batch ingestion endpoint."""
        mock_get_kb.return_value = mock_kb

        with patch('knowledgebeast.api.routes.Path') as mock_path:
            # Mock all files as existing
            mock_file = Mock()
            mock_file.exists.return_value = True
            mock_file.is_file.return_value = True
            mock_path.return_value = mock_file

            response = client.post("/batch-ingest", json={
                "file_paths": ["/file1.md", "/file2.md"]
            })
            assert response.status_code == 200

            data = response.json()
            assert data["success"] is True
            assert data["total_files"] == 2


class TestWarmEndpoint:
    """Test warming endpoint."""

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_warm_endpoint(self, mock_get_kb, client, mock_kb):
        """Test warm endpoint triggers warming."""
        mock_kb.warm_up.return_value = None
        mock_get_kb.return_value = mock_kb

        response = client.post("/warm", json={"force_rebuild": False})
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "warm_time" in data
        assert "queries_executed" in data

        # Verify warm_up was called
        mock_kb.warm_up.assert_called_once()

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_warm_with_rebuild(self, mock_get_kb, client, mock_kb):
        """Test warm endpoint with force rebuild."""
        mock_get_kb.return_value = mock_kb

        response = client.post("/warm", json={"force_rebuild": True})
        assert response.status_code == 200

        # Verify rebuild was called
        mock_kb.rebuild_index.assert_called_once()


class TestCacheEndpoint:
    """Test cache management endpoint."""

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_clear_cache_endpoint(self, mock_get_kb, client, mock_kb):
        """Test clear cache endpoint."""
        mock_kb.clear_cache.return_value = None
        mock_get_kb.return_value = mock_kb

        response = client.post("/cache/clear")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "cleared_count" in data

        # Verify clear_cache was called
        mock_kb.clear_cache.assert_called_once()


class TestHeartbeatEndpoints:
    """Test heartbeat management endpoints."""

    @patch('knowledgebeast.api.routes._heartbeat_instance', None)
    def test_heartbeat_status_not_running(self, client):
        """Test heartbeat status when not running."""
        response = client.get("/heartbeat/status")
        assert response.status_code == 200

        data = response.json()
        assert data["running"] is False

    @patch('knowledgebeast.api.routes.get_kb_instance')
    @patch('knowledgebeast.api.routes.KnowledgeBaseHeartbeat')
    def test_start_heartbeat(self, mock_heartbeat_class, mock_get_kb, client, mock_kb):
        """Test starting heartbeat."""
        mock_heartbeat = Mock()
        mock_heartbeat.is_running.return_value = False
        mock_heartbeat_class.return_value = mock_heartbeat
        mock_get_kb.return_value = mock_kb

        response = client.post("/heartbeat/start")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["running"] is True

    @patch('knowledgebeast.api.routes._heartbeat_instance')
    def test_stop_heartbeat(self, mock_instance, client):
        """Test stopping heartbeat."""
        mock_instance.is_running.return_value = True

        response = client.post("/heartbeat/stop")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True


class TestCollectionsEndpoints:
    """Test collections endpoints."""

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_list_collections(self, mock_get_kb, client, mock_kb):
        """Test listing collections."""
        mock_get_kb.return_value = mock_kb

        response = client.get("/collections")
        assert response.status_code == 200

        data = response.json()
        assert "collections" in data
        assert "count" in data
        assert data["count"] > 0

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_get_collection_info(self, mock_get_kb, client, mock_kb):
        """Test getting collection info."""
        mock_get_kb.return_value = mock_kb

        response = client.get("/collections/default")
        assert response.status_code == 200

        data = response.json()
        assert "name" in data
        assert "document_count" in data

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_get_nonexistent_collection(self, mock_get_kb, client, mock_kb):
        """Test getting nonexistent collection returns 404."""
        mock_get_kb.return_value = mock_kb

        response = client.get("/collections/nonexistent")
        assert response.status_code == 404


class TestErrorHandling:
    """Test error handling in API routes."""

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_query_error_500(self, mock_get_kb, client):
        """Test query returns 500 on internal error."""
        mock_kb = Mock()
        mock_kb.query.side_effect = Exception("Internal error")
        mock_kb._generate_cache_key.return_value = "key"
        mock_get_kb.return_value = mock_kb

        response = client.post("/query", json={"query": "test"})
        assert response.status_code == 500

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_stats_error_500(self, mock_get_kb, client):
        """Test stats returns 500 on error."""
        mock_kb = Mock()
        mock_kb.get_stats.side_effect = Exception("Stats error")
        mock_get_kb.return_value = mock_kb

        response = client.get("/stats")
        assert response.status_code == 500


class TestValidation:
    """Test request validation."""

    def test_query_validation_empty_query(self, client):
        """Test query validation rejects empty query."""
        # Pydantic validation should catch this
        response = client.post("/query", json={"query": ""})
        # May be 422 (validation error) or 400 depending on where it's caught
        assert response.status_code in [400, 422]

    def test_batch_ingest_validation(self, client):
        """Test batch ingest validation."""
        # Empty file_paths list should fail
        response = client.post("/batch-ingest", json={"file_paths": []})
        assert response.status_code == 422  # Pydantic validation error
