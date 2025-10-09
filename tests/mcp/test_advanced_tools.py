"""Tests for advanced MCP tools.

Tests cover:
- kb_export_project
- kb_import_project
- kb_project_health
- kb_batch_ingest
- kb_delete_document
"""

import asyncio
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Avoid importing the mcp package that requires server.py
sys.modules["knowledgebeast.mcp.server"] = MagicMock()

from knowledgebeast.mcp.config import MCPConfig
from knowledgebeast.mcp.tools import KnowledgeBeastTools
from knowledgebeast.core.project_manager import Project


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mcp_config(temp_dir):
    """Create MCP configuration for tests."""
    return MCPConfig(
        projects_db_path=str(temp_dir / "projects.db"),
        chroma_path=str(temp_dir / "chroma_db"),
        cache_capacity=10,
    )


@pytest.fixture
def tools(mcp_config):
    """Create KnowledgeBeastTools instance."""
    with patch("knowledgebeast.monitoring.health.ProjectHealthMonitor"):
        return KnowledgeBeastTools(mcp_config)


@pytest.fixture
def mock_project():
    """Create mock project."""
    return Project(
        project_id="test-project-123",
        name="Test Project",
        description="Test project description",
        embedding_model="all-MiniLM-L6-v2",
    )


# ===== Export Project Tests =====


@pytest.mark.asyncio
async def test_export_project_success(tools, mock_project, temp_dir):
    """Test successful project export."""
    output_path = temp_dir / "export.zip"

    # Mock project manager
    tools.project_manager.get_project = MagicMock(return_value=mock_project)
    tools.project_manager.export_project = MagicMock(return_value=str(output_path))

    # Call export
    result = await tools.kb_export_project(
        project_id="test-project-123", output_path=str(output_path)
    )

    # Verify success
    assert result["success"] is True
    assert result["project_id"] == "test-project-123"
    assert result["project_name"] == "Test Project"
    assert "output_path" in result

    # Verify export was called
    tools.project_manager.export_project.assert_called_once_with(
        "test-project-123", str(output_path)
    )


@pytest.mark.asyncio
async def test_export_project_not_found(tools):
    """Test export with non-existent project."""
    tools.project_manager.get_project = MagicMock(return_value=None)

    result = await tools.kb_export_project(
        project_id="nonexistent", output_path="/tmp/test.zip"
    )

    assert "error" in result
    assert "Project not found" in result["error"]
    assert result["error_type"] == "ProjectNotFound"


@pytest.mark.asyncio
async def test_export_project_validation_error(tools):
    """Test export with invalid inputs."""
    # Empty project_id
    result = await tools.kb_export_project(project_id="", output_path="/tmp/test.zip")
    assert "error" in result
    assert result["error_type"] == "ValidationError"

    # None project_id
    result = await tools.kb_export_project(
        project_id=None, output_path="/tmp/test.zip"
    )
    assert "error" in result
    assert result["error_type"] == "ValidationError"


# ===== Import Project Tests =====


@pytest.mark.asyncio
async def test_import_project_success(tools, mock_project, temp_dir):
    """Test successful project import."""
    zip_path = temp_dir / "export.zip"

    # Create a valid ZIP file
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"version": "2.3.0"}))

    # Mock project manager
    tools.project_manager.import_project = MagicMock(return_value="imported-id-123")
    tools.project_manager.get_project = MagicMock(return_value=mock_project)

    # Call import
    result = await tools.kb_import_project(
        zip_path=str(zip_path), new_project_name="Imported Project"
    )

    # Verify success
    assert result["success"] is True
    assert result["project_id"] == "imported-id-123"
    assert result["project_name"] == "Test Project"

    # Verify import was called
    tools.project_manager.import_project.assert_called_once()


@pytest.mark.asyncio
async def test_import_project_file_not_found(tools):
    """Test import with non-existent file."""
    result = await tools.kb_import_project(zip_path="/nonexistent/file.zip")

    assert "error" in result
    assert "not found" in result["error"].lower()
    assert result["error_type"] == "ValidationError"


@pytest.mark.asyncio
async def test_import_project_invalid_extension(tools, temp_dir):
    """Test import with non-ZIP file."""
    txt_file = temp_dir / "test.txt"
    txt_file.write_text("not a zip")

    result = await tools.kb_import_project(zip_path=str(txt_file))

    assert "error" in result
    assert result["error_type"] == "ValidationError"


