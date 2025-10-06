"""Tests for LRU cache implementation."""

import pytest
from knowledgebeast.core.cache import LRUCache


class TestLRUCacheInitialization:
    """Test LRU cache initialization."""

    def test_init_default_capacity(self):
        """Test cache initializes with default capacity."""
        cache = LRUCache()
        assert cache.capacity == 100
        assert len(cache) == 0

    def test_init_custom_capacity(self):
        """Test cache initializes with custom capacity."""
        cache = LRUCache(capacity=50)
        assert cache.capacity == 50
        assert len(cache) == 0

    def test_init_invalid_capacity(self):
        """Test cache raises error for invalid capacity."""
        with pytest.raises(ValueError, match="Capacity must be positive"):
            LRUCache(capacity=0)

        with pytest.raises(ValueError, match="Capacity must be positive"):
            LRUCache(capacity=-1)


class TestLRUCacheBasicOperations:
    """Test basic cache operations."""

    def test_put_and_get(self):
        """Test putting and getting items."""
        cache = LRUCache[str, int](capacity=5)
        cache.put("key1", 100)
        assert cache.get("key1") == 100

    def test_get_nonexistent_key(self):
        """Test getting nonexistent key returns None."""
        cache = LRUCache[str, int](capacity=5)
        assert cache.get("nonexistent") is None

    def test_put_updates_existing_key(self):
        """Test putting existing key updates value."""
        cache = LRUCache[str, int](capacity=5)
        cache.put("key1", 100)
        cache.put("key1", 200)
        assert cache.get("key1") == 200
        assert len(cache) == 1  # Should still be 1 item

    def test_clear(self):
        """Test clearing cache."""
        cache = LRUCache[str, int](capacity=5)
        cache.put("key1", 100)
        cache.put("key2", 200)
        cache.put("key3", 300)

        assert len(cache) == 3
        cache.clear()
        assert len(cache) == 0
        assert cache.get("key1") is None

    def test_contains(self):
        """Test __contains__ method."""
        cache = LRUCache[str, int](capacity=5)
        cache.put("key1", 100)

        assert "key1" in cache
        assert "nonexistent" not in cache


class TestLRUEviction:
    """Test LRU eviction policy."""

    def test_lru_eviction(self):
        """Test least recently used item is evicted."""
        cache = LRUCache[str, int](capacity=3)

        # Fill cache
        cache.put("key1", 1)
        cache.put("key2", 2)
        cache.put("key3", 3)
        assert len(cache) == 3

        # Add one more, should evict key1 (least recently used)
        cache.put("key4", 4)
        assert len(cache) == 3
        assert cache.get("key1") is None
        assert cache.get("key2") == 2
        assert cache.get("key3") == 3
        assert cache.get("key4") == 4

    def test_access_updates_recency(self):
        """Test accessing item updates its recency."""
        cache = LRUCache[str, int](capacity=3)

        cache.put("key1", 1)
        cache.put("key2", 2)
        cache.put("key3", 3)

        # Access key1 to make it recently used
        _ = cache.get("key1")

        # Add new item, should evict key2 (now least recently used)
        cache.put("key4", 4)
        assert cache.get("key1") == 1  # Still present
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key3") == 3
        assert cache.get("key4") == 4

    def test_put_updates_recency(self):
        """Test putting to existing key updates its recency."""
        cache = LRUCache[str, int](capacity=3)

        cache.put("key1", 1)
        cache.put("key2", 2)
        cache.put("key3", 3)

        # Update key1 to make it recently used
        cache.put("key1", 10)

        # Add new item, should evict key2
        cache.put("key4", 4)
        assert cache.get("key1") == 10  # Still present, with new value
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key3") == 3
        assert cache.get("key4") == 4


