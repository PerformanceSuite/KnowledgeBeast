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


@pytest.mark.asyncio
async def test_import_project_basic(mcp_tools, tmp_path):
    """Test basic project import from JSON."""
    # Create and export a project first
    create_result = await mcp_tools.kb_create_project(
        name="Original Project",
        description="To be exported and imported"
    )
    original_id = create_result["project_id"]

    await mcp_tools.kb_ingest(
        project_id=original_id,
        content="Test document content",
        metadata={"source": "test"}
    )

    export_path = tmp_path / "export.json"
    await mcp_tools.kb_export_project(
        project_id=original_id,
        output_path=str(export_path),
        format="json"
    )

    # Import as new project
    import_result = await mcp_tools.kb_import_project(
        file_path=str(export_path),
        project_name="Imported Project"
    )

    assert "error" not in import_result
    assert import_result["project_id"] != original_id  # New ID
    assert import_result["document_count"] == 1
    assert import_result["source_file"] == str(export_path)

    # Verify imported project exists and has data
    projects = await mcp_tools.kb_list_projects()
    imported_project = next(p for p in projects if p["project_id"] == import_result["project_id"])
    assert imported_project["name"] == "Imported Project"

    # Verify document was imported
    docs = await mcp_tools.kb_list_documents(project_id=import_result["project_id"])
    assert docs["total_documents"] == 1


@pytest.mark.asyncio
async def test_import_project_file_not_found(mcp_tools):
    """Test import fails for nonexistent file."""
    result = await mcp_tools.kb_import_project(
        file_path="/nonexistent/file.json"
    )

    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_import_project_invalid_json(mcp_tools, tmp_path):
    """Test import fails for invalid JSON."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{invalid json")

    result = await mcp_tools.kb_import_project(
        file_path=str(bad_file)
    )

    assert "error" in result
    assert "invalid" in result["error"].lower() or "parse" in result["error"].lower()


@pytest.mark.asyncio
async def test_import_project_auto_name(mcp_tools, tmp_path):
    """Test import generates name if not provided."""
    # Create minimal export
    create_result = await mcp_tools.kb_create_project(name="Test")
    original_id = create_result["project_id"]

    export_path = tmp_path / "export.json"
    await mcp_tools.kb_export_project(
        project_id=original_id,
        output_path=str(export_path)
    )

    # Import without specifying name
    import_result = await mcp_tools.kb_import_project(
        file_path=str(export_path)
    )

    assert "error" not in import_result
    # Should generate name from original: "Test (imported)"
    projects = await mcp_tools.kb_list_projects()
    imported = next(p for p in projects if p["project_id"] == import_result["project_id"])
    assert "import" in imported["name"].lower()


@pytest.mark.asyncio
async def test_export_import_zip_format(mcp_tools, tmp_path):
    """Test export/import with ZIP compression."""
    # Create project with multiple documents
    result = await mcp_tools.kb_create_project(name="Zip Test")
    project_id = result["project_id"]

    for i in range(5):
        await mcp_tools.kb_ingest(
            project_id=project_id,
            content=f"Document {i} content " * 100,  # Large content
            metadata={"index": i}
        )

    # Export as ZIP
    export_path = tmp_path / "export.zip"
    export_result = await mcp_tools.kb_export_project(
        project_id=project_id,
        output_path=str(export_path),
        format="zip"
    )

    assert "error" not in export_result
    assert export_path.exists()
    assert export_path.suffix == ".zip"

    # Verify it's a valid ZIP
    import zipfile
    assert zipfile.is_zipfile(export_path)

    # Import from ZIP
    import_result = await mcp_tools.kb_import_project(
        file_path=str(export_path),
        project_name="Imported from ZIP"
    )

    assert "error" not in import_result
    assert import_result["document_count"] == 5
