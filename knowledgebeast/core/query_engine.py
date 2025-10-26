"""Query Engine - Core search and ranking functionality.

This module implements the query execution logic, including term matching,
relevance ranking, and result formatting. It also includes hybrid search
combining vector similarity and keyword matching.

Features:
- Graceful degradation when ChromaDB is unavailable
- Automatic fallback to keyword search
- Circuit breaker detection and handling
- Cache-based fallback for resilience
"""

import logging
import threading
from typing import Dict, List, Tuple, Optional, Literal
import numpy as np
from sentence_transformers import SentenceTransformer

from knowledgebeast.core.repository import DocumentRepository
from knowledgebeast.core.constants import ERR_EMPTY_SEARCH_TERMS
from knowledgebeast.core.cache import LRUCache
from knowledgebeast.utils.metrics import measure_vector_search
from knowledgebeast.utils.observability import get_tracer

logger = logging.getLogger(__name__)

__all__ = ['QueryEngine', 'HybridQueryEngine']


class QueryEngine:
    """Engine for executing queries against the document index.

    This class handles query parsing, term matching, relevance ranking,
    and result formatting. It uses the snapshot pattern for lock-free
    query execution.

    Thread Safety:
        - Query execution is lock-free after snapshot creation
        - Multiple queries can execute in parallel
        - No internal state modified during queries

    Attributes:
        repository: Document repository for data access
    """

    def __init__(self, repository: DocumentRepository) -> None:
        """Initialize query engine.

        Args:
            repository: Document repository instance
        """
        self.repository = repository

    def execute_query(self, search_terms: str) -> List[Tuple[str, Dict]]:
        """Execute query against document index.

        Uses the snapshot pattern for lock-free query execution:
        1. Create index snapshot (minimal lock time)
        2. Search without locks (parallel queries possible)
        3. Retrieve documents (single lock)

        Args:
            search_terms: Search query string

        Returns:
            List of (doc_id, document) tuples sorted by relevance

        Raises:
            ValueError: If search_terms is empty
        """
        if not search_terms or not search_terms.strip():
            raise ValueError(ERR_EMPTY_SEARCH_TERMS)

        # Parse query into terms
        terms = self._parse_query(search_terms)

        # Create index snapshot (repository handles locking)
        index_snapshot = self.repository.get_index_snapshot(terms)

        # Search WITHOUT holding lock - this is the performance optimization!
        # Multiple queries can now execute in parallel
        matches = self._match_documents(index_snapshot)

        # Rank results by relevance
        ranked_results = self._rank_results(matches)

        # Get document data (repository handles locking)
        doc_ids = [doc_id for doc_id, _ in ranked_results]
        documents = self.repository.get_documents_by_ids(doc_ids)

        # Combine doc_ids with documents
        # Ensure we got documents for all IDs (safety check)
        if len(documents) != len(doc_ids):
            logger.warning(f"Document ID mismatch: expected {len(doc_ids)}, got {len(documents)}")
            # Filter to only doc_ids that have corresponding documents
            results = [(doc_id, doc) for doc_id, doc in zip(doc_ids, documents) if doc]
        else:
            results = list(zip(doc_ids, documents))

        logger.debug(f"Query '{search_terms[:50]}' returned {len(results)} results")
        return results

    def get_answer(self, question: str, max_content_length: int = 500) -> str:
        """Get formatted answer for a question.

        Args:
            question: Question string
            max_content_length: Maximum content length to return

        Returns:
            Formatted answer with most relevant document content
        """
        try:
            results = self.execute_query(question)

            if not results:
                return "❌ No relevant documentation found."

            # Return most relevant document
            doc_id, doc = results[0]
            content_preview = doc['content'][:max_content_length]
            if len(doc['content']) > max_content_length:
                content_preview += "..."

            return f"📄 **{doc['name']}** ({doc_id})\n\n{content_preview}"

        except Exception as e:
            logger.error(f"Error getting answer: {e}", exc_info=True)
            return f"❌ Error getting answer: {e}"

    def _parse_query(self, query: str) -> List[str]:
        """Parse query string into search terms.

        Args:
            query: Query string

        Returns:
            List of normalized search terms
        """
        # Simple whitespace tokenization with lowercase normalization
        return query.lower().split()

    def _match_documents(self, index_snapshot: Dict[str, List[str]]) -> Dict[str, int]:
        """Match documents against search terms.

        Args:
            index_snapshot: Snapshot of term index

        Returns:
            Dictionary mapping doc_id to match score (number of matching terms)
        """
        matches: Dict[str, int] = {}

        for term, doc_ids in index_snapshot.items():
            for doc_id in doc_ids:
                matches[doc_id] = matches.get(doc_id, 0) + 1

        return matches

    def _rank_results(self, matches: Dict[str, int]) -> List[Tuple[str, int]]:
        """Rank query results by relevance.

        Currently uses simple term frequency ranking.
        Future: Could implement TF-IDF, BM25, or other ranking algorithms.

        Args:
            matches: Dictionary mapping doc_id to match score

        Returns:
            List of (doc_id, score) tuples sorted by score (descending)
        """
        return sorted(matches.items(), key=lambda x: x[1], reverse=True)