class TestCacheHitMiss:
    """Test cache hit and miss scenarios."""

    def test_cache_hit(self):
        """Test cache hit returns correct value."""
        cache = LRUCache[str, str](capacity=5)
        cache.put("question", "answer")

        result = cache.get("question")
        assert result == "answer"

    def test_cache_miss(self):
        """Test cache miss returns None."""
        cache = LRUCache[str, str](capacity=5)

        result = cache.get("nonexistent")
        assert result is None

    def test_multiple_cache_hits(self):
        """Test multiple cache hits."""
        cache = LRUCache[str, int](capacity=5)
        for i in range(5):
            cache.put(f"key{i}", i * 10)

        for i in range(5):
            assert cache.get(f"key{i}") == i * 10


class TestCapacityLimit:
    """Test cache capacity limits."""

    def test_capacity_limit_enforced(self):
        """Test cache never exceeds capacity."""
        capacity = 5
        cache = LRUCache[int, int](capacity=capacity)

        # Add more items than capacity
        for i in range(capacity * 2):
            cache.put(i, i * 10)
            assert len(cache) <= capacity

        # Final size should equal capacity
        assert len(cache) == capacity

    def test_single_item_capacity(self):
        """Test cache with capacity of 1."""
        cache = LRUCache[str, int](capacity=1)

        cache.put("key1", 1)
        assert len(cache) == 1
        assert cache.get("key1") == 1

        cache.put("key2", 2)
        assert len(cache) == 1
        assert cache.get("key1") is None
        assert cache.get("key2") == 2


class TestCacheStats:
    """Test cache statistics."""

    def test_stats(self):
        """Test stats method returns correct information."""
        cache = LRUCache[str, int](capacity=10)

        stats = cache.stats()
        assert stats["size"] == 0
        assert stats["capacity"] == 10
        assert stats["utilization"] == 0.0

        cache.put("key1", 1)
        cache.put("key2", 2)

        stats = cache.stats()
        assert stats["size"] == 2
        assert stats["capacity"] == 10
        assert stats["utilization"] == 0.2

    def test_stats_full_cache(self):
        """Test stats when cache is full."""
        cache = LRUCache[str, int](capacity=5)

        for i in range(5):
            cache.put(f"key{i}", i)

        stats = cache.stats()
        assert stats["size"] == 5
        assert stats["capacity"] == 5
        assert stats["utilization"] == 1.0


class TestDifferentTypes:
    """Test cache with different value types."""

    def test_string_values(self):
        """Test cache with string values."""
        cache = LRUCache[str, str](capacity=5)
        cache.put("greeting", "Hello, World!")
        assert cache.get("greeting") == "Hello, World!"

    def test_list_values(self):
        """Test cache with list values."""
        cache = LRUCache[str, list](capacity=5)
        cache.put("numbers", [1, 2, 3, 4, 5])
        assert cache.get("numbers") == [1, 2, 3, 4, 5]

    def test_dict_values(self):
        """Test cache with dict values."""
        cache = LRUCache[str, dict](capacity=5)
        cache.put("data", {"key": "value", "count": 42})
        assert cache.get("data") == {"key": "value", "count": 42}

    def test_tuple_values(self):
        """Test cache with tuple values."""
        cache = LRUCache[str, tuple](capacity=5)
        cache.put("point", (10, 20, 30))
        assert cache.get("point") == (10, 20, 30)


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_cache_clear(self):
        """Test clearing empty cache."""
        cache = LRUCache[str, int](capacity=5)
        cache.clear()  # Should not raise error
        assert len(cache) == 0

    def test_same_key_multiple_updates(self):
        """Test updating same key multiple times."""
        cache = LRUCache[str, int](capacity=3)

        for i in range(10):
            cache.put("key", i)

        assert len(cache) == 1
        assert cache.get("key") == 9

    def test_interleaved_operations(self):
        """Test interleaved put and get operations."""
        cache = LRUCache[str, int](capacity=3)

        cache.put("a", 1)
        assert cache.get("a") == 1

        cache.put("b", 2)
        cache.put("c", 3)

        assert cache.get("b") == 2
        assert cache.get("a") == 1

        cache.put("d", 4)  # Should evict c

        assert cache.get("c") is None
        assert cache.get("a") == 1
        assert cache.get("b") == 2
        assert cache.get("d") == 4
