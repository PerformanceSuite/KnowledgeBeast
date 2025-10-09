"""Semantic Cache - Embedding-based caching for similar queries.

This module provides semantic caching capabilities to reduce latency by:
1. Caching query results with embedding-based similarity
2. TTL-based cache expiration
3. LRU eviction policy
4. Thread-safe cache operations
5. Cache warming for common queries
"""

import logging
import threading
import time
import hashlib
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
import numpy as np

from knowledgebeast.core.cache import LRUCache

logger = logging.getLogger(__name__)


@dataclass
class CachedEntry:
    """Cached query entry with TTL.

    Attributes:
        query: Original query string
        embedding: Query embedding vector
        results: Cached results
        timestamp: Creation timestamp
        ttl_seconds: Time-to-live in seconds
        hit_count: Number of cache hits for this entry
    """
    query: str
    embedding: np.ndarray
    results: Any
    timestamp: float
    ttl_seconds: int
    hit_count: int = 0

    def is_expired(self) -> bool:
        """Check if entry has expired.

        Returns:
            True if expired, False otherwise
        """
        age = time.time() - self.timestamp
        return age > self.ttl_seconds

    def matches(self, query_embedding: np.ndarray, similarity_threshold: float) -> Tuple[bool, float]:
        """Check if query embedding matches this entry.

        Args:
            query_embedding: Query embedding to compare
            similarity_threshold: Minimum similarity threshold

        Returns:
            Tuple of (matches, similarity_score)
        """
        similarity = self._cosine_similarity(self.embedding, query_embedding)
        return similarity >= similarity_threshold, similarity

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score (0-1)
        """
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))


class SemanticCache:
    """Semantic cache for query results using embedding similarity.

    This cache stores query results and retrieves them for semantically similar
    queries (based on cosine similarity of embeddings) rather than exact matches.

    Features:
        - Embedding-based similarity matching
        - TTL-based cache expiration
        - LRU eviction policy
        - Thread-safe operations
        - Cache warming support
        - Hit/miss statistics

    Thread Safety:
        - All operations protected by threading.Lock
        - Snapshot pattern for read operations
        - Minimal lock scope for performance

    Performance:
        - O(n) lookup where n = cache size (linear scan for similarity)
        - Future: Could use FAISS or Annoy for O(log n) approximate search
        - LRU cache for efficient memory management

    Attributes:
        similarity_threshold: Minimum cosine similarity for cache hit (0-1)
        ttl_seconds: Default time-to-live for cache entries
        max_entries: Maximum number of cache entries (LRU eviction)
        cache: LRU cache for storing entries
        stats: Cache statistics (hits, misses, etc.)
        _lock: Thread safety lock
    """

    def __init__(
        self,
        similarity_threshold: float = 0.95,
        ttl_seconds: int = 3600,
        max_entries: int = 10000
    ):
        """Initialize semantic cache.

        Args:
            similarity_threshold: Minimum similarity for cache hit (0-1, default 0.95)
            ttl_seconds: Time-to-live for cache entries (default 1 hour)
            max_entries: Maximum number of cache entries (default 10,000)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if not 0 <= similarity_threshold <= 1:
            raise ValueError("similarity_threshold must be between 0 and 1")

        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")

        if max_entries <= 0:
            raise ValueError("max_entries must be positive")

        self.similarity_threshold = similarity_threshold
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries

        # LRU cache for efficient memory management
        self.cache: LRUCache[str, CachedEntry] = LRUCache(capacity=max_entries)

        # Thread safety lock
        self._lock = threading.Lock()

        # Statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expirations': 0,
            'total_queries': 0,
        }

        logger.info(f"SemanticCache initialized: threshold={similarity_threshold}, "
                   f"ttl={ttl_seconds}s, max_entries={max_entries}")

    def get(
        self,
        query: str,
        embedding: np.ndarray
    ) -> Optional[Tuple[Any, float, str]]:
        """Get cached results for semantically similar query.

        This method performs a linear scan through cached entries to find
        the best matching query based on embedding similarity.

        Args:
            query: Query string
            embedding: Query embedding vector

        Returns:
            Tuple of (results, similarity_score, matched_query) if cache hit
            None if cache miss

        Thread-safe through locking.
        """
        with self._lock:
            self.stats['total_queries'] += 1

            # Get all cache keys (snapshot)
            cache_keys = list(self.cache.cache.keys())

        # Search for best match (without lock - snapshot pattern)
        best_match: Optional[Tuple[str, CachedEntry, float]] = None
        best_similarity = 0.0

        for cache_key in cache_keys:
            # Get entry with lock
            with self._lock:
                entry = self.cache.get(cache_key)

            if entry is None:
                continue

            # Check expiration
            if entry.is_expired():
                with self._lock:
                    self.cache.cache.pop(cache_key, None)
                    self.stats['expirations'] += 1
                continue

            # Check similarity match
            matches, similarity = entry.matches(embedding, self.similarity_threshold)

            if matches and similarity > best_similarity:
                best_similarity = similarity
                best_match = (cache_key, entry, similarity)

        # Update stats and return result
        if best_match:
            cache_key, entry, similarity = best_match

            with self._lock:
                self.stats['hits'] += 1
                entry.hit_count += 1
                # Update LRU position
                self.cache.put(cache_key, entry)

            logger.debug(f"Cache HIT: query='{query[:50]}' matched '{entry.query[:50]}' "
                        f"(similarity={similarity:.3f})")
            return entry.results, similarity, entry.query
        else:
            with self._lock:
                self.stats['misses'] += 1

            logger.debug(f"Cache MISS: query='{query[:50]}'")
            return None

    def put(
        self,
        query: str,
        embedding: np.ndarray,
        results: Any
    ) -> None:
        """Cache query results with TTL.

        Args:
            query: Query string
            embedding: Query embedding vector
            results: Results to cache

        Thread-safe through locking.
        """
        # Generate cache key from embedding (hash)
        cache_key = self._generate_cache_key(embedding)

        # Create cache entry
        entry = CachedEntry(
            query=query,
            embedding=embedding,
            results=results,
            timestamp=time.time(),
            ttl_seconds=self.ttl_seconds,
            hit_count=0
        )

        # Store in cache
        with self._lock:
            # Check if eviction will occur
            if len(self.cache.cache) >= self.max_entries and cache_key not in self.cache.cache:
                self.stats['evictions'] += 1

            self.cache.put(cache_key, entry)

        logger.debug(f"Cached query: '{query[:50]}' (key={cache_key[:16]}...)")

    def warm(
        self,
        queries: List[str],
        embedding_fn: Any,
        query_fn: Any
    ) -> int:
        """Warm cache with common queries.

        This pre-populates the cache with frequently used queries.

        Args:
            queries: List of queries to warm cache with
            embedding_fn: Function to generate embeddings (query -> embedding)
            query_fn: Function to execute queries (query -> results)

        Returns:
            Number of queries warmed

        Thread-safe through individual put operations.
        """
        warmed_count = 0

        for query in queries:
            try:
                # Generate embedding
                embedding = embedding_fn(query)

                # Execute query
                results = query_fn(query)

                # Cache results
                self.put(query, embedding, results)
                warmed_count += 1

            except Exception as e:
                logger.warning(f"Error warming cache for query '{query[:50]}': {e}")

        logger.info(f"Cache warming completed: {warmed_count}/{len(queries)} queries cached")
        return warmed_count

    def clear(self) -> None:
        """Clear all cache entries.

        Thread-safe through locking.
        """
        with self._lock:
            self.cache.cache.clear()
            self.stats['evictions'] += len(self.cache.cache)

        logger.info("Cache cleared")

    def get_stats(self) -> Dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics

        Thread-safe through locking.
        """
        with self._lock:
            total_queries = self.stats['total_queries']
            hits = self.stats['hits']
            misses = self.stats['misses']

            hit_rate = hits / total_queries if total_queries > 0 else 0.0

            return {
                'hits': hits,
                'misses': misses,
                'total_queries': total_queries,
                'hit_rate': hit_rate,
                'evictions': self.stats['evictions'],
                'expirations': self.stats['expirations'],
                'size': len(self.cache.cache),
                'capacity': self.max_entries,
                'utilization': len(self.cache.cache) / self.max_entries,
                'similarity_threshold': self.similarity_threshold,
                'ttl_seconds': self.ttl_seconds,
            }

    def cleanup_expired(self) -> int:
        """Clean up expired cache entries.

        Returns:
            Number of entries removed

        Thread-safe through locking.
        """
        expired_count = 0

        # Get snapshot of keys
        with self._lock:
            cache_keys = list(self.cache.cache.keys())

        # Check each entry
        for cache_key in cache_keys:
            with self._lock:
                entry = self.cache.cache.get(cache_key)

            if entry and entry.is_expired():
                with self._lock:
                    self.cache.cache.pop(cache_key, None)
                    self.stats['expirations'] += 1
                    expired_count += 1

        if expired_count > 0:
            logger.info(f"Cleaned up {expired_count} expired cache entries")

        return expired_count

    def _generate_cache_key(self, embedding: np.ndarray) -> str:
        """Generate cache key from embedding.

        Args:
            embedding: Embedding vector

        Returns:
            Cache key string (hash of embedding)
        """
        # Hash the embedding for a unique key
        embedding_bytes = embedding.tobytes()
        return hashlib.sha256(embedding_bytes).hexdigest()

    def get_top_queries(self, top_k: int = 10) -> List[Tuple[str, int, float]]:
        """Get top cached queries by hit count.

        Args:
            top_k: Number of top queries to return

        Returns:
            List of (query, hit_count, age_seconds) tuples

        Thread-safe through locking.
        """
        with self._lock:
            entries = []

            for cache_key, entry in self.cache.cache.items():
                age = time.time() - entry.timestamp
                entries.append((entry.query, entry.hit_count, age))

            # Sort by hit count (descending)
            entries.sort(key=lambda x: x[1], reverse=True)

            return entries[:top_k]