@pytest.mark.asyncio
async def test_import_project_conflict_resolution(tools, temp_dir):
    """Test import with conflict resolution."""
    zip_path = temp_dir / "export.zip"

    # Create a valid ZIP file
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"version": "2.3.0"}))

    # Mock project manager
    tools.project_manager.import_project = MagicMock(return_value="imported-id-123")
    tools.project_manager.get_project = MagicMock(
        return_value=Project(
            project_id="imported-id-123",
            name="Imported Project",
            description="",
            embedding_model="all-MiniLM-L6-v2",
        )
    )

    # Test skip (default)
    result = await tools.kb_import_project(
        zip_path=str(zip_path), conflict_resolution="skip"
    )
    assert result["success"] is True
    args, kwargs = tools.project_manager.import_project.call_args
    assert kwargs["overwrite"] is False

    # Test overwrite
    result = await tools.kb_import_project(
        zip_path=str(zip_path), conflict_resolution="overwrite"
    )
    assert result["success"] is True
    args, kwargs = tools.project_manager.import_project.call_args
    assert kwargs["overwrite"] is True


# ===== Project Health Tests =====


@pytest.mark.asyncio
async def test_project_health_success(tools):
    """Test successful health check."""
    health_data = {
        "project_id": "test-project-123",
        "project_name": "Test Project",
        "status": "healthy",
        "metrics": {
            "document_count": 100,
            "total_queries": 500,
            "avg_query_latency_ms": 50.5,
        },
        "alerts": [],
    }

    tools.health_monitor.get_project_health = MagicMock(return_value=health_data)

    result = await tools.kb_project_health(project_id="test-project-123")

    assert result["status"] == "healthy"
    assert result["project_id"] == "test-project-123"
    assert "metrics" in result
    assert result["metrics"]["document_count"] == 100


@pytest.mark.asyncio
async def test_project_health_validation_error(tools):
    """Test health check with invalid project_id."""
    result = await tools.kb_project_health(project_id="")

    assert "error" in result
    assert result["error_type"] == "ValidationError"


@pytest.mark.asyncio
async def test_project_health_with_alerts(tools):
    """Test health check with alerts."""
    health_data = {
        "project_id": "test-project-123",
        "project_name": "Test Project",
        "status": "degraded",
        "metrics": {"avg_query_latency_ms": 600.0},
        "alerts": [
            {
                "severity": "warning",
                "message": "High average query latency: 600ms",
            }
        ],
    }

    tools.health_monitor.get_project_health = MagicMock(return_value=health_data)

    result = await tools.kb_project_health(project_id="test-project-123")

    assert result["status"] == "degraded"
    assert len(result["alerts"]) == 1
    assert result["alerts"][0]["severity"] == "warning"


# ===== Batch Ingest Tests =====


@pytest.mark.asyncio
async def test_batch_ingest_success(tools, mock_project, temp_dir):
    """Test successful batch ingestion."""
    # Create test files
    file1 = temp_dir / "file1.txt"
    file2 = temp_dir / "file2.txt"
    file1.write_text("Content 1")
    file2.write_text("Content 2")

    file_paths = [str(file1), str(file2)]

    # Mock project manager and components
    tools.project_manager.get_project = MagicMock(return_value=mock_project)

    mock_vector_store = MagicMock()
    mock_embedding_engine = MagicMock()
    mock_embedding_engine.embed = MagicMock(return_value=[0.1, 0.2, 0.3])

    with patch("knowledgebeast.mcp.tools.VectorStore", return_value=mock_vector_store):
        with patch(
            "knowledgebeast.mcp.tools.EmbeddingEngine", return_value=mock_embedding_engine
        ):
            result = await tools.kb_batch_ingest(
                project_id="test-project-123", file_paths=file_paths
            )

    # Verify success
    assert result["success"] is True
    assert result["total_files"] == 2
    assert result["success_count"] == 2
    assert result["failed_count"] == 0
    assert len(result["doc_ids"]) == 2


