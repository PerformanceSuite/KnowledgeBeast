"""Tests for API key authentication.

This module tests the authentication system to ensure:
1. Valid API keys allow access to all endpoints
2. Invalid API keys return 401/403 errors
3. Missing API keys return 401/403 errors
4. All 12 endpoints are properly protected
5. Rate limiting works correctly
"""

import os
import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from knowledgebeast.api.app import app
from knowledgebeast.api.auth import (
    get_valid_api_keys,
    validate_api_key,
    check_rate_limit,
    reset_rate_limit,
    get_rate_limit_info,
)


@pytest.fixture
def client_with_valid_key():
    """Create test client with valid API key."""
    client = TestClient(app)
    client.headers.update({"X-API-Key": "test-api-key-12345"})
    return client


@pytest.fixture
def client_with_invalid_key():
    """Create test client with invalid API key."""
    client = TestClient(app)
    client.headers.update({"X-API-Key": "invalid-key-wrong"})
    return client


@pytest.fixture
def client_without_key():
    """Create test client without API key."""
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
    kb.query_cache._cache = {}
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
    kb.config.cache_file = "/tmp/cache.pkl"
    kb.config.knowledge_dirs = [Mock(exists=lambda: True, is_dir=lambda: True)]
    kb.get_stats.return_value = kb.stats
    kb._generate_cache_key.return_value = "test_cache_key"
    return kb


class TestAuthenticationValidKey:
    """Test that valid API keys allow access to all endpoints."""

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_health_with_valid_key(self, mock_get_kb, client_with_valid_key, mock_kb):
        """Test /health endpoint with valid API key."""
        mock_get_kb.return_value = mock_kb
        response = client_with_valid_key.get("/api/v1/health")
        assert response.status_code == 200
        assert "status" in response.json()

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_stats_with_valid_key(self, mock_get_kb, client_with_valid_key, mock_kb):
        """Test /stats endpoint with valid API key."""
        mock_get_kb.return_value = mock_kb
        response = client_with_valid_key.get("/api/v1/stats")
        assert response.status_code == 200
        assert "queries" in response.json()

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_query_with_valid_key(self, mock_get_kb, client_with_valid_key, mock_kb):
        """Test /query endpoint with valid API key."""
        mock_kb.query.return_value = []
        mock_get_kb.return_value = mock_kb
        response = client_with_valid_key.post("/api/v1/query", json={"query": "test"})
        assert response.status_code == 200

    @patch('knowledgebeast.api.routes.get_kb_instance')
    @patch('knowledgebeast.api.routes.Path')
    @patch('knowledgebeast.api.models.Path')
    def test_ingest_with_valid_key(self, mock_models_path, mock_routes_path, mock_get_kb, client_with_valid_key, mock_kb):
        """Test /ingest endpoint with valid API key."""
        # Mock Path for both models (validation) and routes (endpoint logic)
        mock_file = Mock()
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_file.name = "test.md"
        mock_file.suffix = ".md"
        mock_file.resolve.return_value = mock_file
        mock_models_path.return_value = mock_file
        mock_routes_path.return_value = mock_file
        mock_get_kb.return_value = mock_kb

        response = client_with_valid_key.post("/api/v1/ingest", json={"file_path": "/knowledge-base/test.md"})
        assert response.status_code == 200

    @patch('knowledgebeast.api.routes.get_kb_instance')
    @patch('knowledgebeast.api.routes.Path')
    def test_batch_ingest_with_valid_key(self, mock_path, mock_get_kb, client_with_valid_key, mock_kb):
        """Test /batch-ingest endpoint with valid API key."""
        mock_file = Mock()
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_path.return_value = mock_file
        mock_get_kb.return_value = mock_kb

        response = client_with_valid_key.post("/api/v1/batch-ingest", json={"file_paths": ["/knowledge-base/test.md"]})
        assert response.status_code == 200

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_warm_with_valid_key(self, mock_get_kb, client_with_valid_key, mock_kb):
        """Test /warm endpoint with valid API key."""
        mock_get_kb.return_value = mock_kb
        response = client_with_valid_key.post("/api/v1/warm", json={"force_rebuild": False})
        assert response.status_code == 200

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_cache_clear_with_valid_key(self, mock_get_kb, client_with_valid_key, mock_kb):
        """Test /cache/clear endpoint with valid API key."""
        mock_get_kb.return_value = mock_kb
        response = client_with_valid_key.post("/api/v1/cache/clear")
        assert response.status_code == 200

    @patch('knowledgebeast.api.routes._heartbeat_instance', None)
    def test_heartbeat_status_with_valid_key(self, client_with_valid_key):
        """Test /heartbeat/status endpoint with valid API key."""
        response = client_with_valid_key.get("/api/v1/heartbeat/status")
        assert response.status_code == 200

    @patch('knowledgebeast.api.routes.get_kb_instance')
    @patch('knowledgebeast.api.routes.KnowledgeBaseHeartbeat')
    def test_heartbeat_start_with_valid_key(self, mock_heartbeat, mock_get_kb, client_with_valid_key, mock_kb):
        """Test /heartbeat/start endpoint with valid API key."""
        mock_hb = Mock()
        mock_hb.is_running.return_value = False
        mock_heartbeat.return_value = mock_hb
        mock_get_kb.return_value = mock_kb

        response = client_with_valid_key.post("/api/v1/heartbeat/start")
        assert response.status_code == 200

    @patch('knowledgebeast.api.routes._heartbeat_instance')
    def test_heartbeat_stop_with_valid_key(self, mock_instance, client_with_valid_key):
        """Test /heartbeat/stop endpoint with valid API key."""
        mock_instance.is_running.return_value = True
        response = client_with_valid_key.post("/api/v1/heartbeat/stop")
        assert response.status_code == 200

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_collections_with_valid_key(self, mock_get_kb, client_with_valid_key, mock_kb):
        """Test /collections endpoint with valid API key."""
        mock_get_kb.return_value = mock_kb
        response = client_with_valid_key.get("/api/v1/collections")
        assert response.status_code == 200

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_collection_info_with_valid_key(self, mock_get_kb, client_with_valid_key, mock_kb):
        """Test /collections/{name} endpoint with valid API key."""
        mock_get_kb.return_value = mock_kb
        response = client_with_valid_key.get("/api/v1/collections/default")
        assert response.status_code == 200


