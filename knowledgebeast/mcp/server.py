"""MCP server implementation for KnowledgeBeast.

This module provides a Model Context Protocol (MCP) server that exposes
KnowledgeBeast's knowledge management capabilities to MCP clients like Claude Code.

The server uses the FastMCP framework with stdio transport for local development
and production deployment.
"""

import asyncio
import logging
import sys
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from .config import MCPConfig
from .tools import KnowledgeBeastTools

logger = logging.getLogger(__name__)


def create_server(config: MCPConfig) -> FastMCP:
    """Create and configure the MCP server.

    Args:
        config: MCP configuration

    Returns:
        Configured FastMCP server instance
    """
    # Initialize FastMCP server
    mcp = FastMCP(
        name=config.server_name,
        version=config.server_version,
    )

    # Initialize KnowledgeBeast tools
    tools = KnowledgeBeastTools(config)

    # ===== Knowledge Management Tools =====

    @mcp.tool()
    async def kb_search(
        project_id: str,
        query: str,
        mode: str = "hybrid",
        limit: int = 5,
        alpha: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """Search a knowledge base project.

        Search across documents in a project using vector similarity,
        keyword matching, or a hybrid approach.

        Args:
            project_id: Project identifier
            query: Search query text
            mode: Search mode - "vector", "keyword", or "hybrid" (default)
            limit: Maximum number of results to return (default: 5)
            alpha: Hybrid search weight (0=keyword only, 1=vector only, default: 0.7)

        Returns:
            List of search results with content, metadata, and relevance scores
        """
        return await tools.kb_search(
            project_id=project_id,
            query=query,
            mode=mode,
            limit=limit,
            alpha=alpha,
        )

    @mcp.tool()
    async def kb_ingest(
        project_id: str,
        content: Optional[str] = None,
        file_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Ingest a document into a knowledge base project.

        Add content to a project either directly as text or from a file.
        The content will be embedded and indexed for future searches.

        Args:
            project_id: Project identifier
            content: Direct text content (provide either content or file_path)
            file_path: Path to file to ingest (provide either content or file_path)
            metadata: Optional document metadata (tags, source info, etc.)

        Returns:
            Ingestion result with document ID and status
        """
        return await tools.kb_ingest(
            project_id=project_id,
            content=content,
            file_path=file_path,
            metadata=metadata,
        )

    @mcp.tool()
    async def kb_list_documents(
        project_id: str, limit: int = 100
    ) -> Dict[str, Any]:
        """List documents in a knowledge base project.

        Retrieve a list of all documents in a project with their metadata.

        Args:
            project_id: Project identifier
            limit: Maximum number of documents to return (default: 100)

        Returns:
            Document list with IDs, metadata, and project statistics
        """
        return await tools.kb_list_documents(project_id=project_id, limit=limit)

    # ===== Project Management Tools =====

    @mcp.tool()
    async def kb_list_projects() -> List[Dict[str, Any]]:
        """List all knowledge base projects.

        Get a list of all available projects with their metadata
        including names, descriptions, and creation dates.

        Returns:
            List of projects with metadata
        """
        return await tools.kb_list_projects()

    @mcp.tool()
    async def kb_create_project(
        name: str,
        description: str = "",
        embedding_model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new knowledge base project.

        Initialize a new project with its own vector store and configuration.
        Each project can have different embedding models and settings.

        Args:
            name: Project name (must be unique)
            description: Project description (optional)
            embedding_model: Embedding model name (default: all-MiniLM-L6-v2)
            metadata: Optional project metadata (tags, owner, etc.)

        Returns:
            Created project details with ID and configuration
        """
        return await tools.kb_create_project(
            name=name,
            description=description,
            embedding_model=embedding_model,
            metadata=metadata,
        )

    @mcp.tool()
    async def kb_get_project_info(project_id: str) -> Dict[str, Any]:
        """Get detailed information about a project.

        Retrieve comprehensive project details including configuration,
        statistics, and cache performance metrics.

        Args:
            project_id: Project identifier

        Returns:
            Project details with statistics and metadata
        """
        return await tools.kb_get_project_info(project_id=project_id)

    @mcp.tool()
    async def kb_delete_project(project_id: str) -> Dict[str, Any]:
        """Delete a knowledge base project.

        Permanently delete a project and all its associated data including
        documents, embeddings, and metadata. This action cannot be undone.

        Args:
            project_id: Project identifier

        Returns:
            Deletion confirmation with project ID
        """
        return await tools.kb_delete_project(project_id=project_id)

    # ===== Analytics Tools =====

    @mcp.tool()
    async def kb_get_analytics(project_id: str) -> Dict[str, Any]:
        """Get analytics and usage statistics for a project.

        Retrieve detailed analytics including query patterns, cache performance,
        and document statistics.

        Args:
            project_id: Project identifier

        Returns:
            Analytics data with metrics and trends
        """
        # Get project info which includes cache stats
        project_info = await tools.kb_get_project_info(project_id=project_id)

        if "error" in project_info:
            return project_info

        # Format analytics response
        return {
            "project_id": project_id,
            "project_name": project_info.get("name", "Unknown"),
            "document_count": project_info.get("document_count", 0),
            "cache_stats": project_info.get("cache_stats", {}),
            "embedding_model": project_info.get("embedding_model", ""),
            "created_at": project_info.get("created_at", ""),
            "updated_at": project_info.get("updated_at", ""),
        }

    @mcp.tool()
    async def kb_export_project(
        project_id: str, output_path: str, format: str = "zip"
    ) -> Dict[str, Any]:
        """Export a project to a file.

        Export project configuration and documents for backup or transfer.

        Args:
            project_id: Project identifier
            output_path: Path where export file will be saved
            format: Export format - "json", "yaml", or "zip" (default: zip)

        Returns:
            Export result with file path and statistics
        """
        return await tools.kb_export_project(
            project_id=project_id,
            output_path=output_path,
            format=format
        )

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

    @mcp.tool()
    async def kb_health_check() -> Dict[str, Any]:
        """Perform a health check on the KnowledgeBeast system.

        Check system status, component health, and configuration validity.

        Returns:
            Health check results with system status
        """
        try:
            # List projects to verify system is operational
            projects = await tools.kb_list_projects()

            # Check for errors
            if isinstance(projects, list) and len(projects) > 0:
                if "error" in projects[0]:
                    return {
                        "status": "unhealthy",
                        "error": projects[0]["error"],
                        "projects_accessible": False,
                    }

            return {
                "status": "healthy",
                "version": config.server_version,
                "server_name": config.server_name,
                "projects_count": len(projects) if isinstance(projects, list) else 0,
                "projects_accessible": True,
                "default_model": config.default_embedding_model,
                "cache_capacity": config.cache_capacity,
            }

        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)
            return {
                "status": "unhealthy",
                "error": str(e),
                "projects_accessible": False,
            }

    logger.info(
        f"MCP server created: {config.server_name} v{config.server_version} "
        f"(14 tools registered)"
    )

    return mcp


async def serve(config: Optional[MCPConfig] = None) -> None:
    """Run the MCP server with stdio transport.

    This function starts the MCP server and handles communication over
    standard input/output streams. It's designed to be called from the CLI
    or run directly for development and production deployment.

    Args:
        config: Optional MCP configuration (loads from env if not provided)

    Raises:
        Exception: If server initialization or execution fails
    """
    # Load configuration
    if config is None:
        config = MCPConfig.from_env()

    # Setup logging
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,  # Log to stderr, leave stdout for MCP protocol
    )

    logger.info("Starting KnowledgeBeast MCP server...")
    logger.info(f"Configuration: projects_db={config.projects_db_path}, "
                f"chroma={config.chroma_path}")

    try:
        # Create server
        mcp = create_server(config)

        # Run server with stdio transport
        logger.info("MCP server running on stdio transport")
        await mcp.run()

    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


def main() -> None:
    """Entry point for running the server directly.

    This can be used for development or testing:
        python -m knowledgebeast.mcp.server
    """
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        print("\nServer stopped", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
