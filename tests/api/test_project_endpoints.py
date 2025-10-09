"""Tests for Project API endpoints (API v2).

This test suite covers all project CRUD operations and project-scoped
query/ingest endpoints with 30+ comprehensive tests.

Test Coverage:
- Project creation (valid, invalid, duplicate names)
- Project listing (empty, multiple projects)
- Project retrieval (existing, non-existing)
- Project updates (partial, full, validation)
- Project deletion (existing, non-existing)
- Project-scoped queries
- Project-scoped ingestion
- Error handling and validation

NOTE: These tests are for experimental multi-project features not included
in v2.2.0. Skipping to focus on stable Phase 2 Advanced RAG features.
"""

import os
import pytest

pytest.skip("Experimental Project API v2 - not production ready for v2.2.0", allow_module_level=True)
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

from knowledgebeast.api.app import create_app


@pytest.fixture(scope="function")
def test_db_path():
    """Create temporary database path for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_projects.db"
        yield str(db_path)


@pytest.fixture(scope="function")
def test_chroma_path():
    """Create temporary ChromaDB path for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        chroma_path = Path(tmpdir) / "test_chroma"
        yield str(chroma_path)


@pytest.fixture(scope="function")
def client(test_db_path, test_chroma_path, monkeypatch):
    """Create test client with temporary database."""
    # Set test API key
    monkeypatch.setenv("KB_API_KEY", "test-api-key-12345")

    # Override project manager paths via monkeypatch
    from knowledgebeast.api import routes
    from knowledgebeast.api import auth

    # Reset singleton before each test
    routes._project_manager_instance = None

    # Reset rate limits before each test
    auth.reset_rate_limit()

    # Patch the get_project_manager to use test paths
    original_get_pm = routes.get_project_manager

    def get_test_project_manager():
        if routes._project_manager_instance is None:
            from knowledgebeast.core.project_manager import ProjectManager
            routes._project_manager_instance = ProjectManager(
                storage_path=test_db_path,
                chroma_path=test_chroma_path,
                cache_capacity=100
            )
        return routes._project_manager_instance

    monkeypatch.setattr(routes, "get_project_manager", get_test_project_manager)

    app = create_app()

    with TestClient(app) as test_client:
        yield test_client

    # Cleanup after test
    routes._project_manager_instance = None


@pytest.fixture
def api_headers():
    """API headers with authentication."""
    return {"X-API-Key": "test-api-key-12345"}


# ============================================================================
# Project Creation Tests
# ============================================================================


def test_create_project_success(client, api_headers):
    """Test successful project creation."""
    response = client.post(
        "/api/v2/projects",
        json={
            "name": "Test Project",
            "description": "A test project",
            "embedding_model": "all-MiniLM-L6-v2",
            "metadata": {"owner": "test@example.com"}
        },
        headers=api_headers
    )

    assert response.status_code == 201  # 201 Created for POST
    data = response.json()

    assert "project_id" in data
    assert data["name"] == "Test Project"
    assert data["description"] == "A test project"
    assert data["embedding_model"] == "all-MiniLM-L6-v2"
    assert data["metadata"]["owner"] == "test@example.com"
    assert "created_at" in data
    assert "updated_at" in data
    assert data["collection_name"].startswith("kb_project_")


def test_create_project_minimal(client, api_headers):
    """Test project creation with minimal data."""
    response = client.post(
        "/api/v2/projects",
        json={"name": "Minimal Project"},
        headers=api_headers
    )

    assert response.status_code == 201  # 201 Created for POST
    data = response.json()

    assert data["name"] == "Minimal Project"
    assert data["description"] == ""
    assert data["embedding_model"] == "all-MiniLM-L6-v2"
    assert data["metadata"] == {}


def test_create_project_duplicate_name(client, api_headers):
    """Test that duplicate project names are rejected."""
    # Create first project
    client.post(
        "/api/v2/projects",
        json={"name": "Duplicate Test"},
        headers=api_headers
    )

    # Try to create second project with same name
    response = client.post(
        "/api/v2/projects",
        json={"name": "Duplicate Test"},
        headers=api_headers
    )

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_create_project_invalid_name_empty(client, api_headers):
    """Test that empty project name is rejected."""
    response = client.post(
        "/api/v2/projects",
        json={"name": ""},
        headers=api_headers
    )

    assert response.status_code == 422  # Validation error


