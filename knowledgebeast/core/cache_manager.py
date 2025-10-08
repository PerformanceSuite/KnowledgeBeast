"""Cache Manager - Query cache management with LRU eviction.

This module provides a high-level interface for managing query caching,
including cache key generation, hit/miss tracking, and statistics.
"""

import hashlib
import logging
from typing import Dict, List, Tuple, Optional, Generic, TypeVar

from knowledgebeast.core.cache import LRUCache

logger = logging.getLogger(__name__)

__all__ = ['CacheManager']

T = TypeVar('T')


class CacheManager(Generic[T]):
    """Manager for query result caching with statistics tracking.

    This class wraps the LRUCache with additional features:
    - Cache key generation from queries
    - Hit/miss statistics tracking
    - Cache performance metrics

    Thread Safety:
        - Internally thread-safe (delegates to LRUCache)
        - Statistics updates are atomic

    Attributes:
        cache: Underlying LRU cache instance
        stats: Cache hit/miss statistics
    """

    def __init__(self, capacity: int = 100) -> None:
        """Initialize cache manager.

        Args:
            capacity: Maximum number of cached items
        """
        self.cache: LRUCache[str, T] = LRUCache(capacity=capacity)
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0
        }

    def get(self, query: str) -> Optional[T]:
        """Get cached result for a query.

        Args:
            query: Search query string

        Returns:
            Cached result or None if not found
        """
        cache_key = self._generate_cache_key(query)
        result = self.cache.get(cache_key)

        if result is not None:
            self.stats['cache_hits'] += 1
            logger.debug(f"Cache hit for query: {query[:50]}")
        else:
            self.stats['cache_misses'] += 1
            logger.debug(f"Cache miss for query: {query[:50]}")

        return result

    def put(self, query: str, result: T) -> None:
        """Cache result for a query.

        Args:
            query: Search query string
            result: Query result to cache
        """
        cache_key = self._generate_cache_key(query)
        self.cache.put(cache_key, result)
        logger.debug(f"Cached result for query: {query[:50]}")

    def clear(self) -> None:
        """Clear all cached results and reset statistics."""
        self.cache.clear()
        self.reset_stats()
        logger.info("Query cache cleared")

    def get_stats(self) -> Dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache performance metrics
        """
        total_queries = self.stats['cache_hits'] + self.stats['cache_misses']
        hit_rate = (self.stats['cache_hits'] / total_queries * 100) if total_queries > 0 else 0

        cache_stats = self.cache.stats()

        return {
            'cache_hits': self.stats['cache_hits'],
            'cache_misses': self.stats['cache_misses'],
            'total_queries': total_queries,
            'cache_hit_rate': f"{hit_rate:.1f}%",
            'cached_queries': cache_stats['size'],
            'cache_capacity': cache_stats['capacity'],
            'cache_utilization': f"{cache_stats['utilization'] * 100:.1f}%"
        }

    def _generate_cache_key(self, query: str) -> str:
        """Generate deterministic cache key from query.

        Args:
            query: Query string

        Returns:
            MD5 hash of normalized query
        """
        normalized = query.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()

    def __len__(self) -> int:
        """Return number of cached items."""
        return len(self.cache)

    def reset_stats(self) -> None:
        """Reset cache statistics (useful for testing)."""
        self.stats['cache_hits'] = 0
        self.stats['cache_misses'] = 0
        logger.debug("Cache statistics reset")
