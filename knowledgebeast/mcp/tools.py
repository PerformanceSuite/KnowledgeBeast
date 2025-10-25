"""MCP tool implementations for KnowledgeBeast."""

import json
import logging
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.embeddings import EmbeddingEngine
from ..core.project_manager import ProjectManager
from ..core.query_engine import HybridQueryEngine
from ..core.repository import DocumentRepository
from ..core.vector_store import VectorStore
from ..monitoring.health import ProjectHealthMonitor
from .config import MCPConfig
from .validation import InputValidator, ValidationError

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

        # Initialize health monitor
        self.health_monitor = ProjectHealthMonitor(self.project_manager)

        # Initialize input validator
        self.validator = InputValidator()

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
                        "created_at": project.created_at,
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
                "created_at": project.created_at,
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
                "created_at": project.created_at,
                "updated_at": project.updated_at,
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

    # ===== Advanced Tools =====

    async def kb_export_project(
        self, project_id: str, output_path: str, format: str = "zip"
    ) -> Dict[str, Any]:
        """Export project to file with embeddings.

        Args:
            project_id: Project identifier
            output_path: Path to output file
            format: Export format - "json", "yaml", or "zip" (default: zip)

        Returns:
            Export result with file path and status
        """
        try:
            # Validate format
            if format not in ["json", "yaml", "zip"]:
                return {
                    "error": f"Unsupported format: {format}. Use 'json', 'yaml', or 'zip'.",
                    "error_type": "ValidationError"
                }

            # Validate inputs
            try:
                project_id = self.validator.validate_project_id(project_id)
                output_path_obj = self.validator.validate_output_path(
                    output_path, "output_path", allow_overwrite=False
                )
            except ValidationError as e:
                logger.warning(f"Export validation error: {e.message}")
                return e.to_dict()

            # Verify project exists
            project = self.project_manager.get_project(project_id)
            if not project:
                return {
                    "error": f"Project not found: {project_id}",
                    "error_type": "ProjectNotFound",
                }

            # For ZIP format, use project_manager's built-in export
            if format == "zip":
                export_path = self.project_manager.export_project(
                    project_id, str(output_path_obj)
                )
                logger.info(f"Project exported: {project_id} -> {export_path}")

                return {
                    "success": True,
                    "project_id": project_id,
                    "project_name": project.name,
                    "output_path": str(Path(export_path).absolute()),
                    "format": format,
                    "message": "Project exported successfully",
                }

            # For JSON/YAML, export directly
            logger.info(f"Exporting project {project_id} to {format}...")

            # Get project collection
            collection = self.project_manager.get_project_collection(project_id)
            if not collection:
                return {
                    "error": f"Failed to get collection for project: {project_id}",
                    "error_type": "ExportError"
                }

            # Get all data from ChromaDB
            collection_data = collection.get(
                include=["documents", "metadatas", "embeddings"]
            )

            # Build export data
            export_data = {
                "version": "1.0",
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "project": project.to_dict(),
                "documents": [],
                "embeddings": []
            }

            # Add documents and embeddings
            if collection_data.get("ids"):
                for i, doc_id in enumerate(collection_data["ids"]):
                    export_data["documents"].append({
                        "id": doc_id,
                        "content": collection_data["documents"][i] if collection_data.get("documents") else "",
                        "metadata": collection_data["metadatas"][i] if collection_data.get("metadatas") else {}
                    })

                    if collection_data.get("embeddings"):
                        export_data["embeddings"].append({
                            "id": doc_id,
                            "vector": collection_data["embeddings"][i]
                        })

            # Write to file
            output_file = Path(output_path_obj)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            if format == "json":
                with open(output_file, 'w') as f:
                    json.dump(export_data, f, indent=2)
            elif format == "yaml":
                import yaml
                with open(output_file, 'w') as f:
                    yaml.safe_dump(export_data, f)

            logger.info(f"Export complete: {output_file.stat().st_size} bytes")

            return {
                "success": True,
                "project_id": project_id,
                "project_name": project.name,
                "output_path": str(output_file.absolute()),
                "format": format,
                "document_count": len(export_data["documents"]),
                "file_size_bytes": output_file.stat().st_size,
                "message": "Project exported successfully",
            }

        except ValueError as e:
            logger.error(f"Export validation error: {e}", exc_info=True)
            return {"error": str(e), "error_type": "ValidationError"}
        except IOError as e:
            logger.error(f"Export I/O error: {e}", exc_info=True)
            return {"error": str(e), "error_type": "ExportError"}
        except Exception as e:
            logger.error(f"Export error: {e}", exc_info=True)
            return {
                "error": str(e),
                "error_type": "ExportError",
                "project_id": project_id,
            }

    async def kb_import_project(
        self,
        file_path: str,
        project_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Import project from export file.

        Args:
            file_path: Path to export file (JSON, YAML, or ZIP)
            project_name: Optional new name for imported project

        Returns:
            Import result with project_id and status
        """
        try:
            # Validate inputs
            try:
                file_path_obj = self.validator.validate_file_path(
                    file_path, "file_path", must_exist=True,
                    allowed_extensions=[".json", ".yaml", ".yml", ".zip"]
                )
                if project_name:
                    project_name = self.validator.validate_string(
                        project_name,
                        "project_name",
                        required=False,
                        min_length=1,
                        max_length=255,
                    )
            except ValidationError as e:
                logger.warning(f"Import validation error: {e.message}")
                return e.to_dict()

            # Determine format from extension
            file_ext = file_path_obj.suffix.lower()

            # For ZIP format, use project_manager's built-in import
            if file_ext == ".zip":
                project_id = self.project_manager.import_project(
                    str(file_path_obj), new_project_name=project_name
                )

                # Get imported project details
                project = self.project_manager.get_project(project_id)

                logger.info(f"Project imported: {project_id} from {file_path}")

                return {
                    "success": True,
                    "project_id": project_id,
                    "project_name": project.name if project else None,
                    "file_path": str(file_path_obj.absolute()),
                    "message": "Project imported successfully",
                }

            # For JSON/YAML, import directly
            logger.info(f"Importing from: {file_path}")

            # Load export data
            try:
                if file_ext == ".json":
                    with open(file_path_obj) as f:
                        export_data = json.load(f)
                else:  # .yaml or .yml
                    import yaml
                    with open(file_path_obj) as f:
                        export_data = yaml.safe_load(f)
            except (json.JSONDecodeError, Exception) as e:
                return {
                    "error": f"Invalid file format: {str(e)}",
                    "error_type": "ValidationError"
                }

            # Validate export data structure
            required_keys = ["version", "project", "documents", "embeddings"]
            if not all(key in export_data for key in required_keys):
                return {
                    "error": "Invalid export file structure",
                    "error_type": "ValidationError"
                }

            # Get original project data
            original_project = export_data["project"]

            # Generate new project name if not provided
            if not project_name:
                project_name = f"{original_project['name']} (imported)"

            logger.info(f"Creating new project: {project_name}")

            # Create new project
            new_project = self.project_manager.create_project(
                name=project_name,
                description=original_project.get("description", ""),
                embedding_model=original_project.get("embedding_model", "all-MiniLM-L6-v2"),
                metadata={
                    **original_project.get("metadata", {}),
                    "imported_from": original_project["project_id"],
                    "imported_at": datetime.now(timezone.utc).isoformat()
                }
            )

            # Get collection for new project
            collection = self.project_manager.get_project_collection(new_project.project_id)
            if not collection:
                return {
                    "error": "Failed to create collection for imported project",
                    "error_type": "ImportError"
                }

            # Get embedding engine
            embedding_engine = EmbeddingEngine(
                model_name=new_project.embedding_model,
                cache_size=self.config.cache_capacity
            )

            # Import documents and embeddings
            doc_count = 0
            if export_data.get("documents"):
                ids = []
                documents = []
                metadatas = []
                embeddings = []

                # Build parallel arrays for ChromaDB
                for doc in export_data["documents"]:
                    ids.append(doc["id"])
                    documents.append(doc.get("content", ""))
                    metadatas.append(doc.get("metadata", {}))

                # Get embeddings (use existing if available, otherwise regenerate)
                embedding_map = {e["id"]: e["vector"] for e in export_data.get("embeddings", [])}
                for doc_id in ids:
                    if doc_id in embedding_map:
                        embeddings.append(embedding_map[doc_id])
                    else:
                        # Regenerate embedding for this document
                        idx = ids.index(doc_id)
                        vec = embedding_engine.embed(documents[idx])
                        embeddings.append(vec.tolist())

                # Add to collection
                collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas,
                    embeddings=embeddings
                )

                doc_count = len(ids)

            logger.info(f"Import complete: {new_project.project_id} ({doc_count} documents)")

            return {
                "success": True,
                "project_id": new_project.project_id,
                "project_name": new_project.name,
                "document_count": doc_count,
                "file_path": str(file_path_obj.absolute()),
                "original_project_id": original_project["project_id"],
                "message": "Project imported successfully",
            }

        except ValueError as e:
            logger.error(f"Import validation error: {e}", exc_info=True)
            return {"error": str(e), "error_type": "ValidationError"}
        except IOError as e:
            logger.error(f"Import I/O error: {e}", exc_info=True)
            return {"error": str(e), "error_type": "ImportError"}
        except Exception as e:
            logger.error(f"Import error: {e}", exc_info=True)
            return {"error": str(e), "error_type": "ImportError"}

    async def kb_project_health(self, project_id: str) -> Dict[str, Any]:
        """Get project health status with metrics and alerts.

        Args:
            project_id: Project identifier

        Returns:
            Health status with metrics, alerts, and recommendations
        """
        try:
            # Validate inputs
            try:
                project_id = self.validator.validate_project_id(project_id)
            except ValidationError as e:
                logger.warning(f"Health check validation error: {e.message}")
                return e.to_dict()

            # Get health status from monitor
            health_status = self.health_monitor.get_project_health(project_id)

            logger.info(
                f"Health check completed: project={project_id}, "
                f"status={health_status.get('status', 'unknown')}"
            )

            return health_status

        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            return {
                "error": str(e),
                "error_type": "HealthCheckError",
                "project_id": project_id,
                "status": "error",
            }

    async def kb_batch_ingest(
        self, project_id: str, file_paths: List[str]
    ) -> Dict[str, Any]:
        """Ingest multiple files in batch.

        Args:
            project_id: Project identifier
            file_paths: List of file paths to ingest

        Returns:
            Batch ingestion result with success/failure counts and doc_ids
        """
        try:
            # Validate inputs
            try:
                project_id = self.validator.validate_project_id(project_id)
                file_paths = self.validator.validate_list(
                    file_paths,
                    "file_paths",
                    required=True,
                    min_length=1,
                    max_length=1000,
                    item_type=str,
                )
            except ValidationError as e:
                logger.warning(f"Batch ingest validation error: {e.message}")
                return e.to_dict()

            # Verify project exists
            project = self.project_manager.get_project(project_id)
            if not project:
                return {
                    "error": f"Project not found: {project_id}",
                    "error_type": "ProjectNotFound",
                }

            # Get project components
            vector_store = VectorStore(
                persist_directory=self.config.chroma_path,
                collection_name=project.collection_name,
            )

            embedding_engine = EmbeddingEngine(
                model_name=project.embedding_model,
                cache_size=self.config.cache_capacity,
            )

            # Process files in batch
            success_count = 0
            failed_count = 0
            doc_ids = []
            errors = []

            logger.info(f"Starting batch ingest: {len(file_paths)} files")

            for file_path in file_paths:
                try:
                    # Validate file path
                    file_path_obj = Path(file_path)
                    if not file_path_obj.exists():
                        failed_count += 1
                        errors.append(
                            {"file": file_path, "error": "File not found"}
                        )
                        continue

                    # Read and ingest file
                    file_content = file_path_obj.read_text()
                    doc_id = f"doc_{int(time.time() * 1000000)}"
                    embedding = embedding_engine.embed(file_content)

                    doc_metadata = {
                        "source": "batch_ingest",
                        "file_path": str(file_path),
                        "file_name": file_path_obj.name,
                        "project_id": project_id,
                    }

                    vector_store.add(
                        ids=doc_id,
                        embeddings=embedding,
                        documents=file_content,
                        metadatas=doc_metadata,
                    )

                    success_count += 1
                    doc_ids.append(doc_id)

                except Exception as e:
                    failed_count += 1
                    errors.append({"file": file_path, "error": str(e)})
                    logger.warning(f"Failed to ingest {file_path}: {e}")

            logger.info(
                f"Batch ingest completed: success={success_count}, "
                f"failed={failed_count}"
            )

            return {
                "success": True,
                "project_id": project_id,
                "project_name": project.name,
                "total_files": len(file_paths),
                "success_count": success_count,
                "failed_count": failed_count,
                "doc_ids": doc_ids,
                "errors": errors if errors else None,
                "message": f"Batch ingestion completed: {success_count}/{len(file_paths)} files succeeded",
            }

        except Exception as e:
            logger.error(f"Batch ingest error: {e}", exc_info=True)
            return {
                "error": str(e),
                "error_type": "BatchIngestError",
                "project_id": project_id,
            }

    async def kb_delete_document(
        self, project_id: str, doc_id: str
    ) -> Dict[str, Any]:
        """Delete a document from project.

        Args:
            project_id: Project identifier
            doc_id: Document identifier to delete

        Returns:
            Deletion result with status
        """
        try:
            # Validate inputs
            try:
                project_id = self.validator.validate_project_id(project_id)
                doc_id = self.validator.validate_string(
                    doc_id, "doc_id", required=True, min_length=1
                )
            except ValidationError as e:
                logger.warning(f"Delete document validation error: {e.message}")
                return e.to_dict()

            # Verify project exists
            project = self.project_manager.get_project(project_id)
            if not project:
                return {
                    "error": f"Project not found: {project_id}",
                    "error_type": "ProjectNotFound",
                }

            # Get project vector store
            vector_store = VectorStore(
                persist_directory=self.config.chroma_path,
                collection_name=project.collection_name,
            )

            # Check if document exists
            try:
                doc_data = vector_store.get(ids=doc_id)
                if not doc_data.get("ids"):
                    return {
                        "error": f"Document not found: {doc_id}",
                        "error_type": "DocumentNotFound",
                        "project_id": project_id,
                    }
            except Exception as e:
                logger.warning(f"Error checking document existence: {e}")

            # Delete document
            vector_store.delete(ids=doc_id)

            logger.info(f"Document deleted: project={project_id}, doc_id={doc_id}")

            return {
                "success": True,
                "project_id": project_id,
                "doc_id": doc_id,
                "message": f"Document {doc_id} deleted successfully",
            }

        except Exception as e:
            logger.error(f"Delete document error: {e}", exc_info=True)
            return {
                "error": str(e),
                "error_type": "DeleteDocumentError",
                "project_id": project_id,
                "doc_id": doc_id,
            }

