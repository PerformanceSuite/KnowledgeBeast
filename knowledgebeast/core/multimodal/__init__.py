"""Multi-modal processing engines for KnowledgeBeast.

This package provides engines for processing multi-modal content:
- CLIPEmbeddings: Generate image embeddings using CLIP models
- OCREngine: Extract text from images using Tesseract
"""

from .clip_embeddings import CLIPEmbeddings, CLIP_AVAILABLE
from .ocr_engine import OCREngine, TESSERACT_AVAILABLE

__all__ = [
    'CLIPEmbeddings',
    'CLIP_AVAILABLE',
    'OCREngine',
    'TESSERACT_AVAILABLE',
]
