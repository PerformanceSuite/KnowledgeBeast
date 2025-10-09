"""KnowledgeBeast MCP Server.

Native Model Context Protocol (MCP) integration for KnowledgeBeast.
Provides Claude Code with direct access to knowledge base operations.
"""

from .server import serve

__all__ = ["serve"]
