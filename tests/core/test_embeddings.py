"""Tests for embedding engine implementation."""

import hashlib
import threading
import time
from unittest.mock import Mock, patch

import numpy as np
import pytest

from knowledgebeast.core.embeddings import EmbeddingEngine


class TestEmbeddingEngineInitialization:
    """Test embedding engine initialization."""

    def test_init_default_model(self):
        """Test engine initializes with default model."""
        engine = EmbeddingEngine()
        assert engine.model_name == "all-MiniLM-L6-v2"
        assert engine.embedding_dim == 384
        assert engine.cache.capacity == 1000

    def test_init_custom_model(self):
        """Test engine initializes with custom model."""
        engine = EmbeddingEngine(model_name="all-mpnet-base-v2")
        assert engine.model_name == "all-mpnet-base-v2"
        assert engine.embedding_dim == 768

    def test_init_multilingual_model(self):
        """Test engine initializes with multilingual model."""
        engine = EmbeddingEngine(model_name="paraphrase-multilingual-mpnet-base-v2")
        assert engine.model_name == "paraphrase-multilingual-mpnet-base-v2"
        assert engine.embedding_dim == 768

    def test_init_invalid_model(self):
        """Test engine raises error for invalid model."""
        with pytest.raises(ValueError, match="Unsupported model"):
            EmbeddingEngine(model_name="invalid-model")

    def test_init_custom_cache_size(self):
        """Test engine initializes with custom cache size."""
        engine = EmbeddingEngine(cache_size=500)
        assert engine.cache.capacity == 500

    def test_init_stats(self):
        """Test engine initializes stats correctly."""
        engine = EmbeddingEngine()
        assert engine.stats["cache_hits"] == 0
        assert engine.stats["cache_misses"] == 0
        assert engine.stats["embeddings_generated"] == 0
        assert engine.stats["total_queries"] == 0

    def test_supported_models(self):
        """Test all supported models are accessible."""
        assert "all-MiniLM-L6-v2" in EmbeddingEngine.SUPPORTED_MODELS
        assert "all-mpnet-base-v2" in EmbeddingEngine.SUPPORTED_MODELS
        assert "paraphrase-multilingual-mpnet-base-v2" in EmbeddingEngine.SUPPORTED_MODELS


class TestEmbeddingGeneration:
    """Test embedding generation."""

    def test_embed_single_text(self):
        """Test embedding single text."""
        engine = EmbeddingEngine()
        embedding = engine.embed("Hello world")

        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (384,)
        assert embedding.dtype == np.float32

    def test_embed_multiple_texts(self):
        """Test embedding multiple texts."""
        engine = EmbeddingEngine()
        texts = ["Hello", "World", "Test"]
        embeddings = engine.embed(texts)

        assert isinstance(embeddings, list)
        assert len(embeddings) == 3
        for emb in embeddings:
            assert isinstance(emb, np.ndarray)
            assert emb.shape == (384,)

    def test_embed_empty_text(self):
        """Test embedding empty text."""
        engine = EmbeddingEngine()
        embedding = engine.embed("")

        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (384,)

    def test_embed_normalization(self):
        """Test embeddings are normalized by default."""
        engine = EmbeddingEngine()
        embedding = engine.embed("Test text", normalize=True)

        # Check L2 norm is approximately 1
        norm = np.linalg.norm(embedding)
        assert abs(norm - 1.0) < 1e-6

    def test_embed_without_normalization(self):
        """Test embeddings without normalization."""
        engine = EmbeddingEngine()
        embedding = engine.embed("Test text", normalize=False)

        # Without normalization, norm is typically != 1.0, but may be close
        # Just verify we get a valid embedding
        norm = np.linalg.norm(embedding)
        assert norm > 0  # Valid embedding has positive norm
        assert isinstance(embedding, np.ndarray)

    def test_embed_different_models(self):
        """Test embedding with different model dimensions."""
        engine_mini = EmbeddingEngine(model_name="all-MiniLM-L6-v2")
        engine_mpnet = EmbeddingEngine(model_name="all-mpnet-base-v2")

        emb_mini = engine_mini.embed("Test")
        emb_mpnet = engine_mpnet.embed("Test")

        assert emb_mini.shape == (384,)
        assert emb_mpnet.shape == (768,)


