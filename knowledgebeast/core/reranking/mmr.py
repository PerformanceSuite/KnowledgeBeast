"""Maximal Marginal Relevance (MMR) reranker for diversity.

This module implements MMR-based reranking to balance relevance and diversity
in search results.
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from knowledgebeast.core.reranking.base import BaseReranker
from knowledgebeast.utils.model_cache import get_global_model_cache

logger = logging.getLogger(__name__)


class MMRReranker(BaseReranker):
    """Maximal Marginal Relevance (MMR) reranker for result diversity.

    MMR balances relevance and diversity by selecting documents that are:
    1. Relevant to the query (high relevance score)
    2. Diverse from already selected documents (low similarity)

    The algorithm:
        MMR = λ * relevance(d, q) - (1-λ) * max_similarity(d, selected)

    Where:
        - λ (lambda) controls the relevance-diversity tradeoff
        - λ = 1.0: Pure relevance (no diversity)
        - λ = 0.0: Pure diversity (no relevance)
        - λ = 0.5: Balanced relevance and diversity

    Features:
        - Configurable diversity parameter (lambda)
        - Uses sentence embeddings for similarity computation
        - Efficient incremental selection
        - Preserves original relevance scores

    Thread Safety:
        This class is thread-safe. Model loading and computations are protected.
    """

    DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    DEFAULT_LAMBDA = 0.5

    def __init__(
        self,
        diversity: float = DEFAULT_LAMBDA,
        embedding_model: Optional[str] = None,
        use_gpu: bool = True
    ):
        """Initialize the MMR reranker.

        Args:
            diversity: Diversity parameter (0-1). Higher = more relevance, lower = more diversity.
                      Also known as lambda. Default: 0.5 (balanced)
            embedding_model: Name of the embedding model (default: all-MiniLM-L6-v2)
            use_gpu: Whether to use GPU if available (default: True)

        Raises:
            ValueError: If diversity is not in [0, 1] range
        """
        if not 0 <= diversity <= 1:
            raise ValueError(f"Diversity must be in [0, 1], got {diversity}")

        self.diversity = diversity
        self.embedding_model_name = embedding_model or self.DEFAULT_MODEL

        # Determine device
        self.device = "cpu"
        if use_gpu:
            import torch
            if torch.cuda.is_available():
                self.device = "cuda"
            elif torch.backends.mps.is_available():
                self.device = "mps"

        self._model: Optional[SentenceTransformer] = None
        self._model_cache = get_global_model_cache()

        logger.info(
            f"MMRReranker initialized: diversity={diversity}, "
            f"model={self.embedding_model_name}, device={self.device}"
        )

    def _load_model(self) -> SentenceTransformer:
        """Load the sentence transformer model.

        Returns:
            Loaded SentenceTransformer model

        Thread Safety:
            Protected by model cache lock
        """
        def load_fn():
            logger.info(f"Loading embedding model: {self.embedding_model_name}")
            model = SentenceTransformer(self.embedding_model_name, device=self.device)
            return model

        return self._model_cache.get_or_load(
            f"mmr_{self.embedding_model_name}",
            load_fn
        )

    @property
    def model(self) -> SentenceTransformer:
        """Get the embedding model (lazy loading).

        Returns:
            SentenceTransformer instance
        """
        if self._model is None:
            self._model = self._load_model()
        return self._model

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """Rerank search results using MMR for diversity.

        Args:
            query: The search query string
            results: List of search results with 'content' field and optionally
                    'vector_score' or 'rerank_score' for relevance
            top_k: Number of top results to return (default: 10)

        Returns:
            Reranked list of results with diversity scores

        Raises:
            ValueError: If results is empty or invalid
        """
        if not results:
            raise ValueError("Results list cannot be empty")

        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        # Validate results have required fields
        for i, result in enumerate(results):
            if "content" not in result:
                raise ValueError(f"Result {i} missing 'content' field")

        # Encode query
        query_embedding = self.model.encode(
            [query],
            convert_to_numpy=True,
            show_progress_bar=False
        )[0]

        # Encode all documents
        documents = [result["content"] for result in results]
        doc_embeddings = self.model.encode(
            documents,
            convert_to_numpy=True,
            show_progress_bar=False,
            batch_size=32
        )

        # Get relevance scores (use existing scores if available, otherwise compute)
        relevance_scores = self._get_relevance_scores(
            results,
            query_embedding,
            doc_embeddings
        )

        # Perform MMR selection
        selected_indices = self._mmr_select(
            query_embedding,
            doc_embeddings,
            relevance_scores,
            top_k
        )

        # Build reranked results
        reranked_results = []
        for rank, idx in enumerate(selected_indices, 1):
            result = results[idx].copy()
            result["rank"] = rank
            result["mmr_score"] = float(relevance_scores[idx])
            result["final_score"] = float(relevance_scores[idx])
            # Preserve original scores
            if "rerank_score" not in result and "vector_score" in result:
                result["rerank_score"] = result["vector_score"]
            reranked_results.append(result)

        logger.debug(
            f"MMR reranked {len(results)} results to top {top_k} "
            f"(diversity={self.diversity})"
        )

        return reranked_results

    def _get_relevance_scores(
        self,
        results: List[Dict[str, Any]],
        query_embedding: np.ndarray,
        doc_embeddings: np.ndarray
    ) -> np.ndarray:
        """Get or compute relevance scores for results.

        Args:
            results: List of results
            query_embedding: Query embedding vector
            doc_embeddings: Document embedding vectors

        Returns:
            Array of relevance scores
        """
        # Try to use existing scores (rerank_score > vector_score > computed)
        scores = []
        use_existing = True

        for result in results:
            if "rerank_score" in result:
                scores.append(result["rerank_score"])
            elif "vector_score" in result:
                scores.append(result["vector_score"])
            else:
                use_existing = False
                break

        if use_existing and scores:
            return np.array(scores)

        # Compute cosine similarity as relevance scores
        logger.debug("Computing relevance scores from embeddings")
        similarities = self._cosine_similarity(query_embedding, doc_embeddings)

        # Normalize to [0, 1]
        min_sim, max_sim = similarities.min(), similarities.max()
        if max_sim > min_sim:
            similarities = (similarities - min_sim) / (max_sim - min_sim)

        return similarities

    def _mmr_select(
        self,
        query_embedding: np.ndarray,
        doc_embeddings: np.ndarray,
        relevance_scores: np.ndarray,
        top_k: int
    ) -> List[int]:
        """Perform MMR selection algorithm.

        Args:
            query_embedding: Query embedding vector
            doc_embeddings: Document embedding vectors
            relevance_scores: Relevance scores for each document
            top_k: Number of documents to select

        Returns:
            List of selected document indices in order
        """
        selected_indices = []
        remaining_indices = list(range(len(doc_embeddings)))

        # Compute all pairwise similarities once (for efficiency)
        doc_similarities = self._pairwise_cosine_similarity(doc_embeddings)

        for _ in range(min(top_k, len(doc_embeddings))):
            if not remaining_indices:
                break

            # Compute MMR scores for remaining documents
            mmr_scores = []
            for idx in remaining_indices:
                # Relevance term
                relevance = relevance_scores[idx]

                # Diversity term (max similarity to selected documents)
                if selected_indices:
                    max_similarity = max(
                        doc_similarities[idx][selected_idx]
                        for selected_idx in selected_indices
                    )
                else:
                    max_similarity = 0.0

                # MMR formula: λ * relevance - (1-λ) * max_similarity
                mmr_score = (
                    self.diversity * relevance -
                    (1 - self.diversity) * max_similarity
                )
                mmr_scores.append(mmr_score)

            # Select document with highest MMR score
            best_idx = remaining_indices[np.argmax(mmr_scores)]
            selected_indices.append(best_idx)
            remaining_indices.remove(best_idx)

        return selected_indices

    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> np.ndarray:
        """Compute cosine similarity between a vector and multiple vectors.

        Args:
            vec1: Single vector (1D array)
            vec2: Multiple vectors (2D array)

        Returns:
            Array of cosine similarities
        """
        # Normalize vectors
        vec1_norm = vec1 / (np.linalg.norm(vec1) + 1e-10)
        vec2_norm = vec2 / (np.linalg.norm(vec2, axis=1, keepdims=True) + 1e-10)

        # Compute dot product
        return np.dot(vec2_norm, vec1_norm)

    @staticmethod
    def _pairwise_cosine_similarity(vectors: np.ndarray) -> np.ndarray:
        """Compute pairwise cosine similarity matrix.

        Args:
            vectors: Matrix of vectors (N x D)

        Returns:
            Similarity matrix (N x N)
        """
        # Normalize vectors
        norms = np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-10
        normalized = vectors / norms

        # Compute similarity matrix
        return np.dot(normalized, normalized.T)

    def supports_batch(self) -> bool:
        """Check if this reranker supports batch processing.

        Returns:
            True (MMR uses batch embedding)
        """
        return True

    def supports_gpu(self) -> bool:
        """Check if this reranker supports GPU acceleration.

        Returns:
            True if GPU is available and being used
        """
        return self.device in ["cuda", "mps"]

    def get_model_name(self) -> str:
        """Get the name of the embedding model.

        Returns:
            Model name string
        """
        return f"MMR({self.embedding_model_name}, λ={self.diversity})"

    def get_stats(self) -> Dict[str, Any]:
        """Get reranker statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "model_name": self.embedding_model_name,
            "diversity": self.diversity,
            "device": self.device,
            "model_loaded": self._model is not None,
            "supports_gpu": self.supports_gpu(),
            "supports_batch": self.supports_batch(),
        }