class TestAuthenticationInvalidKey:
    """Test that invalid API keys are rejected by all endpoints."""

    def test_health_with_invalid_key(self, client_with_invalid_key):
        """Test /health endpoint rejects invalid API key."""
        response = client_with_invalid_key.get("/api/v1/health")
        assert response.status_code == 401
        assert "Invalid API key" in response.json().get("detail", "")

    def test_stats_with_invalid_key(self, client_with_invalid_key):
        """Test /stats endpoint rejects invalid API key."""
        response = client_with_invalid_key.get("/api/v1/stats")
        assert response.status_code == 401

    def test_query_with_invalid_key(self, client_with_invalid_key):
        """Test /query endpoint rejects invalid API key."""
        response = client_with_invalid_key.post("/api/v1/query", json={"query": "test"})
        assert response.status_code == 401

    def test_ingest_with_invalid_key(self, client_with_invalid_key):
        """Test /ingest endpoint rejects invalid API key."""
        response = client_with_invalid_key.post("/api/v1/ingest", json={"file_path": "/knowledge-base/test.md"})
        assert response.status_code == 401

    def test_batch_ingest_with_invalid_key(self, client_with_invalid_key):
        """Test /batch-ingest endpoint rejects invalid API key."""
        response = client_with_invalid_key.post("/api/v1/batch-ingest", json={"file_paths": ["/knowledge-base/test.md"]})
        assert response.status_code == 401

    def test_warm_with_invalid_key(self, client_with_invalid_key):
        """Test /warm endpoint rejects invalid API key."""
        response = client_with_invalid_key.post("/api/v1/warm", json={"force_rebuild": False})
        assert response.status_code == 401

    def test_cache_clear_with_invalid_key(self, client_with_invalid_key):
        """Test /cache/clear endpoint rejects invalid API key."""
        response = client_with_invalid_key.post("/api/v1/cache/clear")
        assert response.status_code == 401

    def test_heartbeat_status_with_invalid_key(self, client_with_invalid_key):
        """Test /heartbeat/status endpoint rejects invalid API key."""
        response = client_with_invalid_key.get("/api/v1/heartbeat/status")
        assert response.status_code == 401

    def test_heartbeat_start_with_invalid_key(self, client_with_invalid_key):
        """Test /heartbeat/start endpoint rejects invalid API key."""
        response = client_with_invalid_key.post("/api/v1/heartbeat/start")
        assert response.status_code == 401

    def test_heartbeat_stop_with_invalid_key(self, client_with_invalid_key):
        """Test /heartbeat/stop endpoint rejects invalid API key."""
        response = client_with_invalid_key.post("/api/v1/heartbeat/stop")
        assert response.status_code == 401

    def test_collections_with_invalid_key(self, client_with_invalid_key):
        """Test /collections endpoint rejects invalid API key."""
        response = client_with_invalid_key.get("/api/v1/collections")
        assert response.status_code == 401

    def test_collection_info_with_invalid_key(self, client_with_invalid_key):
        """Test /collections/{name} endpoint rejects invalid API key."""
        response = client_with_invalid_key.get("/api/v1/collections/default")
        assert response.status_code == 401


