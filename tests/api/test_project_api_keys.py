"""Tests for project-scoped API key management.

This module tests the API key creation, validation, scoping, expiration,
and revocation functionality for project-level access control.
"""

import pytest
import time
from datetime import datetime, timedelta

from knowledgebeast.core.project_auth import ProjectAuthManager


@pytest.fixture
def auth_manager(tmp_path):
    """Create a temporary auth manager for testing."""
    db_path = tmp_path / "test_auth.db"
    return ProjectAuthManager(db_path=str(db_path))


@pytest.fixture
def sample_project_id():
    """Sample project ID for testing."""
    return "proj_test_123"


def test_create_api_key(auth_manager, sample_project_id):
    """Test creating a basic API key with default settings."""
    key_info = auth_manager.create_api_key(
        project_id=sample_project_id,
        name="Test Key"
    )

    assert key_info["project_id"] == sample_project_id
    assert key_info["name"] == "Test Key"
    assert key_info["api_key"].startswith("kb_")
    assert len(key_info["api_key"]) == 46  # kb_ + 43 chars
    assert "key_id" in key_info
    assert key_info["scopes"] == ["read", "write"]  # Default scopes
    assert key_info["expires_at"] is None  # No expiration by default


def test_create_api_key_with_scopes(auth_manager, sample_project_id):
    """Test creating an API key with custom scopes."""
    # Read-only key
    read_key = auth_manager.create_api_key(
        project_id=sample_project_id,
        name="Read Only Key",
        scopes=["read"]
    )

    assert read_key["scopes"] == ["read"]

    # Admin key
    admin_key = auth_manager.create_api_key(
        project_id=sample_project_id,
        name="Admin Key",
        scopes=["read", "write", "admin"]
    )

    assert set(admin_key["scopes"]) == {"read", "write", "admin"}

    # Invalid scope should raise error
    with pytest.raises(ValueError, match="Invalid scopes"):
        auth_manager.create_api_key(
            project_id=sample_project_id,
            name="Invalid Key",
            scopes=["invalid_scope"]
        )


def test_list_api_keys(auth_manager, sample_project_id):
    """Test listing all API keys for a project."""
    # Initially empty
    keys = auth_manager.list_project_keys(sample_project_id)
    assert len(keys) == 0

    # Create multiple keys
    auth_manager.create_api_key(sample_project_id, "Key 1", scopes=["read"])
    auth_manager.create_api_key(sample_project_id, "Key 2", scopes=["write"])
    auth_manager.create_api_key(sample_project_id, "Key 3", scopes=["admin"])

    # List should show all keys
    keys = auth_manager.list_project_keys(sample_project_id)
    assert len(keys) == 3

    # Verify keys are for the correct project
    for key in keys:
        assert "key_id" in key
        assert "name" in key
        assert "scopes" in key
        assert "created_at" in key
        assert "api_key" not in key  # Raw key never returned in list


def test_revoke_api_key(auth_manager, sample_project_id):
    """Test revoking an API key."""
    # Create a key
    key_info = auth_manager.create_api_key(sample_project_id, "Test Key")
    key_id = key_info["key_id"]
    api_key = key_info["api_key"]

    # Verify it works before revocation
    assert auth_manager.validate_project_access(api_key, sample_project_id, "read") is True

    # Revoke the key
    success = auth_manager.revoke_api_key(key_id)
    assert success is True

    # Verify it no longer works
    assert auth_manager.validate_project_access(api_key, sample_project_id, "read") is False

    # Revoke again should return False (key not found)
    success = auth_manager.revoke_api_key("nonexistent_key_id")
    assert success is False


