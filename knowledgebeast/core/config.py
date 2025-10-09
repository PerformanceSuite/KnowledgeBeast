"""Configuration management for KnowledgeBeast."""

import os
import multiprocessing
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any
import yaml


@dataclass
class KnowledgeBeastConfig:
    """Configuration for KnowledgeBeast RAG engine.

    Supports environment variables with KB_ prefix:
    - KB_KNOWLEDGE_DIRS: Comma-separated list of knowledge directories
    - KB_CACHE_FILE: Path to cache file
    - KB_MAX_CACHE_SIZE: Maximum number of cached queries
    - KB_HEARTBEAT_INTERVAL: Heartbeat interval in seconds
    - KB_AUTO_WARM: Auto-warm on initialization (true/false)
    - KB_MAX_WORKERS: Number of parallel workers for document ingestion
    - KB_EMBEDDING_MODEL: Embedding model name
    - KB_VECTOR_SEARCH_MODE: Search mode (vector, keyword, hybrid)
    - KB_CHUNK_SIZE: Document chunk size for embeddings
    - KB_CHUNK_OVERLAP: Chunk overlap size
    - KB_USE_VECTOR_SEARCH: Enable vector search (true/false)
    - KB_CHROMADB_PATH: Path to ChromaDB storage

    Attributes:
        knowledge_dirs: List of knowledge base directories to ingest
        cache_file: Path to cache file for persistent storage
        max_cache_size: Maximum number of cached queries (LRU eviction)
        heartbeat_interval: Heartbeat interval in seconds
        auto_warm: Auto-warm knowledge base on initialization
        warming_queries: List of queries to execute during warming
        enable_progress_callbacks: Enable progress callbacks for long operations
        verbose: Enable verbose logging
        max_workers: Maximum number of parallel workers for document ingestion (default: CPU count)
        embedding_model: Sentence-transformer model for embeddings
        vector_search_mode: Search mode (vector, keyword, hybrid)
        chunk_size: Document chunk size for embeddings
        chunk_overlap: Chunk overlap size
        use_vector_search: Enable vector search (default: True for v2+)
        chromadb_path: Path to ChromaDB persistent storage
    """

    # Knowledge base directories (supports multiple)
    knowledge_dirs: List[Path] = field(default_factory=lambda: [Path("knowledge-base")])

    # Cache settings
    cache_file: Path = field(default_factory=lambda: Path(".knowledge_cache.pkl"))
    max_cache_size: int = 100

    # Heartbeat settings
    heartbeat_interval: int = 300  # 5 minutes default

    # Warming settings
    auto_warm: bool = True
    warming_queries: List[str] = field(default_factory=lambda: [
        "claude code slash commands path",
        "librosa audio analysis parameters",
        "juce processBlock real-time audio",
        "supercollider synthdef patterns",
        "end-session cleanup procedure",
        "music theory chord progressions",
        "audio dsp fft algorithms"
    ])

    # Performance settings
    enable_progress_callbacks: bool = True
    verbose: bool = True
    max_workers: Optional[int] = None  # None = auto-detect CPU count

    # Vector RAG settings (v2+)
    embedding_model: str = "all-MiniLM-L6-v2"
    vector_search_mode: str = "hybrid"  # vector, keyword, hybrid
    chunk_size: int = 1000
    chunk_overlap: int = 200
    use_vector_search: bool = True
    chromadb_path: Path = field(default_factory=lambda: Path("./data/chromadb"))

    # Query expansion settings (Phase 2)
    query_expansion_enabled: bool = True
    query_expansion_synonyms: bool = True
    query_expansion_acronyms: bool = True
    query_expansion_max_expansions: int = 3

    # Semantic cache settings (Phase 2)
    semantic_cache_enabled: bool = True
    semantic_cache_similarity_threshold: float = 0.95
    semantic_cache_ttl_seconds: int = 3600  # 1 hour
    semantic_cache_max_entries: int = 10000

    def __post_init__(self) -> None:
        """Validate and load from environment variables."""
        # Load from environment variables if set
        if env_dirs := os.getenv('KB_KNOWLEDGE_DIRS'):
            self.knowledge_dirs = [Path(p.strip()) for p in env_dirs.split(',') if p.strip()]

        if env_cache := os.getenv('KB_CACHE_FILE'):
            self.cache_file = Path(env_cache)

        if env_cache_size := os.getenv('KB_MAX_CACHE_SIZE'):
            self.max_cache_size = int(env_cache_size)

        if env_interval := os.getenv('KB_HEARTBEAT_INTERVAL'):
            self.heartbeat_interval = int(env_interval)

        if env_auto_warm := os.getenv('KB_AUTO_WARM'):
            self.auto_warm = env_auto_warm.lower() in ('true', '1', 'yes')

        if env_max_workers := os.getenv('KB_MAX_WORKERS'):
            self.max_workers = int(env_max_workers)

        # Vector RAG environment variables
        if env_embedding_model := os.getenv('KB_EMBEDDING_MODEL'):
            self.embedding_model = env_embedding_model

        if env_search_mode := os.getenv('KB_VECTOR_SEARCH_MODE'):
            self.vector_search_mode = env_search_mode

        if env_chunk_size := os.getenv('KB_CHUNK_SIZE'):
            self.chunk_size = int(env_chunk_size)

        if env_chunk_overlap := os.getenv('KB_CHUNK_OVERLAP'):
            self.chunk_overlap = int(env_chunk_overlap)

        if env_use_vector := os.getenv('KB_USE_VECTOR_SEARCH'):
            self.use_vector_search = env_use_vector.lower() in ('true', '1', 'yes')

        if env_chromadb_path := os.getenv('KB_CHROMADB_PATH'):
            self.chromadb_path = Path(env_chromadb_path)

        # Query expansion environment variables
        if env_expansion_enabled := os.getenv('KB_QUERY_EXPANSION_ENABLED'):
            self.query_expansion_enabled = env_expansion_enabled.lower() in ('true', '1', 'yes')

        if env_expansion_synonyms := os.getenv('KB_QUERY_EXPANSION_SYNONYMS'):
            self.query_expansion_synonyms = env_expansion_synonyms.lower() in ('true', '1', 'yes')

        if env_expansion_acronyms := os.getenv('KB_QUERY_EXPANSION_ACRONYMS'):
            self.query_expansion_acronyms = env_expansion_acronyms.lower() in ('true', '1', 'yes')

        if env_expansion_max := os.getenv('KB_QUERY_EXPANSION_MAX_EXPANSIONS'):
            self.query_expansion_max_expansions = int(env_expansion_max)

        # Semantic cache environment variables
        if env_cache_enabled := os.getenv('KB_SEMANTIC_CACHE_ENABLED'):
            self.semantic_cache_enabled = env_cache_enabled.lower() in ('true', '1', 'yes')

        if env_cache_threshold := os.getenv('KB_SEMANTIC_CACHE_SIMILARITY_THRESHOLD'):
            self.semantic_cache_similarity_threshold = float(env_cache_threshold)

        if env_cache_ttl := os.getenv('KB_SEMANTIC_CACHE_TTL_SECONDS'):
            self.semantic_cache_ttl_seconds = int(env_cache_ttl)

        if env_cache_max := os.getenv('KB_SEMANTIC_CACHE_MAX_ENTRIES'):
            self.semantic_cache_max_entries = int(env_cache_max)

        # Auto-detect CPU count if not set
        if self.max_workers is None:
            self.max_workers = multiprocessing.cpu_count()

        # Validate
        if not self.knowledge_dirs:
            raise ValueError("At least one knowledge directory must be specified")

        if self.max_cache_size <= 0:
            raise ValueError("max_cache_size must be positive")

        if self.heartbeat_interval < 10:
            raise ValueError("heartbeat_interval must be at least 10 seconds")

        if self.max_workers <= 0:
            raise ValueError("max_workers must be positive")

        # Validate vector RAG settings
        if self.vector_search_mode not in ('vector', 'keyword', 'hybrid'):
            raise ValueError("vector_search_mode must be 'vector', 'keyword', or 'hybrid'")

        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be positive")

        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")

        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")

        # Validate query expansion settings
        if self.query_expansion_max_expansions < 0:
            raise ValueError("query_expansion_max_expansions must be non-negative")

        # Validate semantic cache settings
        if not 0 <= self.semantic_cache_similarity_threshold <= 1:
            raise ValueError("semantic_cache_similarity_threshold must be between 0 and 1")

        if self.semantic_cache_ttl_seconds <= 0:
            raise ValueError("semantic_cache_ttl_seconds must be positive")

        if self.semantic_cache_max_entries <= 0:
            raise ValueError("semantic_cache_max_entries must be positive")

    def get_all_knowledge_paths(self) -> List[Path]:
        """Get all knowledge directory paths.

        Returns:
            List of Path objects for all knowledge directories
        """
        return self.knowledge_dirs

    def print_config(self) -> None:
        """Print current configuration."""
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"KnowledgeBeast Configuration: dirs={len(self.knowledge_dirs)}, "
                   f"cache={self.cache_file}, max_cache={self.max_cache_size}, "
                   f"heartbeat={self.heartbeat_interval}s, auto_warm={self.auto_warm}, "
                   f"max_workers={self.max_workers}, vector_search={self.use_vector_search}")

        if not self.verbose:
            return

        print("⚙️  KnowledgeBeast Configuration:")
        print(f"   Knowledge Directories: {', '.join(str(p) for p in self.knowledge_dirs)}")
        print(f"   Cache File: {self.cache_file}")
        print(f"   Max Cache Size: {self.max_cache_size}")
        print(f"   Heartbeat Interval: {self.heartbeat_interval}s")
        print(f"   Auto Warm: {self.auto_warm}")
        print(f"   Warming Queries: {len(self.warming_queries)} queries")
        print(f"   Progress Callbacks: {self.enable_progress_callbacks}")
        print(f"   Verbose: {self.verbose}")
        print(f"   Max Workers: {self.max_workers}")
        print()
        print("🔍 Vector RAG Configuration:")
        print(f"   Use Vector Search: {self.use_vector_search}")
        print(f"   Embedding Model: {self.embedding_model}")
        print(f"   Search Mode: {self.vector_search_mode}")
        print(f"   Chunk Size: {self.chunk_size}")
        print(f"   Chunk Overlap: {self.chunk_overlap}")
        print(f"   ChromaDB Path: {self.chromadb_path}")
        print()


class Config:
    """Knowledge base configuration for CLI."""

    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.name = data.get('name', 'KnowledgeBeast')
        self.description = data.get('description', '')
        self.version = data.get('version', '1.0')
        self.paths = data.get('paths', {})
        self.cache = data.get('cache', {})
        self.search = data.get('search', {})
        self.heartbeat = data.get('heartbeat', {})

    @classmethod
    def from_file(cls, path: Path) -> 'Config':
        """Load configuration from YAML file."""
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(data)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self.data.get(key, default)