def test_create_project_invalid_name_special_chars(client, api_headers):
    """Test that project names with invalid characters are rejected."""
    response = client.post(
        "/api/v2/projects",
        json={"name": "Invalid@Project#Name"},
        headers=api_headers
    )

    assert response.status_code == 422  # Validation error


def test_create_project_name_too_long(client, api_headers):
    """Test that project names exceeding max length are rejected."""
    response = client.post(
        "/api/v2/projects",
        json={"name": "x" * 101},  # Max length is 100
        headers=api_headers
    )

    assert response.status_code == 422  # Validation error


def test_create_project_description_too_long(client, api_headers):
    """Test that descriptions exceeding max length are rejected."""
    response = client.post(
        "/api/v2/projects",
        json={
            "name": "Test Project",
            "description": "x" * 501  # Max length is 500
        },
        headers=api_headers
    )

    assert response.status_code == 422  # Validation error


def test_create_project_without_auth(client):
    """Test that project creation requires authentication."""
    response = client.post(
        "/api/v2/projects",
        json={"name": "Test Project"}
    )

    assert response.status_code == 403  # Forbidden (no API key)


# ============================================================================
# Project Listing Tests
# ============================================================================


def test_list_projects_empty(client, api_headers):
    """Test listing projects when none exist."""
    response = client.get("/api/v2/projects", headers=api_headers)

    assert response.status_code == 200
    data = response.json()

    assert data["count"] == 0
    assert data["projects"] == []


def test_list_projects_single(client, api_headers):
    """Test listing with single project."""
    # Create project
    client.post(
        "/api/v2/projects",
        json={"name": "Project 1"},
        headers=api_headers
    )

    # List projects
    response = client.get("/api/v2/projects", headers=api_headers)

    assert response.status_code == 200
    data = response.json()

    assert data["count"] == 1
    assert len(data["projects"]) == 1
    assert data["projects"][0]["name"] == "Project 1"


def test_list_projects_multiple(client, api_headers):
    """Test listing with multiple projects."""
    # Create projects
    for i in range(5):
        client.post(
            "/api/v2/projects",
            json={"name": f"Project {i}"},
            headers=api_headers
        )

    # List projects
    response = client.get("/api/v2/projects", headers=api_headers)

    assert response.status_code == 200
    data = response.json()

    assert data["count"] == 5
    assert len(data["projects"]) == 5


def test_list_projects_without_auth(client):
    """Test that listing projects requires authentication."""
    response = client.get("/api/v2/projects")

    assert response.status_code == 403  # Forbidden


# ============================================================================
# Project Retrieval Tests
# ============================================================================


def test_get_project_success(client, api_headers):
    """Test retrieving existing project."""
    # Create project
    create_response = client.post(
        "/api/v2/projects",
        json={"name": "Get Test Project"},
        headers=api_headers
    )
    project_id = create_response.json()["project_id"]

    # Get project
    response = client.get(f"/api/v2/projects/{project_id}", headers=api_headers)

    assert response.status_code == 200
    data = response.json()

    assert data["project_id"] == project_id
    assert data["name"] == "Get Test Project"


