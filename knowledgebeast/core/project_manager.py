"""Multi-Project Isolation and Management.

This module provides complete project isolation for KnowledgeBeast, allowing
multiple independent projects to coexist without data leakage.

Features:
- Per-project ChromaDB collection isolation
- Per-project query cache isolation
- Persistent project metadata storage (SQLite)
- Thread-safe CRUD operations
- Support for 100+ concurrent projects
- Complete cleanup and teardown

Architecture:
- Project: Dataclass representing project metadata
- ProjectManager: Thread-safe project lifecycle management
- SQLite: Persistent metadata storage
- ChromaDB: Per-project collection isolation (kb_project_{project_id})
- LRUCache: Per-project query cache isolation
"""

import sqlite3
import threading
import time
import uuid
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

import chromadb
from chromadb.config import Settings

from knowledgebeast.core.cache import LRUCache

logger = logging.getLogger(__name__)

__all__ = ['Project', 'ProjectManager']


@dataclass
class Project:
    """Project metadata and configuration.

    Attributes:
        project_id: Unique project identifier (UUID)
        name: Human-readable project name
        description: Project description
        collection_name: ChromaDB collection name (kb_project_{project_id})
        embedding_model: Embedding model for this project
        created_at: Project creation timestamp
        updated_at: Last update timestamp
        metadata: Additional project metadata (JSON-compatible dict)
    """
    project_id: str
    name: str
    description: str = ""
    collection_name: str = ""
    embedding_model: str = "all-MiniLM-L6-v2"
    created_at: str = ""
    updated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize computed fields."""
        if not self.collection_name:
            self.collection_name = f"kb_project_{self.project_id}"

        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()

        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert project to dictionary.

        Returns:
            Dictionary representation of project
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """Create project from dictionary.

        Args:
            data: Dictionary with project data

        Returns:
            Project instance
        """
        return cls(**data)


class ProjectManager:
    """Thread-safe multi-project lifecycle management.

    This class provides complete project isolation with per-project:
    - ChromaDB collections
    - Query caches
    - Metadata storage

    Thread Safety:
        - All public methods protected by RLock
        - Atomic CRUD operations
        - Safe concurrent project access

    Storage:
        - SQLite for project metadata
        - ChromaDB for per-project collections
        - In-memory LRU caches per project

    Connection Pooling:
        - Singleton ChromaDB client (thread-safe)
        - Collection cache for fast access
        - Minimizes connection overhead

    Usage:
        manager = ProjectManager(storage_path="./projects.db")

        # Create project
        project = manager.create_project(
            name="My Project",
            description="Audio ML project",
            embedding_model="all-MiniLM-L6-v2"
        )

        # Get project
        project = manager.get_project(project_id)

        # List all projects
        projects = manager.list_projects()

        # Delete project (with cleanup)
        manager.delete_project(project_id)
    """

    def __init__(
        self,
        storage_path: str = "projects.db",
        chroma_path: str = "./chroma_db",
        cache_capacity: int = 100
    ):
        """Initialize project manager.

        Args:
            storage_path: Path to SQLite database file
            chroma_path: Path to ChromaDB storage directory
            cache_capacity: Per-project cache capacity (default: 100)
        """
        self.storage_path = Path(storage_path)
        self.chroma_path = Path(chroma_path)
        self.cache_capacity = cache_capacity

        # Thread safety lock
        self._lock = threading.RLock()

        # Per-project caches (project_id -> LRUCache)
        self._project_caches: Dict[str, LRUCache] = {}

        # ChromaDB client (lazy initialization with singleton pattern)
        self._chroma_client: Optional[chromadb.Client] = None
        self._client_lock = threading.RLock()

        # Collection cache for fast access (project_id -> Collection)
        self._collection_cache: Dict[str, Any] = {}
        self._cache_lock = threading.RLock()

        # Initialize database
        self._init_database()

        logger.info(f"ProjectManager initialized: storage={storage_path}, chroma={chroma_path}")

    def _init_database(self) -> None:
        """Initialize SQLite database schema."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    collection_name TEXT NOT NULL,
                    embedding_model TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT
                )
            """)

            # Create index on name for faster lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_project_name
                ON projects(name)
            """)

            conn.commit()
            logger.debug("Database schema initialized")

    @contextmanager
    def _get_db_connection(self):
        """Get database connection context manager.

        Yields:
            SQLite connection
        """
        conn = sqlite3.connect(str(self.storage_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    @property
    def chroma_client(self) -> chromadb.Client:
        """Lazy-initialized singleton ChromaDB client (thread-safe).

        Uses double-check locking pattern for optimal performance.

        Returns:
            ChromaDB client instance
        """
        if self._chroma_client is None:
            with self._client_lock:
                # Double-check locking pattern
                if self._chroma_client is None:
                    self.chroma_path.mkdir(parents=True, exist_ok=True)
                    # Use PersistentClient for proper persistence
                    self._chroma_client = chromadb.PersistentClient(
                        path=str(self.chroma_path)
                    )
                    logger.info(f"ChromaDB client initialized (singleton): {self.chroma_path}")

        return self._chroma_client

    def get_collection(self, project_id: str) -> Optional[Any]:
        """Get or create cached collection (thread-safe).

        Uses collection cache to minimize ChromaDB access overhead.

        Args:
            project_id: Project identifier

        Returns:
            ChromaDB collection or None if project not found
        """
        with self._cache_lock:
            # Check if collection is cached
            if project_id in self._collection_cache:
                logger.debug(f"Collection cache hit for project: {project_id}")
                return self._collection_cache[project_id]

            # Verify project exists
            project = self._load_project_from_db(project_id)
            if not project:
                logger.warning(f"Project not found: {project_id}")
                return None

            # Get or create collection
            try:
                collection = self.chroma_client.get_or_create_collection(
                    name=project.collection_name,
                    metadata={
                        "project_id": project.project_id,
                        "embedding_model": project.embedding_model
                    }
                )
                # Cache the collection
                self._collection_cache[project_id] = collection
                logger.debug(f"Collection cached for project: {project_id}")
                return collection
            except Exception as e:
                logger.error(f"Failed to get collection for project {project_id}: {e}")
                return None

    def invalidate_collection_cache(self, project_id: str) -> None:
        """Invalidate cached collection (e.g., after deletion).

        Args:
            project_id: Project identifier
        """
        with self._cache_lock:
            if project_id in self._collection_cache:
                del self._collection_cache[project_id]
                logger.debug(f"Invalidated collection cache for project: {project_id}")

    def _get_chroma_client(self) -> chromadb.Client:
        """Get or create ChromaDB client (deprecated - use chroma_client property).

        Returns:
            ChromaDB client instance
        """
        return self.chroma_client

    def create_project(
        self,
        name: str,
        description: str = "",
        embedding_model: str = "all-MiniLM-L6-v2",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Project:
        """Create a new project with isolated resources.

        Args:
            name: Project name
            description: Project description
            embedding_model: Embedding model to use
            metadata: Additional metadata

        Returns:
            Created Project instance

        Raises:
            ValueError: If project name already exists
        """
        with self._lock:
            # Check for duplicate name
            existing = self._get_project_by_name(name)
            if existing:
                raise ValueError(f"Project with name '{name}' already exists")

            # Generate unique ID
            project_id = str(uuid.uuid4())

            # Create project
            project = Project(
                project_id=project_id,
                name=name,
                description=description,
                embedding_model=embedding_model,
                metadata=metadata or {}
            )

            # Store in database
            self._store_project(project)

            # Initialize per-project resources
            self._initialize_project_resources(project)

            logger.info(f"Created project: {project_id} ({name})")
            return project

    def _store_project(self, project: Project) -> None:
        """Store project in database.

        Args:
            project: Project to store
        """
        import json

        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO projects
                (project_id, name, description, collection_name, embedding_model,
                 created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project.project_id,
                project.name,
                project.description,
                project.collection_name,
                project.embedding_model,
                project.created_at,
                project.updated_at,
                json.dumps(project.metadata)
            ))
            conn.commit()

    def _initialize_project_resources(self, project: Project) -> None:
        """Initialize per-project resources.

        Args:
            project: Project to initialize resources for
        """
        # Initialize query cache
        self._project_caches[project.project_id] = LRUCache(
            capacity=self.cache_capacity
        )

        # Initialize ChromaDB collection using get_collection (which caches it)
        # This uses the connection pooling pattern
        collection = self.get_collection(project.project_id)
        if collection:
            logger.debug(f"Initialized ChromaDB collection: {project.collection_name}")
        else:
            logger.warning(f"Failed to initialize collection for project: {project.project_id}")

    def get_project(self, project_id: str) -> Optional[Project]:
        """Get project by ID.

        Args:
            project_id: Project identifier

        Returns:
            Project instance or None if not found
        """
        with self._lock:
            return self._load_project_from_db(project_id)

    def _load_project_from_db(self, project_id: str) -> Optional[Project]:
        """Load project from database.

        Args:
            project_id: Project identifier

        Returns:
            Project instance or None if not found
        """
        import json

        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM projects WHERE project_id = ?",
                (project_id,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            return Project(
                project_id=row['project_id'],
                name=row['name'],
                description=row['description'],
                collection_name=row['collection_name'],
                embedding_model=row['embedding_model'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                metadata=json.loads(row['metadata']) if row['metadata'] else {}
            )

    def _get_project_by_name(self, name: str) -> Optional[Project]:
        """Get project by name.

        Args:
            name: Project name

        Returns:
            Project instance or None if not found
        """
        import json

        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM projects WHERE name = ?",
                (name,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            return Project(
                project_id=row['project_id'],
                name=row['name'],
                description=row['description'],
                collection_name=row['collection_name'],
                embedding_model=row['embedding_model'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                metadata=json.loads(row['metadata']) if row['metadata'] else {}
            )

    def list_projects(self) -> List[Project]:
        """List all projects.

        Returns:
            List of all Project instances
        """
        import json

        with self._lock:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM projects ORDER BY created_at DESC")
                rows = cursor.fetchall()

                projects = []
                for row in rows:
                    project = Project(
                        project_id=row['project_id'],
                        name=row['name'],
                        description=row['description'],
                        collection_name=row['collection_name'],
                        embedding_model=row['embedding_model'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at'],
                        metadata=json.loads(row['metadata']) if row['metadata'] else {}
                    )
                    projects.append(project)

                return projects

    def update_project(
        self,
        project_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        embedding_model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Project]:
        """Update project metadata.

        Args:
            project_id: Project identifier
            name: New name (optional)
            description: New description (optional)
            embedding_model: New embedding model (optional)
            metadata: New metadata (optional)

        Returns:
            Updated Project instance or None if not found
        """
        import json

        with self._lock:
            project = self._load_project_from_db(project_id)
            if not project:
                return None

            # Update fields
            if name is not None:
                # Check for duplicate name
                existing = self._get_project_by_name(name)
                if existing and existing.project_id != project_id:
                    raise ValueError(f"Project with name '{name}' already exists")
                project.name = name

            if description is not None:
                project.description = description

            if embedding_model is not None:
                project.embedding_model = embedding_model

            if metadata is not None:
                project.metadata = metadata

            project.updated_at = datetime.utcnow().isoformat()

            # Update in database
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE projects
                    SET name = ?, description = ?, embedding_model = ?,
                        updated_at = ?, metadata = ?
                    WHERE project_id = ?
                """, (
                    project.name,
                    project.description,
                    project.embedding_model,
                    project.updated_at,
                    json.dumps(project.metadata),
                    project_id
                ))
                conn.commit()

            logger.info(f"Updated project: {project_id}")
            return project

    def delete_project(self, project_id: str) -> bool:
        """Delete project and cleanup all resources.

        Args:
            project_id: Project identifier

        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            project = self._load_project_from_db(project_id)
            if not project:
                return False

            # Cleanup resources
            self._cleanup_project_resources(project)

            # Delete from database
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM projects WHERE project_id = ?",
                    (project_id,)
                )
                conn.commit()

            logger.info(f"Deleted project: {project_id}")
            return True

    def _cleanup_project_resources(self, project: Project) -> None:
        """Cleanup all project resources.

        Args:
            project: Project to cleanup
        """
        # Clear query cache
        if project.project_id in self._project_caches:
            self._project_caches[project.project_id].clear()
            del self._project_caches[project.project_id]
            logger.debug(f"Cleared cache for project: {project.project_id}")

        # Invalidate collection cache
        self.invalidate_collection_cache(project.project_id)

        # Delete ChromaDB collection
        try:
            self.chroma_client.delete_collection(name=project.collection_name)
            logger.debug(f"Deleted ChromaDB collection: {project.collection_name}")
        except Exception as e:
            logger.warning(f"Failed to delete ChromaDB collection: {e}")

    def get_project_cache(self, project_id: str) -> Optional[LRUCache]:
        """Get per-project query cache.

        Args:
            project_id: Project identifier

        Returns:
            LRUCache instance or None if project not found
        """
        with self._lock:
            if project_id not in self._project_caches:
                # Verify project exists and initialize cache
                project = self._load_project_from_db(project_id)
                if not project:
                    return None

                self._project_caches[project_id] = LRUCache(
                    capacity=self.cache_capacity
                )

            return self._project_caches[project_id]

    def get_project_collection(self, project_id: str) -> Optional[Any]:
        """Get per-project ChromaDB collection.

        Uses connection pooling and collection cache for optimal performance.

        Args:
            project_id: Project identifier

        Returns:
            ChromaDB collection or None if project not found
        """
        # Delegate to get_collection which handles caching
        return self.get_collection(project_id)

    def clear_project_cache(self, project_id: str) -> bool:
        """Clear per-project query cache.

        Args:
            project_id: Project identifier

        Returns:
            True if cleared, False if project not found
        """
        with self._lock:
            cache = self.get_project_cache(project_id)
            if cache:
                cache.clear()
                logger.debug(f"Cleared cache for project: {project_id}")
                return True
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get project manager statistics.

        Returns:
            Dictionary with statistics
        """
        with self._lock:
            projects = self.list_projects()

            total_cache_size = sum(
                len(cache) for cache in self._project_caches.values()
            )

            return {
                'total_projects': len(projects),
                'total_cache_entries': total_cache_size,
                'cache_capacity_per_project': self.cache_capacity,
                'storage_path': str(self.storage_path),
                'chroma_path': str(self.chroma_path)
            }

    def cleanup_all(self) -> None:
        """Cleanup all project resources (for testing/teardown)."""
        with self._lock:
            projects = self.list_projects()
            for project in projects:
                self._cleanup_project_resources(project)

            # Clear all caches
            self._project_caches.clear()

            logger.info("Cleaned up all project resources")

    def close(self) -> None:
        """Close ChromaDB client and clear all caches.

        Should be called when shutting down the ProjectManager.
        """
        with self._client_lock:
            self._chroma_client = None

        with self._cache_lock:
            self._collection_cache.clear()

        with self._lock:
            self._project_caches.clear()

        logger.info("ProjectManager closed and all caches cleared")

    def __enter__(self) -> 'ProjectManager':
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - cleanup resources."""
        try:
            self.cleanup_all()
        except Exception as e:
            logger.error(f"Cleanup error in __exit__: {e}", exc_info=True)

        return False