@pytest.mark.asyncio
async def test_batch_ingest_partial_failure(tools, mock_project, temp_dir):
    """Test batch ingestion with some failures."""
    # Create only one file
    file1 = temp_dir / "file1.txt"
    file1.write_text("Content 1")

    file_paths = [str(file1), "/nonexistent/file.txt"]

    # Mock project manager
    tools.project_manager.get_project = MagicMock(return_value=mock_project)

    mock_vector_store = MagicMock()
    mock_embedding_engine = MagicMock()
    mock_embedding_engine.embed = MagicMock(return_value=[0.1, 0.2, 0.3])

    with patch("knowledgebeast.mcp.tools.VectorStore", return_value=mock_vector_store):
        with patch(
            "knowledgebeast.mcp.tools.EmbeddingEngine", return_value=mock_embedding_engine
        ):
            result = await tools.kb_batch_ingest(
                project_id="test-project-123", file_paths=file_paths
            )

    # Verify partial success
    assert result["success"] is True
    assert result["total_files"] == 2
    assert result["success_count"] == 1
    assert result["failed_count"] == 1
    assert len(result["errors"]) == 1


@pytest.mark.asyncio
async def test_batch_ingest_validation_error(tools):
    """Test batch ingest with validation errors."""
    # Empty file list
    result = await tools.kb_batch_ingest(project_id="test-project-123", file_paths=[])
    assert "error" in result
    assert result["error_type"] == "ValidationError"

    # Invalid project_id
    result = await tools.kb_batch_ingest(project_id="", file_paths=["file.txt"])
    assert "error" in result
    assert result["error_type"] == "ValidationError"

    # Non-list file_paths
    result = await tools.kb_batch_ingest(
        project_id="test-project-123", file_paths="not-a-list"
    )
    assert "error" in result
    assert result["error_type"] == "ValidationError"


# ===== Delete Document Tests =====


@pytest.mark.asyncio
async def test_delete_document_success(tools, mock_project):
    """Test successful document deletion."""
    # Mock project manager
    tools.project_manager.get_project = MagicMock(return_value=mock_project)

    # Mock vector store
    mock_vector_store = MagicMock()
    mock_vector_store.get = MagicMock(return_value={"ids": ["doc-123"]})
    mock_vector_store.delete = MagicMock()

    with patch("knowledgebeast.mcp.tools.VectorStore", return_value=mock_vector_store):
        result = await tools.kb_delete_document(
            project_id="test-project-123", doc_id="doc-123"
        )

    # Verify success
    assert result["success"] is True
    assert result["doc_id"] == "doc-123"
    assert result["project_id"] == "test-project-123"

    # Verify delete was called
    mock_vector_store.delete.assert_called_once_with(ids="doc-123")


@pytest.mark.asyncio
async def test_delete_document_not_found(tools, mock_project):
    """Test deletion of non-existent document."""
    # Mock project manager
    tools.project_manager.get_project = MagicMock(return_value=mock_project)

    # Mock vector store - document not found
    mock_vector_store = MagicMock()
    mock_vector_store.get = MagicMock(return_value={"ids": []})

    with patch("knowledgebeast.mcp.tools.VectorStore", return_value=mock_vector_store):
        result = await tools.kb_delete_document(
            project_id="test-project-123", doc_id="nonexistent"
        )

    # Verify error
    assert "error" in result
    assert "Document not found" in result["error"]
    assert result["error_type"] == "DocumentNotFound"


@pytest.mark.asyncio
async def test_delete_document_validation_error(tools):
    """Test document deletion with validation errors."""
    # Empty doc_id
    result = await tools.kb_delete_document(project_id="test-project-123", doc_id="")
    assert "error" in result
    assert result["error_type"] == "ValidationError"

    # Empty project_id
    result = await tools.kb_delete_document(project_id="", doc_id="doc-123")
    assert "error" in result
    assert result["error_type"] == "ValidationError"


@pytest.mark.asyncio
async def test_delete_document_project_not_found(tools):
    """Test document deletion with non-existent project."""
    tools.project_manager.get_project = MagicMock(return_value=None)

    result = await tools.kb_delete_document(
        project_id="nonexistent", doc_id="doc-123"
    )

    assert "error" in result
    assert "Project not found" in result["error"]
    assert result["error_type"] == "ProjectNotFound"
