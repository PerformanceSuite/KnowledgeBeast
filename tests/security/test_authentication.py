"""Comprehensive authentication tests for KnowledgeBeast API.

Tests cover:
- API key validation (valid/invalid keys)
- Missing API key rejection
- Protected endpoint access
- Multiple API keys support
- Rate limiting per key
- Authentication bypass attempts
- Edge cases and security scenarios
"""

import os
from typing import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from knowledgebeast.api.app import app
from knowledgebeast.api.auth import (
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW,
    check_rate_limit,
    get_rate_limit_info,
    get_valid_api_keys,
    reset_rate_limit,
    validate_api_key,
)


# Test fixtures
@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create a test client."""
    yield TestClient(app)


@pytest.fixture(autouse=True)
def reset_env():
    """Reset environment variables and rate limits before each test."""
    # Store original env vars
    original_api_key = os.environ.get("KB_API_KEY")

    yield

    # Reset rate limits
    reset_rate_limit()

    # Restore original env vars
    if original_api_key:
        os.environ["KB_API_KEY"] = original_api_key
    elif "KB_API_KEY" in os.environ:
        del os.environ["KB_API_KEY"]


# ============================================================================
# API Key Validation Tests
# ============================================================================


def test_get_valid_api_keys_single_key():
    """Test loading single API key from environment."""
    with patch.dict(os.environ, {"KB_API_KEY": "test_key_123"}):
        keys = get_valid_api_keys()
        assert len(keys) == 1
        assert "test_key_123" in keys


def test_get_valid_api_keys_multiple_keys():
    """Test loading multiple comma-separated API keys."""
    with patch.dict(os.environ, {"KB_API_KEY": "key1,key2,key3"}):
        keys = get_valid_api_keys()
        assert len(keys) == 3
        assert "key1" in keys
        assert "key2" in keys
        assert "key3" in keys


def test_get_valid_api_keys_with_whitespace():
    """Test API keys are trimmed of whitespace."""
    with patch.dict(os.environ, {"KB_API_KEY": " key1 , key2 , key3 "}):
        keys = get_valid_api_keys()
        assert len(keys) == 3
        assert "key1" in keys
        assert "key2" in keys
        assert "key3" in keys


def test_get_valid_api_keys_empty_string():
    """Test empty API key string returns empty set."""
    with patch.dict(os.environ, {"KB_API_KEY": ""}):
        keys = get_valid_api_keys()
        assert len(keys) == 0


def test_get_valid_api_keys_not_set():
    """Test missing API key env var returns empty set."""
    with patch.dict(os.environ, {}, clear=True):
        if "KB_API_KEY" in os.environ:
            del os.environ["KB_API_KEY"]
        keys = get_valid_api_keys()
        assert len(keys) == 0


def test_validate_api_key_valid():
    """Test validation of valid API key."""
    with patch.dict(os.environ, {"KB_API_KEY": "valid_key"}):
        assert validate_api_key("valid_key") is True


def test_validate_api_key_invalid():
    """Test validation rejects invalid API key."""
    with patch.dict(os.environ, {"KB_API_KEY": "valid_key"}):
        assert validate_api_key("invalid_key") is False


def test_validate_api_key_one_of_many():
    """Test validation with multiple keys accepts any valid key."""
    with patch.dict(os.environ, {"KB_API_KEY": "key1,key2,key3"}):
        assert validate_api_key("key1") is True
        assert validate_api_key("key2") is True
        assert validate_api_key("key3") is True
        assert validate_api_key("invalid") is False


def test_validate_api_key_no_keys_configured():
    """Test validation allows access when no keys configured (dev mode)."""
    with patch.dict(os.environ, {}, clear=True):
        if "KB_API_KEY" in os.environ:
            del os.environ["KB_API_KEY"]
        # In dev mode with no keys, should allow access
        assert validate_api_key("any_key") is True


# ============================================================================
# Rate Limiting Tests
# ============================================================================


def test_rate_limit_within_limit():
    """Test rate limiting allows requests within limit."""
    reset_rate_limit()
    api_key = "test_key"

    # Should allow first request
    assert check_rate_limit(api_key) is True

    # Should allow requests within limit
    for _ in range(RATE_LIMIT_REQUESTS - 2):
        assert check_rate_limit(api_key) is True


def test_rate_limit_exceeds_limit():
    """Test rate limiting blocks requests exceeding limit."""
    reset_rate_limit()
    api_key = "test_key"

    # Make requests up to limit
    for _ in range(RATE_LIMIT_REQUESTS):
        check_rate_limit(api_key)

    # Next request should be blocked
    assert check_rate_limit(api_key) is False


def test_rate_limit_per_key():
    """Test rate limiting is tracked separately per API key."""
    reset_rate_limit()
    key1 = "key1"
    key2 = "key2"

    # Max out key1
    for _ in range(RATE_LIMIT_REQUESTS):
        check_rate_limit(key1)

    # key1 should be blocked
    assert check_rate_limit(key1) is False

    # key2 should still be allowed
    assert check_rate_limit(key2) is True


def test_rate_limit_info():
    """Test getting rate limit information."""
    reset_rate_limit()
    api_key = "test_key"

    # Make some requests
    for _ in range(5):
        check_rate_limit(api_key)

    info = get_rate_limit_info(api_key)
    assert info["requests_made"] == 5
    assert info["requests_remaining"] == RATE_LIMIT_REQUESTS - 5
    assert info["window_seconds"] == RATE_LIMIT_WINDOW
    assert info["limit"] == RATE_LIMIT_REQUESTS


def test_rate_limit_reset_specific_key():
    """Test resetting rate limit for specific key."""
    reset_rate_limit()
    key1 = "key1"
    key2 = "key2"

    # Make requests for both keys
    for _ in range(10):
        check_rate_limit(key1)
        check_rate_limit(key2)

    # Reset only key1
    reset_rate_limit(key1)

    info1 = get_rate_limit_info(key1)
    info2 = get_rate_limit_info(key2)

    assert info1["requests_made"] == 0
    assert info2["requests_made"] == 10


def test_rate_limit_reset_all():
    """Test resetting all rate limits."""
    reset_rate_limit()

    # Make requests for multiple keys
    for key in ["key1", "key2", "key3"]:
        for _ in range(10):
            check_rate_limit(key)

    # Reset all
    reset_rate_limit()

    for key in ["key1", "key2", "key3"]:
        info = get_rate_limit_info(key)
        assert info["requests_made"] == 0


# ============================================================================
# Protected Endpoint Tests
# ============================================================================


def test_health_endpoint_with_valid_key(client):
    """Test health endpoint accepts valid API key."""
    with patch.dict(os.environ, {"KB_API_KEY": "test_key"}):
        response = client.get("/api/v1/health", headers={"X-API-Key": "test_key"})
        assert response.status_code == 200


def test_health_endpoint_without_key(client):
    """Test health endpoint rejects missing API key."""
    with patch.dict(os.environ, {"KB_API_KEY": "test_key"}):
        response = client.get("/api/v1/health")
        assert response.status_code == 403  # FastAPI returns 403 for missing header


def test_health_endpoint_with_invalid_key(client):
    """Test health endpoint rejects invalid API key."""
    with patch.dict(os.environ, {"KB_API_KEY": "valid_key"}):
        response = client.get("/api/v1/health", headers={"X-API-Key": "invalid_key"})
        assert response.status_code == 401


def test_stats_endpoint_protected(client):
    """Test stats endpoint requires authentication."""
    with patch.dict(os.environ, {"KB_API_KEY": "test_key"}):
        # Without key
        response = client.get("/api/v1/stats")
        assert response.status_code == 403

        # With valid key
        response = client.get("/api/v1/stats", headers={"X-API-Key": "test_key"})
        assert response.status_code == 200


def test_query_endpoint_protected(client):
    """Test query endpoint requires authentication."""
    with patch.dict(os.environ, {"KB_API_KEY": "test_key"}):
        query_data = {"query": "test query"}

        # Without key
        response = client.post("/api/v1/query", json=query_data)
        assert response.status_code == 403

        # With valid key
        response = client.post("/api/v1/query", json=query_data, headers={"X-API-Key": "test_key"})
        # Should get 200 or 500 (depending on KB initialization), not 401/403
        assert response.status_code != 403
        assert response.status_code != 401


def test_collections_endpoint_protected(client):
    """Test collections endpoint requires authentication."""
    with patch.dict(os.environ, {"KB_API_KEY": "test_key"}):
        # Without key
        response = client.get("/api/v1/collections")
        assert response.status_code == 403

        # With valid key
        response = client.get("/api/v1/collections", headers={"X-API-Key": "test_key"})
        # Should get 200 or 500 (depending on KB initialization), not 401/403
        assert response.status_code != 403
        assert response.status_code != 401


# ============================================================================
# Multiple Keys Tests
# ============================================================================


def test_multiple_keys_all_valid(client):
    """Test all configured API keys work."""
    with patch.dict(os.environ, {"KB_API_KEY": "key1,key2,key3"}):
        for key in ["key1", "key2", "key3"]:
            response = client.get("/api/v1/health", headers={"X-API-Key": key})
            assert response.status_code == 200


def test_multiple_keys_invalid_rejected(client):
    """Test invalid keys rejected with multiple keys configured."""
    with patch.dict(os.environ, {"KB_API_KEY": "key1,key2,key3"}):
        response = client.get("/api/v1/health", headers={"X-API-Key": "invalid_key"})
        assert response.status_code == 401


# ============================================================================
# Security Bypass Attempts
# ============================================================================


def test_case_sensitive_api_key(client):
    """Test API keys are case-sensitive."""
    with patch.dict(os.environ, {"KB_API_KEY": "TestKey"}):
        # Correct case
        response = client.get("/api/v1/health", headers={"X-API-Key": "TestKey"})
        assert response.status_code == 200

        # Wrong case
        response = client.get("/api/v1/health", headers={"X-API-Key": "testkey"})
        assert response.status_code == 401


def test_empty_api_key_header(client):
    """Test empty API key header is rejected."""
    with patch.dict(os.environ, {"KB_API_KEY": "test_key"}):
        response = client.get("/api/v1/health", headers={"X-API-Key": ""})
        assert response.status_code in [401, 403]


def test_sql_injection_in_api_key(client):
    """Test SQL injection attempts in API key."""
    with patch.dict(os.environ, {"KB_API_KEY": "valid_key"}):
        malicious_keys = [
            "' OR '1'='1",
            "admin'--",
            "'; DROP TABLE users;--",
        ]

        for mal_key in malicious_keys:
            response = client.get("/api/v1/health", headers={"X-API-Key": mal_key})
            assert response.status_code == 401


def test_special_characters_in_api_key(client):
    """Test API keys with special characters work correctly."""
    special_key = "key-with_special.chars!@#$%"
    with patch.dict(os.environ, {"KB_API_KEY": special_key}):
        response = client.get("/api/v1/health", headers={"X-API-Key": special_key})
        assert response.status_code == 200


def test_very_long_api_key(client):
    """Test very long API keys are handled correctly."""
    long_key = "a" * 1000
    with patch.dict(os.environ, {"KB_API_KEY": long_key}):
        response = client.get("/api/v1/health", headers={"X-API-Key": long_key})
        assert response.status_code == 200


# ============================================================================
# Edge Cases
# ============================================================================


def test_whitespace_only_api_key():
    """Test whitespace-only API key is not valid."""
    with patch.dict(os.environ, {"KB_API_KEY": "   "}):
        keys = get_valid_api_keys()
        assert len(keys) == 0


def test_duplicate_keys_in_config():
    """Test duplicate keys are deduplicated."""
    with patch.dict(os.environ, {"KB_API_KEY": "key1,key1,key2,key2"}):
        keys = get_valid_api_keys()
        assert len(keys) == 2
        assert "key1" in keys
        assert "key2" in keys


def test_api_key_with_commas_not_supported():
    """Test API keys containing commas are split."""
    # This is expected behavior - commas are delimiters
    with patch.dict(os.environ, {"KB_API_KEY": "key,with,commas"}):
        keys = get_valid_api_keys()
        # Should be split into 3 separate keys
        assert len(keys) == 3
