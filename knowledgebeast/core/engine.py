#!/usr/bin/env python3
"""
Enhanced Knowledge Base RAG Engine with Component-Based Architecture

This module has been refactored from a 685-line God Object into a clean,
component-based architecture following SOLID principles.

Features:
- Automatic startup warming for reduced first-query latency
- Semantic query caching with LRU eviction
- Background heartbeat for continuous interaction
- Performance metrics and health monitoring
- Auto-cache invalidation on file changes
- Multi-directory knowledge base support
- Progress callbacks for long operations
- Enhanced error handling and recovery

Architecture:
- DocumentRepository: Data access layer (Repository Pattern)
- CacheManager: Query cache management
- QueryEngine: Search and ranking logic
- DocumentIndexer: Document ingestion and index building
- KnowledgeBaseBuilder: Complex initialization (Builder Pattern)
- KnowledgeBase: Orchestrator using composition

Backward Compatibility:
All public APIs remain unchanged. Existing code will work without modification.
"""

import time
import logging
import threading
import types
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Callable, Literal

from knowledgebeast.core.config import KnowledgeBeastConfig
from knowledgebeast.core.repository import DocumentRepository
from knowledgebeast.core.cache_manager import CacheManager
from knowledgebeast.core.query_engine import QueryEngine, HybridQueryEngine
from knowledgebeast.core.indexer import DocumentIndexer
from knowledgebeast.core.embeddings import EmbeddingEngine
from knowledgebeast.core.vector_store import VectorStore

# Configure logging
logger = logging.getLogger(__name__)

__all__ = ['KnowledgeBase']


