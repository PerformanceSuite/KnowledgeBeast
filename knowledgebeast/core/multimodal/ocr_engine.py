"""OCR engine for text extraction from images and scanned PDFs.

This module provides OCR functionality using Tesseract with:
- Text extraction from images
- Multi-language support
- Confidence scoring
- Quality filtering
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Graceful dependency degradation
try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
    logger.info("Tesseract OCR engine available")
except ImportError:
    TESSERACT_AVAILABLE = False
    pytesseract = None
    Image = None
    logger.warning("Tesseract not available - OCR disabled")

try:
    import PyPDF2
    from pdf2image import convert_from_path
    PDF_TO_IMAGE_AVAILABLE = True
except ImportError:
    PDF_TO_IMAGE_AVAILABLE = False
    logger.warning("pdf2image not available - PDF OCR disabled")


class OCREngine:
    """OCR engine using Tesseract for text extraction.

    Thread Safety:
        - Stateless engine, safe for concurrent use
        - Each extraction call is independent
        - No shared mutable state

    Attributes:
        language: OCR language code (default: 'eng')
        min_confidence: Minimum confidence threshold (0-100)
        config: Additional Tesseract configuration
    """

    def __init__(
        self,
        language: str = 'eng',
        min_confidence: int = 60,
        config: str = ''
    ):
        """Initialize OCR engine.

        Args:
            language: Tesseract language code (e.g., 'eng', 'fra', 'spa')
            min_confidence: Minimum confidence score (0-100) for text
            config: Additional Tesseract configuration string

        Raises:
            RuntimeError: If Tesseract is not available
        """
        if not TESSERACT_AVAILABLE:
            raise RuntimeError(
                "Tesseract not available. Install with: "
                "pip install pytesseract pillow"
            )

        self.language = language
        self.min_confidence = min_confidence
        self.config = config

    def extract_text(self, image_path: Path) -> Dict[str, Any]:
        """Extract text from image with OCR.

        Args:
            image_path: Path to image file

        Returns:
            Dictionary containing:
                - text: Extracted text
                - confidence: Average confidence score
                - word_count: Number of words extracted
                - details: Detailed word-level information

        Raises:
            FileNotFoundError: If image file doesn't exist
            RuntimeError: If OCR fails
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        try:
            # Open image
            image = Image.open(image_path)

            # Extract text
            text = pytesseract.image_to_string(
                image,
                lang=self.language,
                config=self.config
            )

            # Get detailed data with confidence scores
            data = pytesseract.image_to_data(
                image,
                lang=self.language,
                config=self.config,
                output_type=pytesseract.Output.DICT
            )

            # Filter by confidence and collect words
            words = []
            confidences = []

            for i, conf in enumerate(data['conf']):
                if conf != -1 and conf >= self.min_confidence:
                    word = data['text'][i].strip()
                    if word:
                        words.append({
                            'text': word,
                            'confidence': conf,
                            'box': {
                                'left': data['left'][i],
                                'top': data['top'][i],
                                'width': data['width'][i],
                                'height': data['height'][i],
                            }
                        })
                        confidences.append(conf)

            # Calculate average confidence
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0

            return {
                'text': text.strip(),
                'confidence': round(avg_confidence, 2),
                'word_count': len(words),
                'details': words,
                'language': self.language,
            }

        except Exception as e:
            logger.error(f"OCR extraction failed for {image_path}: {e}")
            raise RuntimeError(f"OCR failed: {e}") from e

    def extract_from_pdf(self, pdf_path: Path, max_pages: Optional[int] = None) -> Dict[str, Any]:
        """Extract text from scanned PDF using OCR.

        Args:
            pdf_path: Path to PDF file
            max_pages: Maximum number of pages to process (None for all)

        Returns:
            Dictionary containing:
                - text: Full extracted text
                - pages: List of page-level results
                - total_confidence: Average confidence across all pages

        Raises:
            FileNotFoundError: If PDF doesn't exist
            RuntimeError: If PDF to image conversion is not available or OCR fails
        """
        if not PDF_TO_IMAGE_AVAILABLE:
            raise RuntimeError(
                "PDF OCR requires pdf2image. Install with: "
                "pip install pdf2image"
            )

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        try:
            # Convert PDF to images
            images = convert_from_path(pdf_path)

            if max_pages:
                images = images[:max_pages]

            # Process each page
            pages = []
            all_text = []
            all_confidences = []

            for page_num, image in enumerate(images, 1):
                try:
                    # Extract text from page
                    text = pytesseract.image_to_string(
                        image,
                        lang=self.language,
                        config=self.config
                    )

                    # Get confidence scores
                    data = pytesseract.image_to_data(
                        image,
                        lang=self.language,
                        config=self.config,
                        output_type=pytesseract.Output.DICT
                    )

                    # Calculate page confidence
                    page_confidences = [
                        conf for conf in data['conf']
                        if conf != -1 and conf >= self.min_confidence
                    ]
                    page_confidence = (
                        sum(page_confidences) / len(page_confidences)
                        if page_confidences else 0
                    )

                    pages.append({
                        'page_number': page_num,
                        'text': text.strip(),
                        'confidence': round(page_confidence, 2),
                        'char_count': len(text),
                    })

                    if text.strip():
                        all_text.append(f"[Page {page_num}]\n{text}")

                    if page_confidences:
                        all_confidences.extend(page_confidences)

                except Exception as e:
                    logger.warning(f"OCR failed for page {page_num}: {e}")

            # Calculate overall confidence
            total_confidence = (
                sum(all_confidences) / len(all_confidences)
                if all_confidences else 0
            )

            return {
                'text': '\n\n'.join(all_text),
                'pages': pages,
                'total_confidence': round(total_confidence, 2),
                'page_count': len(pages),
                'language': self.language,
            }

        except Exception as e:
            logger.error(f"PDF OCR failed for {pdf_path}: {e}")
            raise RuntimeError(f"PDF OCR failed: {e}") from e

    def get_available_languages(self) -> List[str]:
        """Get list of available OCR languages.

        Returns:
            List of language codes supported by Tesseract
        """
        if not TESSERACT_AVAILABLE:
            return []

        try:
            langs = pytesseract.get_languages()
            return sorted(langs)
        except Exception as e:
            logger.warning(f"Could not get language list: {e}")
            return ['eng']  # Default fallback
