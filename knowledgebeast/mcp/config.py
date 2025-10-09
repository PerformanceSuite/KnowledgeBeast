"""MCP server configuration."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class MCPConfig:
    """Configuration for KnowledgeBeast MCP server."""

    # Storage paths
    projects_db_path: str = "./kb_projects.db"
    chroma_path: str = "./chroma_db"

    # Default project settings
    default_embedding_model: str = "all-MiniLM-L6-v2"
    cache_capacity: int = 100

    # MCP server settings
    server_name: str = "knowledgebeast"
    server_version: str = "2.3.1"

    # Logging
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "MCPConfig":
        """Create configuration from environment variables."""
        return cls(
            projects_db_path=os.getenv("KB_PROJECTS_DB", "./kb_projects.db"),
            chroma_path=os.getenv("KB_CHROMA_PATH", "./chroma_db"),
            default_embedding_model=os.getenv(
                "KB_DEFAULT_MODEL", "all-MiniLM-L6-v2"
            ),
            cache_capacity=int(os.getenv("KB_CACHE_CAPACITY", "100")),
            log_level=os.getenv("KB_LOG_LEVEL", "INFO"),
        )

    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        Path(self.chroma_path).mkdir(parents=True, exist_ok=True)
        Path(self.projects_db_path).parent.mkdir(parents=True, exist_ok=True)
