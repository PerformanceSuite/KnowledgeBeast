"""Document Indexer - Handles document ingestion and index building.

This module is responsible for discovering documents, converting them,
and building the search index with parallel processing support.
"""

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from knowledgebeast.core.repository import DocumentRepository
from knowledgebeast.core.config import KnowledgeBeastConfig
from knowledgebeast.core.constants import (
    MAX_RETRY_ATTEMPTS,
    RETRY_MIN_WAIT_SECONDS,
    RETRY_MAX_WAIT_SECONDS,
    RETRY_MULTIPLIER,
)

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
            """Simple markdown reader fallback."""
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


class DocumentIndexer:
    """Indexer for document discovery, conversion, and index building.

    This class handles the entire document ingestion pipeline:
    - Document discovery across multiple directories
    - Parallel document conversion with retry logic
    - Index building with word tokenization
    - Progress reporting for long operations

    Thread Safety:
        - Document conversion happens in parallel workers
        - Results are merged after all workers complete
        - Final index update is atomic (delegated to repository)

    Attributes:
        config: Configuration object
        repository: Document repository for storage
        converter: Document converter instance
        progress_callback: Optional callback for progress updates
    """

    def __init__(
        self,
        config: KnowledgeBeastConfig,
        repository: DocumentRepository,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> None:
        """Initialize document indexer.

        Args:
            config: Configuration object
            repository: Document repository instance
            progress_callback: Optional callback for progress updates
                              Signature: callback(message: str, current: int, total: int)
        """
        self.config = config
        self.repository = repository
        self.converter = DocumentConverter()
        self.progress_callback = progress_callback if config.enable_progress_callbacks else None

    def ingest_all(self) -> None:
        """Ingest all documents from configured knowledge directories.

        Uses cached index if available and up-to-date.
        Auto-rebuilds if any source files are newer than cache.

        Raises:
            FileNotFoundError: If knowledge directories don't exist
            PermissionError: If cache file can't be read/written
        """
        cache_path = Path(self.config.cache_file)

        # Check if cache exists and is valid
        if cache_path.exists():
            cache_is_stale = self._is_cache_stale(cache_path)

            if not cache_is_stale:
                # Try to load from cache
                if self.repository.load_from_cache(cache_path):
                    logger.info(f"Loaded knowledge base from cache - {self.repository.document_count()} documents")
                    if self.config.verbose:
                        print("📚 Loaded knowledge base from cache (up-to-date)")
                        print(f"   - {self.repository.document_count()} documents indexed")
                        print(f"   - {self.repository.term_count()} unique terms\n")
                    return
                else:
                    # Cache load failed, rebuild
                    logger.warning("Cache load failed, rebuilding index")
                    if self.config.verbose:
                        print("🔄 Cache invalid, rebuilding index...")
            else:
                logger.info("Cache is stale, rebuilding index...")
                if self.config.verbose:
                    print("🔄 Cache is stale, rebuilding index...")

        # Build fresh index
        self._build_index()

        # Save cache for faster subsequent loads
        self.repository.save_to_cache(cache_path)

    def rebuild_index(self) -> None:
        """Force rebuild of the document index."""
        logger.info("Forcing index rebuild...")
        if self.config.verbose:
            print("🔄 Forcing index rebuild...")

        self._build_index()

        cache_path = Path(self.config.cache_file)
        self.repository.save_to_cache(cache_path)

    def _is_cache_stale(self, cache_path: Path) -> bool:
        """Check if cache is stale compared to source files.

        Args:
            cache_path: Path to cache file

        Returns:
            True if cache is stale, False otherwise
        """
        try:
            cache_mtime = cache_path.stat().st_mtime

            # Collect all markdown files from all directories
            all_md_files = self._discover_documents()

            # Check if any file is newer than cache
            for _, md_file in all_md_files:
                if md_file.stat().st_mtime > cache_mtime:
                    logger.debug(f"Cache is stale (newer file: {md_file.name})")
                    if self.config.verbose:
                        print(f"🔄 Cache is stale (newer file: {md_file.name})")
                    return True

            # Check if file count changed
            if self.repository.document_count() != len(all_md_files):
                logger.debug(f"Cache is stale (file count changed: {self.repository.document_count()} → {len(all_md_files)})")
                if self.config.verbose:
                    print(f"🔄 Cache is stale (file count changed: "
                          f"{self.repository.document_count()} → {len(all_md_files)})")
                return True

            return False

        except Exception as e:
            logger.error(f"Cache staleness check failed: {e}", exc_info=True)
            if self.config.verbose:
                print(f"⚠️  Cache staleness check failed: {e}")
            return True

    def _discover_documents(self) -> List[Tuple[Path, Path]]:
        """Discover all markdown files from configured directories.

        Returns:
            List of (kb_dir, md_file) tuples
        """
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

        return all_md_files

    def _build_index(self) -> None:
        """Build document index from all knowledge directories using parallel processing."""
        logger.info("Ingesting knowledge base...")
        if self.config.verbose:
            print("📚 Ingesting knowledge base...")

        # Discover all markdown files
        all_md_files = self._discover_documents()
        total_files = len(all_md_files)

        logger.info(f"Found {total_files} documents across {len(self.config.knowledge_dirs)} directories")
        if self.config.verbose:
            print(f"   Found {total_files} documents across {len(self.config.knowledge_dirs)} directories")
            print(f"   Using {self.config.max_workers} parallel workers")

        # Build new index in local variables (no locks needed during processing)
        new_documents = {}
        new_index = {}

        # Process documents in parallel
        processed_count = 0
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit all tasks
            future_to_file = {
                executor.submit(self._process_single_document, kb_dir, md_file): (kb_dir, md_file)
                for kb_dir, md_file in all_md_files
            }

            # Process completed tasks as they finish
            for future in as_completed(future_to_file):
                kb_dir, md_file = future_to_file[future]
                processed_count += 1

                self._report_progress(f"Ingesting {md_file.name}", processed_count, total_files)

                try:
                    result = future.result()
                    if result:
                        doc_id, document_data, word_index = result

                        # Add document to collection
                        new_documents[doc_id] = document_data

                        # Merge word index
                        for word, doc_ids in word_index.items():
                            if word not in new_index:
                                new_index[word] = []
                            new_index[word].extend(doc_ids)

                except Exception as e:
                    logger.error(f"Error processing future for {md_file}: {e}", exc_info=True)
                    if self.config.verbose:
                        print(f"   ❌ Error processing {md_file}: {e}")

        # Atomically replace repository contents
        self.repository.replace_index(new_documents, new_index)

        logger.info(f"Ingestion complete! {len(new_documents)} documents, {len(new_index)} terms")
        if self.config.verbose:
            print(f"\n✅ Ingestion complete!")
            print(f"   - {self.repository.document_count()} documents indexed")
            print(f"   - {self.repository.term_count()} unique terms\n")

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

    def _process_single_document(self, kb_dir: Path, md_file: Path) -> Optional[Tuple[str, Dict, Dict[str, List[str]]]]:
        """Process a single document and return its data and index.

        Args:
            kb_dir: Knowledge base directory
            md_file: Path to markdown file

        Returns:
            Tuple of (doc_id, document_data, word_index) or None if failed
        """
        try:
            result = self._convert_document_with_retry(md_file)
            if result.document:
                # Store document with relative path from its knowledge dir
                doc_id = str(md_file.relative_to(kb_dir.parent))
                document_data = {
                    'path': str(md_file),
                    'content': result.document.export_to_markdown(),
                    'name': result.document.name,
                    'kb_dir': str(kb_dir)
                }

                # Build word index for this document
                content_lower = document_data['content'].lower()
                words = content_lower.split()
                word_index = {}
                for word in set(words):
                    word_index[word] = [doc_id]

                logger.debug(f"Ingested: {doc_id}")
                if self.config.verbose:
                    print(f"   ✅ Ingested: {doc_id}")

                return (doc_id, document_data, word_index)

        except Exception as e:
            logger.error(f"Failed to ingest {md_file}: {e}", exc_info=True)
            if self.config.verbose:
                print(f"   ❌ Failed to ingest {md_file}: {e}")

        return None

    def _report_progress(self, message: str, current: int = 0, total: int = 0) -> None:
        """Report progress if callback is configured.

        Args:
            message: Progress message
            current: Current progress value
            total: Total progress value
        """
        if self.progress_callback:
            try:
                self.progress_callback(message, current, total)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")
                if self.config.verbose:
                    print(f"⚠️  Progress callback error: {e}")