class HybridQueryEngine:
    """Hybrid search engine combining vector similarity and keyword matching.

    This class implements three search modes:
    1. Vector search: Pure semantic similarity using embeddings
    2. Keyword search: Traditional term matching (backward compatible)
    3. Hybrid search: Weighted combination of vector and keyword scores

    Features:
        - Configurable alpha parameter for hybrid weighting
        - MMR (Maximal Marginal Relevance) re-ranking
        - Diversity sampling for varied results
        - Thread-safe operation with embedding cache
        - Lock-free query execution

    v3.0 Changes:
        - Added backend parameter for pluggable vector storage
        - Defaults to None (backward compatible)
        - When None, uses internal embedding cache (legacy behavior)
        - When provided, delegates vector operations to backend

    Thread Safety:
        - Embedding model is thread-safe (read-only after init)
        - Embedding cache is thread-safe (LRUCache)
        - Query execution is lock-free after snapshot
        - Repository operations are protected by repository locks

    Attributes:
        repository: Document repository for data access
        keyword_engine: QueryEngine for keyword search
        backend: Optional VectorBackend for vector operations (v3.0+)
        model: SentenceTransformer for embeddings
        embedding_cache: LRU cache for document embeddings (legacy)
        alpha: Default weight for hybrid search (0-1, default 0.7)
    """

    def __init__(
        self,
        repository: DocumentRepository,
        backend: Optional['VectorBackend'] = None,
        model_name: str = "all-MiniLM-L6-v2",
        alpha: float = 0.7,
        cache_size: int = 1000
    ) -> None:
        """Initialize hybrid query engine.

        Args:
            repository: Document repository instance
            backend: Optional VectorBackend instance (v3.0+)
                     If None, uses legacy in-memory embedding cache
            model_name: Name of sentence-transformers model to use
            alpha: Default weight for vector search in hybrid mode (0-1)
            cache_size: Size of embedding cache (legacy mode only)

        Raises:
            ValueError: If alpha not in [0, 1]
        """
        if not 0 <= alpha <= 1:
            raise ValueError("alpha must be between 0 and 1")

        self.repository = repository
        self.keyword_engine = QueryEngine(repository)
        self.backend = backend
        self.alpha = alpha

        # Load embedding model (thread-safe after initialization)
        logger.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)

        # Legacy mode: In-memory embedding cache (used when backend=None)
        self.embedding_cache: LRUCache[str, np.ndarray] = LRUCache(capacity=cache_size)

        # Only pre-compute embeddings if NOT using backend
        # (backend manages its own embeddings)
        if self.backend is None:
            logger.info("Using legacy in-memory embedding cache (no backend)")
            self._precompute_embeddings()
        else:
            logger.info(f"Using {self.backend.__class__.__name__} backend for vector operations")

    def refresh_embeddings(self) -> int:
        """Refresh embeddings for all documents in repository.

        This method can be called after documents are added to ensure
        all documents have their embeddings cached. Useful for testing
        and when documents are added after engine initialization.

        Returns:
            Number of documents embedded

        Thread-safe through repository locking.
        """
        return self._precompute_embeddings()

    def _precompute_embeddings(self) -> int:
        """Pre-compute embeddings for all documents in repository.

        This is called during initialization to populate the embedding cache.
        Thread-safe through repository locking.

        Returns:
            Number of documents embedded
        """
        logger.info("Pre-computing document embeddings...")
        stats = self.repository.get_stats()
        doc_count = stats['documents']

        if doc_count == 0:
            logger.warning("No documents in repository to embed")
            return 0

        # Get all document IDs (repository handles locking)
        with self.repository._lock:
            doc_ids = list(self.repository.documents.keys())

        # Compute embeddings for each document
        for i, doc_id in enumerate(doc_ids):
            doc = self.repository.get_document(doc_id)
            if doc:
                embedding = self._get_embedding(doc['content'])
                self.embedding_cache.put(doc_id, embedding)

                if (i + 1) % 100 == 0:
                    logger.debug(f"Embedded {i + 1}/{doc_count} documents")

        logger.info(f"Completed embedding {doc_count} documents")
        return doc_count

    def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding for text.

        Args:
            text: Text to embed

        Returns:
            Numpy array of embedding vector
        """
        # Model.encode is thread-safe
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding

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

    def search_vector(
        self,
        query: str,
        top_k: int = 10,
        fallback_on_error: bool = True
    ) -> Tuple[List[Tuple[str, Dict, float]], bool]:
        """Pure vector similarity search using embeddings with graceful degradation.

        Args:
            query: Search query string
            top_k: Number of top results to return
            fallback_on_error: Fallback to keyword search on error (default: True)

        Returns:
            Tuple of (results, degraded_mode) where:
            - results: List of (doc_id, document, score) tuples sorted by similarity
            - degraded_mode: True if fallback to keyword search was used
        """
        if not query or not query.strip():
            return [], False

        try:
            # Get query embedding
            query_embedding = self._get_embedding(query)

            # Get all document IDs (repository handles locking)
            with self.repository._lock:
                doc_ids = list(self.repository.documents.keys())

            # Compute similarities (lock-free)
            similarities = []
            for doc_id in doc_ids:
                # Get cached embedding, or compute on-the-fly if not cached
                doc_embedding = self.embedding_cache.get(doc_id)
                if doc_embedding is None:
                    # Embedding not cached - compute and cache it
                    doc = self.repository.get_document(doc_id)
                    if doc and 'content' in doc:
                        doc_embedding = self._get_embedding(doc['content'])
                        self.embedding_cache.put(doc_id, doc_embedding)

                if doc_embedding is not None:
                    similarity = self._cosine_similarity(query_embedding, doc_embedding)
                    similarities.append((doc_id, similarity))

            # Sort by similarity (descending)
            similarities.sort(key=lambda x: x[1], reverse=True)

            # Get top-k results
            top_results = similarities[:top_k]

            # Retrieve documents (repository handles locking)
            doc_ids_top = [doc_id for doc_id, _ in top_results]
            documents = self.repository.get_documents_by_ids(doc_ids_top)

            # Combine with scores
            results = [
                (doc_id, doc, score)
                for (doc_id, score), doc in zip(top_results, documents)
            ]

            logger.debug(f"Vector search for '{query[:50]}' returned {len(results)} results")
            return results, False

        except CircuitBreakerError as e:
            logger.warning(f"Circuit breaker open for vector search: {e}")
            if fallback_on_error:
                logger.info("Falling back to keyword search (degraded mode)")
                keyword_results = self.search_keyword(query)
                return keyword_results, True
            else:
                return [], True

        except Exception as e:
            logger.error(f"Vector search failed: {e}", exc_info=True)
            if fallback_on_error:
                logger.info("Falling back to keyword search due to error (degraded mode)")
                try:
                    keyword_results = self.search_keyword(query)
                    return keyword_results, True
                except Exception as fallback_error:
                    logger.error(f"Keyword fallback also failed: {fallback_error}")
                    return [], True
            else:
                return [], True

    def search_keyword(
        self,
        query: str
    ) -> List[Tuple[str, Dict, float]]:
        """Keyword-based search (backward compatible with QueryEngine).

        Args:
            query: Search query string

        Returns:
            List of (doc_id, document, score) tuples sorted by relevance

        Raises:
            ValueError: If query is empty
        """
        # Use existing QueryEngine
        results = self.keyword_engine.execute_query(query)

        # Normalize scores to 0-1 range
        if not results:
            return []

        max_score = max(len(query.split()), 1)  # Max possible term matches

        # Add normalized scores
        scored_results = [
            (doc_id, doc, len([t for t in query.lower().split()
                              if t in doc['content'].lower()]) / max_score)
            for doc_id, doc in results
        ]

        logger.debug(f"Keyword search for '{query[:50]}' returned {len(scored_results)} results")
        return scored_results

    def search_hybrid(
        self,
        query: str,
        alpha: Optional[float] = None,
        top_k: int = 10
    ) -> Tuple[List[Tuple[str, Dict, float]], bool]:
        """Hybrid search combining vector and keyword scores with graceful degradation.

        Final score = alpha * vector_score + (1 - alpha) * keyword_score

        Args:
            query: Search query string
            alpha: Weight for vector search (0-1). If None, uses self.alpha
            top_k: Number of top results to return

        Returns:
            Tuple of (results, degraded_mode) where:
            - results: List of (doc_id, document, score) tuples sorted by combined score
            - degraded_mode: True if vector search unavailable (keyword-only mode)

        Raises:
            ValueError: If alpha not in [0, 1]
        """
        tracer = get_tracer()
        with tracer.start_as_current_span("query.hybrid_search") as span:
            if not query or not query.strip():
                span.set_attribute("query.empty", True)
                return [], False

            alpha = alpha if alpha is not None else self.alpha
            if not 0 <= alpha <= 1:
                raise ValueError("alpha must be between 0 and 1")

            # Add span attributes
            span.set_attribute("query.text", query[:100])  # Truncate for safety
            span.set_attribute("query.alpha", alpha)
            span.set_attribute("query.top_k", top_k)
            span.set_attribute("query.type", "hybrid")

            # Measure hybrid search with metrics
            with measure_vector_search("hybrid"):
                # Get vector scores
                with tracer.start_as_current_span("query.vector_phase") as vector_span:
                    vector_results, degraded = self.search_vector(query, top_k=top_k * 2)  # Get more for reranking
                    vector_scores = {doc_id: score for doc_id, _, score in vector_results}
                    vector_span.set_attribute("results_count", len(vector_results))
                    vector_span.set_attribute("degraded_mode", degraded)

                # Get keyword scores
                with tracer.start_as_current_span("query.keyword_phase") as keyword_span:
                    keyword_results = self.search_keyword(query)
                    keyword_scores = {doc_id: score for doc_id, _, score in keyword_results}
                    keyword_span.set_attribute("results_count", len(keyword_results))

                # Combine scores
                with tracer.start_as_current_span("query.score_combination") as combine_span:
                    all_doc_ids = set(vector_scores.keys()) | set(keyword_scores.keys())
                    combined_scores = {}

                    for doc_id in all_doc_ids:
                        v_score = vector_scores.get(doc_id, 0.0)
                        k_score = keyword_scores.get(doc_id, 0.0)
                        combined_scores[doc_id] = alpha * v_score + (1 - alpha) * k_score

                    # Sort by combined score
                    ranked_ids = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
                    top_ids = ranked_ids[:top_k]
                    combine_span.set_attribute("unique_docs", len(all_doc_ids))
                    combine_span.set_attribute("top_results", len(top_ids))

                # Retrieve documents
                doc_ids_top = [doc_id for doc_id, _ in top_ids]
                documents = self.repository.get_documents_by_ids(doc_ids_top)

                # Combine with scores
                results = [
                    (doc_id, doc, score)
                    for (doc_id, score), doc in zip(top_ids, documents)
                ]

            span.set_attribute("query.final_results", len(results))
            span.set_attribute("query.degraded_mode", degraded)
            logger.debug(f"Hybrid search (alpha={alpha}) for '{query[:50]}' returned {len(results)} results (degraded={degraded})")
            return results, degraded

    def search_with_mmr(
        self,
        query: str,
        lambda_param: float = 0.5,
        top_k: int = 10,
        mode: Literal['vector', 'keyword', 'hybrid'] = 'hybrid'
    ) -> List[Tuple[str, Dict, float]]:
        """Search with Maximal Marginal Relevance (MMR) re-ranking.

        MMR balances relevance and diversity by selecting documents that are
        both relevant to the query and diverse from already selected documents.

        Score = lambda * relevance - (1 - lambda) * max_similarity_to_selected

        Args:
            query: Search query string
            lambda_param: Weight for relevance vs diversity (0-1)
            top_k: Number of top results to return
            mode: Search mode ('vector', 'keyword', 'hybrid')

        Returns:
            List of (doc_id, document, score) tuples with MMR re-ranking.
            Returns empty list if query is empty.

        Raises:
            ValueError: If lambda_param not in [0, 1]
        """
        if not query or not query.strip():
            return []

        if not 0 <= lambda_param <= 1:
            raise ValueError("lambda_param must be between 0 and 1")

        # Get initial results (more than top_k for diversity)
        if mode == 'vector':
            candidates, _ = self.search_vector(query, top_k=top_k * 3)
        elif mode == 'keyword':
            candidates = self.search_keyword(query)[:top_k * 3]
        else:  # hybrid
            candidates, _ = self.search_hybrid(query, top_k=top_k * 3)

        if not candidates:
            return []

        # Initialize
        selected = []
        candidate_pool = list(candidates)

        # Get query embedding for vector similarity
        query_embedding = self._get_embedding(query)

        # MMR selection loop
        while len(selected) < top_k and candidate_pool:
            if not selected:
                # First selection: most relevant
                best_idx = 0
                best_candidate = candidate_pool.pop(0)
                selected.append(best_candidate)
            else:
                # MMR scoring
                best_score = -float('inf')
                best_idx = -1

                for i, (doc_id, doc, relevance) in enumerate(candidate_pool):
                    # Get document embedding
                    doc_embedding = self.embedding_cache.get(doc_id)
                    if doc_embedding is None:
                        continue

                    # Max similarity to already selected documents
                    max_sim = 0.0
                    for selected_id, _, _ in selected:
                        selected_embedding = self.embedding_cache.get(selected_id)
                        if selected_embedding is not None:
                            sim = self._cosine_similarity(doc_embedding, selected_embedding)
                            max_sim = max(max_sim, sim)

                    # MMR score
                    mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim

                    if mmr_score > best_score:
                        best_score = mmr_score
                        best_idx = i

                if best_idx >= 0:
                    selected.append(candidate_pool.pop(best_idx))
                else:
                    break

        logger.debug(f"MMR search (mode={mode}, lambda={lambda_param}) returned {len(selected)} results")
        return selected

    def search_with_diversity(
        self,
        query: str,
        diversity_threshold: float = 0.8,
        top_k: int = 10,
        mode: Literal['vector', 'keyword', 'hybrid'] = 'hybrid'
    ) -> List[Tuple[str, Dict, float]]:
        """Search with diversity sampling.

        Ensures selected documents are dissimilar to each other (diversity).
        Only selects documents with similarity < diversity_threshold to already selected.

        Args:
            query: Search query string
            diversity_threshold: Maximum similarity threshold for diversity (0-1)
            top_k: Number of top results to return
            mode: Search mode ('vector', 'keyword', 'hybrid')

        Returns:
            List of (doc_id, document, score) tuples with diversity filtering.
            Returns empty list if query is empty.

        Raises:
            ValueError: If threshold not in [0, 1]
        """
        if not query or not query.strip():
            return []

        if not 0 <= diversity_threshold <= 1:
            raise ValueError("diversity_threshold must be between 0 and 1")

        # Get initial results
        if mode == 'vector':
            candidates, _ = self.search_vector(query, top_k=top_k * 3)
        elif mode == 'keyword':
            candidates = self.search_keyword(query)[:top_k * 3]
        else:  # hybrid
            candidates, _ = self.search_hybrid(query, top_k=top_k * 3)

        if not candidates:
            return []

        # Diversity filtering
        selected = []

        for doc_id, doc, score in candidates:
            if len(selected) >= top_k:
                break

            # Check diversity against already selected
            doc_embedding = self.embedding_cache.get(doc_id)
            if doc_embedding is None:
                continue

            is_diverse = True
            for selected_id, _, _ in selected:
                selected_embedding = self.embedding_cache.get(selected_id)
                if selected_embedding is not None:
                    similarity = self._cosine_similarity(doc_embedding, selected_embedding)
                    if similarity >= diversity_threshold:
                        is_diverse = False
                        break

            if is_diverse:
                selected.append((doc_id, doc, score))

        logger.debug(f"Diversity search (threshold={diversity_threshold}) returned {len(selected)} results")
        return selected

    def get_embedding_stats(self) -> Dict:
        """Get embedding cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return self.embedding_cache.stats()
