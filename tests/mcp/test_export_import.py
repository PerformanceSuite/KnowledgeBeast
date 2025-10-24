"""Tests for MCP export/import functionality."""

import json
import pytest
from pathlib import Path

# Use fixtures from conftest (mocked for fast tests)


@pytest.mark.asyncio
async def test_export_project_basic(mcp_tools, tmp_path):
    """Test basic project export to JSON."""
    # Create a test project
    result = await mcp_tools.kb_create_project(
        name="Test Export Project",
        description="Project for testing export",
        embedding_model="all-MiniLM-L6-v2",
        metadata={"test": True}
    )
    project_id = result["project_id"]

    # Ingest a test document
    await mcp_tools.kb_ingest(
        project_id=project_id,
        content="This is test content for export.",
        metadata={"doc_type": "test"}
    )

    # Export the project
    export_path = tmp_path / "export.json"
    export_result = await mcp_tools.kb_export_project(
        project_id=project_id,
        output_path=str(export_path),
        format="json"
    )

    # Verify export succeeded
    assert "error" not in export_result
    assert export_result["project_id"] == project_id
    assert export_result["document_count"] == 1
    assert export_result["file_path"] == str(export_path)
    assert export_path.exists()

    # Verify export file structure
    with open(export_path) as f:
        export_data = json.load(f)

    assert export_data["version"] == "1.0"
    assert export_data["project"]["project_id"] == project_id
    assert export_data["project"]["name"] == "Test Export Project"
    assert len(export_data["documents"]) == 1
    assert len(export_data["embeddings"]) == 1


@pytest.mark.asyncio
async def test_export_project_not_found(mcp_tools, tmp_path):
    """Test export fails gracefully for nonexistent project."""
    export_path = tmp_path / "export.json"
    result = await mcp_tools.kb_export_project(
        project_id="nonexistent-id",
        output_path=str(export_path),
        format="json"
    )

    assert "error" in result
    assert "not found" in result["error"].lower()
    assert not export_path.exists()


@pytest.mark.asyncio
async def test_export_empty_project(mcp_tools, tmp_path):
    """Test export of project with no documents."""
    # Create empty project
    result = await mcp_tools.kb_create_project(
        name="Empty Project",
        description="No documents"
    )
    project_id = result["project_id"]

    # Export
    export_path = tmp_path / "empty_export.json"
    export_result = await mcp_tools.kb_export_project(
        project_id=project_id,
        output_path=str(export_path),
        format="json"
    )

    assert "error" not in export_result
    assert export_result["document_count"] == 0

    # Verify structure
    with open(export_path) as f:
        export_data = json.load(f)

    assert len(export_data["documents"]) == 0
    assert len(export_data["embeddings"]) == 0
