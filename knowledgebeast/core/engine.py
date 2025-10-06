#!/usr/bin/env python3
"""
Enhanced Knowledge Base RAG Engine with Warming & Heartbeat
Ported and enhanced from Performia knowledge_rag_v2.py

Features:
- Automatic startup warming for reduced first-query latency
- Semantic query caching with LRU eviction
- Background heartbeat for continuous interaction
- Performance metrics and health monitoring
- Auto-cache invalidation on file changes
- Multi-directory knowledge base support
- Progress callbacks for long operations
- Enhanced error handling and recovery
"""

from pathlib import Path
import json
import pickle
import time
import hashlib
import threading
import logging
from typing import Dict, List, Tuple, Optional, Callable
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from knowledgebeast.core.config import KnowledgeBeastConfig
from knowledgebeast.core.cache import LRUCache
from knowledgebeast.core.constants import (
    MAX_RETRY_ATTEMPTS,
    RETRY_MIN_WAIT_SECONDS,
    RETRY_MAX_WAIT_SECONDS,
    RETRY_MULTIPLIER,
    CACHE_TEMP_SUFFIX,
    JSON_INDENT,
    ERR_EMPTY_SEARCH_TERMS
)

# Configure logging
logger = logging.getLogger(__name__)

# Graceful dependency degradation for docling
try:
    from docling.document_converter import DocumentConverter
    DOCLING_AVAILABLE = True
    logger.info("Docling document converter loaded successfully")
except ImportError:
    DOCLING_AVAILABLE = False
    logger.warning("Docling not available, using fallback converter")

    class FallbackConverter:
        """Fallback converter for when docling is not available."""

        def convert(self, path: Path):
            """Simple markdown reader fallback.

            Args:
                path: Path to markdown file

            Returns:
                SimpleNamespace with document structure
            """
            from types import SimpleNamespace

            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()

                return SimpleNamespace(
                    document=SimpleNamespace(
                        name=path.name,
                        export_to_markdown=lambda: content
                    )
                )
            except Exception as e:
                logger.error(f"Fallback converter failed for {path}: {e}")
                raise

    DocumentConverter = FallbackConverter