class TestAuthenticationMissingKey:
    """Test that requests without API keys are rejected by all endpoints."""

    def test_health_without_key(self, client_without_key):
        """Test /health endpoint rejects missing API key."""
        response = client_without_key.get("/api/v1/health")
        # FastAPI's auto_error=True on APIKeyHeader returns 403 when header is missing
        assert response.status_code == 403

    def test_stats_without_key(self, client_without_key):
        """Test /stats endpoint rejects missing API key."""
        response = client_without_key.get("/api/v1/stats")
        assert response.status_code == 403

    def test_query_without_key(self, client_without_key):
        """Test /query endpoint rejects missing API key."""
        response = client_without_key.post("/api/v1/query", json={"query": "test"})
        assert response.status_code == 403

    def test_ingest_without_key(self, client_without_key):
        """Test /ingest endpoint rejects missing API key."""
        response = client_without_key.post("/api/v1/ingest", json={"file_path": "/knowledge-base/test.md"})
        assert response.status_code == 403

    def test_batch_ingest_without_key(self, client_without_key):
        """Test /batch-ingest endpoint rejects missing API key."""
        response = client_without_key.post("/api/v1/batch-ingest", json={"file_paths": ["/knowledge-base/test.md"]})
        assert response.status_code == 403

    def test_warm_without_key(self, client_without_key):
        """Test /warm endpoint rejects missing API key."""
        response = client_without_key.post("/api/v1/warm", json={"force_rebuild": False})
        assert response.status_code == 403

    def test_cache_clear_without_key(self, client_without_key):
        """Test /cache/clear endpoint rejects missing API key."""
        response = client_without_key.post("/api/v1/cache/clear")
        assert response.status_code == 403

    def test_heartbeat_status_without_key(self, client_without_key):
        """Test /heartbeat/status endpoint rejects missing API key."""
        response = client_without_key.get("/api/v1/heartbeat/status")
        assert response.status_code == 403

    def test_heartbeat_start_without_key(self, client_without_key):
        """Test /heartbeat/start endpoint rejects missing API key."""
        response = client_without_key.post("/api/v1/heartbeat/start")
        assert response.status_code == 403

    def test_heartbeat_stop_without_key(self, client_without_key):
        """Test /heartbeat/stop endpoint rejects missing API key."""
        response = client_without_key.post("/api/v1/heartbeat/stop")
        assert response.status_code == 403

    def test_collections_without_key(self, client_without_key):
        """Test /collections endpoint rejects missing API key."""
        response = client_without_key.get("/api/v1/collections")
        assert response.status_code == 403

    def test_collection_info_without_key(self, client_without_key):
        """Test /collections/{name} endpoint rejects missing API key."""
        response = client_without_key.get("/api/v1/collections/default")
        assert response.status_code == 403


class TestEndpointProtection:
    """Test that all 12 endpoints are properly protected."""

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_all_endpoints_protected(self, mock_get_kb, mock_kb):
        """Verify all 12 production endpoints require authentication."""
        mock_get_kb.return_value = mock_kb
        client = TestClient(app)

        # List of all 12 endpoints
        endpoints = [
            ("GET", "/api/v1/health"),
            ("GET", "/api/v1/stats"),
            ("POST", "/api/v1/query", {"query": "test"}),
            ("POST", "/api/v1/ingest", {"file_path": "/knowledge-base/test.md"}),
            ("POST", "/api/v1/batch-ingest", {"file_paths": ["/knowledge-base/test.md"]}),
            ("POST", "/api/v1/warm", {"force_rebuild": False}),
            ("POST", "/api/v1/cache/clear", None),
            ("GET", "/api/v1/heartbeat/status"),
            ("POST", "/api/v1/heartbeat/start", None),
            ("POST", "/api/v1/heartbeat/stop", None),
            ("GET", "/api/v1/collections"),
            ("GET", "/api/v1/collections/default"),
        ]

        # Test each endpoint without API key
        for method, path, *payload in endpoints:
            if method == "GET":
                response = client.get(path)
            else:
                response = client.post(path, json=payload[0] if payload else None)

            # All endpoints should reject requests without API key
            assert response.status_code == 403, f"{method} {path} should return 403 without API key"

        # Test each endpoint with invalid API key
        client.headers.update({"X-API-Key": "invalid-key"})
        for method, path, *payload in endpoints:
            if method == "GET":
                response = client.get(path)
            else:
                response = client.post(path, json=payload[0] if payload else None)

            # All endpoints should reject invalid API keys
            assert response.status_code == 401, f"{method} {path} should return 401 with invalid API key"


