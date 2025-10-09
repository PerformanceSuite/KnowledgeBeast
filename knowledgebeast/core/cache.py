"""LRU Cache implementation using OrderedDict."""

import threading
import time
from collections import OrderedDict
from typing import Any, Generic, Optional, TypeVar

from knowledgebeast.utils.metrics import measure_cache_operation

K = TypeVar("K")
V = TypeVar("V")


class LRUCache(Generic[K, V]):
    """Thread-safe LRU (Least Recently Used) cache implementation.
    
    This cache automatically evicts the least recently used items when
    the maximum capacity is reached.
    
    Attributes:
        capacity: Maximum number of items the cache can hold
        cache: OrderedDict storing the cached items
    """
    
    def __init__(self, capacity: int = 100) -> None:
        """Initialize the LRU cache.

        Args:
            capacity: Maximum number of items to store

        Raises:
            ValueError: If capacity is not positive
        """
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        self.capacity = capacity
        self.cache: OrderedDict[K, V] = OrderedDict()
        self._lock = threading.Lock()
    
    def get(self, key: K) -> Optional[V]:
        """Get an item from the cache.

        Args:
            key: The key to look up

        Returns:
            The cached value if found, None otherwise
        """
        with measure_cache_operation("get", "lru"):
            with self._lock:
                if key not in self.cache:
                    return None
                # Move to end to mark as recently used
                self.cache.move_to_end(key)
                return self.cache[key]
    
    def put(self, key: K, value: V) -> None:
        """Put an item in the cache.

        Args:
            key: The key to store under
            value: The value to store
        """
        with measure_cache_operation("put", "lru"):
            with self._lock:
                if key in self.cache:
                    # Update existing key and move to end
                    self.cache.move_to_end(key)
                self.cache[key] = value

                # Remove least recently used item if over capacity
                if len(self.cache) > self.capacity:
                    self.cache.popitem(last=False)
    
    def clear(self) -> None:
        """Clear all items from the cache."""
        with measure_cache_operation("clear", "lru"):
            with self._lock:
                self.cache.clear()
    
    def __len__(self) -> int:
        """Return the current number of items in the cache."""
        with self._lock:
            return len(self.cache)
    
    def __contains__(self, key: K) -> bool:
        """Check if a key exists in the cache."""
        with self._lock:
            return key in self.cache
    
    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            return {
                "size": len(self.cache),
                "capacity": self.capacity,
                "utilization": len(self.cache) / self.capacity if self.capacity > 0 else 0
            }
