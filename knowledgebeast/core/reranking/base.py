"""Base reranker interface for KnowledgeBeast."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseReranker(ABC):
    """Abstract base class for all reranking implementations.

    All rerankers must implement the rerank method to reorder search results
    based on query relevance.
    """

    @abstractmethod
    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """Rerank search results based on query relevance.

        Args:
            query: The search query string
            results: List of search results, each containing at least:
                - 'content': The document text
                - 'vector_score': Original vector similarity score
            top_k: Number of top results to return (default: 10)

        Returns:
            Reranked list of results with additional fields:
                - 'rerank_score': The re-ranking relevance score (0-1)
                - 'final_score': The final combined score
                - 'rank': The new rank position (1-indexed)

        Raises:
            ValueError: If results is empty or invalid
        """
        pass

    def supports_batch(self) -> bool:
        """Check if this reranker supports batch processing.

        Returns:
            True if batch processing is supported, False otherwise
        """
        return False

    def supports_gpu(self) -> bool:
        """Check if this reranker supports GPU acceleration.

        Returns:
            True if GPU acceleration is supported, False otherwise
        """
        return False

    def get_model_name(self) -> str:
        """Get the name/identifier of the reranking model.

        Returns:
            Model name string
        """
        return self.__class__.__name__
