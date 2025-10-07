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
from typing import Dict, List, Tuple, Optional, Callable

from knowledgebeast.core.config import KnowledgeBeastConfig
from knowledgebeast.core.repository import DocumentRepository
from knowledgebeast.core.cache_manager import CacheManager
from knowledgebeast.core.query_engine import QueryEngine
from knowledgebeast.core.indexer import DocumentIndexer

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
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ):
        """
        Initialize Knowledge Base with optional config and callbacks.

        Args:
            config: KnowledgeBeastConfig instance (uses defaults if None)
            progress_callback: Optional callback for progress updates
                              Signature: callback(message: str, current: int, total: int)
        """
        self.config = config or KnowledgeBeastConfig()
        self.progress_callback = progress_callback if self.config.enable_progress_callbacks else None

        # Thread safety lock (reentrant for nested operations)
        self._lock = threading.RLock()

        # Initialize components using composition
        self._repository = DocumentRepository()
        self._cache_manager: CacheManager[List[Tuple[str, Dict]]] = CacheManager(
            capacity=self.config.max_cache_size
        )
        self._query_engine = QueryEngine(self._repository)
        self._indexer = DocumentIndexer(self.config, self._repository, self.progress_callback)

        # Performance metrics
        self.last_access = time.time()
        self.stats = {
            'queries': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'warm_queries': 0,
            'last_warm_time': None,
            'total_documents': 0,
            'total_terms': 0
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

    def query(self, search_terms: str, use_cache: bool = True) -> List[Tuple[str, Dict]]:
        """
        Query the knowledge base for relevant documents with semantic caching.

        Args:
            search_terms: Search query string
            use_cache: If True, use cached results if available

        Returns:
            List of (doc_id, document) tuples sorted by relevance

        Raises:
            ValueError: If search_terms is empty
        """
        # Update stats (thread-safe with lock)
        with self._lock:
            self.stats['queries'] += 1
            self.last_access = time.time()

        # Check cache if enabled
        if use_cache:
            cached_result = self._cache_manager.get(search_terms)
            if cached_result is not None:
                # Update local stats for backward compatibility
                with self._lock:
                    self.stats['cache_hits'] = self._cache_manager.stats['cache_hits']
                    self.stats['cache_misses'] = self._cache_manager.stats['cache_misses']
                return cached_result

        # Execute query using query engine
        try:
            results = self._query_engine.execute_query(search_terms)

            # Cache results if enabled
            if use_cache:
                self._cache_manager.put(search_terms, results)

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
