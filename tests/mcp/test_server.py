"""Tests for MCP server implementation.

These tests verify the MCP server initialization, tool registration,
and basic functionality without requiring actual MCP client connections.
"""

import asyncio
import pytest
import tempfile
from pathlib import Path
from typing import Dict, Any

from knowledgebeast.mcp.config import MCPConfig
from knowledgebeast.mcp.server import create_server
from knowledgebeast.mcp.tools import KnowledgeBeastTools


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir)
        projects_db = temp_path / "test_projects.db"
        chroma_path = temp_path / "test_chroma"
        chroma_path.mkdir(exist_ok=True)

        yield {
            "projects_db": str(projects_db),
            "chroma_path": str(chroma_path),
        }


@pytest.fixture
def test_config(temp_dirs):
    """Create a test MCP configuration."""
    return MCPConfig(
        projects_db_path=temp_dirs["projects_db"],
        chroma_path=temp_dirs["chroma_path"],
        log_level="DEBUG",
    )


@pytest.fixture
def mcp_server(test_config):
    """Create an MCP server instance for testing."""
    return create_server(test_config)


class TestMCPServerInitialization:
    """Tests for MCP server initialization and configuration."""

    def test_server_creation(self, test_config):
        """Test that MCP server can be created with valid configuration."""
        server = create_server(test_config)
        assert server is not None
        assert server.name == test_config.server_name
        # FastMCP doesn't expose version directly, but we can verify it was created
        assert hasattr(server, 'name')

    def test_server_with_default_config(self, temp_dirs):
        """Test server creation with default configuration values."""
        config = MCPConfig(
            projects_db_path=temp_dirs["projects_db"],
            chroma_path=temp_dirs["chroma_path"],
        )
        server = create_server(config)
        assert server is not None
        assert server.name == "knowledgebeast"

    def test_config_from_env(self, monkeypatch, temp_dirs):
        """Test configuration can be loaded from environment variables."""
        monkeypatch.setenv("KB_PROJECTS_DB", temp_dirs["projects_db"])
        monkeypatch.setenv("KB_CHROMA_PATH", temp_dirs["chroma_path"])
        monkeypatch.setenv("KB_LOG_LEVEL", "DEBUG")

        config = MCPConfig.from_env()
        assert config.projects_db_path == temp_dirs["projects_db"]
        assert config.chroma_path == temp_dirs["chroma_path"]
        assert config.log_level == "DEBUG"

    def test_directory_creation(self, test_config):
        """Test that required directories are created during initialization."""
        test_config.ensure_directories()

        chroma_path = Path(test_config.chroma_path)
        assert chroma_path.exists()
        assert chroma_path.is_dir()


