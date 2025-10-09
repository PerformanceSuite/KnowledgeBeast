"""CLIP-based image embeddings for semantic image search.

This module provides image embedding functionality using OpenAI's CLIP model:
- Generate image embeddings
- Generate text embeddings for image queries
- Text-to-image similarity search
- Image-to-image similarity search
- GPU acceleration support
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np

logger = logging.getLogger(__name__)

# Graceful dependency degradation
try:
    import torch
    from transformers import CLIPProcessor, CLIPModel
    from PIL import Image
    CLIP_AVAILABLE = True
    logger.info("CLIP models available")
except ImportError as e:
    CLIP_AVAILABLE = False
    torch = None
    CLIPProcessor = None
    CLIPModel = None
    Image = None
    logger.warning(f"CLIP not available - image embeddings disabled: {e}")


class CLIPEmbeddings:
    """CLIP-based image embedding generator.

    This class provides semantic image embeddings using OpenAI's CLIP model
    for cross-modal (text-image) similarity search.

    Thread Safety:
        - Model loading is not thread-safe (should be done once at initialization)
        - Inference is thread-safe after model is loaded
        - Each encode call is independent

    Attributes:
        model_name: CLIP model identifier (default: openai/clip-vit-large-patch14)
        device: Device for inference ('cuda', 'cpu', or 'mps')
        model: Loaded CLIP model
        processor: CLIP image/text processor
    """

    DEFAULT_MODEL = "openai/clip-vit-large-patch14"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: Optional[str] = None
    ):
        """Initialize CLIP embeddings.

        Args:
            model_name: HuggingFace model identifier for CLIP
            device: Device to use ('cuda', 'cpu', 'mps', or None for auto)

        Raises:
            RuntimeError: If CLIP dependencies are not available
        """
        if not CLIP_AVAILABLE:
            raise RuntimeError(
                "CLIP not available. Install with: "
                "pip install transformers>=4.30.0 torch>=2.0.0 torchvision>=0.15.0 pillow>=10.0.0"
            )

        self.model_name = model_name
        self.device = self._get_device(device)

        # Lazy loading - models loaded on first use
        self._model = None
        self._processor = None

    def _get_device(self, device: Optional[str] = None) -> str:
        """Determine the best device for inference.

        Args:
            device: Requested device or None for auto-detection

        Returns:
            Device string ('cuda', 'mps', or 'cpu')
        """
        if device:
            return device

        # Auto-detect best device
        if torch.cuda.is_available():
            return 'cuda'
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return 'mps'
        else:
            return 'cpu'

    @property
    def model(self):
        """Lazy-load CLIP model."""
        if self._model is None:
            logger.info(f"Loading CLIP model: {self.model_name}")
            self._model = CLIPModel.from_pretrained(self.model_name)
            self._model.to(self.device)
            self._model.eval()  # Set to evaluation mode
            logger.info(f"CLIP model loaded on {self.device}")
        return self._model

    @property
    def processor(self):
        """Lazy-load CLIP processor."""
        if self._processor is None:
            logger.info(f"Loading CLIP processor: {self.model_name}")
            self._processor = CLIPProcessor.from_pretrained(self.model_name)
        return self._processor

    def encode_image(self, image_path: Union[Path, str]) -> np.ndarray:
        """Generate embedding for an image.

        Args:
            image_path: Path to image file

        Returns:
            Normalized embedding vector (numpy array)

        Raises:
            FileNotFoundError: If image doesn't exist
            RuntimeError: If encoding fails
        """
        image_path = Path(image_path)

        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        try:
            # Load and preprocess image
            image = Image.open(image_path).convert('RGB')

            inputs = self.processor(
                images=image,
                return_tensors="pt"
            ).to(self.device)

            # Generate embedding
            with torch.no_grad():
                image_features = self.model.get_image_features(**inputs)

            # Normalize embedding
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)

            # Convert to numpy
            embedding = image_features.cpu().numpy()[0]

            return embedding

        except Exception as e:
            logger.error(f"Image encoding failed for {image_path}: {e}")
            raise RuntimeError(f"Image encoding failed: {e}") from e

    def encode_images_batch(self, image_paths: List[Union[Path, str]], batch_size: int = 32) -> np.ndarray:
        """Generate embeddings for multiple images in batches.

        Args:
            image_paths: List of image file paths
            batch_size: Number of images to process at once

        Returns:
            Array of normalized embeddings (shape: [num_images, embedding_dim])

        Raises:
            RuntimeError: If batch encoding fails
        """
        embeddings = []

        for i in range(0, len(image_paths), batch_size):
            batch_paths = image_paths[i:i + batch_size]

            try:
                # Load images
                images = []
                for path in batch_paths:
                    try:
                        img = Image.open(path).convert('RGB')
                        images.append(img)
                    except Exception as e:
                        logger.warning(f"Failed to load {path}: {e}")
                        continue

                if not images:
                    continue

                # Process batch
                inputs = self.processor(
                    images=images,
                    return_tensors="pt"
                ).to(self.device)

                # Generate embeddings
                with torch.no_grad():
                    features = self.model.get_image_features(**inputs)

                # Normalize
                features = features / features.norm(dim=-1, keepdim=True)

                # Convert to numpy and append
                batch_embeddings = features.cpu().numpy()
                embeddings.append(batch_embeddings)

            except Exception as e:
                logger.error(f"Batch encoding failed for batch {i//batch_size}: {e}")
                continue

        if not embeddings:
            raise RuntimeError("No images could be encoded")

        return np.vstack(embeddings)

    def encode_text(self, text: str) -> np.ndarray:
        """Generate embedding for text query.

        Args:
            text: Text query for image search

        Returns:
            Normalized embedding vector (numpy array)

        Raises:
            RuntimeError: If encoding fails
        """
        try:
            inputs = self.processor(
                text=[text],
                return_tensors="pt",
                padding=True
            ).to(self.device)

            # Generate embedding
            with torch.no_grad():
                text_features = self.model.get_text_features(**inputs)

            # Normalize embedding
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

            # Convert to numpy
            embedding = text_features.cpu().numpy()[0]

            return embedding

        except Exception as e:
            logger.error(f"Text encoding failed: {e}")
            raise RuntimeError(f"Text encoding failed: {e}") from e

    def encode_texts_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """Generate embeddings for multiple text queries.

        Args:
            texts: List of text queries
            batch_size: Number of texts to process at once

        Returns:
            Array of normalized embeddings (shape: [num_texts, embedding_dim])
        """
        embeddings = []

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]

            try:
                inputs = self.processor(
                    text=batch_texts,
                    return_tensors="pt",
                    padding=True,
                    truncation=True
                ).to(self.device)

                with torch.no_grad():
                    features = self.model.get_text_features(**inputs)

                features = features / features.norm(dim=-1, keepdim=True)
                batch_embeddings = features.cpu().numpy()
                embeddings.append(batch_embeddings)

            except Exception as e:
                logger.error(f"Batch text encoding failed: {e}")
                continue

        if not embeddings:
            raise RuntimeError("No texts could be encoded")

        return np.vstack(embeddings)

    def compute_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray
    ) -> float:
        """Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity score (0-1)
        """
        # Embeddings are already normalized, so dot product = cosine similarity
        similarity = float(np.dot(embedding1, embedding2))
        return similarity

    def search_images_by_text(
        self,
        query_text: str,
        image_embeddings: np.ndarray,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """Search images using text query.

        Args:
            query_text: Text query
            image_embeddings: Array of image embeddings
            top_k: Number of top results to return

        Returns:
            List of results with indices and similarity scores
        """
        # Encode query
        query_embedding = self.encode_text(query_text)

        # Compute similarities
        similarities = image_embeddings @ query_embedding

        # Get top-k indices
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        results = [
            {
                'index': int(idx),
                'similarity': float(similarities[idx])
            }
            for idx in top_indices
        ]

        return results

    def search_images_by_image(
        self,
        query_image_path: Union[Path, str],
        image_embeddings: np.ndarray,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """Search images using image query.

        Args:
            query_image_path: Path to query image
            image_embeddings: Array of image embeddings
            top_k: Number of top results to return

        Returns:
            List of results with indices and similarity scores
        """
        # Encode query image
        query_embedding = self.encode_image(query_image_path)

        # Compute similarities
        similarities = image_embeddings @ query_embedding

        # Get top-k indices
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        results = [
            {
                'index': int(idx),
                'similarity': float(similarities[idx])
            }
            for idx in top_indices
        ]

        return results

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about loaded model.

        Returns:
            Dictionary with model information
        """
        return {
            'model_name': self.model_name,
            'device': self.device,
            'model_loaded': self._model is not None,
            'processor_loaded': self._processor is not None,
        }