class TestCaching:
    """Test embedding caching."""

    def test_cache_hit(self):
        """Test cache returns cached embeddings."""
        engine = EmbeddingEngine()

        # First call - cache miss
        emb1 = engine.embed("Hello world", use_cache=True)
        assert engine.stats["cache_misses"] == 1
        assert engine.stats["cache_hits"] == 0

        # Second call - cache hit
        emb2 = engine.embed("Hello world", use_cache=True)
        assert engine.stats["cache_misses"] == 1
        assert engine.stats["cache_hits"] == 1

        # Should be identical
        np.testing.assert_array_equal(emb1, emb2)

    def test_cache_disabled(self):
        """Test caching can be disabled."""
        engine = EmbeddingEngine()

        # Both calls should be cache misses
        emb1 = engine.embed("Hello world", use_cache=False)
        emb2 = engine.embed("Hello world", use_cache=False)

        assert engine.stats["cache_misses"] == 2
        assert engine.stats["cache_hits"] == 0

    def test_cache_key_normalization(self):
        """Test cache key normalizes whitespace."""
        engine = EmbeddingEngine()

        # Different whitespace should produce same cache key
        emb1 = engine.embed("Hello  world", use_cache=True)
        emb2 = engine.embed("Hello world", use_cache=True)

        # Should get cache hit due to normalization
        assert engine.stats["cache_hits"] == 1

    def test_cache_eviction(self):
        """Test cache evicts old entries when full."""
        engine = EmbeddingEngine(cache_size=5)

        # Fill cache
        for i in range(6):
            engine.embed(f"Text {i}", use_cache=True)

        # Cache should be at capacity
        cache_stats = engine.cache.stats()
        assert cache_stats["size"] == 5

    def test_clear_cache(self):
        """Test clearing cache."""
        engine = EmbeddingEngine()

        engine.embed("Test 1", use_cache=True)
        engine.embed("Test 2", use_cache=True)

        assert engine.cache.stats()["size"] == 2

        engine.clear_cache()

        assert engine.cache.stats()["size"] == 0
        assert engine.stats["cache_hits"] == 0
        assert engine.stats["cache_misses"] == 0


class TestBatchEmbedding:
    """Test batch embedding operations."""

    def test_embed_batch_small(self):
        """Test batch embedding with small batch."""
        engine = EmbeddingEngine()
        texts = [f"Text {i}" for i in range(10)]

        embeddings = engine.embed_batch(texts, batch_size=32)

        assert len(embeddings) == 10
        for emb in embeddings:
            assert emb.shape == (384,)

    def test_embed_batch_multiple_batches(self):
        """Test batch embedding with multiple batches."""
        engine = EmbeddingEngine()
        texts = [f"Text {i}" for i in range(100)]

        embeddings = engine.embed_batch(texts, batch_size=32)

        assert len(embeddings) == 100

    def test_embed_batch_with_cache(self):
        """Test batch embedding uses cache."""
        engine = EmbeddingEngine()
        texts = ["Same text"] * 10

        embeddings = engine.embed_batch(texts, batch_size=5, use_cache=True)

        # Should have cache hits after first occurrence
        assert engine.stats["cache_hits"] > 0
        assert len(embeddings) == 10


