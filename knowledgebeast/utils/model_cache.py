"""Model caching utility for KnowledgeBeast.

Provides thread-safe LRU caching for loaded ML models to optimize memory usage
and reduce model loading time.
"""

import logging
import threading
from collections import OrderedDict
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ModelCache:
    """Thread-safe LRU cache for ML models.

    This cache stores loaded models in memory with an LRU eviction policy
    to manage memory usage while maintaining fast access to frequently used models.

    Thread Safety:
        All operations are protected by a threading.Lock() for thread-safe access.
    """

    def __init__(self, capacity: int = 5, memory_limit_mb: Optional[int] = None):
        """Initialize the model cache.

        Args:
            capacity: Maximum number of models to cache (default: 5)
            memory_limit_mb: Optional memory limit in MB (not enforced, for tracking only)
        """
        self.capacity = capacity
        self.memory_limit_mb = memory_limit_mb
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.Lock()
        self._load_counts: dict[str, int] = {}
        self._hit_count = 0
        self._miss_count = 0

        logger.info(
            f"ModelCache initialized with capacity={capacity}, "
            f"memory_limit_mb={memory_limit_mb}"
        )

    def get(self, key: str) -> Optional[Any]:
        """Get a model from the cache.

        Args:
            key: Model identifier (e.g., model name)

        Returns:
            Cached model or None if not found

        Thread Safety:
            Protected by self._lock
        """
        with self._lock:
            if key not in self._cache:
                self._miss_count += 1
                logger.debug(f"Model cache miss: {key}")
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hit_count += 1
            logger.debug(f"Model cache hit: {key}")
            return self._cache[key]

    def put(self, key: str, model: Any) -> None:
        """Put a model in the cache.

        If the cache is full, the least recently used model is evicted.

        Args:
            key: Model identifier (e.g., model name)
            model: The loaded model to cache

        Thread Safety:
            Protected by self._lock
        """
        with self._lock:
            # If key exists, update and move to end
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = model
                logger.debug(f"Model cache updated: {key}")
                return

            # Add new entry
            self._cache[key] = model
            self._load_counts[key] = self._load_counts.get(key, 0) + 1

            # Evict LRU if over capacity
            if len(self._cache) > self.capacity:
                evicted_key, evicted_model = self._cache.popitem(last=False)
                logger.info(
                    f"Model cache eviction: {evicted_key} "
                    f"(cache size: {len(self._cache)})"
                )
                # Attempt to free memory (model-specific cleanup)
                self._cleanup_model(evicted_model)

            logger.debug(f"Model cache stored: {key} (cache size: {len(self._cache)})")

    def get_or_load(
        self,
        key: str,
        load_fn: Callable[[], Any]
    ) -> Any:
        """Get a model from cache or load it if not present.

        This is a convenience method that combines get() and put() operations.

        Args:
            key: Model identifier
            load_fn: Function to call if model not in cache (should return loaded model)

        Returns:
            The cached or newly loaded model

        Thread Safety:
            Protected by self._lock
        """
        # Try to get from cache first
        model = self.get(key)
        if model is not None:
            return model

        # Load model (outside lock to avoid blocking)
        logger.info(f"Loading model: {key}")
        model = load_fn()

        # Store in cache
        self.put(key, model)
        return model

    def clear(self) -> int:
        """Clear all models from the cache.

        Returns:
            Number of models evicted

        Thread Safety:
            Protected by self._lock
        """
        with self._lock:
            count = len(self._cache)
            for model in self._cache.values():
                self._cleanup_model(model)
            self._cache.clear()
            logger.info(f"Model cache cleared: {count} models evicted")
            return count

    def remove(self, key: str) -> bool:
        """Remove a specific model from the cache.

        Args:
            key: Model identifier to remove

        Returns:
            True if model was removed, False if not found

        Thread Safety:
            Protected by self._lock
        """
        with self._lock:
            if key in self._cache:
                model = self._cache.pop(key)
                self._cleanup_model(model)
                logger.info(f"Model removed from cache: {key}")
                return True
            return False

    def stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics

        Thread Safety:
            Protected by self._lock
        """
        with self._lock:
            total_requests = self._hit_count + self._miss_count
            hit_rate = (
                self._hit_count / total_requests if total_requests > 0 else 0.0
            )

            return {
                "size": len(self._cache),
                "capacity": self.capacity,
                "utilization": len(self._cache) / self.capacity if self.capacity > 0 else 0.0,
                "hit_count": self._hit_count,
                "miss_count": self._miss_count,
                "hit_rate": hit_rate,
                "cached_models": list(self._cache.keys()),
                "load_counts": dict(self._load_counts),
            }

    def _cleanup_model(self, model: Any) -> None:
        """Attempt to cleanup/free model resources.

        Args:
            model: The model to cleanup

        Note:
            This is a best-effort cleanup. Different model types may require
            different cleanup procedures.
        """
        try:
            # Try common cleanup methods
            if hasattr(model, "cpu"):
                # Move PyTorch models to CPU to free GPU memory
                model.cpu()
            if hasattr(model, "close"):
                model.close()
            if hasattr(model, "cleanup"):
                model.cleanup()
        except Exception as e:
            logger.warning(f"Model cleanup failed: {e}")

    def __len__(self) -> int:
        """Get the number of cached models.

        Returns:
            Number of models in cache

        Thread Safety:
            Protected by self._lock
        """
        with self._lock:
            return len(self._cache)

    def __contains__(self, key: str) -> bool:
        """Check if a model is in the cache.

        Args:
            key: Model identifier

        Returns:
            True if model is cached, False otherwise

        Thread Safety:
            Protected by self._lock
        """
        with self._lock:
            return key in self._cache


# Global model cache instance
_global_model_cache: Optional[ModelCache] = None


def get_global_model_cache(
    capacity: int = 5,
    memory_limit_mb: Optional[int] = None
) -> ModelCache:
    """Get or create the global model cache instance.

    Args:
        capacity: Maximum number of models to cache (only used on first call)
        memory_limit_mb: Optional memory limit in MB (only used on first call)

    Returns:
        Global ModelCache instance

    Thread Safety:
        This function is not thread-safe for the initialization.
        Call it once during application startup before concurrent access.
    """
    global _global_model_cache

    if _global_model_cache is None:
        _global_model_cache = ModelCache(
            capacity=capacity,
            memory_limit_mb=memory_limit_mb
        )

    return _global_model_cache
