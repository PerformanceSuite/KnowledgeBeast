# MCP Export/Import Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use @superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement project export and import functionality for MCP server to enable backup, migration, and data portability

**Architecture:** Export serializes project metadata and ChromaDB collection data to JSON/ZIP format. Import deserializes and reconstitutes projects with validation, conflict resolution, and progress reporting.

**Tech Stack:** Python stdlib (json, zipfile), ChromaDB query API, KnowledgeBeast ProjectManager/VectorStore

---

## Task 1: Export - Write Failing Tests

**Files:**
- Create: `tests/mcp/test_export_import.py`

**Step 1: Write the failing test for basic project export**

```python
"""Tests for MCP export/import functionality."""

import json
import pytest
import tempfile
from pathlib import Path
from knowledgebeast.mcp.tools import KnowledgeBeastTools
from knowledgebeast.mcp.config import MCPConfig


@pytest.fixture
def mcp_tools(tmp_path):
    """Create MCP tools instance with temporary storage."""
    config = MCPConfig(
        projects_db_path=str(tmp_path / "test_projects.db"),
        chroma_path=str(tmp_path / "test_chroma"),
        cache_capacity=10
    )
    return KnowledgeBeastTools(config)


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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/mcp/test_export_import.py::test_export_project_basic -v`
Expected: FAIL with "Export functionality not yet implemented"

**Step 3: Commit failing tests**

```bash
git add tests/mcp/test_export_import.py
git commit -m "test: Add failing tests for MCP export functionality

- test_export_project_basic: Basic export to JSON
- test_export_project_not_found: Error handling
- test_export_empty_project: Edge case handling

Part of MCP export/import implementation (RED phase)"
```

---

## Task 2: Export - Implement Core Export Logic

**Files:**
- Modify: `knowledgebeast/mcp/tools.py:~250-280` (add new method)

**Step 1: Write the minimal implementation**

Add this method to `KnowledgeBeastTools` class in `tools.py`:

```python
async def kb_export_project(
    self,
    project_id: str,
    output_path: str,
    format: str = "json"
) -> Dict[str, Any]:
    """Export a project to a file.

    Args:
        project_id: Project identifier
        output_path: Path where export file will be saved
        format: Export format (json or yaml)

    Returns:
        Export result with statistics
    """
    try:
        # Validate format
        if format not in ["json", "yaml"]:
            return {"error": f"Unsupported format: {format}. Use 'json' or 'yaml'."}

        # Get project
        project = self.project_manager.get_project(project_id)
        if not project:
            return {"error": f"Project not found: {project_id}"}

        # Get project documents from ChromaDB
        vector_store = VectorStore(
            persist_directory=self.config.chroma_path,
            collection_name=project.collection_name
        )

        # Query all documents from collection
        collection_data = vector_store.collection.get(
            include=["documents", "metadatas", "embeddings"]
        )

        # Build export data structure
        export_data = {
            "version": "1.0",
            "exported_at": datetime.utcnow().isoformat(),
            "project": project.to_dict(),
            "documents": [],
            "embeddings": []
        }

        # Add documents and embeddings
        if collection_data["ids"]:
            for i, doc_id in enumerate(collection_data["ids"]):
                export_data["documents"].append({
                    "id": doc_id,
                    "content": collection_data["documents"][i] if collection_data["documents"] else "",
                    "metadata": collection_data["metadatas"][i] if collection_data["metadatas"] else {}
                })

                if collection_data["embeddings"]:
                    export_data["embeddings"].append({
                        "id": doc_id,
                        "vector": collection_data["embeddings"][i]
                    })

        # Write to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            with open(output_file, 'w') as f:
                json.dump(export_data, f, indent=2)
        elif format == "yaml":
            import yaml
            with open(output_file, 'w') as f:
                yaml.safe_dump(export_data, f)

        logger.info(f"Exported project {project_id}: {len(export_data['documents'])} documents")

        return {
            "project_id": project_id,
            "file_path": str(output_file),
            "format": format,
            "document_count": len(export_data["documents"]),
            "file_size_bytes": output_file.stat().st_size
        }

    except Exception as e:
        logger.error(f"Export error: {e}", exc_info=True)
        return {"error": str(e)}
```

**Step 2: Add necessary imports**

At top of `knowledgebeast/mcp/tools.py`:

```python
from datetime import datetime
from knowledgebeast.core.vector_store import VectorStore
```

**Step 3: Update server.py to use new implementation**

Modify `knowledgebeast/mcp/server.py:194-214`:

