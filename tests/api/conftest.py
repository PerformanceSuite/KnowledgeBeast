"""API Test Fixtures with Complete Isolation.

This module provides test fixtures with complete isolation for API tests,
ensuring tests don't interfere with each other through shared state.

Features:
- Isolated database per test function
- Isolated ChromaDB collections per test
- Singleton ProjectManager reset between tests
- Rate limit reset between tests
- Automatic cleanup

Thread Safety:
- Each test gets fresh instances
- No shared state between tests
- Parallel test execution safe
"""

import tempfile
import shutil
from pathlib import Path
from typing import Generator
import pytest
from fastapi.testclient import TestClient

from knowledgebeast.api.app import create_app


@pytest.fixture(scope="function")
def isolated_db(tmp_path: Path) -> Generator[str, None, None]:
    """Provide isolated database per test function.

    Args:
        tmp_path: Pytest temporary directory fixture

    Yields:
        Path to isolated test database
    """
    db_path = tmp_path / "test_projects.db"
    yield str(db_path)
    # Cleanup happens automatically with tmp_path


@pytest.fixture(autouse=True, scope="function")
def reset_chroma(monkeypatch, tmp_path: Path) -> Generator[str, None, None]:
    """Reset ChromaDB between tests - applies to ALL tests automatically.

    This fixture is autouse=True, so it runs for every test function
    without needing to be explicitly requested.

    Args:
        monkeypatch: Pytest monkeypatch fixture
        tmp_path: Pytest temporary directory fixture

    Yields:
        Path to isolated ChromaDB directory
    """
    chroma_path = tmp_path / "chroma_test"
    chroma_path.mkdir(exist_ok=True)

    # Set environment variable for ChromaDB path
    monkeypatch.setenv("KB_CHROMA_PATH", str(chroma_path))

    yield str(chroma_path)

    # Cleanup
    if chroma_path.exists():
        shutil.rmtree(chroma_path, ignore_errors=True)


@pytest.fixture(scope="function")
def clean_project_manager(reset_chroma: str, isolated_db: str, monkeypatch) -> Generator:
    """Provide clean ProjectManager instance per test.

    Resets singleton and creates fresh instance with isolated paths.

    Args:
        reset_chroma: Isolated ChromaDB path from reset_chroma fixture
        isolated_db: Isolated database path from isolated_db fixture
        monkeypatch: Pytest monkeypatch fixture

    Yields:
        Clean ProjectManager instance
    """
    from knowledgebeast.core.project_manager import ProjectManager
    from knowledgebeast.api import routes

    # Reset singleton if it exists
    if hasattr(ProjectManager, '_instance'):
        delattr(ProjectManager, '_instance')

    # Also reset the module-level singleton in routes
    routes._project_manager_instance = None

    # Create new instance with isolated paths
    pm = ProjectManager(
        storage_path=isolated_db,
        chroma_path=reset_chroma,
        cache_capacity=100
    )

    yield pm

    # Cleanup
    try:
        pm.cleanup_all()
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture(scope="function")
def client(clean_project_manager, monkeypatch) -> Generator[TestClient, None, None]:
    """Create test client with clean ProjectManager.

    This fixture provides a completely isolated test client for each test.

    Args:
        clean_project_manager: Clean ProjectManager instance
        monkeypatch: Pytest monkeypatch fixture

    Yields:
        TestClient for API testing
    """
    # Set test API key
    monkeypatch.setenv("KB_API_KEY", "test-api-key-12345")

    # Disable rate limiting for tests (set very high limit)
    monkeypatch.setenv("KB_RATE_LIMIT_PER_MINUTE", "10000")

    # Override project manager getter to use our clean instance
    from knowledgebeast.api import routes
    from knowledgebeast.api import auth

    # Reset rate limits before each test
    auth.reset_rate_limit()

    # Disable the custom auth rate limiter by setting a very high limit
    original_rate_limit = auth.RATE_LIMIT_REQUESTS
    auth.RATE_LIMIT_REQUESTS = 100000
    monkeypatch.setattr(auth, "RATE_LIMIT_REQUESTS", 100000)

    # Patch the get_project_manager to use our clean instance
    def get_test_project_manager():
        return clean_project_manager

    monkeypatch.setattr(routes, "get_project_manager", get_test_project_manager)

    # Disable slowapi rate limiting by patching the limiter's enabled flag
    # and resetting its storage
    routes.limiter._enabled = False  # Disable the limiter entirely

    # Also reset the storage backend to clear any accumulated state
    if hasattr(routes.limiter, '_storage'):
        routes.limiter._storage.reset()

    # Patch the limit decorator to be a no-op
    def noop_limit_decorator(*args, **kwargs):
        """No-op decorator that just returns the function unchanged."""
        def decorator(func):
            return func
        # If called with function directly (no parens), return it
        if args and callable(args[0]):
            return args[0]
        return decorator

    monkeypatch.setattr(routes.limiter, "limit", noop_limit_decorator)

    # Create app
    app = create_app()

    with TestClient(app) as test_client:
        yield test_client

    # Reset rate limit after test
    auth.reset_rate_limit()

    # Cleanup happens in clean_project_manager fixture


@pytest.fixture
def api_headers() -> dict:
    """API headers with authentication.

    Returns:
        Dictionary with X-API-Key header
    """
    return {"X-API-Key": "test-api-key-12345"}