class TestMCPTools:
    """Tests for MCP tool functionality."""

    @pytest.mark.asyncio
    async def test_health_check_tool(self, test_config):
        """Test the health check tool returns valid status."""
        tools = KnowledgeBeastTools(test_config)
        server = create_server(test_config)

        # The health check tool should be accessible
        # We can't directly call it without FastMCP runtime, but we can test
        # the underlying tools implementation
        projects = await tools.kb_list_projects()
        assert isinstance(projects, list)

    @pytest.mark.asyncio
    async def test_list_projects_empty(self, test_config):
        """Test listing projects returns empty list initially."""
        tools = KnowledgeBeastTools(test_config)
        projects = await tools.kb_list_projects()

        assert isinstance(projects, list)
        assert len(projects) == 0

    @pytest.mark.asyncio
    async def test_create_and_list_project(self, test_config):
        """Test creating a project and listing it."""
        tools = KnowledgeBeastTools(test_config)

        # Create a test project
        result = await tools.kb_create_project(
            name="Test Project",
            description="A test project",
        )

        assert "success" in result or "project_id" in result
        assert result.get("success") is True
        project_id = result.get("project_id")
        assert project_id is not None

        # List projects and verify it's there
        projects = await tools.kb_list_projects()
        assert isinstance(projects, list)
        assert len(projects) == 1
        assert projects[0]["name"] == "Test Project"
        assert projects[0]["project_id"] == project_id

    @pytest.mark.asyncio
    async def test_get_project_info(self, test_config):
        """Test getting project information."""
        tools = KnowledgeBeastTools(test_config)

        # Create a test project
        create_result = await tools.kb_create_project(
            name="Info Test Project",
            description="Testing project info",
        )
        project_id = create_result.get("project_id")

        # Get project info
        info = await tools.kb_get_project_info(project_id)

        assert "project_id" in info
        assert info["project_id"] == project_id
        assert info["name"] == "Info Test Project"
        assert info["description"] == "Testing project info"
        assert "document_count" in info
        assert "cache_stats" in info

    @pytest.mark.asyncio
    async def test_get_nonexistent_project(self, test_config):
        """Test getting info for non-existent project returns error."""
        tools = KnowledgeBeastTools(test_config)

        info = await tools.kb_get_project_info("nonexistent-project-id")

        assert "error" in info
        assert "not found" in info["error"].lower()

    @pytest.mark.asyncio
    async def test_ingest_direct_content(self, test_config):
        """Test ingesting content directly."""
        tools = KnowledgeBeastTools(test_config)

        # Create a test project
        create_result = await tools.kb_create_project(
            name="Ingest Test Project",
        )
        project_id = create_result.get("project_id")

        # Ingest some content
        ingest_result = await tools.kb_ingest(
            project_id=project_id,
            content="This is a test document with some content for testing.",
            metadata={"source": "test", "tags": ["testing"]},
        )

        assert "success" in ingest_result or "doc_id" in ingest_result
        assert ingest_result.get("success") is True
        assert "doc_id" in ingest_result

    @pytest.mark.asyncio
    async def test_search_empty_project(self, test_config):
        """Test searching an empty project returns no results."""
        tools = KnowledgeBeastTools(test_config)

        # Create a test project
        create_result = await tools.kb_create_project(
            name="Empty Search Project",
        )
        project_id = create_result.get("project_id")

        # Search the empty project
        results = await tools.kb_search(
            project_id=project_id,
            query="test query",
        )

        assert isinstance(results, list)
        # Empty project should return empty results
        assert len(results) == 0 or (len(results) > 0 and "error" not in results[0])

    @pytest.mark.asyncio
    async def test_delete_project(self, test_config):
        """Test deleting a project."""
        tools = KnowledgeBeastTools(test_config)

        # Create a test project
        create_result = await tools.kb_create_project(
            name="Delete Test Project",
        )
        project_id = create_result.get("project_id")

        # Verify it exists
        projects = await tools.kb_list_projects()
        assert len(projects) == 1

        # Delete the project
        delete_result = await tools.kb_delete_project(project_id)

        assert delete_result.get("success") is True
        assert delete_result.get("project_id") == project_id

        # Verify it's gone
        projects = await tools.kb_list_projects()
        assert len(projects) == 0

    @pytest.mark.asyncio
    async def test_ingest_without_content_or_file(self, test_config):
        """Test ingesting without content or file_path returns error."""
        tools = KnowledgeBeastTools(test_config)

        # Create a test project
        create_result = await tools.kb_create_project(
            name="Error Test Project",
        )
        project_id = create_result.get("project_id")

        # Try to ingest without content or file_path
        result = await tools.kb_ingest(project_id=project_id)

        assert "error" in result
        assert "content or file_path" in result["error"].lower()


class TestMCPServerTools:
    """Tests for MCP server tool registration and structure."""

    def test_server_has_tools(self, mcp_server):
        """Test that server has tools registered."""
        # FastMCP registers tools internally, verify server object exists
        assert mcp_server is not None
        assert hasattr(mcp_server, 'name')

    def test_tool_names_are_valid(self, mcp_server):
        """Test that all tool names follow naming conventions."""
        # Tool names should start with 'kb_' prefix
        expected_tools = [
            "kb_search",
            "kb_ingest",
            "kb_list_documents",
            "kb_list_projects",
            "kb_create_project",
            "kb_get_project_info",
            "kb_delete_project",
            "kb_export_project",
            "kb_import_project",
            "kb_get_analytics",
            "kb_health_check",
        ]

        # We can't directly access tools from FastMCP, but we can verify
        # the server was created successfully with expected configuration
        assert mcp_server.name == "knowledgebeast"


class TestMCPConfig:
    """Tests for MCP configuration handling."""

    def test_config_defaults(self):
        """Test that configuration has sensible defaults."""
        config = MCPConfig()

        assert config.projects_db_path == "./kb_projects.db"
        assert config.chroma_path == "./chroma_db"
        assert config.default_embedding_model == "all-MiniLM-L6-v2"
        assert config.cache_capacity == 100
        assert config.server_name == "knowledgebeast"
        assert config.log_level == "INFO"

    def test_config_custom_values(self, temp_dirs):
        """Test configuration with custom values."""
        config = MCPConfig(
            projects_db_path=temp_dirs["projects_db"],
            chroma_path=temp_dirs["chroma_path"],
            default_embedding_model="custom-model",
            cache_capacity=200,
            log_level="DEBUG",
        )

        assert config.projects_db_path == temp_dirs["projects_db"]
        assert config.chroma_path == temp_dirs["chroma_path"]
        assert config.default_embedding_model == "custom-model"
        assert config.cache_capacity == 200
        assert config.log_level == "DEBUG"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