```python
@mcp.tool()
async def kb_export_project(
    project_id: str, output_path: str, format: str = "json"
) -> Dict[str, Any]:
    """Export a project to a file.

    Export project configuration and documents for backup or transfer.

    Args:
        project_id: Project identifier
        output_path: Path where export file will be saved
        format: Export format - "json" or "yaml" (default: json)

    Returns:
        Export result with file path and statistics
    """
    return await tools.kb_export_project(
        project_id=project_id,
        output_path=output_path,
        format=format
    )
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/mcp/test_export_import.py -k export -v`
Expected: PASS (all export tests green)

**Step 5: Commit working export**

```bash
git add knowledgebeast/mcp/tools.py knowledgebeast/mcp/server.py
git commit -m "feat: Implement MCP project export functionality

- Add kb_export_project method to KnowledgeBeastTools
- Export project metadata, documents, and embeddings to JSON/YAML
- Handle errors gracefully (project not found, invalid format)
- Support empty projects

Part of MCP export/import implementation (GREEN phase)"
```

---

## Task 3: Import - Write Failing Tests

**Files:**
- Modify: `tests/mcp/test_export_import.py:~90` (add import tests)

**Step 1: Write failing tests for import functionality**

Add to existing `tests/mcp/test_export_import.py`:

```python
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
    assert docs["total"] == 1


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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/mcp/test_export_import.py::test_import_project_basic -v`
Expected: FAIL with "Import functionality not yet implemented"

**Step 3: Commit failing import tests**

```bash
git add tests/mcp/test_export_import.py
git commit -m "test: Add failing tests for MCP import functionality

- test_import_project_basic: Round-trip export/import
- test_import_project_file_not_found: Error handling
- test_import_project_invalid_json: Validation
- test_import_project_auto_name: Auto-naming

Part of MCP export/import implementation (RED phase)"
```

---

## Task 4: Import - Implement Core Import Logic

**Files:**
- Modify: `knowledgebeast/mcp/tools.py:~350-420` (add new method)

**Step 1: Write minimal import implementation**

Add this method to `KnowledgeBeastTools` class:

```python
async def kb_import_project(
    self,
    file_path: str,
    project_name: Optional[str] = None
) -> Dict[str, Any]:
    """Import a project from an exported file.

    Args:
        file_path: Path to export file (JSON or YAML)
        project_name: Optional name for imported project

    Returns:
        Import result with new project ID and statistics
    """
    try:
        # Check file exists
        import_file = Path(file_path)
        if not import_file.exists():
            return {"error": f"File not found: {file_path}"}

        # Determine format from extension
        format_type = "json" if import_file.suffix == ".json" else "yaml"

        # Load export data
        try:
            if format_type == "json":
                with open(import_file) as f:
                    export_data = json.load(f)
            else:
                import yaml
                with open(import_file) as f:
                    export_data = yaml.safe_load(f)
        except (json.JSONDecodeError, yaml.YAMLError) as e:
            return {"error": f"Invalid {format_type.upper()} file: {str(e)}"}

        # Validate export data structure
        required_keys = ["version", "project", "documents", "embeddings"]
        if not all(key in export_data for key in required_keys):
            return {"error": "Invalid export file structure"}

        # Get original project data
        original_project = export_data["project"]

        # Generate new project name if not provided
        if not project_name:
            project_name = f"{original_project['name']} (imported)"

        # Create new project
        new_project = self.project_manager.create_project(
            name=project_name,
            description=original_project.get("description", ""),
            embedding_model=original_project.get("embedding_model", "all-MiniLM-L6-v2"),
            metadata={
                **original_project.get("metadata", {}),
                "imported_from": original_project["project_id"],
                "imported_at": datetime.utcnow().isoformat()
            }
        )

        # Get vector store for new project
        vector_store = VectorStore(
            persist_directory=self.config.chroma_path,
            collection_name=new_project.collection_name
        )

        embedding_engine = EmbeddingEngine(
            model_name=new_project.embedding_model,
            cache_size=self.config.cache_capacity
        )

        # Import documents and embeddings
        doc_count = 0
        if export_data["documents"]:
            ids = []
            documents = []
            metadatas = []
            embeddings = []

            # Build parallel arrays for ChromaDB
            for doc in export_data["documents"]:
                ids.append(doc["id"])
                documents.append(doc["content"])
                metadatas.append(doc.get("metadata", {}))

            # Get embeddings (use existing if available, otherwise regenerate)
            embedding_map = {e["id"]: e["vector"] for e in export_data["embeddings"]}
            for doc_id in ids:
                if doc_id in embedding_map:
                    embeddings.append(embedding_map[doc_id])
                else:
                    # Regenerate embedding for this document
                    idx = ids.index(doc_id)
                    vec = embedding_engine.embed(documents[idx])
                    embeddings.append(vec.tolist())

            # Add to collection
            vector_store.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings
            )

            doc_count = len(ids)

        logger.info(f"Imported project: {new_project.project_id} ({doc_count} documents)")

        return {
            "project_id": new_project.project_id,
            "name": new_project.name,
            "document_count": doc_count,
            "source_file": file_path,
            "original_project_id": original_project["project_id"]
        }

    except Exception as e:
        logger.error(f"Import error: {e}", exc_info=True)
        return {"error": str(e)}
```

