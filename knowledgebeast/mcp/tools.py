"""MCP tool implementations for KnowledgeBeast."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.embeddings import EmbeddingEngine
from ..core.project_manager import ProjectManager
from ..core.query_engine import HybridQueryEngine
from ..core.repository import DocumentRepository
from ..core.vector_store import VectorStore
from .config import MCPConfig

logger = logging.getLogger(__name__)


class KnowledgeBeastTools:
    """MCP tools for KnowledgeBeast operations."""

    def __init__(self, config: MCPConfig):
        """Initialize KnowledgeBeast tools.

        Args:
            config: MCP configuration
        """
        self.config = config
        config.ensure_directories()

        # Initialize core components
        self.project_manager = ProjectManager(
            storage_path=config.projects_db_path,
            chroma_path=config.chroma_path,
            cache_capacity=config.cache_capacity,
        )

        logger.info(
            f"KnowledgeBeast MCP tools initialized "
            f"(projects_db={config.projects_db_path}, chroma={config.chroma_path})"
        )

    # ===== Knowledge Management Tools =====

    async def kb_search(
        self,
        project_id: str,
        query: str,
        mode: str = "hybrid",
        limit: int = 5,
        alpha: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """Search a knowledge base project.

        Args:
            project_id: Project identifier
            query: Search query
            mode: Search mode (vector, keyword, hybrid)
            limit: Maximum number of results
            alpha: Hybrid search alpha (0=keyword, 1=vector)

        Returns:
            List of search results with content and metadata
        """
        try:
            # Get project
            project = self.project_manager.get_project(project_id)
            if not project:
                return [{"error": f"Project not found: {project_id}"}]

            # Get project components
            vector_store = VectorStore(
                persist_directory=self.config.chroma_path,
                collection_name=project.collection_name,
            )

            embedding_engine = EmbeddingEngine(
                model_name=project.embedding_model,
                cache_size=self.config.cache_capacity,
            )

            repo = DocumentRepository()
            query_engine = HybridQueryEngine(repo, embedding_engine, vector_store)

            # Perform search based on mode
            if mode == "vector":
                results = query_engine.search_vector(query, top_k=limit)
            elif mode == "keyword":
                results = query_engine.search_keyword(query, top_k=limit)
            else:  # hybrid
                results = query_engine.search_hybrid(query, alpha=alpha, top_k=limit)

            # Format results
            formatted_results = []
            for doc_id, doc_data, score in results:
                formatted_results.append(
                    {
                        "doc_id": doc_id,
                        "content": doc_data.get("content", "")[:500],  # Truncate
                        "name": doc_data.get("name", ""),
                        "path": doc_data.get("path", ""),
                        "score": float(score),
                    }
                )

            logger.info(
                f"Search completed: project={project_id}, mode={mode}, "
                f"query_len={len(query)}, results={len(formatted_results)}"
            )

            return formatted_results

        except Exception as e:
            logger.error(f"Search error: {e}", exc_info=True)
            return [{"error": str(e)}]

    async def kb_ingest(
        self,
        project_id: str,
        content: Optional[str] = None,
        file_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Ingest a document into a knowledge base project.

        Args:
            project_id: Project identifier
            content: Direct content (if not using file_path)
            file_path: Path to file to ingest
            metadata: Optional document metadata

        Returns:
            Ingestion result with doc_id and status
        """
        try:
            # Validate inputs
            if not content and not file_path:
                return {"error": "Must provide either content or file_path"}

            # Get project
            project = self.project_manager.get_project(project_id)
            if not project:
                return {"error": f"Project not found: {project_id}"}

            # Get project components
            vector_store = VectorStore(
                persist_directory=self.config.chroma_path,
                collection_name=project.collection_name,
            )

            embedding_engine = EmbeddingEngine(
                model_name=project.embedding_model,
                cache_size=self.config.cache_capacity,
            )

            # Prepare document
            if content:
                # Direct content ingestion
                import time

                doc_id = f"doc_{int(time.time() * 1000)}"
                embedding = embedding_engine.embed(content)

                doc_metadata = metadata or {}
                doc_metadata.update({"source": "direct", "project_id": project_id})

                vector_store.add(
                    ids=doc_id,
                    embeddings=embedding,
                    documents=content,
                    metadatas=doc_metadata,
                )

                logger.info(
                    f"Document ingested: project={project_id}, doc_id={doc_id}, "
                    f"content_len={len(content)}"
                )

                return {
                    "success": True,
                    "doc_id": doc_id,
                    "message": f"Document ingested into project {project.name}",
                }

            else:
                # File ingestion
                file_path_obj = Path(file_path)
                if not file_path_obj.exists():
                    return {"error": f"File not found: {file_path}"}

                # Read file content
                file_content = file_path_obj.read_text()

                import time

                doc_id = f"doc_{int(time.time() * 1000)}"
                embedding = embedding_engine.embed(file_content)

                doc_metadata = metadata or {}
                doc_metadata.update(
                    {
                        "source": "file",
                        "file_path": str(file_path),
                        "file_name": file_path_obj.name,
                        "project_id": project_id,
                    }
                )

                vector_store.add(
                    ids=doc_id,
                    embeddings=embedding,
                    documents=file_content,
                    metadatas=doc_metadata,
                )

                logger.info(
                    f"File ingested: project={project_id}, doc_id={doc_id}, "
                    f"file={file_path}"
                )

                return {
                    "success": True,
                    "doc_id": doc_id,
                    "file_path": str(file_path),
                    "message": f"File ingested into project {project.name}",
                }

        except Exception as e:
            logger.error(f"Ingestion error: {e}", exc_info=True)
            return {"error": str(e)}

    async def kb_list_documents(
        self, project_id: str, limit: int = 100
    ) -> Dict[str, Any]:
        """List documents in a knowledge base project.

        Args:
            project_id: Project identifier
            limit: Maximum number of documents to return

        Returns:
            List of documents with metadata
        """
        try:
            # Get project
            project = self.project_manager.get_project(project_id)
            if not project:
                return {"error": f"Project not found: {project_id}"}

            # Get project vector store
            vector_store = VectorStore(
                persist_directory=self.config.chroma_path,
                collection_name=project.collection_name,
            )

            # Get document count
            doc_count = vector_store.count()

            # Get documents (peek)
            if doc_count > 0:
                results = vector_store.peek(limit=min(limit, doc_count))
                documents = []

                for i, doc_id in enumerate(results.get("ids", [])):
                    documents.append(
                        {
                            "doc_id": doc_id,
                            "metadata": results.get("metadatas", [])[i]
                            if i < len(results.get("metadatas", []))
                            else {},
                        }
                    )
            else:
                documents = []

            logger.info(
                f"Documents listed: project={project_id}, count={doc_count}, "
                f"returned={len(documents)}"
            )

            return {
                "project_id": project_id,
                "project_name": project.name,
                "total_documents": doc_count,
                "documents": documents,
            }

        except Exception as e:
            logger.error(f"List documents error: {e}", exc_info=True)
            return {"error": str(e)}

    # ===== Project Management Tools =====

    async def kb_list_projects(self) -> List[Dict[str, Any]]:
        """List all knowledge base projects.

        Returns:
            List of projects with metadata
        """
        try:
            projects = self.project_manager.list_projects()

            formatted_projects = []
            for project in projects:
                formatted_projects.append(
                    {
                        "project_id": project.project_id,
                        "name": project.name,
                        "description": project.description,
                        "embedding_model": project.embedding_model,
                        "created_at": project.created_at.isoformat(),
                    }
                )

            logger.info(f"Projects listed: count={len(formatted_projects)}")
            return formatted_projects

        except Exception as e:
            logger.error(f"List projects error: {e}", exc_info=True)
            return [{"error": str(e)}]

    async def kb_create_project(
        self,
        name: str,
        description: str = "",
        embedding_model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new knowledge base project.

        Args:
            name: Project name
            description: Project description
            embedding_model: Embedding model to use (default: all-MiniLM-L6-v2)
            metadata: Optional project metadata

        Returns:
            Created project details
        """
        try:
            project = self.project_manager.create_project(
                name=name,
                description=description,
                embedding_model=embedding_model or self.config.default_embedding_model,
                metadata=metadata or {},
            )

            logger.info(
                f"Project created: project_id={project.project_id}, name={name}"
            )

            return {
                "success": True,
                "project_id": project.project_id,
                "name": project.name,
                "description": project.description,
                "embedding_model": project.embedding_model,
                "collection_name": project.collection_name,
                "created_at": project.created_at.isoformat(),
            }

        except Exception as e:
            logger.error(f"Create project error: {e}", exc_info=True)
            return {"error": str(e)}

    async def kb_get_project_info(self, project_id: str) -> Dict[str, Any]:
        """Get detailed information about a project.

        Args:
            project_id: Project identifier

        Returns:
            Project details including statistics
        """
        try:
            project = self.project_manager.get_project(project_id)
            if not project:
                return {"error": f"Project not found: {project_id}"}

            # Get document count
            vector_store = VectorStore(
                persist_directory=self.config.chroma_path,
                collection_name=project.collection_name,
            )
            doc_count = vector_store.count()

            # Get cache stats
            cache_stats = self.project_manager.get_cache_stats(project_id)

            logger.info(f"Project info retrieved: project_id={project_id}")

            return {
                "project_id": project.project_id,
                "name": project.name,
                "description": project.description,
                "embedding_model": project.embedding_model,
                "collection_name": project.collection_name,
                "created_at": project.created_at.isoformat(),
                "updated_at": project.updated_at.isoformat(),
                "metadata": project.metadata,
                "document_count": doc_count,
                "cache_stats": cache_stats,
            }

        except Exception as e:
            logger.error(f"Get project info error: {e}", exc_info=True)
            return {"error": str(e)}

    async def kb_delete_project(self, project_id: str) -> Dict[str, Any]:
        """Delete a knowledge base project.

        Args:
            project_id: Project identifier

        Returns:
            Deletion result
        """
        try:
            self.project_manager.delete_project(project_id)

            logger.info(f"Project deleted: project_id={project_id}")

            return {"success": True, "project_id": project_id, "message": "Project deleted successfully"}

        except Exception as e:
            logger.error(f"Delete project error: {e}", exc_info=True)
            return {"error": str(e)}
