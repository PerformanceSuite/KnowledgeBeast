"""Image converter with CLIP embeddings and OCR support.

This module provides image processing with:
- CLIP-based semantic embeddings
- OCR text extraction
- Thumbnail generation
- Image metadata extraction
- Multi-format support (PNG, JPG, GIF, BMP, etc.)
"""

import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
from types import SimpleNamespace

logger = logging.getLogger(__name__)

# Graceful dependency degradation
try:
    from PIL import Image
    import PIL.ExifTags as ExifTags
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    Image = None
    ExifTags = None
    logger.warning("Pillow not available - image processing disabled")


class ImageConverter:
    """Image converter with CLIP embeddings and OCR.

    This converter provides comprehensive image processing with graceful
    degradation when optional dependencies are unavailable.

    Thread Safety:
        - Stateless converter, safe for concurrent use
        - Each convert() call is independent
        - CLIP and OCR engines handle their own thread safety

    Attributes:
        use_clip: Whether to generate CLIP embeddings (default: True)
        use_ocr: Whether to extract text via OCR (default: True)
        generate_thumbnail: Whether to create thumbnails (default: True)
        thumbnail_size: Thumbnail dimensions (width, height)
    """

    SUPPORTED_FORMATS = {
        '.jpg', '.jpeg', '.png', '.gif', '.bmp',
        '.tiff', '.tif', '.webp', '.ico'
    }

    def __init__(
        self,
        use_clip: bool = True,
        use_ocr: bool = True,
        generate_thumbnail: bool = True,
        thumbnail_size: tuple = (256, 256)
    ):
        """Initialize ImageConverter.

        Args:
            use_clip: Whether to generate CLIP embeddings
            use_ocr: Whether to extract text via OCR
            generate_thumbnail: Whether to create thumbnails
            thumbnail_size: Thumbnail dimensions (width, height)

        Raises:
            RuntimeError: If Pillow is not available
        """
        if not PILLOW_AVAILABLE:
            raise RuntimeError(
                "Pillow not available. Install with: pip install pillow>=10.0.0"
            )

        self.use_clip = use_clip
        self.use_ocr = use_ocr
        self.generate_thumbnail = generate_thumbnail
        self.thumbnail_size = thumbnail_size

        # Lazy-load CLIP and OCR engines
        self.clip_engine = None
        self.ocr_engine = None

        if use_clip:
            try:
                from ..core.multimodal.clip_embeddings import CLIPEmbeddings
                self.clip_engine = CLIPEmbeddings()
            except Exception as e:
                logger.warning(f"CLIP engine not available: {e}")
                self.use_clip = False

        if use_ocr:
            try:
                from ..core.multimodal.ocr_engine import OCREngine
                self.ocr_engine = OCREngine()
            except Exception as e:
                logger.warning(f"OCR engine not available: {e}")
                self.use_ocr = False

    def is_supported(self, path: Path) -> bool:
        """Check if file format is supported.

        Args:
            path: Path to file

        Returns:
            True if format is supported, False otherwise
        """
        return path.suffix.lower() in self.SUPPORTED_FORMATS

    def extract_metadata(self, path: Path, image: Optional[Any] = None) -> Dict[str, Any]:
        """Extract metadata from image.

        Args:
            path: Path to image file
            image: Optional PIL Image object (avoids re-loading)

        Returns:
            Dictionary containing metadata
        """
        metadata = {
            'filename': path.name,
            'format': path.suffix.lower().lstrip('.'),
            'size_bytes': path.stat().st_size if path.exists() else 0,
            'modality': 'image',
            'document_type': 'image',
        }

        try:
            # File system metadata
            stat = path.stat()
            metadata['created'] = datetime.fromtimestamp(stat.st_ctime).isoformat()
            metadata['modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
        except Exception as e:
            logger.warning(f"Could not extract file metadata: {e}")

        # Extract image-specific metadata
        if image is None:
            try:
                image = Image.open(path)
            except Exception as e:
                logger.warning(f"Could not open image for metadata: {e}")
                return metadata

        try:
            # Basic image info
            metadata['width'] = image.width
            metadata['height'] = image.height
            metadata['mode'] = image.mode
            metadata['format_detail'] = image.format

            # EXIF data
            if hasattr(image, '_getexif') and image._getexif():
                exif_data = {}
                exif = image._getexif()

                for tag_id, value in exif.items():
                    tag = ExifTags.TAGS.get(tag_id, tag_id)
                    try:
                        # Convert bytes to string if needed
                        if isinstance(value, bytes):
                            value = value.decode('utf-8', errors='ignore')
                        exif_data[tag] = value
                    except:
                        pass

                # Extract useful EXIF fields
                if 'DateTime' in exif_data:
                    metadata['exif_datetime'] = exif_data['DateTime']
                if 'Make' in exif_data:
                    metadata['camera_make'] = exif_data['Make']
                if 'Model' in exif_data:
                    metadata['camera_model'] = exif_data['Model']
                if 'Software' in exif_data:
                    metadata['software'] = exif_data['Software']

        except Exception as e:
            logger.debug(f"Could not extract image metadata: {e}")

        metadata['title'] = path.stem

        return metadata

    def generate_thumbnail_image(self, image: Any, path: Path) -> Optional[str]:
        """Generate thumbnail for image.

        Args:
            image: PIL Image object
            path: Original image path (for thumbnail naming)

        Returns:
            Path to thumbnail file or None if failed
        """
        try:
            # Create thumbnail
            thumbnail = image.copy()
            thumbnail.thumbnail(self.thumbnail_size, Image.Resampling.LANCZOS)

            # Save thumbnail
            thumb_path = path.parent / f"{path.stem}_thumb{path.suffix}"
            thumbnail.save(thumb_path)

            return str(thumb_path)

        except Exception as e:
            logger.warning(f"Thumbnail generation failed: {e}")
            return None

    def extract_text_ocr(self, path: Path) -> Optional[Dict[str, Any]]:
        """Extract text from image using OCR.

        Args:
            path: Path to image file

        Returns:
            OCR result dictionary or None if OCR unavailable
        """
        if not self.use_ocr or not self.ocr_engine:
            return None

        try:
            ocr_result = self.ocr_engine.extract_text(path)
            return ocr_result
        except Exception as e:
            logger.warning(f"OCR extraction failed for {path}: {e}")
            return None

    def generate_embedding(self, path: Path) -> Optional[List[float]]:
        """Generate CLIP embedding for image.

        Args:
            path: Path to image file

        Returns:
            Embedding vector as list or None if CLIP unavailable
        """
        if not self.use_clip or not self.clip_engine:
            return None

        try:
            embedding = self.clip_engine.encode_image(path)
            return embedding.tolist()
        except Exception as e:
            logger.warning(f"CLIP embedding failed for {path}: {e}")
            return None

    def convert(self, path: Path, enable_chunking: bool = False) -> SimpleNamespace:
        """Convert image with embeddings, OCR, and metadata extraction.

        Args:
            path: Path to image file
            enable_chunking: Not used for images (for API compatibility)

        Returns:
            SimpleNamespace with:
                - document: SimpleNamespace with name and export_to_markdown method
                - chunks: Empty list (images aren't chunked)
                - metadata: Image metadata including dimensions, EXIF data
                - embedding: CLIP embedding vector (if use_clip=True)
                - ocr_text: Extracted text (if use_ocr=True)
                - thumbnail_path: Path to thumbnail (if generate_thumbnail=True)

        Raises:
            ValueError: If file format is not supported
            FileNotFoundError: If file does not exist
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
            # Load image
            image = Image.open(path)

            # Extract metadata
            metadata = self.extract_metadata(path, image)

            # Generate CLIP embedding
            embedding = None
            if self.use_clip:
                embedding = self.generate_embedding(path)
                if embedding:
                    metadata['has_embedding'] = True
                    metadata['embedding_dim'] = len(embedding)

            # Extract text via OCR
            ocr_result = None
            ocr_text = ""
            if self.use_ocr:
                ocr_result = self.extract_text_ocr(path)
                if ocr_result:
                    ocr_text = ocr_result.get('text', '')
                    metadata['ocr_confidence'] = ocr_result.get('confidence', 0)
                    metadata['ocr_word_count'] = ocr_result.get('word_count', 0)

            # Generate thumbnail
            thumbnail_path = None
            if self.generate_thumbnail:
                thumbnail_path = self.generate_thumbnail_image(image, path)
                if thumbnail_path:
                    metadata['thumbnail_path'] = thumbnail_path

            # Create markdown representation
            markdown = f"# {metadata['title']}\n\n"
            markdown += f"![{metadata['title']}]({path})\n\n"
            markdown += f"**Image Properties:**\n"
            markdown += f"- Size: {metadata['width']} x {metadata['height']}\n"
            markdown += f"- Format: {metadata['format_detail']}\n"
            markdown += f"- File size: {metadata['size_bytes']} bytes\n"

            if ocr_text:
                markdown += f"\n**Extracted Text (OCR):**\n\n{ocr_text}\n"

            # Return result
            return SimpleNamespace(
                document=SimpleNamespace(
                    name=metadata['title'],
                    export_to_markdown=lambda: markdown
                ),
                chunks=[],  # Images aren't chunked
                metadata=metadata,
                embedding=embedding,
                ocr_text=ocr_text,
                ocr_result=ocr_result,
                thumbnail_path=thumbnail_path
            )

        except Exception as e:
            logger.error(f"Image conversion failed for {path}: {e}")
            raise RuntimeError(f"Image conversion failed: {e}") from e

    def convert_batch(self, image_paths: List[Path]) -> List[SimpleNamespace]:
        """Convert multiple images (useful for batch embedding generation).

        Args:
            image_paths: List of image file paths

        Returns:
            List of conversion results
        """
        results = []

        for path in image_paths:
            try:
                result = self.convert(path)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to convert {path}: {e}")
                continue

        return results