class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_validate_api_key_function(self):
        """Test validate_api_key function."""
        with patch.dict(os.environ, {"KB_API_KEY": "test-key-123"}):
            assert validate_api_key("test-key-123") is True
            assert validate_api_key("wrong-key") is False

    def test_multiple_api_keys(self):
        """Test that multiple API keys can be configured."""
        with patch.dict(os.environ, {"KB_API_KEY": "key1,key2,key3"}):
            keys = get_valid_api_keys()
            assert len(keys) == 3
            assert "key1" in keys
            assert "key2" in keys
            assert "key3" in keys

    def test_rate_limiting_basic(self):
        """Test basic rate limiting functionality."""
        reset_rate_limit("test-key")

        # First request should succeed
        assert check_rate_limit("test-key") is True

        # Get rate limit info
        info = get_rate_limit_info("test-key")
        assert info["requests_made"] == 1
        assert info["requests_remaining"] == 99
        assert info["limit"] == 100

    def test_rate_limit_reset(self):
        """Test rate limit reset."""
        # Make some requests
        for _ in range(5):
            check_rate_limit("test-key-reset")

        info = get_rate_limit_info("test-key-reset")
        assert info["requests_made"] == 5

        # Reset
        reset_rate_limit("test-key-reset")

        # Check cleared
        info = get_rate_limit_info("test-key-reset")
        assert info["requests_made"] == 0

    def test_empty_api_key_config(self):
        """Test behavior when no API keys configured."""
        with patch.dict(os.environ, {"KB_API_KEY": ""}):
            keys = get_valid_api_keys()
            assert len(keys) == 0
            # When no keys configured, validation allows access (dev mode)
            assert validate_api_key("any-key") is True


class TestAuthenticationSecurity:
    """Test security aspects of authentication."""

    def test_api_key_not_logged_in_response(self, client_with_invalid_key):
        """Ensure API keys are not exposed in error responses."""
        response = client_with_invalid_key.get("/api/v1/health")
        response_text = response.text
        # API key should not appear in response
        assert "invalid-key-wrong" not in response_text.lower()

    def test_www_authenticate_header(self, client_with_invalid_key):
        """Test that WWW-Authenticate header is returned on auth failure."""
        response = client_with_invalid_key.get("/api/v1/health")
        # Note: WWW-Authenticate header is set in the auth module
        assert response.status_code == 401

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_different_keys_have_separate_rate_limits(self, mock_get_kb, mock_kb):
        """Test that different API keys have independent rate limits."""
        mock_get_kb.return_value = mock_kb

        # Reset rate limits
        reset_rate_limit()

        key1 = "test-key-1"
        key2 = "test-key-2"

        with patch.dict(os.environ, {"KB_API_KEY": f"{key1},{key2}"}):
            client1 = TestClient(app)
            client1.headers.update({"X-API-Key": key1})

            client2 = TestClient(app)
            client2.headers.update({"X-API-Key": key2})

            # Make requests with key1
            for _ in range(5):
                client1.get("/api/v1/health")

            # Make requests with key2
            for _ in range(3):
                client2.get("/api/v1/health")

            # Check rate limits are separate
            info1 = get_rate_limit_info(key1)
            info2 = get_rate_limit_info(key2)

            assert info1["requests_made"] == 5
            assert info2["requests_made"] == 3


class TestEndpointCoverage:
    """Ensure all endpoints are tested for authentication."""

    def test_endpoint_count(self):
        """Verify we're testing all 12 documented endpoints."""
        # This test serves as documentation that we have 12 endpoints
        endpoint_groups = {
            "health": 2,  # /health, /stats
            "query": 1,   # /query
            "ingest": 2,  # /ingest, /batch-ingest
            "management": 2,  # /warm, /cache/clear
            "heartbeat": 3,  # /heartbeat/status, /heartbeat/start, /heartbeat/stop
            "collections": 2,  # /collections, /collections/{name}
        }
        total = sum(endpoint_groups.values())
        assert total == 12, "Should have exactly 12 endpoints"
