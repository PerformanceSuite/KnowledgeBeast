"""Re-ranking helper utilities for API endpoints.

This module provides helper functions to apply re-ranking to search results
in API endpoints with proper metrics tracking and error handling.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from knowledgebeast.core.reranking import CrossEncoderReranker, MMRReranker
from knowledgebeast.utils.metrics import (
    measure_reranking,
    record_model_load,
    record_score_improvement,
)

logger = logging.getLogger(__name__)

# Global reranker instances (singleton pattern)
_cross_encoder: Optional[CrossEncoderReranker] = None
_mmr_reranker: Optional[MMRReranker] = None


def get_cross_encoder_reranker() -> CrossEncoderReranker:
    """Get or create the global cross-encoder reranker instance.

    Returns:
        CrossEncoderReranker instance

    Thread Safety:
        First call initializes the reranker. Subsequent calls return cached instance.
    """
    global _cross_encoder

    if _cross_encoder is None:
        logger.info("Initializing Cross-Encoder reranker...")
        _cross_encoder = CrossEncoderReranker(
            model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
            batch_size=16,
            use_gpu=True,
            timeout=5.0
        )
        # Warmup in background (non-blocking)
        try:
            _cross_encoder.warmup()
        except Exception as e:
            logger.warning(f"Cross-encoder warmup failed: {e}")

        record_model_load("cross-encoder/ms-marco-MiniLM-L-6-v2")

    return _cross_encoder


def get_mmr_reranker(diversity: float = 0.5) -> MMRReranker:
    """Get or create an MMR reranker instance with specified diversity.

    Args:
        diversity: Diversity parameter (0-1)

    Returns:
        MMRReranker instance

    Note:
        Currently uses a global instance. Could be extended to cache
        multiple instances with different diversity settings.
    """
    global _mmr_reranker

    if _mmr_reranker is None or _mmr_reranker.diversity != diversity:
        logger.info(f"Initializing MMR reranker (diversity={diversity})...")
        _mmr_reranker = MMRReranker(
            diversity=diversity,
            use_gpu=True
        )
        record_model_load(f"mmr_diversity_{diversity}")

    return _mmr_reranker


def apply_reranking(
    query: str,
    results: List[Dict[str, Any]],
    use_cross_encoder: bool = True,
    use_mmr: bool = False,
    diversity: Optional[float] = None,
    top_k: int = 10
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Apply re-ranking to search results.

    Args:
        query: The search query
        results: List of search results with 'content' field
        use_cross_encoder: Whether to use cross-encoder reranking
        use_mmr: Whether to use MMR for diversity (applied after cross-encoder if both enabled)
        diversity: MMR diversity parameter (0-1), if None uses 0.5
        top_k: Number of top results to return

    Returns:
        Tuple of (reranked_results, metadata_dict)
        metadata_dict contains reranking information like model name, duration, etc.

    Raises:
        ValueError: If results is empty or invalid
    """
    if not results:
        return results, {"reranked": False}

    metadata = {
        "reranked": False,
        "rerank_model": None,
        "rerank_duration_ms": 0
    }

    reranked_results = results
    start_time = time.time()

    try:
        # Apply cross-encoder reranking first (if enabled)
        if use_cross_encoder:
            logger.debug(f"Applying cross-encoder reranking to {len(results)} results")
            reranker = get_cross_encoder_reranker()

            with measure_reranking("cross_encoder"):
                reranked_results = reranker.rerank(query, results, top_k=top_k)

            metadata["reranked"] = True
            metadata["rerank_model"] = reranker.get_model_name()

            # Record score improvements
            for result in reranked_results:
                if "vector_score" in result and "rerank_score" in result:
                    record_score_improvement(
                        "cross_encoder",
                        result["vector_score"],
                        result["rerank_score"]
                    )

        # Apply MMR for diversity (if enabled)
        if use_mmr:
            mmr_diversity = diversity if diversity is not None else 0.5
            logger.debug(f"Applying MMR reranking (diversity={mmr_diversity})")

            reranker = get_mmr_reranker(diversity=mmr_diversity)

            with measure_reranking("mmr"):
                reranked_results = reranker.rerank(query, reranked_results, top_k=top_k)

            metadata["reranked"] = True
            if metadata["rerank_model"]:
                metadata["rerank_model"] += f" + {reranker.get_model_name()}"
            else:
                metadata["rerank_model"] = reranker.get_model_name()

        duration_ms = int((time.time() - start_time) * 1000)
        metadata["rerank_duration_ms"] = duration_ms

        logger.debug(
            f"Reranking completed in {duration_ms}ms: "
            f"cross_encoder={use_cross_encoder}, mmr={use_mmr}"
        )

        return reranked_results, metadata

    except Exception as e:
        logger.error(f"Reranking failed: {e}", exc_info=True)
        # Return original results on failure
        metadata["reranked"] = False
        metadata["rerank_error"] = str(e)
        return results[:top_k], metadata


def prepare_results_for_reranking(
    raw_results: List[tuple],
    add_vector_scores: bool = True
) -> List[Dict[str, Any]]:
    """Prepare raw results for reranking.

    Converts tuple-based results to dictionaries and optionally adds placeholder
    vector scores.

    Args:
        raw_results: List of (doc_id, doc_dict) tuples
        add_vector_scores: Whether to add placeholder vector scores

    Returns:
        List of dictionaries ready for reranking
    """
    prepared = []

    for i, (doc_id, doc) in enumerate(raw_results):
        result = {
            "doc_id": doc_id,
            "content": doc.get("content", ""),
            "name": doc.get("name", ""),
            "path": doc.get("path", ""),
            "kb_dir": doc.get("kb_dir", "")
        }

        # Add placeholder vector score (descending order based on position)
        if add_vector_scores:
            # Simple scoring: first result gets highest score
            result["vector_score"] = max(0.0, 1.0 - (i * 0.01))

        prepared.append(result)

    return prepared


def convert_to_query_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert reranked results to QueryResult format.

    Args:
        results: Reranked results

    Returns:
        List of results in QueryResult format
    """
    # Already in dict format, just ensure all required fields are present
    converted = []

    for result in results:
        converted.append({
            "doc_id": result.get("doc_id", ""),
            "content": result.get("content", ""),
            "name": result.get("name", ""),
            "path": result.get("path", ""),
            "kb_dir": result.get("kb_dir", ""),
            "vector_score": result.get("vector_score"),
            "rerank_score": result.get("rerank_score"),
            "final_score": result.get("final_score"),
            "rank": result.get("rank")
        })

    return converted
