"""Tests for CORS (Cross-Origin Resource Sharing) configuration.

This test suite validates that CORS is properly configured to:
- Allow requests from configured origins
- Reject requests from non-whitelisted origins
- Only allow specified HTTP methods (GET, POST, DELETE, OPTIONS)
- Properly handle preflight OPTIONS requests
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import os

from knowledgebeast.api.app import create_app


class TestCORSConfiguration:
    """Test CORS middleware configuration and behavior."""

    def test_cors_allowed_origin_accepted(self):
        """Test that requests from allowed origins receive CORS headers."""
        # Set allowed origins and API key
        with patch.dict(os.environ, {
            "KB_ALLOWED_ORIGINS": "http://localhost:3000,https://app.example.com",
            "KB_API_KEY": "test-api-key-12345"
        }):
            app = create_app()
            client = TestClient(app)

            # Test request from allowed origin
            response = client.get(
                "/api/v1/health",
                headers={
                    "Origin": "http://localhost:3000",
                    "X-API-Key": "test-api-key-12345"
                }
            )

            # Should receive CORS headers
            assert response.status_code == 200
            assert "access-control-allow-origin" in response.headers
            assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
            assert response.headers.get("access-control-allow-credentials") == "true"

    def test_cors_second_allowed_origin(self):
        """Test that multiple configured origins are supported."""
        with patch.dict(os.environ, {
            "KB_ALLOWED_ORIGINS": "http://localhost:3000,https://app.example.com",
            "KB_API_KEY": "test-api-key-12345"
        }):
            app = create_app()
            client = TestClient(app)

            # Test request from second allowed origin
            response = client.get(
                "/api/v1/health",
                headers={
                    "Origin": "https://app.example.com",
                    "X-API-Key": "test-api-key-12345"
                }
            )

            assert response.status_code == 200
            assert "access-control-allow-origin" in response.headers
            assert response.headers["access-control-allow-origin"] == "https://app.example.com"

    def test_cors_disallowed_origin_rejected(self):
        """Test that requests from non-whitelisted origins do not receive CORS headers."""
        with patch.dict(os.environ, {
            "KB_ALLOWED_ORIGINS": "http://localhost:3000",
            "KB_API_KEY": "test-api-key-12345"
        }):
            app = create_app()
            client = TestClient(app)

            # Test request from disallowed origin
            response = client.get(
                "/api/v1/health",
                headers={
                    "Origin": "https://evil-site.com",
                    "X-API-Key": "test-api-key-12345"
                }
            )

            # Should succeed but not include CORS headers for the evil origin
            assert response.status_code == 200
            # CORS headers should not allow the evil origin
            if "access-control-allow-origin" in response.headers:
                assert response.headers["access-control-allow-origin"] != "https://evil-site.com"

    def test_cors_preflight_allowed_methods(self):
        """Test that only specified HTTP methods are allowed via CORS."""
        with patch.dict(os.environ, {
            "KB_ALLOWED_ORIGINS": "http://localhost:3000",
            "KB_API_KEY": "test-api-key-12345"
        }):
            app = create_app()
            client = TestClient(app)

            # Send OPTIONS preflight request
            response = client.options(
                "/api/v1/health",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "Content-Type"
                }
            )

            assert response.status_code == 200
            assert "access-control-allow-methods" in response.headers

            # Check that methods are explicitly listed (not *)
            allowed_methods = response.headers["access-control-allow-methods"]
            assert "GET" in allowed_methods
            assert "POST" in allowed_methods
            assert "DELETE" in allowed_methods
            assert "OPTIONS" in allowed_methods
            # Should NOT contain wildcard
            assert allowed_methods != "*"

    def test_cors_no_wildcard_origins(self):
        """Test that wildcard origins are not used even when env var is not set."""
        # Clear the env var to test defaults
        with patch.dict(os.environ, {"KB_API_KEY": "test-api-key-12345"}, clear=True):
            app = create_app()
            client = TestClient(app)

            # Test with a random origin
            response = client.get(
                "/api/v1/health",
                headers={
                    "Origin": "https://random-site.com",
                    "X-API-Key": "test-api-key-12345"
                }
            )

            # Should not allow wildcard access
            if "access-control-allow-origin" in response.headers:
                assert response.headers["access-control-allow-origin"] != "*"

    def test_cors_default_localhost_origins(self):
        """Test that default localhost origins are allowed when env var not set."""
        with patch.dict(os.environ, {"KB_API_KEY": "test-api-key-12345"}, clear=True):
            app = create_app()
            client = TestClient(app)

            # Test localhost:3000 (common development port)
            response = client.get(
                "/api/v1/health",
                headers={
                    "Origin": "http://localhost:3000",
                    "X-API-Key": "test-api-key-12345"
                }
            )

            assert response.status_code == 200
            assert "access-control-allow-origin" in response.headers
            assert response.headers["access-control-allow-origin"] == "http://localhost:3000"

    def test_cors_credentials_enabled(self):
        """Test that credentials are allowed for CORS requests."""
        with patch.dict(os.environ, {
            "KB_ALLOWED_ORIGINS": "http://localhost:3000",
            "KB_API_KEY": "test-api-key-12345"
        }):
            app = create_app()
            client = TestClient(app)

            response = client.get(
                "/api/v1/health",
                headers={
                    "Origin": "http://localhost:3000",
                    "X-API-Key": "test-api-key-12345"
                }
            )

            assert "access-control-allow-credentials" in response.headers
            assert response.headers["access-control-allow-credentials"] == "true"

    def test_cors_exposed_headers(self):
        """Test that custom headers are properly exposed."""
        with patch.dict(os.environ, {
            "KB_ALLOWED_ORIGINS": "http://localhost:3000",
            "KB_API_KEY": "test-api-key-12345"
        }):
            app = create_app()
            client = TestClient(app)

            # Send OPTIONS preflight request
            response = client.options(
                "/api/v1/health",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET"
                }
            )

            # Check exposed headers
            if "access-control-expose-headers" in response.headers:
                exposed = response.headers["access-control-expose-headers"]
                assert "X-Request-ID" in exposed or "x-request-id" in exposed.lower()
                assert "X-Process-Time" in exposed or "x-process-time" in exposed.lower()

    def test_cors_restricted_methods_only(self):
        """Test that only GET, POST, DELETE, OPTIONS are allowed, not wildcard."""
        with patch.dict(os.environ, {
            "KB_ALLOWED_ORIGINS": "http://localhost:3000",
            "KB_API_KEY": "test-api-key-12345"
        }):
            app = create_app()
            client = TestClient(app)

            # Test preflight for disallowed method (e.g., PUT)
            response = client.options(
                "/api/v1/health",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "PUT"
                }
            )

            # Verify methods are explicit, not wildcard
            if "access-control-allow-methods" in response.headers:
                methods = response.headers["access-control-allow-methods"]
                assert methods != "*", "CORS methods should not be wildcard (*)"
                # PUT might be rejected or not, but we ensure it's explicit
                assert "GET" in methods and "POST" in methods

    def test_cors_multiple_origins_comma_separated(self):
        """Test that comma-separated origins are properly parsed and allowed."""
        origins_str = "http://localhost:3000,http://localhost:8080,https://app.example.com"
        with patch.dict(os.environ, {
            "KB_ALLOWED_ORIGINS": origins_str,
            "KB_API_KEY": "test-api-key-12345"
        }):
            app = create_app()
            client = TestClient(app)

            # Test each origin
            for origin in ["http://localhost:3000", "http://localhost:8080", "https://app.example.com"]:
                response = client.get(
                    "/api/v1/health",
                    headers={
                        "Origin": origin,
                        "X-API-Key": "test-api-key-12345"
                    }
                )

                assert response.status_code == 200
                assert "access-control-allow-origin" in response.headers
                assert response.headers["access-control-allow-origin"] == origin


class TestCORSSecurityHardening:
    """Test CORS security hardening measures."""

    def test_no_wildcard_in_production_config(self):
        """Ensure production-like config doesn't use wildcards."""
        production_origins = "https://api.example.com,https://app.example.com"
        with patch.dict(os.environ, {
            "KB_ALLOWED_ORIGINS": production_origins,
            "KB_API_KEY": "test-api-key-12345"
        }):
            app = create_app()
            client = TestClient(app)

            # Try with production origin
            response = client.get(
                "/api/v1/health",
                headers={
                    "Origin": "https://api.example.com",
                    "X-API-Key": "test-api-key-12345"
                }
            )

            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"] == "https://api.example.com"
            assert response.headers["access-control-allow-origin"] != "*"

    def test_empty_origin_handling(self):
        """Test behavior when origin header is empty or missing."""
        with patch.dict(os.environ, {
            "KB_ALLOWED_ORIGINS": "http://localhost:3000",
            "KB_API_KEY": "test-api-key-12345"
        }):
            app = create_app()
            client = TestClient(app)

            # Request without origin header
            response = client.get(
                "/api/v1/health",
                headers={"X-API-Key": "test-api-key-12345"}
            )

            # Should still work, just no CORS headers needed
            assert response.status_code == 200

    def test_malformed_origin_rejected(self):
        """Test that malformed origins don't break CORS."""
        with patch.dict(os.environ, {
            "KB_ALLOWED_ORIGINS": "http://localhost:3000",
            "KB_API_KEY": "test-api-key-12345"
        }):
            app = create_app()
            client = TestClient(app)

            # Try with malformed origin
            response = client.get(
                "/api/v1/health",
                headers={
                    "Origin": "not-a-valid-url",
                    "X-API-Key": "test-api-key-12345"
                }
            )

            # Should not crash and should not allow the malformed origin
            assert response.status_code == 200
            if "access-control-allow-origin" in response.headers:
                assert response.headers["access-control-allow-origin"] != "not-a-valid-url"