class TestSimilarity:
    """Test similarity computation."""

    def test_similarity_cosine_identical(self):
        """Test cosine similarity of identical texts."""
        engine = EmbeddingEngine()

        sim = engine.similarity("Hello world", "Hello world", metric="cosine")

        # Should be very close to 1
        assert abs(sim - 1.0) < 0.01

    def test_similarity_cosine_different(self):
        """Test cosine similarity of different texts."""
        engine = EmbeddingEngine()

        sim = engine.similarity("Hello world", "Goodbye moon", metric="cosine")

        # Should be less than 1
        assert sim < 1.0

    def test_similarity_from_embeddings(self):
        """Test similarity from pre-computed embeddings."""
        engine = EmbeddingEngine()

        emb1 = engine.embed("Hello")
        emb2 = engine.embed("World")

        sim = engine.similarity(emb1, emb2, metric="cosine")

        assert isinstance(sim, float)
        assert 0 <= sim <= 1

    def test_similarity_dot_product(self):
        """Test dot product similarity."""
        engine = EmbeddingEngine()

        sim = engine.similarity("Hello", "Hello", metric="dot")

        assert isinstance(sim, float)

    def test_similarity_invalid_metric(self):
        """Test invalid similarity metric raises error."""
        engine = EmbeddingEngine()

        with pytest.raises(ValueError, match="Unsupported metric"):
            engine.similarity("Hello", "World", metric="invalid")


class TestStatistics:
    """Test statistics tracking."""

    def test_get_stats(self):
        """Test getting statistics."""
        engine = EmbeddingEngine()

        engine.embed("Test 1", use_cache=True)
        engine.embed("Test 1", use_cache=True)
        engine.embed("Test 2", use_cache=True)

        stats = engine.get_stats()

        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 2
        assert stats["embeddings_generated"] == 2
        assert stats["total_queries"] == 3
        assert stats["cache_hit_rate"] == 1/3
        assert stats["model_name"] == "all-MiniLM-L6-v2"
        assert stats["embedding_dim"] == 384

    def test_stats_cache_utilization(self):
        """Test cache utilization in stats."""
        engine = EmbeddingEngine(cache_size=10)

        for i in range(5):
            engine.embed(f"Text {i}", use_cache=True)

        stats = engine.get_stats()

        assert stats["cache_size"] == 5
        assert stats["cache_capacity"] == 10
        assert stats["cache_utilization"] == 0.5


class TestThreadSafety:
    """Test thread safety."""

    def test_concurrent_embedding(self):
        """Test concurrent embedding from multiple threads."""
        engine = EmbeddingEngine()
        results = []
        errors = []

        def embed_text(text):
            try:
                emb = engine.embed(text, use_cache=True)
                results.append(emb)
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(50):
            t = threading.Thread(target=embed_text, args=(f"Text {i % 10}",))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 50

    def test_concurrent_stats_consistency(self):
        """Test stats remain consistent under concurrent load."""
        engine = EmbeddingEngine()

        def embed_texts():
            for i in range(10):
                engine.embed(f"Text {i}", use_cache=True)

        threads = [threading.Thread(target=embed_texts) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        stats = engine.get_stats()

        # Total queries should equal cache hits + misses
        assert stats["total_queries"] == stats["cache_hits"] + stats["cache_misses"]


class TestUtilityMethods:
    """Test utility methods."""

    def test_get_embedding_dim(self):
        """Test getting embedding dimension."""
        engine = EmbeddingEngine()
        assert engine.get_embedding_dim() == 384

    def test_repr(self):
        """Test string representation."""
        engine = EmbeddingEngine(model_name="all-MiniLM-L6-v2", cache_size=500)
        repr_str = repr(engine)

        assert "all-MiniLM-L6-v2" in repr_str
        assert "384" in repr_str
        assert "500" in repr_str

    def test_generate_cache_key(self):
        """Test cache key generation."""
        engine = EmbeddingEngine()

        key1 = engine._generate_cache_key("Hello  world")
        key2 = engine._generate_cache_key("Hello world")

        # Should be same due to whitespace normalization
        assert key1 == key2

        # Different text should have different key
        key3 = engine._generate_cache_key("Different text")
        assert key1 != key3
