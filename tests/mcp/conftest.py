"""Shared fixtures for MCP tests with optimized mocking.

This module provides comprehensive mocking to eliminate slow I/O operations:
- Mock EmbeddingEngine to avoid downloading 79MB models
- Mock VectorStore for instant ChromaDB operations
- Mock ProjectManager for fast project isolation

Performance Target: <10 seconds for entire MCP test suite
"""

import pytest
import tempfile
from pathlib import Path
from typing import Generator, Dict, Any, List, Optional
from unittest.mock import Mock, MagicMock, patch
import numpy as np

# Import config without triggering server imports
import sys
from knowledgebeast.core.project_manager import Project

# Mock MCPConfig to avoid importing server dependencies
class MCPConfig:
    """Mock MCPConfig for testing."""
    def __init__(
        self,
        projects_db_path: str = "./kb_projects.db",
        chroma_path: str = "./chroma_db",
        default_embedding_model: str = "all-MiniLM-L6-v2",
        cache_capacity: int = 100,
        server_name: str = "knowledgebeast",
        log_level: str = "INFO"
    ):
        self.projects_db_path = projects_db_path
        self.chroma_path = chroma_path
        self.default_embedding_model = default_embedding_model
        self.cache_capacity = cache_capacity
        self.server_name = server_name
        self.log_level = log_level

    @classmethod
    def from_env(cls):
        """Create MCPConfig from environment variables."""
        import os
        return cls(
            projects_db_path=os.getenv("KB_PROJECTS_DB", "./kb_projects.db"),
            chroma_path=os.getenv("KB_CHROMA_PATH", "./chroma_db"),
            default_embedding_model=os.getenv("KB_DEFAULT_MODEL", "all-MiniLM-L6-v2"),
            cache_capacity=int(os.getenv("KB_CACHE_CAPACITY", "100")),
            server_name=os.getenv("KB_SERVER_NAME", "knowledgebeast"),
            log_level=os.getenv("KB_LOG_LEVEL", "INFO")
        )

    def ensure_directories(self):
        """Ensure required directories exist."""
        from pathlib import Path
        Path(self.chroma_path).mkdir(parents=True, exist_ok=True)
        Path(self.projects_db_path).parent.mkdir(parents=True, exist_ok=True)


# ===== Mock Data =====

MOCK_EMBEDDING = [0.1] * 384  # all-MiniLM-L6-v2 dimension
MOCK_EMBEDDINGS_2D = np.array([[0.1] * 384, [0.2] * 384])


# ===== Core Mocks =====

@pytest.fixture
def mock_embedding_engine():
    """Mock EmbeddingEngine to avoid model downloads (79MB).

    Returns embeddings instantly without downloading models.
    """
    mock = MagicMock()
    mock.model_name = "all-MiniLM-L6-v2"
    mock.embed.return_value = MOCK_EMBEDDING
    mock.embed_batch.return_value = MOCK_EMBEDDINGS_2D
    mock.dimension = 384
    return mock


