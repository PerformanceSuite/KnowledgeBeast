"""Chunk pipeline orchestrator for KnowledgeBeast."""

import time
from typing import List, Dict, Any, Optional
from pathlib import Path

from knowledgebeast.core.chunking.base import BaseChunker, Chunk
from knowledgebeast.core.chunking.semantic import SemanticChunker
from knowledgebeast.core.chunking.recursive import RecursiveCharacterChunker
from knowledgebeast.core.chunking.markdown import MarkdownAwareChunker
from knowledgebeast.core.chunking.code import CodeAwareChunker

try:
    from knowledgebeast.utils.metrics import (
        CHUNKING_DURATION,
        CHUNKS_CREATED_TOTAL,
        CHUNK_SIZE_BYTES,
        CHUNK_OVERLAP_RATIO
    )
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False


class ChunkProcessor:
    """Pipeline orchestrator for chunking documents.

    This processor:
    1. Selects appropriate chunking strategy based on content type
    2. Applies chunking with configured parameters
    3. Enriches chunks with metadata
    4. Tracks metrics for observability
    5. Supports batch processing

    Attributes:
        config: Chunking configuration
        chunkers: Dictionary of available chunkers by strategy name
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize chunk processor.

        Args:
            config: Configuration dictionary with:
                - strategy: str (semantic, recursive, markdown, code, auto)
                - chunk_size: int
                - chunk_overlap: int
                - semantic_similarity_threshold: float
                - respect_markdown_structure: bool
                - preserve_code_blocks: bool
        """
        self.config = config or {}
        self.default_strategy = self.config.get('strategy', 'auto')

        # Initialize chunkers
        self.chunkers = self._init_chunkers()

        # Stats
        self.stats = {
            'total_chunks': 0,
            'total_documents': 0,
            'total_bytes': 0,
            'strategy_usage': {}
        }

    def _init_chunkers(self) -> Dict[str, BaseChunker]:
        """Initialize all chunker instances.

        Returns:
            Dictionary of chunker name to instance
        """
        chunkers = {}

        # Semantic chunker
        semantic_config = {
            'similarity_threshold': self.config.get('semantic_similarity_threshold', 0.7),
            'min_chunk_size': 2,
            'max_chunk_size': 10
        }
        chunkers['semantic'] = SemanticChunker(semantic_config)

        # Recursive character chunker
        recursive_config = {
            'chunk_size': self.config.get('chunk_size', 512),
            'chunk_overlap': self.config.get('chunk_overlap', 128)
        }
        chunkers['recursive'] = RecursiveCharacterChunker(recursive_config)

        # Markdown-aware chunker
        markdown_config = {
            'max_chunk_size': self.config.get('chunk_size', 2000),
            'preserve_headers': self.config.get('respect_markdown_structure', True)
        }
        chunkers['markdown'] = MarkdownAwareChunker(markdown_config)

        # Code-aware chunker
        code_config = {
            'max_chunk_size': 100,
            'preserve_imports': self.config.get('preserve_code_blocks', True)
        }
        chunkers['code'] = CodeAwareChunker(code_config)

        return chunkers

    def process(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        strategy: Optional[str] = None
    ) -> List[Chunk]:
        """Process text into chunks.

        Args:
            text: Text to chunk
            metadata: Document metadata
            strategy: Chunking strategy to use (overrides default)

        Returns:
            List of Chunk objects
        """
        if not text or not text.strip():
            return []

        metadata = metadata or {}
        strategy = strategy or self.default_strategy

        # Auto-select strategy if needed
        if strategy == 'auto':
            strategy = self._select_strategy(text, metadata)

        # Get chunker
        chunker = self.chunkers.get(strategy)
        if not chunker:
            # Fallback to recursive chunker
            chunker = self.chunkers['recursive']
            strategy = 'recursive'

        # Track timing
        start_time = time.time()

        # Perform chunking
        chunks = chunker.chunk(text, metadata)

        # Enrich chunks with additional metadata
        chunks = self._enrich_chunks(chunks, strategy)

        # Record metrics
        duration = time.time() - start_time
        self._record_metrics(chunks, strategy, duration)

        # Update stats
        self._update_stats(chunks, strategy)

        return chunks

    def process_batch(
        self,
        documents: List[Dict[str, Any]],
        strategy: Optional[str] = None
    ) -> List[Chunk]:
        """Process multiple documents in batch.

        Args:
            documents: List of documents with 'text' and optional 'metadata'
            strategy: Chunking strategy to use (overrides default)

        Returns:
            List of all chunks from all documents
        """
        all_chunks = []

        for doc in documents:
            text = doc.get('text', '')
            metadata = doc.get('metadata', {})
            doc_strategy = doc.get('strategy', strategy)

            chunks = self.process(text, metadata, doc_strategy)
            all_chunks.extend(chunks)

        return all_chunks

    def _select_strategy(self, text: str, metadata: Dict[str, Any]) -> str:
        """Auto-select chunking strategy based on content.

        Args:
            text: Text content
            metadata: Document metadata

        Returns:
            Strategy name
        """
        # Check file type from metadata
        file_path = metadata.get('file_path', '')
        if file_path:
            file_path_lower = file_path.lower()

            # Code files
            code_extensions = ('.py', '.js', '.ts', '.java', '.cpp', '.go', '.rs', '.c', '.h')
            if any(file_path_lower.endswith(ext) for ext in code_extensions):
                return 'code'

            # Markdown files
            if file_path_lower.endswith('.md'):
                return 'markdown'

        # Heuristic detection based on content
        if text.startswith('#') or '```' in text or text.count('\n##') > 2:
            # Looks like markdown
            return 'markdown'

        if 'def ' in text or 'function ' in text or 'class ' in text:
            # Looks like code
            return 'code'

        # Check if text is long enough for semantic chunking
        sentence_count = text.count('.') + text.count('!') + text.count('?')
        if sentence_count >= 5:
            # Use semantic chunking for prose
            return 'semantic'

        # Default to recursive
        return 'recursive'

    def _enrich_chunks(self, chunks: List[Chunk], strategy: str) -> List[Chunk]:
        """Enrich chunks with additional metadata.

        Args:
            chunks: List of chunks
            strategy: Strategy used

        Returns:
            Enriched chunks
        """
        for chunk in chunks:
            # Add strategy info
            chunk.metadata['chunking_strategy'] = strategy

            # Add chunk size metrics
            chunk.metadata['char_count'] = len(chunk.text)
            chunk.metadata['word_count'] = len(chunk.text.split())

            # Calculate overlap ratio if applicable
            if chunk.metadata.get('chunk_index', 0) > 0:
                overlap = self.config.get('chunk_overlap', 0)
                chunk_size = self.config.get('chunk_size', 512)
                if chunk_size > 0:
                    chunk.metadata['overlap_ratio'] = overlap / chunk_size

        return chunks

    def _record_metrics(self, chunks: List[Chunk], strategy: str, duration: float):
        """Record Prometheus metrics.

        Args:
            chunks: List of chunks created
            strategy: Strategy used
            duration: Processing duration
        """
        if not METRICS_AVAILABLE:
            return

        # Record duration
        CHUNKING_DURATION.labels(strategy=strategy).observe(duration)

        # Record chunks created
        CHUNKS_CREATED_TOTAL.labels(strategy=strategy).inc(len(chunks))

        # Record chunk sizes
        for chunk in chunks:
            chunk_bytes = len(chunk.text.encode('utf-8'))
            CHUNK_SIZE_BYTES.labels(strategy=strategy).observe(chunk_bytes)

            # Record overlap ratio if present
            if 'overlap_ratio' in chunk.metadata:
                CHUNK_OVERLAP_RATIO.labels(strategy=strategy).observe(
                    chunk.metadata['overlap_ratio']
                )

    def _update_stats(self, chunks: List[Chunk], strategy: str):
        """Update internal statistics.

        Args:
            chunks: List of chunks
            strategy: Strategy used
        """
        self.stats['total_chunks'] += len(chunks)
        self.stats['total_documents'] += 1

        for chunk in chunks:
            self.stats['total_bytes'] += len(chunk.text.encode('utf-8'))

        # Update strategy usage
        if strategy not in self.stats['strategy_usage']:
            self.stats['strategy_usage'][strategy] = 0
        self.stats['strategy_usage'][strategy] += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics.

        Returns:
            Dictionary with processor stats
        """
        return {
            **self.stats,
            'config': self.config,
            'available_strategies': list(self.chunkers.keys())
        }

    def reset_stats(self):
        """Reset statistics."""
        self.stats = {
            'total_chunks': 0,
            'total_documents': 0,
            'total_bytes': 0,
            'strategy_usage': {}
        }