**Step 2: Add import to EmbeddingEngine**

Add at top of `tools.py` if not present:

```python
from knowledgebeast.core.embeddings import EmbeddingEngine
```

**Step 3: Update server.py to use implementation**

Modify `knowledgebeast/mcp/server.py:217-235`:

```python
@mcp.tool()
async def kb_import_project(
    file_path: str, project_name: Optional[str] = None
) -> Dict[str, Any]:
    """Import a project from a file.

    Import a previously exported project or load from a template.

    Args:
        file_path: Path to import file (JSON or YAML)
        project_name: Optional name for imported project (generates if not provided)

    Returns:
        Import result with new project ID and statistics
    """
    return await tools.kb_import_project(
        file_path=file_path,
        project_name=project_name
    )
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/mcp/test_export_import.py -v`
Expected: PASS (all tests green)

**Step 5: Commit working import**

```bash
git add knowledgebeast/mcp/tools.py knowledgebeast/mcp/server.py
git commit -m "feat: Implement MCP project import functionality

- Add kb_import_project method to KnowledgeBeastTools
- Load project metadata, documents, and embeddings from file
- Auto-generate project name if not provided
- Validate import file structure
- Handle JSON and YAML formats
- Regenerate embeddings if missing

Part of MCP export/import implementation (GREEN phase)"
```

---

## Task 5: Add ZIP Compression Support

**Files:**
- Modify: `tests/mcp/test_export_import.py:~200` (add zip tests)
- Modify: `knowledgebeast/mcp/tools.py:~280,~420` (update methods)

**Step 1: Write failing test for ZIP export**

Add to `tests/mcp/test_export_import.py`:

```python
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
```

**Step 2: Run test to verify failure**

Run: `pytest tests/mcp/test_export_import.py::test_export_import_zip_format -v`
Expected: FAIL with "Unsupported format: zip"

**Step 3: Implement ZIP support in export**

Modify `kb_export_project` in `tools.py` to add ZIP handling:

```python
# In kb_export_project method, after line "if format not in...":
if format not in ["json", "yaml", "zip"]:
    return {"error": f"Unsupported format: {format}. Use 'json', 'yaml', or 'zip'."}

# After building export_data, replace file writing section with:
if format == "zip":
    # Create ZIP with JSON inside
    with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Write project data
        zf.writestr("project.json", json.dumps(export_data, indent=2))
elif format == "json":
    with open(output_file, 'w') as f:
        json.dump(export_data, f, indent=2)
elif format == "yaml":
    import yaml
    with open(output_file, 'w') as f:
        yaml.safe_dump(export_data, f)
```

Add import at top:

```python
import zipfile
```

**Step 4: Implement ZIP support in import**

Modify `kb_import_project` in `tools.py`:

```python
# After "Determine format from extension":
format_type = "zip" if import_file.suffix == ".zip" else (
    "json" if import_file.suffix == ".json" else "yaml"
)

# Replace "Load export data" section:
try:
    if format_type == "zip":
        with zipfile.ZipFile(import_file, 'r') as zf:
            # Read project.json from ZIP
            export_data = json.loads(zf.read("project.json"))
    elif format_type == "json":
        with open(import_file) as f:
            export_data = json.load(f)
    else:
        import yaml
        with open(import_file) as f:
            export_data = yaml.safe_load(f)
except (json.JSONDecodeError, yaml.YAMLError, zipfile.BadZipFile) as e:
    return {"error": f"Invalid {format_type.upper()} file: {str(e)}"}
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/mcp/test_export_import.py::test_export_import_zip_format -v`
Expected: PASS

**Step 6: Commit ZIP support**

```bash
git add tests/mcp/test_export_import.py knowledgebeast/mcp/tools.py
git commit -m "feat: Add ZIP compression support for export/import

- Support 'zip' format in kb_export_project
- Compress JSON data with ZIP_DEFLATED
- Auto-detect ZIP format in kb_import_project
- Reduces file size for large projects

Part of MCP export/import implementation"
```

---

## Task 6: Add Progress Reporting (Optional Enhancement)