@pytest.fixture
def mock_vector_store():
    """Mock VectorStore for instant ChromaDB operations.

    Simulates ChromaDB without actual I/O.
    Each test gets a fresh instance to avoid test pollution.
    """
    mock = MagicMock()
    mock.collection_name = "test_collection"
    mock._documents = {}  # In-memory document store (fresh per test)
    mock._next_id = 0

    def mock_add(ids, embeddings, documents, metadatas):
        """Simulate document addition."""
        if isinstance(ids, str):
            ids = [ids]
            embeddings = [embeddings]
            documents = [documents]
            metadatas = [metadatas]

        for id, emb, doc, meta in zip(ids, embeddings, documents, metadatas):
            mock._documents[id] = {
                'embedding': emb,
                'document': doc,
                'metadata': meta or {}
            }

    def mock_query(query_embeddings, n_results=5, where=None):
        """Simulate vector search."""
        doc_ids = list(mock._documents.keys())[:n_results]
        return {
            'ids': [doc_ids] if doc_ids else [[]],
            'documents': [[mock._documents[id]['document'] for id in doc_ids]] if doc_ids else [[]],
            'metadatas': [[mock._documents[id]['metadata'] for id in doc_ids]] if doc_ids else [[]],
            'distances': [[0.1 * (i + 1) for i in range(len(doc_ids))]] if doc_ids else [[]],
        }

    def mock_get(ids=None, where=None, limit=None, include=None):
        """Simulate document retrieval."""
        if ids:
            if isinstance(ids, str):
                ids = [ids]
            results = {id: mock._documents[id] for id in ids if id in mock._documents}
        else:
            results = dict(list(mock._documents.items())[:limit]) if limit else mock._documents

        return {
            'ids': list(results.keys()),
            'documents': [v['document'] for v in results.values()] if include and 'documents' in include else None,
            'metadatas': [v['metadata'] for v in results.values()] if include and 'metadatas' in include else None,
            'embeddings': [v['embedding'] for v in results.values()] if include and 'embeddings' in include else None,
        }

    def mock_peek(limit=10):
        """Simulate peek operation."""
        doc_items = list(mock._documents.items())[:limit]
        return {
            'ids': [id for id, _ in doc_items],
            'documents': [v['document'] for _, v in doc_items],
            'metadatas': [v['metadata'] for _, v in doc_items],
        }

    def mock_delete(ids):
        """Simulate document deletion."""
        if isinstance(ids, str):
            ids = [ids]
        for id in ids:
            mock._documents.pop(id, None)

    def mock_count():
        """Simulate document count."""
        return len(mock._documents)

    mock.add.side_effect = mock_add
    mock.query.side_effect = mock_query
    mock.get.side_effect = mock_get
    mock.peek.side_effect = mock_peek
    mock.delete.side_effect = mock_delete
    mock.count.side_effect = mock_count

    return mock