class KnowledgeBase:
    """
    RAG Knowledge Base with warming, caching, and performance optimization.

    This class has been refactored to use composition, delegating responsibilities
    to specialized components while maintaining full backward compatibility.

    Components:
    - repository: Handles document storage and index management
    - cache_manager: Manages query result caching
    - query_engine: Executes queries and ranks results
    - indexer: Handles document ingestion and index building

    Features:
    - Multi-directory knowledge base support
    - Automatic cache warming on startup
    - LRU query caching with configurable size
    - Stale cache detection and auto-rebuild
    - Progress callbacks for long operations
    - Thread-safe operation
    - Comprehensive error handling

    Usage:
        # With config object
        config = KnowledgeBeastConfig(
            knowledge_dirs=[Path("kb1"), Path("kb2")],
            auto_warm=True
        )
        kb = KnowledgeBase(config)
        results = kb.query("librosa best practices")
        stats = kb.get_stats()

        # With defaults
        kb = KnowledgeBase()
        results = kb.query("audio processing")

        # Using Builder Pattern (advanced)
        from knowledgebeast.core.builder import KnowledgeBaseBuilder
        kb = (KnowledgeBaseBuilder()
              .with_config(config)
              .with_progress_callback(callback)
              .build())
    """

    def __init__(
        self,
        config: Optional[KnowledgeBeastConfig] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        enable_vector: bool = True,
        embedding_model: str = "all-MiniLM-L6-v2",
        vector_cache_size: int = 1000,
        persist_directory: Optional[str] = None
    ):
        """
        Initialize Knowledge Base with optional config and callbacks.

        Args:
            config: KnowledgeBeastConfig instance (uses defaults if None)
            progress_callback: Optional callback for progress updates
                              Signature: callback(message: str, current: int, total: int)
            enable_vector: Enable vector embeddings and hybrid search (default: True)
            embedding_model: Sentence-transformer model for embeddings (default: all-MiniLM-L6-v2)
            vector_cache_size: Size of embedding cache (default: 1000)
            persist_directory: Directory for persistent vector storage (default: None = in-memory)
        """
        self.config = config or KnowledgeBeastConfig()
        self.progress_callback = progress_callback if self.config.enable_progress_callbacks else None
        self.enable_vector = enable_vector

        # Thread safety lock (reentrant for nested operations)
        self._lock = threading.RLock()

        # Initialize components using composition
        self._repository = DocumentRepository()
        self._cache_manager: CacheManager[List[Tuple[str, Dict]]] = CacheManager(
            capacity=self.config.max_cache_size
        )
        self._query_engine = QueryEngine(self._repository)

        # Initialize vector components if enabled
        self._embedding_engine: Optional[EmbeddingEngine] = None
        self._vector_store: Optional[VectorStore] = None
        self._embedding_model = embedding_model
        self._vector_cache_size = vector_cache_size

        if self.enable_vector:
            logger.info(f"Initializing vector RAG components (model: {embedding_model})")
            self._embedding_engine = EmbeddingEngine(
                model_name=embedding_model,
                cache_size=vector_cache_size
            )

            # Set up persist directory (default to .chroma in project root)
            if persist_directory is None:
                persist_directory = str(Path(self.config.cache_file).parent / ".chroma")

            self._vector_store = VectorStore(
                persist_directory=persist_directory,
                collection_name="knowledgebeast_docs"
            )

            logger.info("Vector RAG components initialized successfully")

        # Initialize indexer with vector components
        self._indexer = DocumentIndexer(
            self.config,
            self._repository,
            self.progress_callback,
            enable_vector=enable_vector,
            embedding_engine=self._embedding_engine,
            vector_store=self._vector_store
        )

        # Performance metrics
        self.last_access = time.time()
        self.stats = {
            'queries': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'warm_queries': 0,
            'last_warm_time': None,
            'total_documents': 0,
            'total_terms': 0,
            'vector_queries': 0,
            'keyword_queries': 0,
            'hybrid_queries': 0,
            'embeddings_generated': 0
        }

        # Auto-warm if configured
        if self.config.auto_warm:
            self.warm_up()

    @classmethod
    def _from_builder(
        cls,
        config: KnowledgeBeastConfig,
        repository: DocumentRepository,
        cache_manager: CacheManager,
        query_engine: QueryEngine,
        indexer: DocumentIndexer,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> 'KnowledgeBase':
        """Create knowledge base from builder (internal use only).

        This method is used by KnowledgeBaseBuilder to inject components.

        Args:
            config: Configuration object
            repository: Document repository instance
            cache_manager: Cache manager instance
            query_engine: Query engine instance
            indexer: Document indexer instance
            progress_callback: Optional progress callback

        Returns:
            KnowledgeBase instance with injected components
        """
        # Create instance without triggering __init__
        instance = cls.__new__(cls)

        # Set attributes directly
        instance.config = config
        instance.progress_callback = progress_callback
        instance._lock = threading.RLock()
        instance._repository = repository
        instance._cache_manager = cache_manager
        instance._query_engine = query_engine
        instance._indexer = indexer
        instance.last_access = time.time()
        instance.stats = {
            'queries': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'warm_queries': 0,
            'last_warm_time': None,
            'total_documents': 0,
            'total_terms': 0
        }

        # Auto-warm if configured
        if config.auto_warm:
            instance.warm_up()

        return instance

    @classmethod
    def from_config(cls, config: KnowledgeBeastConfig) -> 'KnowledgeBase':
        """Create knowledge base from configuration.

        Args:
            config: KnowledgeBeastConfig instance

        Returns:
            KnowledgeBase instance initialized with config
        """
        return cls(config=config)

    def warm_up(self) -> None:
        """
        Pre-load and warm up the knowledge base.
        Executes common queries to populate cache and reduce first-query latency.
        """
        logger.info("Warming up knowledge base...")
        if self.config.verbose:
            print("🔥 Warming up knowledge base...")

        start = time.time()

        try:
            # Load documents and index
            self.ingest_all()

            # Pre-execute warming queries to populate cache
            total_queries = len(self.config.warming_queries)
            for i, query in enumerate(self.config.warming_queries, 1):
                if self.progress_callback and self.config.enable_progress_callbacks:
                    try:
                        self.progress_callback(f"Warming query: {query[:50]}...", i, total_queries)
                    except Exception as e:
                        logger.warning(f"Progress callback error: {e}")

                try:
                    self.query(query, use_cache=True)  # Populate cache
                    self.stats['warm_queries'] += 1
                except Exception as e:
                    logger.warning(f"Warming query failed '{query}': {e}")
                    if self.config.verbose:
                        print(f"⚠️  Warming query failed '{query}': {e}")

            elapsed = time.time() - start
            self.stats['last_warm_time'] = elapsed

            logger.info(f"Knowledge base warmed in {elapsed:.2f}s - {self._repository.document_count()} documents, {self._repository.term_count()} terms, {self.stats['warm_queries']} queries")
            if self.config.verbose:
                print(f"✅ Knowledge base warmed in {elapsed:.2f}s")
                print(f"   - {self._repository.document_count()} documents loaded")
                print(f"   - {self._repository.term_count()} unique terms indexed")
                print(f"   - {self.stats['warm_queries']} warming queries executed\n")

        except Exception as e:
            logger.error(f"Warming failed: {e}", exc_info=True)
            if self.config.verbose:
                print(f"❌ Warming failed: {e}")
            raise

    def ingest_all(self) -> None:
        """
        Ingest all markdown files from all configured knowledge base directories.
        Uses cached index if available and up-to-date.
        Auto-rebuilds if any source files are newer than cache.

        Delegates to DocumentIndexer component.

        Raises:
            FileNotFoundError: If knowledge directories don't exist
            PermissionError: If cache file can't be read/written
        """
        self._indexer.ingest_all()
        # Update stats after ingestion
        self.stats['total_documents'] = self._repository.document_count()
        self.stats['total_terms'] = self._repository.term_count()

    def query(
        self,
        search_terms: str,
        use_cache: bool = True,
        mode: Literal['hybrid', 'vector', 'keyword'] = 'hybrid',
        top_k: int = 10,
        alpha: Optional[float] = None
    ) -> List[Tuple[str, Dict]]:
        """
        Query the knowledge base for relevant documents with semantic caching.

        Args:
            search_terms: Search query string
            use_cache: If True, use cached results if available
            mode: Search mode - 'hybrid' (default), 'vector', or 'keyword'
                  - hybrid: Combines vector similarity and keyword matching (best of both)
                  - vector: Pure semantic similarity using embeddings
                  - keyword: Traditional term matching (backward compatible)
            top_k: Number of top results to return (default: 10)
            alpha: Weight for vector search in hybrid mode (0-1, default: 0.7)
                   Higher values favor semantic similarity, lower favor exact matches

        Returns:
            List of (doc_id, document) tuples sorted by relevance

        Raises:
            ValueError: If search_terms is empty or alpha is out of range

        Notes:
            - Hybrid mode (default) provides best results for most queries
            - Vector mode is best for semantic/conceptual queries
            - Keyword mode maintains backward compatibility with existing code
            - Results are always returned as (doc_id, document) tuples for compatibility
        """
        # Validate inputs
        if not search_terms or not search_terms.strip():
            raise ValueError("Search terms cannot be empty")

        if alpha is not None and not (0 <= alpha <= 1):
            raise ValueError("alpha must be between 0 and 1")

        # Update stats (thread-safe with lock)
        with self._lock:
            self.stats['queries'] += 1
            self.last_access = time.time()

        # Generate cache key including mode
        cache_key = f"{mode}:{alpha}:{search_terms}" if mode == 'hybrid' else f"{mode}:{search_terms}"

        # Check cache if enabled
        if use_cache:
            cached_result = self._cache_manager.get(cache_key)
            if cached_result is not None:
                # Update local stats for backward compatibility
                with self._lock:
                    self.stats['cache_hits'] = self._cache_manager.stats['cache_hits']
                    self.stats['cache_misses'] = self._cache_manager.stats['cache_misses']
                return cached_result

        # Execute query based on mode
        try:
            # Use vector/hybrid search if enabled and mode is not keyword
            if self.enable_vector and mode != 'keyword' and self._embedding_engine and self._vector_store:
                if mode == 'vector':
                    # Pure vector search using VectorStore
                    results = self._vector_search(search_terms, top_k)
                    with self._lock:
                        self.stats['vector_queries'] += 1
                elif mode == 'hybrid':
                    # Hybrid search combining vector and keyword
                    results = self._hybrid_search(search_terms, alpha or 0.7, top_k)
                    with self._lock:
                        self.stats['hybrid_queries'] += 1
                else:
                    # Fallback to keyword search
                    results = self._query_engine.execute_query(search_terms)
                    with self._lock:
                        self.stats['keyword_queries'] += 1
            else:
                # Keyword search (backward compatible, or when vector is disabled)
                results = self._query_engine.execute_query(search_terms)
                with self._lock:
                    self.stats['keyword_queries'] += 1

            # Cache results if enabled
            if use_cache:
                self._cache_manager.put(cache_key, results)

            # Update local stats for backward compatibility
            with self._lock:
                self.stats['cache_hits'] = self._cache_manager.stats['cache_hits']
                self.stats['cache_misses'] = self._cache_manager.stats['cache_misses']

            return results

        except Exception as e:
            logger.error(f"Query error: {e}", exc_info=True)
            raise

    def get_answer(self, question: str, max_content_length: int = 500) -> str:
        """
        Get answer to a specific question.

        Delegates to QueryEngine component.

        Args:
            question: Question string
            max_content_length: Maximum content length to return

        Returns:
            Formatted answer with most relevant document content
        """
        return self._query_engine.get_answer(question, max_content_length)

    def get_stats(self) -> Dict:
        """
        Return performance statistics.

        Returns:
            Dictionary with performance metrics
        """
        # Get cache statistics
        cache_stats = self._cache_manager.get_stats()

        # Get repository statistics
        repo_stats = self._repository.get_stats()

        # Combine all statistics
        return {
            **self.stats,
            **cache_stats,
            **repo_stats,
            'last_access_age': f"{time.time() - self.last_access:.1f}s ago",
            'knowledge_dirs': [str(d) for d in self.config.knowledge_dirs]
        }

    def clear_cache(self) -> None:
        """Clear query cache (useful for testing or memory management)."""
        self._cache_manager.clear()
        # Reset local stats to match cache_manager
        with self._lock:
            self.stats['cache_hits'] = 0
            self.stats['cache_misses'] = 0
        if self.config.verbose:
            print("🧹 Query cache cleared")

    def rebuild_index(self) -> None:
        """Force rebuild of the document index."""
        self._indexer.rebuild_index()
        # Update stats after rebuild
        self.stats['total_documents'] = self._repository.document_count()
        self.stats['total_terms'] = self._repository.term_count()
        # Clear query cache as index has changed
        self.clear_cache()

    def _is_cache_stale(self, cache_path) -> bool:
        """Check if cache is stale (backward compatibility).

        Delegates to indexer component.

        Args:
            cache_path: Path to cache file

        Returns:
            True if cache is stale, False otherwise
        """
        return self._indexer._is_cache_stale(cache_path)

    def _vector_search(self, query: str, top_k: int = 10) -> List[Tuple[str, Dict]]:
        """Execute pure vector similarity search.

        Args:
            query: Search query string
            top_k: Number of top results to return

        Returns:
            List of (doc_id, document) tuples sorted by similarity
        """
        # Generate query embedding
        query_embedding = self._embedding_engine.embed(query, use_cache=True, normalize=True)

        # Query vector store
        vector_results = self._vector_store.query(
            query_embeddings=query_embedding,
            n_results=top_k,
            include=['distances', 'metadatas', 'documents']
        )

        # Extract document IDs from results
        if not vector_results['ids'] or len(vector_results['ids']) == 0:
            return []

        doc_ids = vector_results['ids'][0]  # First query result

        # Get documents from repository
        results = []
        for doc_id in doc_ids:
            doc = self._repository.get_document(doc_id)
            if doc:
                results.append((doc_id, doc))

        return results

    def _hybrid_search(
        self,
        query: str,
        alpha: float = 0.7,
        top_k: int = 10
    ) -> List[Tuple[str, Dict]]:
        """Execute hybrid search combining vector and keyword search.

        Args:
            query: Search query string
            alpha: Weight for vector search (0-1, default: 0.7)
            top_k: Number of top results to return

        Returns:
            List of (doc_id, document) tuples sorted by combined score
        """
        # Get vector search results
        vector_results = self._vector_search(query, top_k=top_k * 2)

        # Get keyword search results
        keyword_results = self._query_engine.execute_query(query)

        # Normalize and combine scores
        vector_scores = {}
        if vector_results:
            max_vector_rank = len(vector_results)
            for rank, (doc_id, _) in enumerate(vector_results):
                # Inverse rank scoring (1st = 1.0, 2nd = 0.5, etc.)
                vector_scores[doc_id] = 1.0 - (rank / max_vector_rank)

        keyword_scores = {}
        if keyword_results:
            # Count term matches for keyword scoring
            query_terms = set(query.lower().split())
            for doc_id, doc in keyword_results:
                content_lower = doc['content'].lower()
                matches = sum(1 for term in query_terms if term in content_lower)
                keyword_scores[doc_id] = matches / len(query_terms) if query_terms else 0

        # Combine scores
        all_doc_ids = set(vector_scores.keys()) | set(keyword_scores.keys())
        combined_scores = {}

        for doc_id in all_doc_ids:
            v_score = vector_scores.get(doc_id, 0.0)
            k_score = keyword_scores.get(doc_id, 0.0)
            combined_scores[doc_id] = alpha * v_score + (1 - alpha) * k_score

        # Sort by combined score
        sorted_doc_ids = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        top_doc_ids = sorted_doc_ids[:top_k]

        # Get documents
        results = []
        for doc_id, score in top_doc_ids:
            doc = self._repository.get_document(doc_id)
            if doc:
                results.append((doc_id, doc))

        return results

    # ============================================================================
    # Backward Compatibility Properties
    # ============================================================================
    # These properties maintain backward compatibility with code that directly
    # accesses internal attributes. New code should use methods instead.
    #
    # Note: We return read-only MappingProxyType views to prevent external
    # modification of internal state while maintaining backward compatibility.

    @property
    def documents(self) -> types.MappingProxyType:
        """Access to documents (backward compatibility, read-only view).

        Returns:
            Read-only mapping proxy of documents dictionary
        """
        return types.MappingProxyType(self._repository.documents)

    @property
    def index(self) -> types.MappingProxyType:
        """Access to index (backward compatibility, read-only view).

        Returns:
            Read-only mapping proxy of index dictionary
        """
        return types.MappingProxyType(self._repository.index)

    @property
    def query_cache(self):
        """Access to query cache (backward compatibility)."""
        return self._cache_manager.cache

    @property
    def converter(self):
        """Access to document converter (backward compatibility)."""
        return self._indexer.converter

    # ============================================================================
    # Context Manager Protocol
    # ============================================================================

    def __enter__(self) -> "KnowledgeBase":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - cleanup resources."""
        try:
            with self._lock:
                # Clear caches to free memory
                self._cache_manager.clear()
                logger.info("Cleared query cache on exit")

                # Clear repository data
                self._repository.clear()
                logger.info("Cleared document repository on exit")

                # Close converter if it has resources
                if hasattr(self._indexer.converter, 'close') and callable(self._indexer.converter.close):
                    self._indexer.converter.close()
                    logger.info("Closed document converter")

        except Exception as e:
            logger.error(f"Cleanup error in __exit__: {e}", exc_info=True)

        # Don't suppress exceptions from the with block
        return False
