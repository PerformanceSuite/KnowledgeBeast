"""PDF document converter with text extraction, OCR, and metadata support.

This module provides PDF processing with:
- Text extraction using PyPDF2 and pdfplumber
- Layout-aware extraction (columns, tables)
- Image extraction from PDFs
- OCR for scanned PDFs using Tesseract
- Metadata extraction (author, title, dates)
"""

import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from types import SimpleNamespace

logger = logging.getLogger(__name__)

# Graceful dependency degradation for PDF libraries
try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    logger.warning("PyPDF2 not available - PDF text extraction disabled")

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    logger.warning("pdfplumber not available - advanced PDF features disabled")

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    logger.warning("Pillow not available - image extraction from PDFs disabled")


class PDFConverter:
    """PDF document converter with multi-strategy extraction.

    This converter provides comprehensive PDF processing with graceful
    degradation when optional dependencies are unavailable.

    Thread Safety:
        - Stateless converter, safe for concurrent use
        - Each convert() call is independent
        - No shared mutable state

    Attributes:
        chunk_size: Maximum chunk size in characters (default: 1000)
        chunk_overlap: Overlap between chunks in characters (default: 200)
        extract_images: Whether to extract images from PDFs (default: False)
        use_ocr: Whether to use OCR for scanned PDFs (default: False)
    """

    SUPPORTED_FORMATS = {'.pdf'}

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        extract_images: bool = False,
        use_ocr: bool = False
    ):
        """Initialize PDFConverter.

        Args:
            chunk_size: Maximum size of each chunk in characters
            chunk_overlap: Number of characters to overlap between chunks
            extract_images: Whether to extract images from PDFs
            use_ocr: Whether to use OCR for text extraction

        Raises:
            RuntimeError: If no PDF libraries are available
        """
        if not PYPDF2_AVAILABLE and not PDFPLUMBER_AVAILABLE:
            raise RuntimeError(
                "No PDF libraries available. Install with: "
                "pip install PyPDF2>=3.0.0 pdfplumber>=0.10.0"
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.extract_images = extract_images
        self.use_ocr = use_ocr

        # Import OCR engine if needed
        self.ocr_engine = None
        if use_ocr:
            try:
                from ..core.multimodal.ocr_engine import OCREngine
                self.ocr_engine = OCREngine()
            except Exception as e:
                logger.warning(f"OCR engine not available: {e}")

    def is_supported(self, path: Path) -> bool:
        """Check if file format is supported.

        Args:
            path: Path to file

        Returns:
            True if format is supported, False otherwise
        """
        return path.suffix.lower() in self.SUPPORTED_FORMATS

    def extract_metadata(self, path: Path) -> Dict[str, Any]:
        """Extract metadata from PDF.

        Args:
            path: Path to PDF file

        Returns:
            Dictionary containing metadata (title, author, dates, etc.)
        """
        metadata = {
            'filename': path.name,
            'format': 'pdf',
            'size_bytes': path.stat().st_size if path.exists() else 0,
            'modality': 'document',
            'document_type': 'pdf',
        }

        try:
            # File system metadata
            stat = path.stat()
            metadata['created'] = datetime.fromtimestamp(stat.st_ctime).isoformat()
            metadata['modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
        except Exception as e:
            logger.warning(f"Could not extract file metadata: {e}")

        # Extract PDF-specific metadata
        if PYPDF2_AVAILABLE:
            try:
                with open(path, 'rb') as f:
                    pdf_reader = PyPDF2.PdfReader(f)

                    # Page count
                    metadata['page_count'] = len(pdf_reader.pages)

                    # Document info
                    if pdf_reader.metadata:
                        info = pdf_reader.metadata
                        metadata['title'] = info.get('/Title', path.stem)
                        metadata['author'] = info.get('/Author', 'Unknown')
                        metadata['subject'] = info.get('/Subject', '')
                        metadata['creator'] = info.get('/Creator', '')
                        metadata['producer'] = info.get('/Producer', '')

                        # Parse creation/modification dates
                        if '/CreationDate' in info:
                            metadata['pdf_creation_date'] = str(info['/CreationDate'])
                        if '/ModDate' in info:
                            metadata['pdf_mod_date'] = str(info['/ModDate'])
                    else:
                        metadata['title'] = path.stem
                        metadata['author'] = 'Unknown'
            except Exception as e:
                logger.warning(f"Could not extract PDF metadata: {e}")
                metadata['title'] = path.stem
                metadata['author'] = 'Unknown'
                metadata['page_count'] = 0
        else:
            metadata['title'] = path.stem
            metadata['author'] = 'Unknown'
            metadata['page_count'] = 0

        return metadata

    def extract_text_pypdf2(self, path: Path) -> Tuple[str, List[Dict[str, Any]]]:
        """Extract text using PyPDF2.

        Args:
            path: Path to PDF file

        Returns:
            Tuple of (full_text, pages_data)
        """
        pages_data = []
        full_text = []

        with open(path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)

            for page_num, page in enumerate(pdf_reader.pages, 1):
                try:
                    text = page.extract_text()

                    if text.strip():
                        pages_data.append({
                            'page_number': page_num,
                            'text': text,
                            'char_count': len(text),
                        })
                        full_text.append(f"[Page {page_num}]\n{text}")
                except Exception as e:
                    logger.warning(f"Could not extract text from page {page_num}: {e}")

        return '\n\n'.join(full_text), pages_data

    def extract_text_pdfplumber(self, path: Path) -> Tuple[str, List[Dict[str, Any]]]:
        """Extract text using pdfplumber with layout awareness.

        Args:
            path: Path to PDF file

        Returns:
            Tuple of (full_text, pages_data)
        """
        pages_data = []
        full_text = []

        with pdfplumber.open(path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                try:
                    # Extract text with layout
                    text = page.extract_text()

                    # Extract tables
                    tables = page.extract_tables()

                    page_info = {
                        'page_number': page_num,
                        'text': text or '',
                        'char_count': len(text) if text else 0,
                        'table_count': len(tables),
                    }

                    # Format tables as markdown
                    if tables:
                        table_texts = []
                        for table_idx, table in enumerate(tables):
                            if table:
                                # Convert table to markdown
                                table_md = self._table_to_markdown(table)
                                table_texts.append(f"[Table {table_idx + 1}]\n{table_md}")

                        page_info['tables'] = table_texts

                    if text or tables:
                        pages_data.append(page_info)

                        # Build page text
                        page_text = f"[Page {page_num}]"
                        if text:
                            page_text += f"\n{text}"
                        if tables:
                            page_text += "\n\n" + "\n\n".join(page_info.get('tables', []))

                        full_text.append(page_text)

                except Exception as e:
                    logger.warning(f"Could not extract from page {page_num}: {e}")

        return '\n\n'.join(full_text), pages_data

    def _table_to_markdown(self, table: List[List[str]]) -> str:
        """Convert table to markdown format.

        Args:
            table: 2D list of table cells

        Returns:
            Markdown formatted table
        """
        if not table or not table[0]:
            return ""

        lines = []

        # Header row
        header = [str(cell or '') for cell in table[0]]
        lines.append('| ' + ' | '.join(header) + ' |')

        # Separator
        lines.append('|' + '|'.join(['---'] * len(header)) + '|')

        # Data rows
        for row in table[1:]:
            if row:
                cells = [str(cell or '') for cell in row]
                # Pad row if needed
                while len(cells) < len(header):
                    cells.append('')
                lines.append('| ' + ' | '.join(cells[:len(header)]) + ' |')

        return '\n'.join(lines)

    def extract_images(self, path: Path) -> List[Dict[str, Any]]:
        """Extract images from PDF.

        Args:
            path: Path to PDF file

        Returns:
            List of image metadata dictionaries
        """
        if not PYPDF2_AVAILABLE or not PILLOW_AVAILABLE:
            logger.warning("Image extraction requires PyPDF2 and Pillow")
            return []

        images = []

        try:
            with open(path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)

                for page_num, page in enumerate(pdf_reader.pages, 1):
                    try:
                        if '/XObject' in page['/Resources']:
                            xobjects = page['/Resources']['/XObject'].get_object()

                            for obj_name in xobjects:
                                obj = xobjects[obj_name]

                                if obj['/Subtype'] == '/Image':
                                    images.append({
                                        'page': page_num,
                                        'name': obj_name,
                                        'width': obj['/Width'],
                                        'height': obj['/Height'],
                                    })
                    except Exception as e:
                        logger.debug(f"Could not extract images from page {page_num}: {e}")
        except Exception as e:
            logger.warning(f"Image extraction failed: {e}")

        return images

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

            # Try to break at sentence/paragraph boundary
            if end < len(text):
                for i in range(end, max(start, end - 100), -1):
                    if text[i] in '.!?\n':
                        end = i + 1
                        break

            end = min(end, len(text))
            chunk_text = text[start:end].strip()

            if chunk_text:
                chunk_data = {
                    'text': chunk_text,
                    'chunk_index': chunk_index,
                    'start_pos': start,
                    'end_pos': end,
                    'modality': 'text',
                }

                if metadata:
                    chunk_data['metadata'] = metadata.copy()

                chunks.append(chunk_data)
                chunk_index += 1

            # Move start with overlap
            start = end - self.chunk_overlap

            # Ensure progress
            if chunks and start <= chunks[-1]['start_pos']:
                start = end

        return chunks

    def convert(self, path: Path, enable_chunking: bool = True) -> SimpleNamespace:
        """Convert PDF to text with optional chunking and image extraction.

        Args:
            path: Path to PDF file
            enable_chunking: Whether to split into chunks (default: True)

        Returns:
            SimpleNamespace with:
                - document: SimpleNamespace with name and export_to_markdown method
                - chunks: List of text chunks (if enable_chunking=True)
                - metadata: Document metadata
                - pages: List of page-level data
                - images: List of extracted images (if extract_images=True)

        Raises:
            ValueError: If file format is not supported
            FileNotFoundError: If file does not exist
            RuntimeError: If conversion fails
        """
        if not self.is_supported(path):
            raise ValueError(f"Unsupported format: {path.suffix}")

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        try:
            # Extract metadata
            metadata = self.extract_metadata(path)

            # Extract text - prefer pdfplumber for layout awareness
            if PDFPLUMBER_AVAILABLE:
                logger.debug(f"Using pdfplumber for {path.name}")
                full_text, pages_data = self.extract_text_pdfplumber(path)
            elif PYPDF2_AVAILABLE:
                logger.debug(f"Using PyPDF2 for {path.name}")
                full_text, pages_data = self.extract_text_pypdf2(path)
            else:
                raise RuntimeError("No PDF extraction library available")

            # OCR fallback for scanned PDFs
            if self.use_ocr and self.ocr_engine and not full_text.strip():
                logger.info(f"Text extraction failed, trying OCR for {path.name}")
                try:
                    ocr_result = self.ocr_engine.extract_from_pdf(path)
                    full_text = ocr_result.get('text', '')
                    pages_data = ocr_result.get('pages', [])
                except Exception as e:
                    logger.warning(f"OCR failed: {e}")

            # Extract images if requested
            images = []
            if self.extract_images:
                images = self.extract_images(path)
                metadata['image_count'] = len(images)

            # Create chunks
            chunks = []
            if enable_chunking and full_text:
                chunks = self.chunk_text(full_text, metadata)

            # Return result
            return SimpleNamespace(
                document=SimpleNamespace(
                    name=metadata['title'],
                    export_to_markdown=lambda: full_text
                ),
                chunks=chunks,
                metadata=metadata,
                pages=pages_data,
                images=images
            )

        except Exception as e:
            logger.error(f"PDF conversion failed for {path}: {e}")
            raise RuntimeError(f"PDF conversion failed: {e}") from e
