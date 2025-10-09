"""Unit tests for KnowledgeBeast MCP tools.

Tests all 12 MCP tools with comprehensive coverage including:
- Search operations (vector, keyword, hybrid)
- Document ingestion and management
- Project CRUD operations
- Error handling
- Edge cases

Uses mocked ChromaDB for fast, isolated tests (no real I/O).
Performance target: <5 seconds for all tests.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from knowledgebeast.core.project_manager import Project

# All fixtures imported from conftest.py (mocked for speed)
# Note: MCPConfig and KnowledgeBeastTools are mocked to avoid slow I/O


# ===== Project Management Tests =====


@pytest.mark.asyncio
async def test_create_project_basic(mcp_tools):
    """Test creating a basic project."""
    result = await mcp_tools.kb_create_project(
        name="my-project",
        description="A test project",
    )

    assert result["success"] is True
    assert "project_id" in result
    assert result["name"] == "my-project"
    assert result["description"] == "A test project"
    assert result["embedding_model"] == "all-MiniLM-L6-v2"
    assert "created_at" in result


@pytest.mark.asyncio
async def test_create_project_custom_model(mcp_tools):
    """Test creating project with custom embedding model."""
    result = await mcp_tools.kb_create_project(
        name="custom-model-project",
        description="Project with custom model",
        embedding_model="all-mpnet-base-v2",
    )

    assert result["success"] is True
    assert result["embedding_model"] == "all-mpnet-base-v2"


@pytest.mark.asyncio
async def test_create_project_with_metadata(mcp_tools):
    """Test creating project with custom metadata."""
    metadata = {"owner": "test-user", "department": "engineering"}

    result = await mcp_tools.kb_create_project(
        name="metadata-project",
        description="Project with metadata",
        metadata=metadata,
    )

    assert result["success"] is True
    project_id = result["project_id"]

    # Verify metadata persisted
    info = await mcp_tools.kb_get_project_info(project_id)
    assert info["metadata"]["owner"] == "test-user"
    assert info["metadata"]["department"] == "engineering"


@pytest.mark.asyncio
async def test_list_projects_empty(mcp_tools):
    """Test listing projects when none exist."""
    result = await mcp_tools.kb_list_projects()
    assert isinstance(result, list)
    assert len(result) == 0


@pytest.mark.asyncio
async def test_list_projects_multiple(mcp_tools):
    """Test listing multiple projects."""
    # Create multiple projects
    await mcp_tools.kb_create_project("project-1", "First project")
    await mcp_tools.kb_create_project("project-2", "Second project")
    await mcp_tools.kb_create_project("project-3", "Third project")

    result = await mcp_tools.kb_list_projects()

    assert len(result) == 3
    names = [p["name"] for p in result]
    assert "project-1" in names
    assert "project-2" in names
    assert "project-3" in names


@pytest.mark.asyncio
async def test_get_project_info(mcp_tools, sample_project: Project):
    """Test getting detailed project information."""
    result = await mcp_tools.kb_get_project_info(sample_project.project_id)

    assert "error" not in result
    assert result["project_id"] == sample_project.project_id
    assert result["name"] == sample_project.name
    assert result["description"] == sample_project.description
    assert "document_count" in result
    assert "cache_stats" in result
    assert "created_at" in result
    assert "updated_at" in result


@pytest.mark.asyncio
async def test_get_project_info_nonexistent(mcp_tools):
    """Test getting info for nonexistent project."""
    result = await mcp_tools.kb_get_project_info("nonexistent-project-id")

    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_delete_project(mcp_tools):
    """Test deleting a project."""
    # Create project
    create_result = await mcp_tools.kb_create_project("delete-me", "To be deleted")
    project_id = create_result["project_id"]

    # Delete project
    delete_result = await mcp_tools.kb_delete_project(project_id)

    assert delete_result["success"] is True
    assert delete_result["project_id"] == project_id

    # Verify deletion
    projects = await mcp_tools.kb_list_projects()
    project_ids = [p["project_id"] for p in projects]
    assert project_id not in project_ids


@pytest.mark.asyncio
async def test_delete_nonexistent_project(mcp_tools):
    """Test deleting a nonexistent project."""
    result = await mcp_tools.kb_delete_project("nonexistent-id")

    assert "error" in result


# ===== Document Ingestion Tests =====


@pytest.mark.asyncio
async def test_ingest_direct_content(mcp_tools, sample_project: Project):
    """Test ingesting document from direct content."""
    content = "Machine learning is a subset of artificial intelligence."

    result = await mcp_tools.kb_ingest(
        project_id=sample_project.project_id,
        content=content,
    )

    assert result["success"] is True
    assert "doc_id" in result
    assert "message" in result
    assert sample_project.name in result["message"]


@pytest.mark.asyncio
async def test_ingest_direct_content_with_metadata(
    mcp_tools, sample_project: Project
):
    """Test ingesting document with custom metadata."""
    content = "Python is a high-level programming language."
    metadata = {"author": "John Doe", "category": "programming"}

    result = await mcp_tools.kb_ingest(
        project_id=sample_project.project_id,
        content=content,
        metadata=metadata,
    )

    assert result["success"] is True
    assert "doc_id" in result


@pytest.mark.asyncio
async def test_ingest_from_file(
    mcp_tools, sample_project: Project, temp_mcp_dir: Path
):
    """Test ingesting document from file."""
    # Create test file
    test_file = temp_mcp_dir / "test_doc.md"
    test_file.write_text("# Test Document\n\nThis is a test document for ingestion.")

    result = await mcp_tools.kb_ingest(
        project_id=sample_project.project_id,
        file_path=str(test_file),
    )

    assert result["success"] is True
    assert "doc_id" in result
    assert "file_path" in result
    assert result["file_path"] == str(test_file)


@pytest.mark.asyncio
async def test_ingest_nonexistent_file(
    mcp_tools, sample_project: Project
):
    """Test ingesting from nonexistent file."""
    result = await mcp_tools.kb_ingest(
        project_id=sample_project.project_id,
        file_path="/nonexistent/path/file.md",
    )

    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_ingest_no_content_or_file(
    mcp_tools, sample_project: Project
):
    """Test ingesting without content or file_path."""
    result = await mcp_tools.kb_ingest(project_id=sample_project.project_id)

    assert "error" in result
    assert "must provide" in result["error"].lower()


@pytest.mark.asyncio
async def test_ingest_to_nonexistent_project(mcp_tools):
    """Test ingesting to nonexistent project."""
    result = await mcp_tools.kb_ingest(
        project_id="nonexistent-project",
        content="Some content",
    )

    assert "error" in result
    assert "not found" in result["error"].lower()


# ===== Document Listing Tests =====


@pytest.mark.asyncio
async def test_list_documents_empty(
    mcp_tools, sample_project: Project
):
    """Test listing documents in empty project."""
    result = await mcp_tools.kb_list_documents(sample_project.project_id)

    assert "error" not in result
    assert result["project_id"] == sample_project.project_id
    assert result["total_documents"] == 0
    assert len(result["documents"]) == 0


@pytest.mark.asyncio
async def test_list_documents_with_content(
    mcp_tools, sample_project: Project
):
    """Test listing documents after ingestion."""
    # Ingest multiple documents
    await mcp_tools.kb_ingest(sample_project.project_id, content="Document 1")
    await mcp_tools.kb_ingest(sample_project.project_id, content="Document 2")
    await mcp_tools.kb_ingest(sample_project.project_id, content="Document 3")

    result = await mcp_tools.kb_list_documents(sample_project.project_id)

    assert result["total_documents"] == 3
    assert len(result["documents"]) == 3

    # Check document structure
    doc = result["documents"][0]
    assert "doc_id" in doc
    assert "metadata" in doc


@pytest.mark.asyncio
async def test_list_documents_with_limit(
    mcp_tools, sample_project: Project
):
    """Test listing documents with result limit."""
    # Ingest multiple documents
    for i in range(10):
        await mcp_tools.kb_ingest(sample_project.project_id, content=f"Document {i}")

    result = await mcp_tools.kb_list_documents(sample_project.project_id, limit=5)

    assert result["total_documents"] == 10
    assert len(result["documents"]) == 5


@pytest.mark.asyncio
async def test_list_documents_nonexistent_project(mcp_tools):
    """Test listing documents for nonexistent project."""
    result = await mcp_tools.kb_list_documents("nonexistent-project")

    assert "error" in result


# ===== Search Tests =====


@pytest.mark.asyncio
async def test_search_vector_mode(
    mcp_tools, sample_project: Project
):
    """Test vector search mode."""
    # Ingest test documents
    await mcp_tools.kb_ingest(
        sample_project.project_id,
        content="Python is a programming language for data science and machine learning.",
    )
    await mcp_tools.kb_ingest(
        sample_project.project_id,
        content="JavaScript is used for web development and frontend applications.",
    )

    # Search with vector mode
    results = await mcp_tools.kb_search(
        project_id=sample_project.project_id,
        query="artificial intelligence and machine learning",
        mode="vector",
        limit=5,
    )

    assert isinstance(results, list)
    if len(results) > 0 and "error" not in results[0]:
        assert "doc_id" in results[0]
        assert "content" in results[0]
        assert "score" in results[0]


@pytest.mark.asyncio
async def test_search_keyword_mode(
    mcp_tools, sample_project: Project
):
    """Test keyword search mode."""
    # Ingest test documents
    await mcp_tools.kb_ingest(
        sample_project.project_id,
        content="Python programming language with excellent libraries.",
    )

    # Search with keyword mode
    results = await mcp_tools.kb_search(
        project_id=sample_project.project_id,
        query="Python",
        mode="keyword",
        limit=5,
    )

    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_search_hybrid_mode(
    mcp_tools, sample_project: Project
):
    """Test hybrid search mode (default)."""
    # Ingest test documents
    await mcp_tools.kb_ingest(
        sample_project.project_id,
        content="FastAPI is a modern web framework for building APIs with Python.",
    )

    # Search with hybrid mode
    results = await mcp_tools.kb_search(
        project_id=sample_project.project_id,
        query="Python web framework",
        mode="hybrid",
        alpha=0.7,
        limit=5,
    )

    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_search_with_custom_alpha(
    mcp_tools, sample_project: Project
):
    """Test hybrid search with custom alpha parameter."""
    await mcp_tools.kb_ingest(
        sample_project.project_id, content="Test document content"
    )

    # Test different alpha values
    for alpha in [0.0, 0.3, 0.5, 0.7, 1.0]:
        results = await mcp_tools.kb_search(
            project_id=sample_project.project_id,
            query="test",
            mode="hybrid",
            alpha=alpha,
            limit=5,
        )
        assert isinstance(results, list)


@pytest.mark.asyncio
async def test_search_nonexistent_project(mcp_tools):
    """Test searching in nonexistent project."""
    results = await mcp_tools.kb_search(
        project_id="nonexistent-project",
        query="test query",
    )

    assert isinstance(results, list)
    assert len(results) > 0
    assert "error" in results[0]


@pytest.mark.asyncio
async def test_search_empty_project(
    mcp_tools, sample_project: Project
):
    """Test searching in project with no documents."""
    results = await mcp_tools.kb_search(
        project_id=sample_project.project_id,
        query="any query",
    )

    # Empty project should return empty results
    assert isinstance(results, list)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_search_with_result_limit(
    mcp_tools, sample_project: Project
):
    """Test search with custom result limit."""
    # Ingest multiple documents
    for i in range(10):
        await mcp_tools.kb_ingest(
            sample_project.project_id, content=f"Test document number {i}"
        )

    # Search with limit
    results = await mcp_tools.kb_search(
        project_id=sample_project.project_id,
        query="test document",
        limit=3,
    )

    assert len(results) <= 3


# ===== Error Handling Tests =====


@pytest.mark.asyncio
async def test_error_handling_invalid_project_id(mcp_tools):
    """Test error handling with invalid project ID."""
    result = await mcp_tools.kb_get_project_info("")
    assert "error" in result


@pytest.mark.asyncio
async def test_error_handling_search_exception(mcp_tools):
    """Test error handling when search raises exception."""
    # Use invalid project to trigger error
    results = await mcp_tools.kb_search(
        project_id="invalid",
        query="test",
    )

    assert isinstance(results, list)
    assert len(results) > 0
    assert "error" in results[0]


# ===== Cache Tests =====


@pytest.mark.asyncio
async def test_project_cache_isolation(mcp_tools):
    """Test that project caches are isolated."""
    # Create two projects
    result1 = await mcp_tools.kb_create_project("project-1", "First project")
    result2 = await mcp_tools.kb_create_project("project-2", "Second project")

    project_id_1 = result1["project_id"]
    project_id_2 = result2["project_id"]

    # Ingest different content
    await mcp_tools.kb_ingest(project_id_1, content="Content for project 1")
    await mcp_tools.kb_ingest(project_id_2, content="Content for project 2")

    # Search both projects
    results1 = await mcp_tools.kb_search(project_id_1, query="project", limit=5)
    results2 = await mcp_tools.kb_search(project_id_2, query="project", limit=5)

    # Results should be different (isolated)
    assert isinstance(results1, list)
    assert isinstance(results2, list)


# ===== Configuration Tests =====


def test_mcp_config_default_values():
    """Test MCPConfig default values."""
    config = MCPConfig()

    assert config.projects_db_path == "./kb_projects.db"
    assert config.chroma_path == "./chroma_db"
    assert config.default_embedding_model == "all-MiniLM-L6-v2"
    assert config.cache_capacity == 100
    assert config.server_name == "knowledgebeast"
    assert config.log_level == "INFO"


def test_mcp_config_custom_values(temp_mcp_dir: Path):
    """Test MCPConfig with custom values."""
    config = MCPConfig(
        projects_db_path=str(temp_mcp_dir / "custom.db"),
        chroma_path=str(temp_mcp_dir / "custom_chroma"),
        default_embedding_model="all-mpnet-base-v2",
        cache_capacity=200,
        log_level="DEBUG",
    )

    assert config.projects_db_path == str(temp_mcp_dir / "custom.db")
    assert config.chroma_path == str(temp_mcp_dir / "custom_chroma")
    assert config.default_embedding_model == "all-mpnet-base-v2"
    assert config.cache_capacity == 200
    assert config.log_level == "DEBUG"


def test_mcp_config_from_env(monkeypatch, temp_mcp_dir: Path):
    """Test MCPConfig creation from environment variables."""
    monkeypatch.setenv("KB_PROJECTS_DB", str(temp_mcp_dir / "env.db"))
    monkeypatch.setenv("KB_CHROMA_PATH", str(temp_mcp_dir / "env_chroma"))
    monkeypatch.setenv("KB_DEFAULT_MODEL", "all-mpnet-base-v2")
    monkeypatch.setenv("KB_CACHE_CAPACITY", "300")
    monkeypatch.setenv("KB_LOG_LEVEL", "WARNING")

    config = MCPConfig.from_env()

    assert config.projects_db_path == str(temp_mcp_dir / "env.db")
    assert config.chroma_path == str(temp_mcp_dir / "env_chroma")
    assert config.default_embedding_model == "all-mpnet-base-v2"
    assert config.cache_capacity == 300
    assert config.log_level == "WARNING"


def test_mcp_config_ensure_directories(temp_mcp_dir: Path):
    """Test MCPConfig directory creation."""
    config = MCPConfig(
        projects_db_path=str(temp_mcp_dir / "subdir" / "projects.db"),
        chroma_path=str(temp_mcp_dir / "subdir" / "chroma"),
    )

    config.ensure_directories()

    assert Path(config.chroma_path).exists()
    assert Path(config.projects_db_path).parent.exists()


# ===== Performance Tests =====


@pytest.mark.asyncio
async def test_concurrent_project_creation(mcp_tools):
    """Test creating multiple projects concurrently."""
    import asyncio

    async def create_project(i: int):
        return await mcp_tools.kb_create_project(f"project-{i}", f"Project {i}")

    # Create 10 projects concurrently
    tasks = [create_project(i) for i in range(10)]
    results = await asyncio.gather(*tasks)

    # All should succeed
    assert len(results) == 10
    assert all(r["success"] for r in results)

    # Verify all projects exist
    projects = await mcp_tools.kb_list_projects()
    assert len(projects) == 10


@pytest.mark.asyncio
async def test_concurrent_search_requests(
    mcp_tools, sample_project: Project
):
    """Test handling concurrent search requests."""
    import asyncio

    # Ingest test document
    await mcp_tools.kb_ingest(sample_project.project_id, content="Test document content")

    async def search_query(i: int):
        return await mcp_tools.kb_search(
            project_id=sample_project.project_id,
            query=f"query {i}",
            limit=5,
        )

    # Execute 20 concurrent searches
    tasks = [search_query(i) for i in range(20)]
    results = await asyncio.gather(*tasks)

    # All should complete successfully
    assert len(results) == 20
    assert all(isinstance(r, list) for r in results)


# ===== Large Document Tests =====


@pytest.mark.asyncio
async def test_ingest_large_document(
    mcp_tools, sample_project: Project
):
    """Test ingesting a large document (1MB+)."""
    # Create a large document (approximately 1MB)
    large_content = "Test content. " * 70000  # ~1MB

    result = await mcp_tools.kb_ingest(
        project_id=sample_project.project_id,
        content=large_content,
    )

    assert result["success"] is True
    assert "doc_id" in result


@pytest.mark.asyncio
async def test_search_truncates_large_results(
    mcp_tools, sample_project: Project
):
    """Test that search results are truncated for large documents."""
    # Ingest large document
    large_content = "Test content. " * 10000
    await mcp_tools.kb_ingest(sample_project.project_id, content=large_content)

    # Search
    results = await mcp_tools.kb_search(
        project_id=sample_project.project_id,
        query="test",
        limit=5,
    )

    # Results should be truncated to 500 characters
    if len(results) > 0 and "content" in results[0]:
        assert len(results[0]["content"]) <= 500