def test_api_key_scope_enforcement(auth_manager, sample_project_id):
    """Test that read-only keys cannot perform write operations."""
    # Create read-only key
    read_key = auth_manager.create_api_key(
        sample_project_id,
        "Read Only",
        scopes=["read"]
    )

    # Create write key
    write_key = auth_manager.create_api_key(
        sample_project_id,
        "Write Key",
        scopes=["write"]
    )

    # Create admin key
    admin_key = auth_manager.create_api_key(
        sample_project_id,
        "Admin Key",
        scopes=["admin"]
    )

    # Read-only key can read
    assert auth_manager.validate_project_access(
        read_key["api_key"], sample_project_id, "read"
    ) is True

    # Read-only key CANNOT write
    assert auth_manager.validate_project_access(
        read_key["api_key"], sample_project_id, "write"
    ) is False

    # Read-only key CANNOT admin
    assert auth_manager.validate_project_access(
        read_key["api_key"], sample_project_id, "admin"
    ) is False

    # Write key can read and write
    assert auth_manager.validate_project_access(
        write_key["api_key"], sample_project_id, "read"
    ) is True
    assert auth_manager.validate_project_access(
        write_key["api_key"], sample_project_id, "write"
    ) is True

    # Write key CANNOT admin
    assert auth_manager.validate_project_access(
        write_key["api_key"], sample_project_id, "admin"
    ) is False

    # Admin key can do everything
    assert auth_manager.validate_project_access(
        admin_key["api_key"], sample_project_id, "read"
    ) is True
    assert auth_manager.validate_project_access(
        admin_key["api_key"], sample_project_id, "write"
    ) is True
    assert auth_manager.validate_project_access(
        admin_key["api_key"], sample_project_id, "admin"
    ) is True


def test_api_key_expiration(auth_manager, sample_project_id):
    """Test that expired keys are rejected."""
    # Create key that expires in 1 day
    key_info = auth_manager.create_api_key(
        sample_project_id,
        "Expiring Key",
        expires_days=1
    )

    api_key = key_info["api_key"]

    # Should work now
    assert auth_manager.validate_project_access(api_key, sample_project_id, "read") is True

    # Manually expire the key by updating database
    import sqlite3
    with sqlite3.connect(str(auth_manager.db_path)) as conn:
        # Set expiration to 1 hour ago
        past_time = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        conn.execute(
            "UPDATE api_keys SET expires_at = ? WHERE key_id = ?",
            (past_time, key_info["key_id"])
        )
        conn.commit()

    # Should be rejected now
    assert auth_manager.validate_project_access(api_key, sample_project_id, "read") is False


def test_api_key_validation(auth_manager, sample_project_id):
    """Test that valid keys are accepted."""
    key_info = auth_manager.create_api_key(
        sample_project_id,
        "Valid Key",
        scopes=["read", "write"]
    )

    # Valid key with correct project
    assert auth_manager.validate_project_access(
        key_info["api_key"], sample_project_id, "read"
    ) is True

    # Valid key with correct scope
    assert auth_manager.validate_project_access(
        key_info["api_key"], sample_project_id, "write"
    ) is True


def test_api_key_invalid_format(auth_manager, sample_project_id):
    """Test that malformed keys are rejected."""
    # Invalid format keys
    invalid_keys = [
        "invalid_key",
        "kb_tooshort",
        "",
        "kb_" + "x" * 100,  # Too long
        None,
    ]

    for invalid_key in invalid_keys:
        if invalid_key is None:
            # None should be handled gracefully
            assert auth_manager.validate_project_access(None, sample_project_id, "read") is False
        else:
            assert auth_manager.validate_project_access(
                invalid_key, sample_project_id, "read"
            ) is False


def test_api_key_project_isolation(auth_manager):
    """Test that a key for project A cannot access project B."""
    project_a = "proj_a"
    project_b = "proj_b"

    # Create key for project A
    key_a = auth_manager.create_api_key(project_a, "Key A", scopes=["read", "write"])

    # Key should work for project A
    assert auth_manager.validate_project_access(
        key_a["api_key"], project_a, "read"
    ) is True

    # Key should NOT work for project B
    assert auth_manager.validate_project_access(
        key_a["api_key"], project_b, "read"
    ) is False

    # Key should NOT work for project B even with lower scope
    assert auth_manager.validate_project_access(
        key_a["api_key"], project_b, "write"
    ) is False


def test_api_key_last_used_tracking(auth_manager, sample_project_id):
    """Test that last_used_at timestamp is updated on validation."""
    key_info = auth_manager.create_api_key(sample_project_id, "Test Key")

    # Initially, last_used_at should be None
    keys = auth_manager.list_project_keys(sample_project_id)
    assert keys[0]["last_used_at"] is None

    # Use the key
    auth_manager.validate_project_access(
        key_info["api_key"], sample_project_id, "read"
    )

    # Small delay to ensure timestamp difference
    time.sleep(0.01)

    # last_used_at should now be set
    keys = auth_manager.list_project_keys(sample_project_id)
    assert keys[0]["last_used_at"] is not None

    # Parse timestamp to verify it's recent
    last_used = datetime.fromisoformat(keys[0]["last_used_at"])
    time_diff = (datetime.utcnow() - last_used).total_seconds()
    assert time_diff < 5  # Should be within last 5 seconds