class KnowledgeBase:
    """
    RAG Knowledge Base with warming, caching, and performance optimization.

    Features:
    - Multi-directory knowledge base support
    - Automatic cache warming on startup
    - LRU query caching with configurable size
    - Stale cache detection and auto-rebuild
    - Progress callbacks for long operations
    - Thread-safe operation
    - Comprehensive error handling

    Usage:
        # With config object
        config = KnowledgeBeastConfig(
            knowledge_dirs=[Path("kb1"), Path("kb2")],
            auto_warm=True
        )
        kb = KnowledgeBase(config)
        results = kb.query("librosa best practices")
        stats = kb.get_stats()

        # With defaults
        kb = KnowledgeBase()
        results = kb.query("audio processing")
    """

    def __init__(
        self,
        config: Optional[KnowledgeBeastConfig] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ):
        """
        Initialize Knowledge Base with optional config and callbacks.

        Args:
            config: KnowledgeBeastConfig instance (uses defaults if None)
            progress_callback: Optional callback for progress updates
                              Signature: callback(message: str, current: int, total: int)
        """
        self.config = config or KnowledgeBeastConfig()
        self.progress_callback = progress_callback if config and config.enable_progress_callbacks else None

        # Thread safety lock (reentrant for nested operations)
        self._lock = threading.RLock()

        # Initialize components
        self.converter = DocumentConverter()
        self.documents: Dict = {}
        self.index: Dict = {}
        self.query_cache: LRUCache[str, List[Tuple[str, Dict]]] = LRUCache(
            capacity=self.config.max_cache_size
        )
        self.last_access = time.time()

        # Performance metrics
        self.stats = {
            'queries': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'warm_queries': 0,
            'last_warm_time': None,
            'total_documents': 0,
            'total_terms': 0
        }

        # Auto-warm if configured
        if self.config.auto_warm:
            self.warm_up()

    def _report_progress(self, message: str, current: int = 0, total: int = 0) -> None:
        """Report progress if callback is configured."""
        if self.progress_callback:
            try:
                self.progress_callback(message, current, total)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")
                if self.config.verbose:
                    print(f"⚠️  Progress callback error: {e}")

    def warm_up(self) -> None:
        """
        Pre-load and warm up the knowledge base.
        Executes common queries to populate cache and reduce first-query latency.
        """
        logger.info("Warming up knowledge base...")
        if self.config.verbose:
            print("🔥 Warming up knowledge base...")

        start = time.time()

        try:
            # Load documents and index
            self.ingest_all()

            # Pre-execute warming queries to populate cache
            total_queries = len(self.config.warming_queries)
            for i, query in enumerate(self.config.warming_queries, 1):
                self._report_progress(f"Warming query: {query[:50]}...", i, total_queries)
                try:
                    self.query(query, use_cache=True)  # Populate cache - FIXED!
                    self.stats['warm_queries'] += 1
                except Exception as e:
                    logger.warning(f"Warming query failed '{query}': {e}")
                    if self.config.verbose:
                        print(f"⚠️  Warming query failed '{query}': {e}")

            elapsed = time.time() - start
            self.stats['last_warm_time'] = elapsed

            logger.info(f"Knowledge base warmed in {elapsed:.2f}s - {len(self.documents)} documents, {len(self.index)} terms, {self.stats['warm_queries']} queries")
            if self.config.verbose:
                print(f"✅ Knowledge base warmed in {elapsed:.2f}s")
                print(f"   - {len(self.documents)} documents loaded")
                print(f"   - {len(self.index)} unique terms indexed")
                print(f"   - {self.stats['warm_queries']} warming queries executed\n")

        except Exception as e:
            logger.error(f"Warming failed: {e}", exc_info=True)
            if self.config.verbose:
                print(f"❌ Warming failed: {e}")
            raise

    def ingest_all(self) -> None:
        """
        Ingest all markdown files from all configured knowledge base directories.
        Uses cached index if available and up-to-date.
        Auto-rebuilds if any source files are newer than cache.

        Raises:
            FileNotFoundError: If knowledge directories don't exist
            PermissionError: If cache file can't be read/written
        """
        cache_path = Path(self.config.cache_file)

        # Check if cache exists and is valid
        if cache_path.exists():
            try:
                cache_is_stale = self._is_cache_stale(cache_path)

                if not cache_is_stale:
                    # Cache is valid, use it
                    cached_data = None
                    migrated = False

                    # Try JSON first (secure format)
                    try:
                        with open(cache_path, 'r', encoding='utf-8') as f:
                            cached_data = json.load(f)
                            logger.info("Loaded cache from JSON format")
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        # Legacy pickle file - migrate it
                        logger.warning("Detected legacy pickle cache, migrating to JSON")
                        if self.config.verbose:
                            print("🔄 Migrating legacy cache to secure JSON format...")

                        try:
                            with open(cache_path, 'rb') as f:
                                cached_data = pickle.load(f)
                            migrated = True
                        except Exception as pickle_error:
                            logger.error(f"Failed to load legacy pickle cache: {pickle_error}")
                            raise

                    if cached_data:
                        self.documents = cached_data['documents']
                        self.index = cached_data['index']

                        # If we migrated from pickle, save as JSON
                        if migrated:
                            try:
                                with open(cache_path, 'w', encoding='utf-8') as f:
                                    json.dump(cached_data, f, indent=2)
                                logger.info("Successfully migrated cache to JSON format")
                                if self.config.verbose:
                                    print("✅ Cache migrated to JSON format\n")
                            except Exception as save_error:
                                logger.error(f"Failed to save migrated cache: {save_error}")

                    self.stats['total_documents'] = len(self.documents)
                    self.stats['total_terms'] = len(self.index)

                    logger.info(f"Loaded knowledge base from cache - {len(self.documents)} documents, {len(self.index)} terms")
                    if self.config.verbose:
                        print("📚 Loaded knowledge base from cache (up-to-date)")
                        print(f"   - {len(self.documents)} documents indexed")
                        print(f"   - {len(self.index)} unique terms\n")
                    return
                else:
                    logger.info("Cache is stale, rebuilding index...")
                    if self.config.verbose:
                        print("   Rebuilding index...\n")

            except Exception as e:
                logger.error(f"Cache validation failed: {e}", exc_info=True)
                if self.config.verbose:
                    print(f"⚠️  Cache validation failed: {e}, re-ingesting...")

        # Build fresh index
        self._build_index()

        # Save cache for faster subsequent loads
        self._save_cache(cache_path)

    def _is_cache_stale(self, cache_path: Path) -> bool:
        """Check if cache is stale compared to source files."""
        try:
            cache_mtime = cache_path.stat().st_mtime

            # Collect all markdown files from all directories
            all_md_files = []
            for kb_dir in self.config.knowledge_dirs:
                if not kb_dir.exists():
                    if self.config.verbose:
                        print(f"⚠️  Knowledge directory not found: {kb_dir}")
                    continue

                md_files = list(kb_dir.rglob("*.md"))
                md_files = [f for f in md_files if not f.is_symlink()]
                all_md_files.extend(md_files)

            # Check if any file is newer than cache
            for md_file in all_md_files:
                if md_file.stat().st_mtime > cache_mtime:
                    logger.debug(f"Cache is stale (newer file: {md_file.name})")
                    if self.config.verbose:
                        print(f"🔄 Cache is stale (newer file: {md_file.name})")
                    return True

            # Check if file count changed
            cached_data = None

            # Try JSON first (secure format)
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Legacy pickle file
                try:
                    with open(cache_path, 'rb') as f:
                        cached_data = pickle.load(f)
                except Exception as pickle_error:
                    logger.error(f"Failed to load cache for staleness check: {pickle_error}")
                    return True

            if cached_data and len(cached_data['documents']) != len(all_md_files):
                logger.debug(f"Cache is stale (file count changed: {len(cached_data['documents'])} → {len(all_md_files)})")
                if self.config.verbose:
                    print(f"🔄 Cache is stale (file count changed: "
                          f"{len(cached_data['documents'])} → {len(all_md_files)})")
                return True

            return False

        except Exception as e:
            logger.error(f"Cache staleness check failed: {e}", exc_info=True)
            if self.config.verbose:
                print(f"⚠️  Cache staleness check failed: {e}")
            return True

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, min=RETRY_MIN_WAIT_SECONDS, max=RETRY_MAX_WAIT_SECONDS),
        retry=retry_if_exception_type((OSError, IOError)),
        reraise=True
    )
    def _convert_document_with_retry(self, path: Path):
        """Convert document with retry logic for I/O errors.

        Args:
            path: Path to document file

        Returns:
            Converted document result

        Raises:
            Exception: If conversion fails after retries
        """
        return self.converter.convert(path)

    def _build_index(self) -> None:
        """Build document index from all knowledge directories."""
        logger.info("Ingesting knowledge base...")
        if self.config.verbose:
            print("📚 Ingesting knowledge base...")

        # Collect all markdown files (can be done without lock - read-only)
        all_md_files = []
        for kb_dir in self.config.knowledge_dirs:
            if not kb_dir.exists():
                logger.warning(f"Skipping non-existent directory: {kb_dir}")
                if self.config.verbose:
                    print(f"⚠️  Skipping non-existent directory: {kb_dir}")
                continue

            md_files = list(kb_dir.rglob("*.md"))
            md_files = [f for f in md_files if not f.is_symlink()]
            all_md_files.extend([(kb_dir, f) for f in md_files])

        logger.info(f"Found {len(all_md_files)} documents across {len(self.config.knowledge_dirs)} directories")
        if self.config.verbose:
            print(f"   Found {len(all_md_files)} documents across {len(self.config.knowledge_dirs)} directories")

        # Build new index in local variables
        new_documents = {}
        new_index = {}

        # Process each file (document conversion can be parallel, indexing is local)
        for i, (kb_dir, md_file) in enumerate(all_md_files, 1):
            self._report_progress(f"Ingesting {md_file.name}", i, len(all_md_files))

            try:
                result = self._convert_document_with_retry(md_file)
                if result.document:
                    # Store document with relative path from its knowledge dir
                    doc_id = str(md_file.relative_to(kb_dir.parent))
                    new_documents[doc_id] = {
                        'path': str(md_file),
                        'content': result.document.export_to_markdown(),
                        'name': result.document.name,
                        'kb_dir': str(kb_dir)
                    }

                    # Build simple word index
                    content_lower = new_documents[doc_id]['content'].lower()
                    words = content_lower.split()
                    for word in set(words):
                        if word not in new_index:
                            new_index[word] = []
                        new_index[word].append(doc_id)

                    logger.debug(f"Ingested: {doc_id}")
                    if self.config.verbose:
                        print(f"   ✅ Ingested: {doc_id}")

            except Exception as e:
                logger.error(f"Failed to ingest {md_file}: {e}", exc_info=True)
                if self.config.verbose:
                    print(f"   ❌ Failed to ingest {md_file}: {e}")

        # Atomically replace shared state with lock
        with self._lock:
            self.documents = new_documents
            self.index = new_index
            self.stats['total_documents'] = len(self.documents)
            self.stats['total_terms'] = len(self.index)

        logger.info(f"Ingestion complete! {len(new_documents)} documents, {len(new_index)} terms")
        if self.config.verbose:
            print(f"\n✅ Ingestion complete!")
            print(f"   - {len(self.documents)} documents indexed")
            print(f"   - {len(self.index)} unique terms\n")

    @retry(
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MULTIPLIER, min=RETRY_MIN_WAIT_SECONDS, max=RETRY_MAX_WAIT_SECONDS),
        retry=retry_if_exception_type((OSError, IOError)),
        reraise=True
    )
    def _save_cache(self, cache_path: Path) -> None:
        """Save index to cache file using secure JSON format with retry logic.

        Retries up to 3 times with exponential backoff for I/O errors.
        """
        try:
            cache_data = {'documents': self.documents, 'index': self.index}
            # Ensure parent directory exists
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            # Write to temp file first, then atomic rename
            temp_path = cache_path.with_suffix(CACHE_TEMP_SUFFIX)
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=JSON_INDENT, ensure_ascii=False)
            # Atomic rename
            temp_path.replace(cache_path)
            logger.info(f"Saved cache to {cache_path}")
            if self.config.verbose:
                print(f"💾 Cached knowledge base to {cache_path}\n")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}", exc_info=True)
            raise

    def query(self, search_terms: str, use_cache: bool = True) -> List[Tuple[str, Dict]]:
        """
        Query the knowledge base for relevant documents with semantic caching.

        Args:
            search_terms: Search query string
            use_cache: If True, use cached results if available

        Returns:
            List of (doc_id, document) tuples sorted by relevance

        Raises:
            ValueError: If search_terms is empty
        """
        if not search_terms or not search_terms.strip():
            raise ValueError(ERR_EMPTY_SEARCH_TERMS)

        # Update stats (thread-safe with lock)
        with self._lock:
            self.stats['queries'] += 1
            self.last_access = time.time()

        # Generate cache key from query
        cache_key = self._generate_cache_key(search_terms)

        # Check cache (LRU cache is now thread-safe)
        if use_cache:
            cached_result = self.query_cache.get(cache_key)
            if cached_result is not None:
                with self._lock:
                    self.stats['cache_hits'] += 1
                return cached_result

        with self._lock:
            self.stats['cache_misses'] += 1

        # Execute query with minimal lock scope using snapshot pattern
        try:
            search_terms_list = search_terms.lower().split() if isinstance(search_terms, str) else search_terms

            # Create index snapshot with minimal lock time
            # This allows concurrent queries to proceed without blocking each other
            with self._lock:
                index_snapshot = {
                    term: list(self.index.get(term, []))
                    for term in search_terms_list
                }

            # Search WITHOUT holding lock - this is the performance optimization!
            # Multiple queries can now execute in parallel
            matches = {}
            for term, doc_ids in index_snapshot.items():
                for doc_id in doc_ids:
                    matches[doc_id] = matches.get(doc_id, 0) + 1

            # Sort by relevance (number of matching terms)
            sorted_matches = sorted(matches.items(), key=lambda x: x[1], reverse=True)

            # Get document data with single lock
            with self._lock:
                results = [(doc_id, dict(self.documents[doc_id]))
                           for doc_id, _ in sorted_matches]

            # Cache results (LRU cache is thread-safe)
            if use_cache:
                self.query_cache.put(cache_key, results)

            return results

        except Exception as e:
            logger.error(f"Query error: {e}", exc_info=True)
            raise

    def get_answer(self, question: str, max_content_length: int = 500) -> str:
        """
        Get answer to a specific question.

        Args:
            question: Question string
            max_content_length: Maximum content length to return

        Returns:
            Formatted answer with most relevant document content
        """
        try:
            results = self.query(question)

            if not results:
                return "❌ No relevant documentation found."

            # Return most relevant document
            doc_id, doc = results[0]
            content_preview = doc['content'][:max_content_length]
            if len(doc['content']) > max_content_length:
                content_preview += "..."

            return f"📄 **{doc['name']}** ({doc_id})\n\n{content_preview}"

        except Exception as e:
            return f"❌ Error getting answer: {e}"

    def _generate_cache_key(self, query: str) -> str:
        """
        Generate deterministic cache key from query.

        Args:
            query: Query string

        Returns:
            MD5 hash of normalized query
        """
        return hashlib.md5(query.lower().strip().encode()).hexdigest()

    def get_stats(self) -> Dict:
        """
        Return performance statistics.

        Returns:
            Dictionary with performance metrics
        """
        total_queries = self.stats['cache_hits'] + self.stats['cache_misses']
        hit_rate = (self.stats['cache_hits'] / total_queries * 100) if total_queries > 0 else 0

        return {
            **self.stats,
            'cache_hit_rate': f"{hit_rate:.1f}%",
            'total_queries': total_queries,
            'documents': len(self.documents),
            'terms': len(self.index),
            'cached_queries': len(self.query_cache),
            'last_access_age': f"{time.time() - self.last_access:.1f}s ago",
            'knowledge_dirs': [str(d) for d in self.config.knowledge_dirs]
        }

    def clear_cache(self) -> None:
        """Clear query cache (useful for testing or memory management)."""
        self.query_cache.clear()
        logger.info("Query cache cleared")
        if self.config.verbose:
            print("🧹 Query cache cleared")

    def rebuild_index(self) -> None:
        """Force rebuild of the document index."""
        logger.info("Forcing index rebuild...")
        if self.config.verbose:
            print("🔄 Forcing index rebuild...")
        self._build_index()
        cache_path = Path(self.config.cache_file)
        self._save_cache(cache_path)
        # Clear query cache as index has changed
        self.clear_cache()

    def __enter__(self) -> "KnowledgeBase":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - cleanup resources."""
        try:
            with self._lock:
                # Clear caches to free memory
                self.query_cache.clear()
                logger.info("Cleared query cache on exit")

                # Clear references to allow GC
                self.documents.clear()
                self.index.clear()
                logger.info("Cleared document index on exit")

                # Close converter if it has resources
                if hasattr(self.converter, 'close') and callable(self.converter.close):
                    self.converter.close()
                    logger.info("Closed document converter")

        except Exception as e:
            logger.error(f"Cleanup error in __exit__: {e}", exc_info=True)

        # Don't suppress exceptions from the with block
        return False
