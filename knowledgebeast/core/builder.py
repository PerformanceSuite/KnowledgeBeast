"""Knowledge Base Builder - Implements Builder Pattern for complex initialization.

This module provides a fluent interface for constructing KnowledgeBase instances
with various configuration options and components.
"""

import logging
from typing import Optional, Callable
from pathlib import Path

from knowledgebeast.core.config import KnowledgeBeastConfig
from knowledgebeast.core.repository import DocumentRepository
from knowledgebeast.core.cache_manager import CacheManager
from knowledgebeast.core.query_engine import QueryEngine
from knowledgebeast.core.indexer import DocumentIndexer

logger = logging.getLogger(__name__)

__all__ = ['KnowledgeBaseBuilder']


class KnowledgeBaseBuilder:
    """Builder for constructing KnowledgeBase instances.

    This class implements the Builder Pattern, providing a fluent interface
    for configuring and constructing KnowledgeBase instances with all their
    required components.

    Usage:
        builder = KnowledgeBaseBuilder()
        kb = (builder
              .with_config(config)
              .with_progress_callback(callback)
              .build())

    Attributes:
        _config: Configuration object
        _progress_callback: Optional progress callback
        _repository: Document repository
        _cache_manager: Cache manager
        _query_engine: Query engine
        _indexer: Document indexer
    """

    def __init__(self) -> None:
        """Initialize builder with default configuration."""
        self._config: Optional[KnowledgeBeastConfig] = None
        self._progress_callback: Optional[Callable[[str, int, int], None]] = None
        self._repository: Optional[DocumentRepository] = None
        self._cache_manager: Optional[CacheManager] = None
        self._query_engine: Optional[QueryEngine] = None
        self._indexer: Optional[DocumentIndexer] = None

    def with_config(self, config: KnowledgeBeastConfig) -> 'KnowledgeBaseBuilder':
        """Set configuration for the knowledge base.

        Args:
            config: Configuration object

        Returns:
            Builder instance for method chaining
        """
        self._config = config
        return self

    def with_progress_callback(
        self,
        callback: Callable[[str, int, int], None]
    ) -> 'KnowledgeBaseBuilder':
        """Set progress callback for long operations.

        Args:
            callback: Progress callback function
                     Signature: callback(message: str, current: int, total: int)

        Returns:
            Builder instance for method chaining
        """
        self._progress_callback = callback
        return self

    def with_repository(self, repository: DocumentRepository) -> 'KnowledgeBaseBuilder':
        """Set custom document repository (for testing/advanced use).

        Args:
            repository: Document repository instance

        Returns:
            Builder instance for method chaining
        """
        self._repository = repository
        return self

    def with_cache_manager(self, cache_manager: CacheManager) -> 'KnowledgeBaseBuilder':
        """Set custom cache manager (for testing/advanced use).

        Args:
            cache_manager: Cache manager instance

        Returns:
            Builder instance for method chaining
        """
        self._cache_manager = cache_manager
        return self

    def build(self) -> 'KnowledgeBase':
        """Build and return configured KnowledgeBase instance.

        Returns:
            Fully configured KnowledgeBase instance

        Raises:
            ValueError: If required configuration is missing
        """
        # Use default config if not provided
        if self._config is None:
            self._config = KnowledgeBeastConfig()
            logger.debug("Using default KnowledgeBeastConfig")

        # Build components
        repository = self._repository or DocumentRepository()
        cache_manager = self._cache_manager or CacheManager(capacity=self._config.max_cache_size)
        query_engine = QueryEngine(repository)
        indexer = DocumentIndexer(self._config, repository, self._progress_callback)

        # Import here to avoid circular dependency
        from knowledgebeast.core.engine import KnowledgeBase

        # Create KnowledgeBase instance with all components
        kb = KnowledgeBase._from_builder(
            config=self._config,
            repository=repository,
            cache_manager=cache_manager,
            query_engine=query_engine,
            indexer=indexer,
            progress_callback=self._progress_callback
        )

        logger.info("KnowledgeBase built successfully")
        return kb

    def reset(self) -> 'KnowledgeBaseBuilder':
        """Reset builder to initial state.

        Returns:
            Builder instance for method chaining
        """
        self._config = None
        self._progress_callback = None
        self._repository = None
        self._cache_manager = None
        self._query_engine = None
        self._indexer = None
        return self
