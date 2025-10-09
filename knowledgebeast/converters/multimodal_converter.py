"""Unified multimodal document converter.

This module provides a unified interface for converting all supported
document types: PDFs, images, code files, and text documents.
"""

import logging
from pathlib import Path
from typing import Any, Optional
from types import SimpleNamespace

from .pdf_converter import PDFConverter
from .image_converter import ImageConverter
from .code_converter import CodeConverter
from ..core.converters import DoclingConverter, FallbackConverter, DOCLING_AVAILABLE

logger = logging.getLogger(__name__)


class MultiModalConverter:
    """Unified converter for all document types.

    This converter automatically detects file type and routes to the
    appropriate specialized converter.

    Thread Safety:
        - Stateless converter, safe for concurrent use
        - Each convert() call is independent
        - Delegates thread safety to specialized converters

    Attributes:
        pdf_converter: Converter for PDF files
        image_converter: Converter for image files
        code_converter: Converter for code files
        text_converter: Converter for text/markdown files
        chunk_size: Default chunk size for all converters
        chunk_overlap: Default chunk overlap for all converters
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        use_clip: bool = True,
        use_ocr: bool = False,
        extract_images_from_pdf: bool = False
    ):
        """Initialize MultiModalConverter.

        Args:
            chunk_size: Default chunk size for text chunking
            chunk_overlap: Default overlap between chunks
            use_clip: Whether to use CLIP for image embeddings
            use_ocr: Whether to use OCR for text extraction
            extract_images_from_pdf: Whether to extract images from PDFs

        Raises:
            RuntimeError: If no converters are available
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Initialize specialized converters
        try:
            self.pdf_converter = PDFConverter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                extract_images=extract_images_from_pdf,
                use_ocr=use_ocr
            )
            logger.info("PDF converter initialized")
        except Exception as e:
            logger.warning(f"PDF converter not available: {e}")
            self.pdf_converter = None

        try:
            self.image_converter = ImageConverter(
                use_clip=use_clip,
                use_ocr=use_ocr
            )
            logger.info("Image converter initialized")
        except Exception as e:
            logger.warning(f"Image converter not available: {e}")
            self.image_converter = None

        try:
            self.code_converter = CodeConverter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
            logger.info("Code converter initialized")
        except Exception as e:
            logger.warning(f"Code converter not available: {e}")
            self.code_converter = None

        # Initialize text converter (Docling or fallback)
        try:
            if DOCLING_AVAILABLE:
                self.text_converter = DoclingConverter(
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap
                )
                logger.info("Docling text converter initialized")
            else:
                self.text_converter = FallbackConverter()
                logger.info("Fallback text converter initialized")
        except Exception as e:
            logger.warning(f"Text converter not available: {e}")
            self.text_converter = FallbackConverter()

        # Build supported formats map
        self.format_map = {}

        if self.pdf_converter:
            for fmt in self.pdf_converter.SUPPORTED_FORMATS:
                self.format_map[fmt] = 'pdf'

        if self.image_converter:
            for fmt in self.image_converter.SUPPORTED_FORMATS:
                self.format_map[fmt] = 'image'

        if self.code_converter:
            for fmt in self.code_converter.SUPPORTED_FORMATS:
                self.format_map[fmt] = 'code'

        # Text formats
        text_formats = {'.md', '.txt', '.doc', '.docx', '.html', '.pptx'}
        for fmt in text_formats:
            if fmt not in self.format_map:
                self.format_map[fmt] = 'text'

    def detect_file_type(self, path: Path) -> str:
        """Detect file type from extension.

        Args:
            path: Path to file

        Returns:
            File type: 'pdf', 'image', 'code', 'text', or 'unknown'
        """
        suffix = path.suffix.lower()
        return self.format_map.get(suffix, 'unknown')

    def is_supported(self, path: Path) -> bool:
        """Check if file format is supported.

        Args:
            path: Path to file

        Returns:
            True if format is supported, False otherwise
        """
        return self.detect_file_type(path) != 'unknown'

    def get_supported_formats(self) -> dict:
        """Get all supported file formats grouped by type.

        Returns:
            Dictionary mapping file type to list of extensions
        """
        formats = {
            'pdf': [],
            'image': [],
            'code': [],
            'text': [],
        }

        for ext, file_type in self.format_map.items():
            formats[file_type].append(ext)

        return formats

    def convert(self, path: Path, enable_chunking: bool = True) -> SimpleNamespace:
        """Convert document using appropriate converter.

        Args:
            path: Path to document file
            enable_chunking: Whether to split into chunks

        Returns:
            SimpleNamespace with conversion results (structure varies by type)

        Raises:
            ValueError: If file format is not supported
            FileNotFoundError: If file does not exist
            RuntimeError: If conversion fails
        """
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        file_type = self.detect_file_type(path)

        if file_type == 'unknown':
            raise ValueError(
                f"Unsupported file format: {path.suffix}. "
                f"Use get_supported_formats() to see supported formats."
            )

        try:
            if file_type == 'pdf':
                if not self.pdf_converter:
                    raise RuntimeError("PDF converter not available")
                logger.info(f"Converting PDF: {path.name}")
                return self.pdf_converter.convert(path, enable_chunking)

            elif file_type == 'image':
                if not self.image_converter:
                    raise RuntimeError("Image converter not available")
                logger.info(f"Converting image: {path.name}")
                return self.image_converter.convert(path, enable_chunking)

            elif file_type == 'code':
                if not self.code_converter:
                    raise RuntimeError("Code converter not available")
                logger.info(f"Converting code: {path.name}")
                return self.code_converter.convert(path, enable_chunking)

            elif file_type == 'text':
                logger.info(f"Converting text document: {path.name}")
                return self.text_converter.convert(path, enable_chunking)

            else:
                raise ValueError(f"Unknown file type: {file_type}")

        except Exception as e:
            logger.error(f"Conversion failed for {path}: {e}")
            raise

    def convert_with_metadata(self, path: Path, enable_chunking: bool = True) -> dict:
        """Convert document and return enhanced result with file type info.

        Args:
            path: Path to document file
            enable_chunking: Whether to split into chunks

        Returns:
            Dictionary with:
                - result: Conversion result (SimpleNamespace)
                - file_type: Detected file type ('pdf', 'image', 'code', 'text')
                - converter: Name of converter used
        """
        file_type = self.detect_file_type(path)
        result = self.convert(path, enable_chunking)

        converter_name = {
            'pdf': 'PDFConverter',
            'image': 'ImageConverter',
            'code': 'CodeConverter',
            'text': 'DoclingConverter' if DOCLING_AVAILABLE else 'FallbackConverter',
        }.get(file_type, 'UnknownConverter')

        return {
            'result': result,
            'file_type': file_type,
            'converter': converter_name,
        }

    def get_converter_info(self) -> dict:
        """Get information about available converters.

        Returns:
            Dictionary with converter availability and configuration
        """
        return {
            'pdf_available': self.pdf_converter is not None,
            'image_available': self.image_converter is not None,
            'code_available': self.code_converter is not None,
            'text_available': self.text_converter is not None,
            'docling_available': DOCLING_AVAILABLE,
            'chunk_size': self.chunk_size,
            'chunk_overlap': self.chunk_overlap,
            'supported_formats': self.get_supported_formats(),
        }
