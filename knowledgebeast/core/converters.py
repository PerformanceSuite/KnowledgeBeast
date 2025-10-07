"""Document Converters - Handles document format conversion.

This module provides document conversion functionality with graceful
degradation when optional dependencies are not available.
"""

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ['DocumentConverter', 'FallbackConverter', 'get_document_converter', 'DOCLING_AVAILABLE']

# Graceful dependency degradation for docling
try:
    from docling.document_converter import DocumentConverter as DoclingConverter
    DOCLING_AVAILABLE = True
    logger.info("Docling document converter loaded successfully")
except ImportError:
    DOCLING_AVAILABLE = False
    DoclingConverter = None
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


def get_document_converter() -> Any:
    """Get the appropriate document converter.

    Returns the docling DocumentConverter if available,
    otherwise returns the FallbackConverter.

    Returns:
        DocumentConverter instance (either DoclingConverter or FallbackConverter)
    """
    if DOCLING_AVAILABLE and DoclingConverter is not None:
        return DoclingConverter()
    else:
        return FallbackConverter()


# Export for backward compatibility
DocumentConverter = DoclingConverter if DOCLING_AVAILABLE else FallbackConverter