**Files:**
- Modify: `knowledgebeast/mcp/tools.py:~280,~420` (add progress callbacks)

**Step 1: Add progress reporting to export**

Add optional progress callback parameter and logging:

```python
# In kb_export_project, add logging for progress:
logger.info(f"Exporting project {project_id}...")
logger.info(f"Fetching {len(export_data['documents'])} documents from ChromaDB...")
logger.info(f"Writing export file: {output_file}")
logger.info(f"Export complete: {output_file.stat().st_size} bytes")
```

**Step 2: Add progress reporting to import**

```python
# In kb_import_project, add logging:
logger.info(f"Importing from: {file_path}")
logger.info(f"Creating new project: {project_name}")
logger.info(f"Importing {len(export_data['documents'])} documents...")
logger.info(f"Import complete: {new_project.project_id}")
```

**Step 3: Commit progress reporting**

```bash
git add knowledgebeast/mcp/tools.py
git commit -m "feat: Add progress logging to export/import

- Log export stages (fetch, write, complete)
- Log import stages (load, create, ingest)
- Helps debug large project operations

Part of MCP export/import implementation"
```

---

## Task 7: Integration Tests

**Files:**
- Create: `tests/integration/test_export_import_integration.py`

**Step 1: Write integration test for full workflow**

```python
"""Integration tests for export/import workflow."""

import pytest
from knowledgebeast.mcp.tools import KnowledgeBeastTools
from knowledgebeast.mcp.config import MCPConfig


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_export_import_workflow(tmp_path):
    """Test complete export/import workflow with real data."""
    # Setup
    config = MCPConfig(
        projects_db_path=str(tmp_path / "projects.db"),
        chroma_path=str(tmp_path / "chroma"),
        cache_capacity=10
    )
    tools = KnowledgeBeastTools(config)

    # Create project with realistic data
    project_result = await tools.kb_create_project(
        name="Knowledge Base",
        description="Documentation and code examples",
        metadata={"team": "engineering", "version": "1.0"}
    )
    project_id = project_result["project_id"]

    # Ingest multiple documents
    documents = [
        ("Getting Started Guide", "How to get started with the system..."),
        ("API Reference", "Complete API documentation..."),
        ("Code Examples", "Example code snippets for common tasks..."),
    ]

    for name, content in documents:
        await tools.kb_ingest(
            project_id=project_id,
            content=content,
            metadata={"title": name}
        )

    # Verify search works before export
    search_before = await tools.kb_search(
        project_id=project_id,
        query="API documentation",
        mode="keyword",
        limit=5
    )
    assert len(search_before) > 0

    # Export project
    export_path = tmp_path / "backup.json"
    export_result = await tools.kb_export_project(
        project_id=project_id,
        output_path=str(export_path),
        format="json"
    )

    assert "error" not in export_result
    assert export_result["document_count"] == 3

    # Import as new project
    import_result = await tools.kb_import_project(
        file_path=str(export_path),
        project_name="Restored Knowledge Base"
    )

    assert "error" not in import_result
    new_project_id = import_result["project_id"]

    # Verify search works on imported project
    search_after = await tools.kb_search(
        project_id=new_project_id,
        query="API documentation",
        mode="keyword",
        limit=5
    )

    assert len(search_after) > 0
    assert len(search_after) == len(search_before)

    # Verify project metadata preserved
    projects = await tools.kb_list_projects()
    restored = next(p for p in projects if p["project_id"] == new_project_id)
    assert restored["name"] == "Restored Knowledge Base"
    assert "imported_from" in restored["metadata"]
```

**Step 2: Run integration test**

Run: `pytest tests/integration/test_export_import_integration.py -v -m integration`
Expected: PASS

**Step 3: Commit integration tests**

```bash
git add tests/integration/test_export_import_integration.py
git commit -m "test: Add integration tests for export/import workflow

- Test full round-trip with real data
- Verify search functionality preserved
- Verify metadata preserved
- Test with multiple documents

Part of MCP export/import implementation"
```

---

## Task 8: Documentation

**Files:**
- Create: `docs/mcp/export-import-guide.md`

**Step 1: Write user-facing documentation**

