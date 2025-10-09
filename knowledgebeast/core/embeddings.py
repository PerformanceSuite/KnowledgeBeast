"""Vector embeddings engine with multiple model support and caching.

This module provides the EmbeddingEngine class for generating dense vector embeddings
from text using sentence-transformers models with thread-safe LRU caching.
"""

import hashlib
import threading
import time
from typing import Any, List, Optional, Union

import numpy as np
from sentence_transformers import SentenceTransformer

from knowledgebeast.core.cache import LRUCache
from knowledgebeast.utils.metrics import record_cache_hit, record_cache_miss
from knowledgebeast.utils.observability import get_tracer


class EmbeddingEngine:
    """Thread-safe embedding engine with LRU caching and batch support.

    Supports multiple pre-trained sentence-transformer models:
    - all-MiniLM-L6-v2: Fast, lightweight (384 dimensions)
    - all-mpnet-base-v2: Balanced speed/quality (768 dimensions)
    - paraphrase-multilingual-mpnet-base-v2: Multilingual (768 dimensions)

    Features:
    - Thread-safe embedding cache (default 1000 items)
    - Batch processing for performance
    - Automatic model loading and management
    - Cache hit/miss statistics

    Attributes:
        model_name: Name of the sentence-transformer model
        model: Loaded SentenceTransformer model instance
        cache: LRU cache for embedding results
        embedding_dim: Dimensionality of embedding vectors
        stats: Dictionary tracking cache hits, misses, and embeddings generated
    """

    SUPPORTED_MODELS = {
        "all-MiniLM-L6-v2": 384,
        "all-mpnet-base-v2": 768,
        "paraphrase-multilingual-mpnet-base-v2": 768,
    }

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        cache_size: int = 1000,
        device: Optional[str] = None,
    ) -> None:
        """Initialize the embedding engine.

        Args:
            model_name: Name of sentence-transformer model to use
            cache_size: Maximum number of cached embeddings
            device: Device to run model on ('cpu', 'cuda', 'mps', or None for auto)

        Raises:
            ValueError: If model_name is not supported
        """
        if model_name not in self.SUPPORTED_MODELS:
            raise ValueError(
                f"Unsupported model: {model_name}. "
                f"Supported models: {list(self.SUPPORTED_MODELS.keys())}"
            )

        self.model_name = model_name
        self.embedding_dim = self.SUPPORTED_MODELS[model_name]
        self.cache: LRUCache[str, np.ndarray] = LRUCache(capacity=cache_size)
        self._lock = threading.RLock()
        self.stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "embeddings_generated": 0,
            "total_queries": 0,
        }

        # Load model
        self.model = SentenceTransformer(model_name, device=device)

    def _generate_cache_key(self, text: str) -> str:
        """Generate cache key from text.

        Args:
            text: Input text

        Returns:
            MD5 hash of normalized text
        """
        # Normalize whitespace and create hash
        normalized = " ".join(text.split())
        return hashlib.md5(normalized.encode()).hexdigest()

    def embed(
        self,
        text: Union[str, List[str]],
        use_cache: bool = True,
        normalize: bool = True,
    ) -> Union[np.ndarray, List[np.ndarray]]:
        """Generate embeddings for text or batch of texts.

        Args:
            text: Single text string or list of texts
            use_cache: Whether to use cache for lookups/storage
            normalize: Whether to L2 normalize embeddings

        Returns:
            Single embedding array or list of embedding arrays

        Examples:
            >>> engine = EmbeddingEngine()
            >>> embedding = engine.embed("Hello world")
            >>> embedding.shape
            (384,)
            >>> embeddings = engine.embed(["Hello", "World"])
            >>> len(embeddings)
            2
        """
        tracer = get_tracer()
        with tracer.start_as_current_span("embedding.generate") as span:
            is_single = isinstance(text, str)
            texts = [text] if is_single else text

            # Add span attributes
            span.set_attribute("embedding.model", self.model_name)
            span.set_attribute("embedding.batch_size", len(texts))
            span.set_attribute("embedding.use_cache", use_cache)
            span.set_attribute("embedding.normalize", normalize)

            with self._lock:
                self.stats["total_queries"] += len(texts)

            # Check cache for each text
            results = []
            uncached_texts = []
            uncached_indices = []

            for i, txt in enumerate(texts):
                cache_key = self._generate_cache_key(txt)

                if use_cache:
                    cached = self.cache.get(cache_key)
                    if cached is not None:
                        with self._lock:
                            self.stats["cache_hits"] += 1
                        record_cache_hit()
                        results.append((i, cached))
                        continue

                # Track uncached texts
                with self._lock:
                    self.stats["cache_misses"] += 1
                record_cache_miss()
                uncached_texts.append(txt)
                uncached_indices.append(i)

            # Add cache statistics to span
            span.set_attribute("embedding.cache_hits", len(texts) - len(uncached_texts))
            span.set_attribute("embedding.cache_misses", len(uncached_texts))

            # Generate embeddings for uncached texts
            if uncached_texts:
                with tracer.start_as_current_span("embedding.model_encode") as encode_span:
                    encode_span.set_attribute("batch_size", len(uncached_texts))
                    embeddings = self.model.encode(
                        uncached_texts,
                        normalize_embeddings=normalize,
                        show_progress_bar=False,
                        convert_to_numpy=True,
                    )

                with self._lock:
                    self.stats["embeddings_generated"] += len(uncached_texts)

                # Cache results
                for txt, emb in zip(uncached_texts, embeddings):
                    if use_cache:
                        cache_key = self._generate_cache_key(txt)
                        self.cache.put(cache_key, emb)

                # Add to results
                for idx, emb in zip(uncached_indices, embeddings):
                    results.append((idx, emb))

            # Sort by original index and extract embeddings
            results.sort(key=lambda x: x[0])
            embeddings_list = [emb for _, emb in results]

            span.set_attribute("embedding.results_count", len(embeddings_list))
            return embeddings_list[0] if is_single else embeddings_list

    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32,
        use_cache: bool = True,
        normalize: bool = True,
        show_progress: bool = False,
    ) -> List[np.ndarray]:
        """Generate embeddings for large batches with progress tracking.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process at once
            use_cache: Whether to use cache
            normalize: Whether to L2 normalize embeddings
            show_progress: Whether to show progress bar

        Returns:
            List of embedding arrays
        """
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            embeddings = self.embed(
                batch,
                use_cache=use_cache,
                normalize=normalize,
            )
            all_embeddings.extend(embeddings if isinstance(embeddings, list) else [embeddings])

        return all_embeddings

    def similarity(
        self,
        text1: Union[str, np.ndarray],
        text2: Union[str, np.ndarray],
        metric: str = "cosine",
    ) -> float:
        """Compute similarity between two texts or embeddings.

        Args:
            text1: First text or embedding
            text2: Second text or embedding
            metric: Similarity metric ('cosine' or 'dot')

        Returns:
            Similarity score (0-1 for cosine, unbounded for dot product)

        Raises:
            ValueError: If metric is not supported
        """
        if metric not in ["cosine", "dot"]:
            raise ValueError(f"Unsupported metric: {metric}")

        # Get embeddings
        emb1 = self.embed(text1) if isinstance(text1, str) else text1
        emb2 = self.embed(text2) if isinstance(text2, str) else text2

        # Compute similarity
        if metric == "cosine":
            # Cosine similarity (assumes normalized embeddings)
            return float(np.dot(emb1, emb2))
        else:  # dot product
            return float(np.dot(emb1, emb2))

    def get_stats(self) -> dict[str, Any]:
        """Get embedding engine statistics.

        Returns:
            Dictionary with cache and embedding statistics
        """
        with self._lock:
            cache_stats = self.cache.stats()
            total = self.stats["cache_hits"] + self.stats["cache_misses"]
            hit_rate = self.stats["cache_hits"] / total if total > 0 else 0

            return {
                **self.stats,
                "cache_size": cache_stats["size"],
                "cache_capacity": cache_stats["capacity"],
                "cache_utilization": cache_stats["utilization"],
                "cache_hit_rate": hit_rate,
                "model_name": self.model_name,
                "embedding_dim": self.embedding_dim,
            }

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self.cache.clear()
        with self._lock:
            self.stats["cache_hits"] = 0
            self.stats["cache_misses"] = 0

    def get_embedding_dim(self) -> int:
        """Get the dimensionality of embeddings.

        Returns:
            Embedding dimension
        """
        return self.embedding_dim

    def __repr__(self) -> str:
        """Return string representation of engine."""
        return (
            f"EmbeddingEngine(model={self.model_name}, "
            f"dim={self.embedding_dim}, cache_size={self.cache.capacity})"
        )
