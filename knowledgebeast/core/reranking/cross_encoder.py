"""Cross-encoder reranker implementation for KnowledgeBeast.

This module implements cross-encoder based re-ranking using the
sentence-transformers library with the ms-marco-MiniLM-L-6-v2 model.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import numpy as np
import torch
from sentence_transformers import CrossEncoder

from knowledgebeast.core.reranking.base import BaseReranker
from knowledgebeast.utils.model_cache import get_global_model_cache

logger = logging.getLogger(__name__)


class CrossEncoderReranker(BaseReranker):
    """Cross-encoder based reranker for improving search relevance.

    Uses a pre-trained cross-encoder model to score query-document pairs
    and rerank results based on semantic relevance.

    Features:
        - Batch processing for efficiency
        - GPU acceleration support (if available)
        - Model caching for fast access
        - Async reranking support
        - Fallback to vector scores on timeout
        - Score normalization to [0, 1] range

    Thread Safety:
        This class is thread-safe. Model loading and inference are protected
        by internal locks.
    """

    DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    DEFAULT_BATCH_SIZE = 16
    DEFAULT_TIMEOUT = 5.0  # seconds

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        batch_size: int = DEFAULT_BATCH_SIZE,
        use_gpu: bool = True,
        timeout: float = DEFAULT_TIMEOUT,
        max_length: int = 512,
    ):
        """Initialize the cross-encoder reranker.

        Args:
            model_name: Name of the cross-encoder model (default: ms-marco-MiniLM-L-6-v2)
            batch_size: Batch size for processing (default: 16)
            use_gpu: Whether to use GPU if available (default: True)
            timeout: Timeout for reranking in seconds (default: 5.0)
            max_length: Maximum sequence length (default: 512)
        """
        self.model_name = model_name
        self.batch_size = batch_size
        self.timeout = timeout
        self.max_length = max_length

        # Determine device
        self.device = "cpu"
        if use_gpu and torch.cuda.is_available():
            self.device = "cuda"
            logger.info(f"GPU available, using device: {self.device}")
        elif use_gpu and torch.backends.mps.is_available():
            # Apple Silicon GPU support
            self.device = "mps"
            logger.info(f"Apple Silicon GPU available, using device: {self.device}")
        else:
            logger.info(f"Using device: {self.device}")

        self._model: Optional[CrossEncoder] = None
        self._model_cache = get_global_model_cache()
        self._load_count = 0

        logger.info(
            f"CrossEncoderReranker initialized: model={model_name}, "
            f"batch_size={batch_size}, device={self.device}, timeout={timeout}s"
        )

    def _load_model(self) -> CrossEncoder:
        """Load the cross-encoder model.

        Uses model cache for efficient loading.

        Returns:
            Loaded CrossEncoder model

        Thread Safety:
            Protected by model cache lock
        """
        def load_fn():
            logger.info(f"Loading cross-encoder model: {self.model_name}")
            start_time = time.time()

            model = CrossEncoder(
                self.model_name,
                max_length=self.max_length,
                device=self.device
            )

            load_time = time.time() - start_time
            logger.info(
                f"Cross-encoder model loaded in {load_time:.2f}s: {self.model_name}"
            )

            self._load_count += 1
            return model

        return self._model_cache.get_or_load(self.model_name, load_fn)

    @property
    def model(self) -> CrossEncoder:
        """Get the cross-encoder model (lazy loading).

        Returns:
            CrossEncoder model instance
        """
        if self._model is None:
            self._model = self._load_model()
        return self._model

    def warmup(self) -> None:
        """Warm up the model by running a dummy inference.

        This loads the model and performs a test inference to ensure
        everything is ready for production queries.
        """
        logger.info("Warming up cross-encoder model...")
        start_time = time.time()

        # Dummy query-document pair
        dummy_pairs = [["test query", "test document"]]
        self.model.predict(dummy_pairs)

        warmup_time = time.time() - start_time
        logger.info(f"Model warmup completed in {warmup_time:.2f}s")

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """Rerank search results using cross-encoder.

        Args:
            query: The search query string
            results: List of search results with 'content' and 'vector_score' fields
            top_k: Number of top results to return (default: 10)

        Returns:
            Reranked list of results with rerank_score, final_score, and rank fields

        Raises:
            ValueError: If results is empty or invalid
            TimeoutError: If reranking exceeds timeout (falls back to vector scores)
        """
        if not results:
            raise ValueError("Results list cannot be empty")

        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        # Validate results have required fields
        for i, result in enumerate(results):
            if "content" not in result:
                raise ValueError(f"Result {i} missing 'content' field")

        start_time = time.time()

        try:
            # Prepare query-document pairs for batch processing
            pairs = [[query, result.get("content", "")] for result in results]

            # Score all pairs in batches
            scores = self._score_pairs(pairs)

            # Normalize scores to [0, 1] range using sigmoid
            normalized_scores = self._normalize_scores(scores)

            # Add rerank scores to results
            for result, score in zip(results, normalized_scores):
                result["rerank_score"] = float(score)
                # Use rerank_score as final_score (can be combined with vector_score if needed)
                result["final_score"] = float(score)

            # Sort by rerank score (descending)
            reranked_results = sorted(
                results,
                key=lambda x: x["final_score"],
                reverse=True
            )

            # Add rank and limit to top_k
            for i, result in enumerate(reranked_results[:top_k], 1):
                result["rank"] = i

            duration = time.time() - start_time

            # Check timeout
            if duration > self.timeout:
                logger.warning(
                    f"Reranking exceeded timeout ({duration:.2f}s > {self.timeout}s), "
                    f"but completed successfully"
                )

            logger.debug(
                f"Reranked {len(results)} results to top {top_k} in {duration:.3f}s"
            )

            return reranked_results[:top_k]

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Reranking failed after {duration:.2f}s: {e}",
                exc_info=True
            )

            # Fallback: return results sorted by vector_score if available
            if all("vector_score" in r for r in results):
                logger.warning("Falling back to vector scores")
                fallback_results = sorted(
                    results,
                    key=lambda x: x.get("vector_score", 0),
                    reverse=True
                )
                for i, result in enumerate(fallback_results[:top_k], 1):
                    result["rank"] = i
                    result["rerank_score"] = result.get("vector_score", 0)
                    result["final_score"] = result.get("vector_score", 0)
                return fallback_results[:top_k]

            # If no fallback possible, re-raise
            raise

    async def rerank_async(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """Asynchronous reranking for API responsiveness.

        Args:
            query: The search query string
            results: List of search results
            top_k: Number of top results to return

        Returns:
            Reranked list of results

        Raises:
            asyncio.TimeoutError: If reranking exceeds timeout
            ValueError: If results is empty or invalid
        """
        try:
            # Run rerank in executor with timeout
            loop = asyncio.get_event_loop()
            reranked = await asyncio.wait_for(
                loop.run_in_executor(None, self.rerank, query, results, top_k),
                timeout=self.timeout
            )
            return reranked

        except asyncio.TimeoutError:
            logger.warning(
                f"Async reranking timed out after {self.timeout}s, "
                f"falling back to vector scores"
            )

            # Fallback to vector scores
            if all("vector_score" in r for r in results):
                fallback_results = sorted(
                    results,
                    key=lambda x: x.get("vector_score", 0),
                    reverse=True
                )
                for i, result in enumerate(fallback_results[:top_k], 1):
                    result["rank"] = i
                    result["rerank_score"] = result.get("vector_score", 0)
                    result["final_score"] = result.get("vector_score", 0)
                return fallback_results[:top_k]

            raise

    def _score_pairs(self, pairs: List[List[str]]) -> np.ndarray:
        """Score query-document pairs in batches.

        Args:
            pairs: List of [query, document] pairs

        Returns:
            Array of relevance scores
        """
        # Process in batches for efficiency
        all_scores = []

        for i in range(0, len(pairs), self.batch_size):
            batch = pairs[i:i + self.batch_size]
            batch_scores = self.model.predict(
                batch,
                show_progress_bar=False,
                convert_to_numpy=True
            )
            all_scores.extend(batch_scores)

        return np.array(all_scores)

    def _normalize_scores(self, scores: np.ndarray) -> np.ndarray:
        """Normalize scores to [0, 1] range using sigmoid.

        Args:
            scores: Raw cross-encoder scores

        Returns:
            Normalized scores in [0, 1] range
        """
        # Apply sigmoid to map to [0, 1]
        # Cross-encoder scores are typically in [-10, 10] range
        return 1 / (1 + np.exp(-scores))

    def supports_batch(self) -> bool:
        """Check if this reranker supports batch processing.

        Returns:
            True (cross-encoder supports batching)
        """
        return True

    def supports_gpu(self) -> bool:
        """Check if this reranker supports GPU acceleration.

        Returns:
            True if GPU is available and being used
        """
        return self.device in ["cuda", "mps"]

    def get_model_name(self) -> str:
        """Get the name of the cross-encoder model.

        Returns:
            Model name string
        """
        return self.model_name

    def get_stats(self) -> Dict[str, Any]:
        """Get reranker statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "model_name": self.model_name,
            "device": self.device,
            "batch_size": self.batch_size,
            "timeout": self.timeout,
            "max_length": self.max_length,
            "model_loaded": self._model is not None,
            "load_count": self._load_count,
            "supports_gpu": self.supports_gpu(),
            "supports_batch": self.supports_batch(),
        }
