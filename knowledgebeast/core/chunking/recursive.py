"""Recursive character text splitter with markdown structure awareness."""

import re
from typing import List, Dict, Any, Optional
import tiktoken

from knowledgebeast.core.chunking.base import BaseChunker, Chunk


class RecursiveCharacterChunker(BaseChunker):
    """Recursive character splitter that respects markdown structure.

    This chunker:
    1. Respects markdown structure (headers, code blocks, lists)
    2. Uses configurable chunk size with token counting
    3. Provides overlap for context preservation
    4. Tries to split on natural boundaries (paragraphs, sentences)

    Attributes:
        chunk_size: Target chunk size in tokens
        chunk_overlap: Number of overlapping tokens between chunks
        separators: List of separators to try (in order)
        encoding: Tiktoken encoding for token counting
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize recursive character chunker.

        Args:
            config: Configuration dictionary with:
                - chunk_size: int (default: 512)
                - chunk_overlap: int (default: 128)
                - encoding_name: str (default: 'cl100k_base')
        """
        super().__init__(config)
        self.chunk_size = self.config.get('chunk_size', 512)
        self.chunk_overlap = self.config.get('chunk_overlap', 128)
        encoding_name = self.config.get('encoding_name', 'cl100k_base')

        # Validate config
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")

        # Auto-adjust overlap if it's >= chunk_size (e.g., when chunk_size is set small)
        if self.chunk_overlap >= self.chunk_size:
            # Set overlap to 25% of chunk_size (reasonable default)
            self.chunk_overlap = max(1, self.chunk_size // 4)

        # Initialize token encoding
        try:
            self.encoding = tiktoken.get_encoding(encoding_name)
        except Exception:
            # Fallback to simple character counting
            self.encoding = None

        # Separators in order of preference (markdown-aware)
        self.separators = [
            "\n\n\n",  # Multiple newlines (section breaks)
            "\n\n",    # Paragraph breaks
            "\n",      # Line breaks
            ". ",      # Sentence breaks
            "! ",      # Exclamation sentence breaks
            "? ",      # Question sentence breaks
            "; ",      # Semicolon breaks
            ", ",      # Comma breaks
            " ",       # Word breaks
            ""         # Character breaks (last resort)
        ]

    def chunk(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Chunk]:
        """Split text into chunks with overlap.

        Args:
            text: Input text to chunk
            metadata: Optional metadata (file_path, parent_doc_id, etc.)

        Returns:
            List of Chunk objects
        """
        if not text or not text.strip():
            return []

        metadata = metadata or {}
        parent_doc_id = metadata.get('parent_doc_id', 'unknown')

        # Preserve code blocks first
        text, code_blocks = self._extract_code_blocks(text)

        # Split text recursively
        splits = self._split_text_recursive(text, self.separators)

        # Merge splits into chunks with overlap
        chunks = self._merge_splits_with_overlap(
            splits, parent_doc_id, metadata
        )

        # Restore code blocks
        chunks = self._restore_code_blocks(chunks, code_blocks)

        return chunks

    def _extract_code_blocks(self, text: str) -> tuple[str, Dict[str, str]]:
        """Extract code blocks to preserve them during chunking.

        Args:
            text: Input text

        Returns:
            Tuple of (text with placeholders, dict of code blocks)
        """
        code_blocks = {}
        counter = 0

        def replace_code_block(match):
            nonlocal counter
            placeholder = f"__CODE_BLOCK_{counter}__"
            code_blocks[placeholder] = match.group(0)
            counter += 1
            return placeholder

        # Extract fenced code blocks (```...```)
        text = re.sub(
            r'```[\s\S]*?```',
            replace_code_block,
            text
        )

        # Extract inline code (`...`)
        text = re.sub(
            r'`[^`\n]+`',
            replace_code_block,
            text
        )

        return text, code_blocks

    def _restore_code_blocks(
        self,
        chunks: List[Chunk],
        code_blocks: Dict[str, str]
    ) -> List[Chunk]:
        """Restore code blocks in chunks.

        Args:
            chunks: List of chunks with placeholders
            code_blocks: Dictionary of code block placeholders

        Returns:
            List of chunks with restored code blocks
        """
        for chunk in chunks:
            for placeholder, code in code_blocks.items():
                chunk.text = chunk.text.replace(placeholder, code)
        return chunks

    def _split_text_recursive(
        self,
        text: str,
        separators: List[str]
    ) -> List[str]:
        """Recursively split text using separators.

        Args:
            text: Text to split
            separators: List of separators to try

        Returns:
            List of text splits
        """
        if not separators:
            return [text]

        separator = separators[0]
        remaining_separators = separators[1:]

        if separator == "":
            # Last resort: split by characters
            return list(text)

        # Split by current separator
        splits = text.split(separator)

        # Process each split
        final_splits = []
        for split in splits:
            token_count = self._count_tokens(split)

            if token_count <= self.chunk_size:
                # Split is small enough
                if split.strip():
                    final_splits.append(split)
            else:
                # Split is too large, recurse with next separator
                sub_splits = self._split_text_recursive(split, remaining_separators)
                final_splits.extend(sub_splits)

        return final_splits

    def _merge_splits_with_overlap(
        self,
        splits: List[str],
        parent_doc_id: str,
        metadata: Dict[str, Any]
    ) -> List[Chunk]:
        """Merge splits into chunks with overlap.

        Args:
            splits: List of text splits
            parent_doc_id: Parent document ID
            metadata: Base metadata

        Returns:
            List of Chunk objects
        """
        chunks = []
        current_chunk = []
        current_tokens = 0
        chunk_index = 0

        for split in splits:
            split_tokens = self._count_tokens(split)

            # Check if adding this split would exceed chunk size
            if current_tokens + split_tokens > self.chunk_size and current_chunk:
                # Create chunk from current splits
                chunk_text = ' '.join(current_chunk)
                chunk = self._create_chunk(
                    chunk_text, parent_doc_id, chunk_index, metadata
                )
                chunks.append(chunk)
                chunk_index += 1

                # Start new chunk with overlap
                overlap_splits = self._get_overlap_splits(
                    current_chunk, self.chunk_overlap
                )
                current_chunk = overlap_splits
                current_tokens = sum(self._count_tokens(s) for s in current_chunk)

            # Add split to current chunk
            current_chunk.append(split)
            current_tokens += split_tokens

        # Add final chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunk = self._create_chunk(
                chunk_text, parent_doc_id, chunk_index, metadata
            )
            chunks.append(chunk)

        # Update total_chunks in metadata
        for chunk in chunks:
            chunk.metadata['total_chunks'] = len(chunks)

        return chunks

    def _get_overlap_splits(self, splits: List[str], overlap_tokens: int) -> List[str]:
        """Get splits for overlap.

        Args:
            splits: Current chunk splits
            overlap_tokens: Number of tokens to overlap

        Returns:
            List of splits for overlap
        """
        if not splits or overlap_tokens <= 0:
            return []

        overlap_splits = []
        tokens_collected = 0

        # Collect splits from end until we have enough overlap
        for split in reversed(splits):
            split_tokens = self._count_tokens(split)
            overlap_splits.insert(0, split)
            tokens_collected += split_tokens

            if tokens_collected >= overlap_tokens:
                break

        return overlap_splits

    def _create_chunk(
        self,
        text: str,
        parent_doc_id: str,
        chunk_index: int,
        metadata: Dict[str, Any]
    ) -> Chunk:
        """Create chunk with metadata.

        Args:
            text: Chunk text
            parent_doc_id: Parent document ID
            chunk_index: Index of chunk
            metadata: Base metadata

        Returns:
            Chunk object
        """
        chunk_id = self._generate_chunk_id(parent_doc_id, chunk_index)
        token_count = self._count_tokens(text)

        return Chunk(
            chunk_id=chunk_id,
            text=text.strip(),
            metadata={
                **metadata,
                'chunk_index': chunk_index,
                'chunk_type': 'text',
                'token_count': token_count,
                'char_count': len(text)
            }
        )

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: Text to count

        Returns:
            Number of tokens
        """
        if self.encoding:
            try:
                return len(self.encoding.encode(text))
            except Exception:
                pass

        # Fallback: approximate with character count / 4
        return len(text) // 4

    def get_stats(self) -> Dict[str, Any]:
        """Get chunker statistics.

        Returns:
            Dictionary with chunker stats
        """
        return {
            **super().get_stats(),
            'chunk_size': self.chunk_size,
            'chunk_overlap': self.chunk_overlap,
            'has_encoding': self.encoding is not None
        }