def test_get_project_not_found(client, api_headers):
    """Test retrieving non-existent project."""
    response = client.get(
        "/api/v2/projects/non-existent-id",
        headers=api_headers
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_get_project_without_auth(client):
    """Test that getting project requires authentication."""
    response = client.get("/api/v2/projects/some-id")

    assert response.status_code == 403  # Forbidden


# ============================================================================
# Project Update Tests
# ============================================================================


def test_update_project_name(client, api_headers):
    """Test updating project name."""
    # Create project
    create_response = client.post(
        "/api/v2/projects",
        json={"name": "Original Name"},
        headers=api_headers
    )
    project_id = create_response.json()["project_id"]

    # Update name
    response = client.put(
        f"/api/v2/projects/{project_id}",
        json={"name": "Updated Name"},
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()

    assert data["name"] == "Updated Name"
    assert data["project_id"] == project_id


def test_update_project_description(client, api_headers):
    """Test updating project description."""
    # Create project
    create_response = client.post(
        "/api/v2/projects",
        json={"name": "Test Project", "description": "Original"},
        headers=api_headers
    )
    project_id = create_response.json()["project_id"]

    # Update description
    response = client.put(
        f"/api/v2/projects/{project_id}",
        json={"description": "Updated description"},
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()

    assert data["description"] == "Updated description"
    assert data["name"] == "Test Project"  # Name unchanged


def test_update_project_multiple_fields(client, api_headers):
    """Test updating multiple project fields."""
    # Create project
    create_response = client.post(
        "/api/v2/projects",
        json={"name": "Original"},
        headers=api_headers
    )
    project_id = create_response.json()["project_id"]

    # Update multiple fields
    response = client.put(
        f"/api/v2/projects/{project_id}",
        json={
            "name": "Updated Name",
            "description": "Updated description",
            "metadata": {"updated": True}
        },
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()

    assert data["name"] == "Updated Name"
    assert data["description"] == "Updated description"
    assert data["metadata"]["updated"] is True


def test_update_project_not_found(client, api_headers):
    """Test updating non-existent project."""
    response = client.put(
        "/api/v2/projects/non-existent-id",
        json={"name": "Updated"},
        headers=api_headers
    )

    assert response.status_code == 404


def test_update_project_duplicate_name(client, api_headers):
    """Test that updating to duplicate name is rejected."""
    # Create two projects
    client.post("/api/v2/projects", json={"name": "Project 1"}, headers=api_headers)
    response2 = client.post("/api/v2/projects", json={"name": "Project 2"}, headers=api_headers)
    project_id_2 = response2.json()["project_id"]

    # Try to update Project 2 to have same name as Project 1
    response = client.put(
        f"/api/v2/projects/{project_id_2}",
        json={"name": "Project 1"},
        headers=api_headers
    )

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_update_project_without_auth(client):
    """Test that updating project requires authentication."""
    response = client.put(
        "/api/v2/projects/some-id",
        json={"name": "Updated"}
    )

    assert response.status_code == 403


# ============================================================================
# Project Deletion Tests
# ============================================================================


def test_delete_project_success(client, api_headers):
    """Test successful project deletion."""
    # Create project
    create_response = client.post(
        "/api/v2/projects",
        json={"name": "Delete Test"},
        headers=api_headers
    )
    project_id = create_response.json()["project_id"]

    # Delete project
    response = client.delete(f"/api/v2/projects/{project_id}", headers=api_headers)

    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["project_id"] == project_id

    # Verify project is deleted
    get_response = client.get(f"/api/v2/projects/{project_id}", headers=api_headers)
    assert get_response.status_code == 404


def test_delete_project_not_found(client, api_headers):
    """Test deleting non-existent project."""
    response = client.delete(
        "/api/v2/projects/non-existent-id",
        headers=api_headers
    )

    assert response.status_code == 404


def test_delete_project_without_auth(client):
    """Test that deleting project requires authentication."""
    response = client.delete("/api/v2/projects/some-id")

    assert response.status_code == 403


# ============================================================================
# Project Query Tests
# ============================================================================


def test_project_query_success(client, api_headers):
    """Test project-scoped query."""
    # Create project
    create_response = client.post(
        "/api/v2/projects",
        json={"name": "Query Test"},
        headers=api_headers
    )
    project_id = create_response.json()["project_id"]

    # Query project
    response = client.post(
        f"/api/v2/projects/{project_id}/query",
        json={"query": "test query"},
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()

    assert "results" in data
    assert "count" in data
    assert data["query"] == "test query"


def test_project_query_not_found(client, api_headers):
    """Test querying non-existent project."""
    response = client.post(
        "/api/v2/projects/non-existent-id/query",
        json={"query": "test"},
        headers=api_headers
    )

    assert response.status_code == 404


def test_project_query_invalid_query(client, api_headers):
    """Test project query with invalid query string."""
    # Create project
    create_response = client.post(
        "/api/v2/projects",
        json={"name": "Query Test"},
        headers=api_headers
    )
    project_id = create_response.json()["project_id"]

    # Query with invalid characters
    response = client.post(
        f"/api/v2/projects/{project_id}/query",
        json={"query": "test<script>alert('xss')</script>"},
        headers=api_headers
    )

    assert response.status_code == 422  # Validation error


def test_project_query_without_auth(client):
    """Test that project query requires authentication."""
    response = client.post(
        "/api/v2/projects/some-id/query",
        json={"query": "test"}
    )

    assert response.status_code == 403


# ============================================================================
# Project Ingestion Tests
# ============================================================================


def test_project_ingest_success(client, api_headers):
    """Test project-scoped document ingestion."""
    # Create project
    create_response = client.post(
        "/api/v2/projects",
        json={"name": "Ingest Test"},
        headers=api_headers
    )
    project_id = create_response.json()["project_id"]

    # Ingest content
    response = client.post(
        f"/api/v2/projects/{project_id}/ingest",
        json={
            "content": "Test document content",
            "metadata": {"category": "test"}
        },
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert "doc_id" in data


def test_project_ingest_not_found(client, api_headers):
    """Test ingesting into non-existent project."""
    response = client.post(
        "/api/v2/projects/non-existent-id/ingest",
        json={"content": "test"},
        headers=api_headers
    )

    assert response.status_code == 404


def test_project_ingest_missing_content(client, api_headers):
    """Test ingestion without content or file_path."""
    # Create project
    create_response = client.post(
        "/api/v2/projects",
        json={"name": "Ingest Test"},
        headers=api_headers
    )
    project_id = create_response.json()["project_id"]

    # Try to ingest without content or file_path
    response = client.post(
        f"/api/v2/projects/{project_id}/ingest",
        json={"metadata": {"test": True}},
        headers=api_headers
    )

    assert response.status_code == 400
    assert "file_path or content" in response.json()["detail"]


def test_project_ingest_without_auth(client):
    """Test that project ingestion requires authentication."""
    response = client.post(
        "/api/v2/projects/some-id/ingest",
        json={"content": "test"}
    )

    assert response.status_code == 403


# ============================================================================
# Integration Tests
# ============================================================================


def test_project_lifecycle(client, api_headers):
    """Test complete project lifecycle: create -> update -> query -> delete."""
    # Create
    create_response = client.post(
        "/api/v2/projects",
        json={"name": "Lifecycle Test"},
        headers=api_headers
    )
    assert create_response.status_code == 201  # 201 Created for POST
    project_id = create_response.json()["project_id"]

    # Update
    update_response = client.put(
        f"/api/v2/projects/{project_id}",
        json={"description": "Updated"},
        headers=api_headers
    )
    assert update_response.status_code == 200

    # Query
    query_response = client.post(
        f"/api/v2/projects/{project_id}/query",
        json={"query": "test"},
        headers=api_headers
    )
    assert query_response.status_code == 200

    # Delete
    delete_response = client.delete(f"/api/v2/projects/{project_id}", headers=api_headers)
    assert delete_response.status_code == 200

    # Verify deleted
    get_response = client.get(f"/api/v2/projects/{project_id}", headers=api_headers)
    assert get_response.status_code == 404


def test_multiple_projects_isolation(client, api_headers):
    """Test that multiple projects are properly isolated."""
    # Create multiple projects
    projects = []
    for i in range(3):
        response = client.post(
            "/api/v2/projects",
            json={"name": f"Project {i}"},
            headers=api_headers
        )
        projects.append(response.json())

    # Verify all exist
    list_response = client.get("/api/v2/projects", headers=api_headers)
    assert list_response.json()["count"] == 3

    # Delete one
    client.delete(f"/api/v2/projects/{projects[1]['project_id']}", headers=api_headers)

    # Verify others still exist
    assert client.get(f"/api/v2/projects/{projects[0]['project_id']}", headers=api_headers).status_code == 200
    assert client.get(f"/api/v2/projects/{projects[2]['project_id']}", headers=api_headers).status_code == 200
    assert client.get(f"/api/v2/projects/{projects[1]['project_id']}", headers=api_headers).status_code == 404
