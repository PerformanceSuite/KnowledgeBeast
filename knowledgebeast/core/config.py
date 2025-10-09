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

    # Advanced chunking settings (Phase 2)
    chunking_strategy: str = "auto"  # semantic, recursive, markdown, code, auto
    semantic_similarity_threshold: float = 0.7
    respect_markdown_structure: bool = True
    preserve_code_blocks: bool = True

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

        # Advanced chunking environment variables
        if env_chunking_strategy := os.getenv('KB_CHUNKING_STRATEGY'):
            self.chunking_strategy = env_chunking_strategy

        if env_semantic_threshold := os.getenv('KB_SEMANTIC_SIMILARITY_THRESHOLD'):
            self.semantic_similarity_threshold = float(env_semantic_threshold)

        if env_respect_md := os.getenv('KB_RESPECT_MARKDOWN_STRUCTURE'):
            self.respect_markdown_structure = env_respect_md.lower() in ('true', '1', 'yes')

        if env_preserve_code := os.getenv('KB_PRESERVE_CODE_BLOCKS'):
            self.preserve_code_blocks = env_preserve_code.lower() in ('true', '1', 'yes')

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

        # Validate chunking settings
        valid_strategies = ('semantic', 'recursive', 'markdown', 'code', 'auto')
        if self.chunking_strategy not in valid_strategies:
            raise ValueError(f"chunking_strategy must be one of {valid_strategies}")

        if not 0.0 <= self.semantic_similarity_threshold <= 1.0:
            raise ValueError("semantic_similarity_threshold must be between 0.0 and 1.0")

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
        print("📄 Advanced Chunking Configuration:")
        print(f"   Chunking Strategy: {self.chunking_strategy}")
        print(f"   Semantic Similarity Threshold: {self.semantic_similarity_threshold}")
        print(f"   Respect Markdown Structure: {self.respect_markdown_structure}")
        print(f"   Preserve Code Blocks: {self.preserve_code_blocks}")
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