@pytest.fixture
def mock_project_manager(tmp_path):
    """Mock ProjectManager for instant project operations.

    Avoids real SQLite and ChromaDB initialization.
    """
    mock = MagicMock()
    mock._projects = {}  # In-memory project store
    mock._caches = {}
    mock.storage_path = tmp_path / "projects.db"
    mock.chroma_path = tmp_path / "chroma_db"
    mock.cache_capacity = 100

    def mock_create_project(name, description="", embedding_model="all-MiniLM-L6-v2", metadata=None):
        """Simulate project creation."""
        import uuid
        from datetime import datetime, timezone

        # Check for duplicate name
        for p in mock._projects.values():
            if p.name == name:
                raise ValueError(f"Project with name '{name}' already exists")

        project_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        project = Project(
            project_id=project_id,
            name=name,
            description=description,
            embedding_model=embedding_model,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        mock._projects[project_id] = project
        return project

    def mock_get_project(project_id):
        """Simulate project retrieval."""
        return mock._projects.get(project_id)

    def mock_list_projects():
        """Simulate project listing."""
        return list(mock._projects.values())

    def mock_delete_project(project_id):
        """Simulate project deletion."""
        if project_id in mock._projects:
            del mock._projects[project_id]
            return True
        return False

    def mock_get_project_cache(project_id):
        """Simulate cache retrieval."""
        if project_id not in mock._caches:
            from knowledgebeast.core.cache import LRUCache
            mock._caches[project_id] = LRUCache(capacity=100)
        return mock._caches[project_id]

    def mock_get_cache_stats(project_id):
        """Simulate cache stats."""
        cache = mock_get_project_cache(project_id)
        return {
            'size': len(cache) if cache else 0,
            'capacity': 100,
            'utilization': len(cache) / 100 if cache else 0,
        }

    def mock_get_collection(project_id):
        """Simulate ChromaDB collection retrieval."""
        mock_coll = MagicMock()
        mock_coll.name = f"kb_project_{project_id}"
        return mock_coll

    mock.create_project.side_effect = mock_create_project
    mock.get_project.side_effect = mock_get_project
    mock.list_projects.side_effect = mock_list_projects
    mock.delete_project.side_effect = mock_delete_project
    mock.get_project_cache.side_effect = mock_get_project_cache
    mock.get_cache_stats.side_effect = mock_get_cache_stats
    mock.get_collection.side_effect = mock_get_collection
    mock.get_project_collection = mock_get_collection

    return mock


# ===== Integration Fixtures =====

@pytest.fixture
def mock_knowledgebeast_tools(mock_project_manager, mock_embedding_engine, mock_vector_store, tmp_path):
    """Mock KnowledgeBeastTools with all dependencies mocked.

    This fixture creates a mock tools object that behaves like KnowledgeBeastTools
    but uses mocks for all I/O operations.
    """
    config = MCPConfig(
        projects_db_path=str(tmp_path / "test_projects.db"),
        chroma_path=str(tmp_path / "test_chroma"),
        default_embedding_model="all-MiniLM-L6-v2",
        cache_capacity=50,
        log_level="INFO",
    )

    # Create mock tools object
    tools = MagicMock()
    tools.config = config
    tools.project_manager = mock_project_manager
    tools.validator = MagicMock()

    # Import the actual tools module methods and wrap them with mocks
    # This avoids importing the server module
    import asyncio

    # Project management methods
    async def kb_create_project(name, description="", embedding_model=None, metadata=None):
        project = mock_project_manager.create_project(
            name=name,
            description=description,
            embedding_model=embedding_model or config.default_embedding_model,
            metadata=metadata or {},
        )
        return {
            "success": True,
            "project_id": project.project_id,
            "name": project.name,
            "description": project.description,
            "embedding_model": project.embedding_model,
            "collection_name": project.collection_name,
            "created_at": project.created_at,
        }

    async def kb_list_projects():
        projects = mock_project_manager.list_projects()
        return [
            {
                "project_id": p.project_id,
                "name": p.name,
                "description": p.description,
                "embedding_model": p.embedding_model,
                "created_at": p.created_at,
            }
            for p in projects
        ]

    async def kb_get_project_info(project_id):
        project = mock_project_manager.get_project(project_id)
        if not project:
            return {"error": f"Project not found: {project_id}"}

        return {
            "project_id": project.project_id,
            "name": project.name,
            "description": project.description,
            "embedding_model": project.embedding_model,
            "collection_name": project.collection_name,
            "created_at": project.created_at,
            "updated_at": project.updated_at,
            "metadata": project.metadata,
            "document_count": 0,
            "cache_stats": mock_project_manager.get_cache_stats(project_id),
        }

    async def kb_delete_project(project_id):
        success = mock_project_manager.delete_project(project_id)
        if not success:
            return {"error": f"Project not found: {project_id}"}
        return {"success": True, "project_id": project_id, "message": "Project deleted successfully"}

    # Document operations
    _doc_counter = 0  # Counter for unique doc IDs

    async def kb_ingest(project_id, content=None, file_path=None, metadata=None):
        nonlocal _doc_counter

        if not content and not file_path:
            return {"error": "Must provide either content or file_path"}

        project = mock_project_manager.get_project(project_id)
        if not project:
            return {"error": f"Project not found: {project_id}"}

        if file_path:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                return {"error": f"File not found: {file_path}"}
            content = file_path_obj.read_text()

        import time
        _doc_counter += 1
        doc_id = f"doc_{int(time.time() * 1000)}_{_doc_counter}"

        mock_vector_store.add(
            ids=doc_id,
            embeddings=mock_embedding_engine.embed(content),
            documents=content,
            metadatas=metadata or {},
        )

        if file_path:
            return {
                "success": True,
                "doc_id": doc_id,
                "file_path": str(file_path),
                "message": f"File ingested into project {project.name}",
            }
        else:
            return {
                "success": True,
                "doc_id": doc_id,
                "message": f"Document ingested into project {project.name}",
            }

    async def kb_list_documents(project_id, limit=100):
        project = mock_project_manager.get_project(project_id)
        if not project:
            return {"error": f"Project not found: {project_id}"}

        doc_count = mock_vector_store.count()
        results = mock_vector_store.peek(limit=min(limit, doc_count)) if doc_count > 0 else {'ids': [], 'metadatas': []}

        documents = []
        for i, doc_id in enumerate(results.get("ids", [])):
            documents.append({
                "doc_id": doc_id,
                "metadata": results.get("metadatas", [])[i] if i < len(results.get("metadatas", [])) else {},
            })

        return {
            "project_id": project_id,
            "project_name": project.name,
            "total_documents": doc_count,
            "documents": documents,
        }

    async def kb_search(project_id, query, mode="hybrid", limit=5, alpha=0.7):
        project = mock_project_manager.get_project(project_id)
        if not project:
            return [{"error": f"Project not found: {project_id}"}]

        # Simulate search
        query_results = mock_vector_store.query(
            query_embeddings=[mock_embedding_engine.embed(query)],
            n_results=limit
        )

        results = []
        ids = query_results['ids'][0] if query_results['ids'] else []
        docs = query_results['documents'][0] if query_results['documents'] else []
        distances = query_results['distances'][0] if query_results['distances'] else []

        for doc_id, doc, distance in zip(ids, docs, distances):
            results.append({
                "doc_id": doc_id,
                "content": doc[:500],
                "name": "",
                "path": "",
                "score": float(1.0 - distance),  # Convert distance to similarity
            })

        return results

    async def kb_export_project(project_id, output_path, format="json"):
        """Mock export project functionality."""
        import json
        from pathlib import Path

        project = mock_project_manager.get_project(project_id)
        if not project:
            return {"error": f"Project not found: {project_id}"}

        # Get all documents from mock vector store
        collection_data = mock_vector_store.get(include=["documents", "metadatas", "embeddings"])

        # Build export data
        export_data = {
            "version": "1.0",
            "exported_at": "2025-10-24T00:00:00",
            "project": {
                "project_id": project.project_id,
                "name": project.name,
                "description": project.description,
                "embedding_model": project.embedding_model,
                "collection_name": project.collection_name,
                "created_at": project.created_at,
                "metadata": project.metadata,
            },
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

        return {
            "project_id": project_id,
            "file_path": str(output_file),
            "format": format,
            "document_count": len(export_data["documents"]),
            "file_size_bytes": output_file.stat().st_size
        }

    # Attach methods to mock
    tools.kb_create_project = kb_create_project
    tools.kb_list_projects = kb_list_projects
    tools.kb_get_project_info = kb_get_project_info
    tools.kb_delete_project = kb_delete_project
    tools.kb_ingest = kb_ingest
    tools.kb_list_documents = kb_list_documents
    tools.kb_search = kb_search
    tools.kb_export_project = kb_export_project

    return tools


@pytest.fixture
def temp_mcp_dir() -> Generator[Path, None, None]:
    """Create temporary directory for MCP testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir)
        yield temp_path


@pytest.fixture
def mcp_config(temp_mcp_dir: Path) -> MCPConfig:
    """Create test MCP configuration."""
    return MCPConfig(
        projects_db_path=str(temp_mcp_dir / "test_projects.db"),
        chroma_path=str(temp_mcp_dir / "test_chroma"),
        default_embedding_model="all-MiniLM-L6-v2",
        cache_capacity=50,
        log_level="INFO",
    )


@pytest.fixture
def mcp_tools(mock_knowledgebeast_tools):
    """Alias for mock_knowledgebeast_tools (for compatibility)."""
    return mock_knowledgebeast_tools


@pytest.fixture
def sample_project(mcp_tools) -> Project:
    """Create a sample project for testing."""
    import asyncio
    result = asyncio.run(
        mcp_tools.kb_create_project(
            name="test-project",
            description="Test project for unit tests",
        )
    )
    assert result.get("success") is True
    return mcp_tools.project_manager.get_project(result["project_id"])


# ===== Integration Test Fixtures (Real I/O for integration tests) =====

@pytest.fixture
def temp_integration_dir() -> Generator[Path, None, None]:
    """Create temporary directory for integration testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir)
        yield temp_path


@pytest.fixture
def integration_config(temp_integration_dir: Path) -> MCPConfig:
    """Create integration test MCP configuration."""
    return MCPConfig(
        projects_db_path=str(temp_integration_dir / "integration_projects.db"),
        chroma_path=str(temp_integration_dir / "integration_chroma"),
        default_embedding_model="all-MiniLM-L6-v2",
        cache_capacity=100,
        log_level="INFO",
    )


@pytest.fixture
def integration_tools(integration_config: MCPConfig):
    """Create KnowledgeBeast MCP tools for integration testing (REAL I/O).

    WARNING: This uses real ChromaDB and embedding models.
    Only use for integration tests marked with @pytest.mark.integration.
    """
    # Import here to avoid triggering MCP server imports in unit tests
    from knowledgebeast.mcp.tools import KnowledgeBeastTools
    return KnowledgeBeastTools(integration_config)
