"""Query Engine - Core search and ranking functionality.

This module implements the query execution logic, including term matching,
relevance ranking, and result formatting.
"""

import logging
from typing import Dict, List, Tuple

from knowledgebeast.core.repository import DocumentRepository
from knowledgebeast.core.constants import ERR_EMPTY_SEARCH_TERMS

logger = logging.getLogger(__name__)


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
