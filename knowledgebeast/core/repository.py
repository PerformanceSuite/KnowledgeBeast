"""Document Repository - Data access layer for document storage and retrieval.

This module implements the Repository Pattern for document and index storage,
providing a clean abstraction over the underlying data structures.
"""

import json
import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from knowledgebeast.core.constants import (
    MAX_RETRY_ATTEMPTS,
    RETRY_MIN_WAIT_SECONDS,
    RETRY_MAX_WAIT_SECONDS,
    RETRY_MULTIPLIER,
    CACHE_TEMP_SUFFIX,
    JSON_INDENT,
)

logger = logging.getLogger(__name__)

__all__ = ['DocumentRepository']


class DocumentRepository:
    """Repository for document storage and index management.

    This class encapsulates all document and index data access operations,
    providing thread-safe storage and retrieval capabilities.

    Thread Safety:
        - All public methods are protected by RLock
        - Supports concurrent reads through snapshot pattern
        - Atomic updates for index swapping

    Attributes:
        documents: Dictionary mapping doc_id to document data
        index: Dictionary mapping terms to list of doc_ids
        stats: Statistics about repository contents
    """

    def __init__(self) -> None:
        """Initialize empty document repository."""
        self._lock = threading.RLock()
        self.documents: Dict[str, Dict] = {}
        self.index: Dict[str, List[str]] = {}
        self.stats = {
            'total_documents': 0,
            'total_terms': 0
        }

    def add_document(self, doc_id: str, document_data: Dict) -> None:
        """Add or update a document in the repository.

        Args:
            doc_id: Unique document identifier
            document_data: Document metadata and content
        """
        with self._lock:
            self.documents[doc_id] = document_data
            self.stats['total_documents'] = len(self.documents)

    def get_document(self, doc_id: str) -> Optional[Dict]:
        """Get a document by ID.

        Args:
            doc_id: Document identifier

        Returns:
            Document data dictionary or None if not found
        """
        with self._lock:
            doc = self.documents.get(doc_id)
            # Return copy to prevent external modification
            return dict(doc) if doc else None

    def get_documents_by_ids(self, doc_ids: List[str]) -> List[Dict]:
        """Get multiple documents by their IDs.

        Args:
            doc_ids: List of document identifiers

        Returns:
            List of document data dictionaries (copies)
        """
        with self._lock:
            return [dict(self.documents[doc_id]) for doc_id in doc_ids if doc_id in self.documents]

    def index_term(self, term: str, doc_id: str) -> None:
        """Add a term to the index for a document.

        Args:
            term: Search term to index
            doc_id: Document identifier containing this term
        """
        with self._lock:
            if term not in self.index:
                self.index[term] = []
            self.index[term].append(doc_id)

    def get_documents_for_term(self, term: str) -> List[str]:
        """Get all document IDs containing a term.

        Args:
            term: Search term to lookup

        Returns:
            List of document IDs (copy)
        """
        with self._lock:
            return list(self.index.get(term, []))

    def get_index_snapshot(self, terms: List[str]) -> Dict[str, List[str]]:
        """Get snapshot of index for multiple terms.

        This method creates a consistent snapshot of the index for the given terms,
        allowing query execution without holding locks.

        Args:
            terms: List of search terms

        Returns:
            Dictionary mapping terms to lists of document IDs
        """
        with self._lock:
            return {
                term: list(self.index.get(term, []))
                for term in terms
            }

    def replace_index(self, new_documents: Dict[str, Dict], new_index: Dict[str, List[str]]) -> None:
        """Atomically replace documents and index.

        This method provides an atomic swap operation for index rebuilding.

        Args:
            new_documents: New document collection
            new_index: New term index
        """
        with self._lock:
            self.documents = new_documents
            self.index = new_index
            self.stats['total_documents'] = len(self.documents)
            self.stats['total_terms'] = len(self.index)

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, min=RETRY_MIN_WAIT_SECONDS, max=RETRY_MAX_WAIT_SECONDS),
        retry=retry_if_exception_type((OSError, IOError)),
        reraise=True
    )
    def save_to_cache(self, cache_path: Path) -> None:
        """Save documents and index to cache file.

        Uses secure JSON format with atomic write (temp file + rename).
        Retries up to 3 times on I/O errors.

        Args:
            cache_path: Path to cache file

        Raises:
            IOError: If save fails after retries
        """
        try:
            with self._lock:
                cache_data = {
                    'documents': self.documents,
                    'index': self.index
                }

            # Ensure parent directory exists
            cache_path.parent.mkdir(parents=True, exist_ok=True)

            # Write to temp file first, then atomic rename
            temp_path = cache_path.with_suffix(CACHE_TEMP_SUFFIX)
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=JSON_INDENT, ensure_ascii=False)

            # Atomic rename
            temp_path.replace(cache_path)
            logger.info(f"Saved cache to {cache_path}")

        except Exception as e:
            logger.error(f"Failed to save cache: {e}", exc_info=True)
            raise

    def load_from_cache(self, cache_path: Path) -> bool:
        """Load documents and index from cache file.

        Args:
            cache_path: Path to cache file

        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)

            with self._lock:
                self.documents = cached_data['documents']
                self.index = cached_data['index']
                self.stats['total_documents'] = len(self.documents)
                self.stats['total_terms'] = len(self.index)

            logger.info(f"Loaded cache from {cache_path} - {self.stats['total_documents']} documents")
            return True

        except (json.JSONDecodeError, UnicodeDecodeError, KeyError) as e:
            logger.warning(f"Cache file invalid or corrupt: {e}")
            return False
        except FileNotFoundError:
            logger.debug(f"Cache file not found: {cache_path}")
            return False
        except Exception as e:
            logger.error(f"Failed to load cache: {e}", exc_info=True)
            return False

    def get_stats(self) -> Dict:
        """Get repository statistics.

        Returns:
            Dictionary with document and index statistics
        """
        with self._lock:
            return {
                'documents': len(self.documents),
                'terms': len(self.index),
                'total_documents': self.stats['total_documents'],
                'total_terms': self.stats['total_terms']
            }

    def clear(self) -> None:
        """Clear all documents and index data."""
        with self._lock:
            self.documents.clear()
            self.index.clear()
            self.stats['total_documents'] = 0
            self.stats['total_terms'] = 0

    def document_count(self) -> int:
        """Get total number of documents.

        Returns:
            Number of documents in repository
        """
        with self._lock:
            return len(self.documents)

    def term_count(self) -> int:
        """Get total number of indexed terms.

        Returns:
            Number of terms in index
        """
        with self._lock:
            return len(self.index)
