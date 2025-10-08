"""Document Converters - Handles document format conversion.

This module provides document conversion functionality with graceful
degradation when optional dependencies are not available.
"""

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from datetime import datetime
import os

logger = logging.getLogger(__name__)

__all__ = ['DocumentConverter', 'FallbackConverter', 'DoclingConverter', 'get_document_converter', 'DOCLING_AVAILABLE']

# Graceful dependency degradation for docling
try:
    from docling.document_converter import DocumentConverter as BaseDoclingConverter
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    DOCLING_AVAILABLE = True
    logger.info("Docling document converter loaded successfully")
except ImportError:
    DOCLING_AVAILABLE = False
    BaseDoclingConverter = None
    InputFormat = None
    PdfPipelineOptions = None
    logger.warning("Docling not available, using fallback converter")


class FallbackConverter:
    """Fallback converter for when docling is not available.

    This converter provides basic markdown reading functionality
    as a graceful degradation when the docling library is not installed.

    Thread Safety:
        - Stateless converter, safe for concurrent use
        - Each convert() call is independent

    Attributes:
        None - stateless converter
    """

    def convert(self, path: Path) -> SimpleNamespace:
        """Simple markdown reader fallback.

        Args:
            path: Path to markdown file

        Returns:
            SimpleNamespace with document attribute containing name and content

        Raises:
            IOError: If file cannot be read
            UnicodeDecodeError: If file encoding is invalid
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            return SimpleNamespace(
                document=SimpleNamespace(
                    name=path.stem,
                    export_to_markdown=lambda: content
                )
            )
        except Exception as e:
            logger.error(f"Fallback converter failed for {path}: {e}")
            raise


class DoclingConverter:
    """Multi-format document converter using Docling.

    Supports PDF, DOCX, DOC, MD, TXT, HTML, PPTX with smart chunking
    and metadata extraction.

    Thread Safety:
        - Stateless converter, safe for concurrent use
        - Each convert() call is independent

    Attributes:
        chunk_size: Maximum chunk size in characters (default: 1000)
        chunk_overlap: Overlap between chunks in characters (default: 200)
        supported_formats: Set of supported file extensions
    """

    # Formats natively supported by Docling and plain text
    SUPPORTED_FORMATS = {'.pdf', '.docx', '.doc', '.md', '.html', '.pptx', '.txt'}
    # Plain text formats that need special handling
    TEXT_FORMATS = {'.txt', '.md'}

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """Initialize DoclingConverter.

        Args:
            chunk_size: Maximum size of each chunk in characters
            chunk_overlap: Number of characters to overlap between chunks

        Raises:
            RuntimeError: If docling is not available
        """
        if not DOCLING_AVAILABLE:
            raise RuntimeError("Docling is not available. Install with: pip install docling>=2.5.5")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.supported_formats = self.SUPPORTED_FORMATS
        self._base_converter = BaseDoclingConverter()

    def is_supported(self, path: Path) -> bool:
        """Check if file format is supported.

        Args:
            path: Path to file

        Returns:
            True if format is supported, False otherwise
        """
        return path.suffix.lower() in self.SUPPORTED_FORMATS

    def extract_metadata(self, path: Path) -> Dict[str, Any]:
        """Extract metadata from file.

        Args:
            path: Path to file

        Returns:
            Dictionary containing metadata (title, author, dates, etc.)
        """
        metadata = {
            'filename': path.name,
            'format': path.suffix.lower(),
            'size_bytes': path.stat().st_size if path.exists() else 0,
        }

        try:
            # File system metadata
            stat = path.stat()
            metadata['created'] = datetime.fromtimestamp(stat.st_ctime).isoformat()
            metadata['modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
        except Exception as e:
            logger.warning(f"Could not extract file metadata: {e}")

        # Title defaults to filename without extension
        metadata['title'] = path.stem
        metadata['author'] = 'Unknown'

        return metadata

    def chunk_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Split text into overlapping chunks.

        Args:
            text: Text to chunk
            metadata: Optional metadata to include with each chunk

        Returns:
            List of chunks, each containing text and metadata
        """
        if not text:
            return []

        chunks = []
        start = 0
        chunk_index = 0

        while start < len(text):
            # Calculate end position for this chunk
            end = min(start + self.chunk_size, len(text))

            # If this isn't the last chunk and we're not at the end
            if end < len(text):
                # Try to break at a sentence boundary (. ! ?)
                for i in range(end, max(start, end - 100), -1):
                    if text[i] in '.!?\n':
                        end = i + 1
                        break

            # Ensure end doesn't exceed text length
            end = min(end, len(text))

            chunk_text = text[start:end].strip()

            if chunk_text:
                chunk_data = {
                    'text': chunk_text,
                    'chunk_index': chunk_index,
                    'start_pos': start,
                    'end_pos': end,
                }

                if metadata:
                    chunk_data['metadata'] = metadata.copy()

                chunks.append(chunk_data)
                chunk_index += 1

            # Move start position with overlap
            start = end - self.chunk_overlap

            # Ensure we make progress even with small chunks
            if start <= chunks[-1]['start_pos'] if chunks else 0:
                start = end

        return chunks

    def convert(self, path: Path, enable_chunking: bool = True) -> SimpleNamespace:
        """Convert document to text with optional chunking.

        Args:
            path: Path to document file
            enable_chunking: Whether to split into chunks (default: True)

        Returns:
            SimpleNamespace with:
                - document: SimpleNamespace with name and export_to_markdown method
                - chunks: List of text chunks (if enable_chunking=True)
                - metadata: Document metadata

        Raises:
            ValueError: If file format is not supported
            RuntimeError: If conversion fails
        """
        if not self.is_supported(path):
            raise ValueError(
                f"Unsupported format: {path.suffix}. "
                f"Supported formats: {', '.join(sorted(self.SUPPORTED_FORMATS))}"
            )

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        try:
            # Extract metadata
            metadata = self.extract_metadata(path)

            # Handle plain text files specially (Docling may not support them)
            if path.suffix.lower() in self.TEXT_FORMATS:
                try:
                    # Try Docling first
                    result = self._base_converter.convert(path)
                    content = result.document.export_to_markdown()
                    if hasattr(result.document, 'name'):
                        metadata['title'] = result.document.name
                except Exception as e:
                    # Fall back to direct text reading for .txt files
                    logger.debug(f"Docling conversion failed for {path.suffix}, using direct read: {e}")
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
            else:
                # Convert document using base docling converter
                result = self._base_converter.convert(path)
                content = result.document.export_to_markdown()

                # Update metadata with document info if available
                if hasattr(result.document, 'name'):
                    metadata['title'] = result.document.name

            # Create chunks if requested
            chunks = []
            if enable_chunking:
                chunks = self.chunk_text(content, metadata)

            # Return result in expected format
            return SimpleNamespace(
                document=SimpleNamespace(
                    name=metadata['title'],
                    export_to_markdown=lambda: content
                ),
                chunks=chunks,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"DoclingConverter failed for {path}: {e}")
            raise RuntimeError(f"Conversion failed: {e}") from e


def get_document_converter(use_docling: bool = True, chunk_size: int = 1000, chunk_overlap: int = 200) -> Any:
    """Get the appropriate document converter.

    Returns the DoclingConverter if available and requested,
    otherwise returns the FallbackConverter.

    Args:
        use_docling: Whether to use DoclingConverter if available (default: True)
        chunk_size: Chunk size for DoclingConverter (default: 1000)
        chunk_overlap: Chunk overlap for DoclingConverter (default: 200)

    Returns:
        DocumentConverter instance (either DoclingConverter or FallbackConverter)
    """
    if use_docling and DOCLING_AVAILABLE:
        return DoclingConverter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    else:
        return FallbackConverter()


# Export for backward compatibility
DocumentConverter = DoclingConverter if DOCLING_AVAILABLE else FallbackConverter