```markdown
# MCP Export/Import Guide

## Overview

KnowledgeBeast MCP server supports exporting and importing projects for backup, migration, and data portability.

## Export a Project

### Basic Export (JSON)

```python
result = await kb_export_project(
    project_id="your-project-id",
    output_path="/path/to/backup.json",
    format="json"
)
```

### Compressed Export (ZIP)

For large projects, use ZIP compression:

```python
result = await kb_export_project(
    project_id="your-project-id",
    output_path="/path/to/backup.zip",
    format="zip"
)
```

### Export Data Structure

Exports contain:
- Project metadata (name, description, embedding model, etc.)
- All documents with content and metadata
- Vector embeddings
- Timestamps and version information

## Import a Project

### Basic Import

```python
result = await kb_import_project(
    file_path="/path/to/backup.json",
    project_name="Restored Project"
)
```

### Auto-Generated Name

If you don't specify a name, it will be auto-generated:

```python
result = await kb_import_project(
    file_path="/path/to/backup.json"
)
# Creates project named "Original Name (imported)"
```

## Use Cases

### Backup and Restore

```bash
# Backup
kb_export_project(project_id, "/backups/daily.zip", "zip")

# Restore
kb_import_project("/backups/daily.zip", "Restored")
```

### Project Migration

Export from one environment, import to another:

```bash
# On server A
kb_export_project(project_id, "/tmp/project.json")

# Copy file to server B, then:
kb_import_project("/tmp/project.json", "Migrated Project")
```

### Project Templates

Export a well-configured project to use as a template:

```bash
kb_export_project(template_id, "/templates/base-project.json")
kb_import_project("/templates/base-project.json", "New Project from Template")
```

## Best Practices

1. **Use ZIP for Large Projects** - Reduces file size significantly
2. **Include Metadata** - Helps track project lineage
3. **Regular Backups** - Export projects regularly
4. **Test Imports** - Verify imports work before deleting originals
5. **Version Control** - Store exports in version control for history

## Error Handling

Common errors:

- **Project not found** - Check project ID exists
- **File not found** - Verify file path is correct
- **Invalid format** - Ensure JSON/YAML/ZIP is valid
- **Disk space** - Ensure sufficient space for export

## Format Support

| Format | Extension | Compression | Human Readable |
|--------|-----------|-------------|----------------|
| JSON   | .json     | No          | Yes            |
| YAML   | .yaml     | No          | Yes            |
| ZIP    | .zip      | Yes         | No             |
```

**Step 2: Commit documentation**

```bash
git add docs/mcp/export-import-guide.md
git commit -m "docs: Add MCP export/import user guide

- Usage examples for export and import
- Format comparison table
- Best practices and use cases
- Error handling guide

Part of MCP export/import implementation"
```

---

## Task 9: Update MCP Server Metadata

**Files:**
- Modify: `knowledgebeast/mcp/server.py:309-312` (update tool count)

**Step 1: Update server logging message**

```python
# Line 309-312 in server.py, update comment:
logger.info(
    f"MCP server created: {config.server_name} v{config.server_version} "
    f"(12 tools registered)"  # Keep at 12, export/import replace stubs
)
```

**Step 2: Commit metadata update**

```bash
git add knowledgebeast/mcp/server.py
git commit -m "docs: Update MCP server tool count comment

Export/import tools now fully implemented (were stubs)

Part of MCP export/import implementation"
```

---

## Verification Checklist

After completing all tasks, verify:

- [ ] All tests pass: `pytest tests/mcp/test_export_import.py -v`
- [ ] Integration tests pass: `pytest tests/integration/test_export_import_integration.py -v -m integration`
- [ ] Export creates valid JSON/YAML/ZIP files
- [ ] Import successfully restores projects
- [ ] Search works on imported projects
- [ ] Error handling works (file not found, invalid format, etc.)
- [ ] Documentation is complete and accurate
- [ ] Code follows existing patterns (@superpowers:testing-anti-patterns)
- [ ] No test-only methods in production code
- [ ] Progress logging works

## Success Criteria

- ✅ Export function replaces TODO stub
- ✅ Import function replaces TODO stub
- ✅ Round-trip export/import preserves data
- ✅ Multiple format support (JSON, YAML, ZIP)
- ✅ Error handling comprehensive
- ✅ Tests achieve >90% coverage
- ✅ Documentation complete
- ✅ No regressions in existing MCP tests

## Estimated Completion Time

- Tasks 1-4 (Core functionality): 2-3 hours
- Tasks 5-6 (Enhancements): 1 hour
- Tasks 7-9 (Testing & Docs): 1-2 hours
- **Total**: 4-6 hours

## Dependencies

- Existing: `chromadb`, `pydantic`, `fastmcp`
- New: `pyyaml` (for YAML support, optional)

Add to requirements if YAML needed:
```bash
pyyaml>=6.0
```

---

**Plan Status**: Ready for execution
**Created**: 2025-10-24
**TDD Workflow**: RED → GREEN → REFACTOR
**Review Skills**: @superpowers:test-driven-development, @superpowers:testing-anti-patterns
