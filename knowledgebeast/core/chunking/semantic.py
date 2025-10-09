"""Semantic chunker using sentence embeddings for topic shift detection."""

import re
from typing import List, Dict, Any, Optional
import numpy as np
from sentence_transformers import SentenceTransformer

from knowledgebeast.core.chunking.base import BaseChunker, Chunk


class SemanticChunker(BaseChunker):
    """Semantic chunker that uses sentence embeddings to detect topic shifts.

    This chunker:
    1. Splits text into sentences
    2. Generates embeddings for each sentence
    3. Calculates similarity between adjacent sentences
    4. Creates chunk boundaries when similarity drops below threshold
    5. Preserves paragraph coherence

    Attributes:
        similarity_threshold: Threshold for topic shift detection (0.0-1.0)
        min_chunk_size: Minimum number of sentences per chunk
        max_chunk_size: Maximum number of sentences per chunk
        model: SentenceTransformer model for embeddings
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize semantic chunker.

        Args:
            config: Configuration dictionary with:
                - similarity_threshold: float (default: 0.7)
                - min_chunk_size: int (default: 2)
                - max_chunk_size: int (default: 10)
                - model_name: str (default: 'all-MiniLM-L6-v2')
        """
        super().__init__(config)
        self.similarity_threshold = self.config.get('similarity_threshold', 0.7)
        self.min_chunk_size = self.config.get('min_chunk_size', 2)
        self.max_chunk_size = self.config.get('max_chunk_size', 10)
        model_name = self.config.get('model_name', 'all-MiniLM-L6-v2')

        # Validate config
        if not 0.0 <= self.similarity_threshold <= 1.0:
            raise ValueError("similarity_threshold must be between 0.0 and 1.0")
        if self.min_chunk_size < 1:
            raise ValueError("min_chunk_size must be at least 1")
        if self.max_chunk_size < self.min_chunk_size:
            raise ValueError("max_chunk_size must be >= min_chunk_size")

        # Load sentence transformer model
        self.model = SentenceTransformer(model_name)

    def chunk(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Chunk]:
        """Split text into semantic chunks based on topic shifts.

        Args:
            text: Input text to chunk
            metadata: Optional metadata (file_path, parent_doc_id, etc.)

        Returns:
            List of Chunk objects with semantic boundaries
        """
        if not text or not text.strip():
            return []

        metadata = metadata or {}
        parent_doc_id = metadata.get('parent_doc_id', 'unknown')

        # Split into sentences
        sentences = self._split_into_sentences(text)
        if not sentences:
            return []

        # Handle single sentence case
        if len(sentences) == 1:
            chunk_id = self._generate_chunk_id(parent_doc_id, 0)
            return [Chunk(
                chunk_id=chunk_id,
                text=sentences[0],
                metadata={
                    **metadata,
                    'chunk_index': 0,
                    'total_chunks': 1,
                    'chunk_type': 'text',
                    'num_sentences': 1
                }
            )]

        # Generate embeddings for all sentences
        embeddings = self.model.encode(sentences, convert_to_numpy=True)

        # Calculate similarity between adjacent sentences
        similarities = self._calculate_similarities(embeddings)

        # Identify chunk boundaries based on similarity drops
        boundaries = self._identify_boundaries(similarities)

        # Create chunks from boundaries
        chunks = self._create_chunks_from_boundaries(
            sentences, boundaries, parent_doc_id, metadata
        )

        return chunks

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences.

        Args:
            text: Input text

        Returns:
            List of sentences
        """
        # Simple sentence splitter (can be improved with spaCy/NLTK)
        # Handles common abbreviations
        text = re.sub(r'\b(Dr|Mr|Mrs|Ms|Prof|Sr|Jr)\.\s', r'\1<PERIOD> ', text)
        text = re.sub(r'\b([A-Z])\.([A-Z])\.', r'\1<PERIOD>\2<PERIOD>', text)

        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)

        # Restore periods
        sentences = [s.replace('<PERIOD>', '.') for s in sentences]

        # Filter empty sentences
        sentences = [s.strip() for s in sentences if s.strip()]

        return sentences

    def _calculate_similarities(self, embeddings: np.ndarray) -> List[float]:
        """Calculate cosine similarity between adjacent sentence embeddings.

        Args:
            embeddings: Array of sentence embeddings (N x embedding_dim)

        Returns:
            List of similarities between adjacent sentences
        """
        similarities = []
        for i in range(len(embeddings) - 1):
            # Cosine similarity between adjacent embeddings
            sim = np.dot(embeddings[i], embeddings[i + 1]) / (
                np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[i + 1])
            )
            similarities.append(float(sim))
        return similarities

    def _identify_boundaries(self, similarities: List[float]) -> List[int]:
        """Identify chunk boundaries based on similarity drops.

        Args:
            similarities: List of similarities between adjacent sentences

        Returns:
            List of sentence indices where chunks should be split
        """
        boundaries = [0]  # Start with first sentence

        current_chunk_size = 1
        for i, sim in enumerate(similarities):
            current_chunk_size += 1

            # Force boundary if max chunk size reached
            if current_chunk_size >= self.max_chunk_size:
                boundaries.append(i + 1)
                current_chunk_size = 1
            # Create boundary if similarity drops below threshold
            # and minimum chunk size met
            elif sim < self.similarity_threshold and current_chunk_size >= self.min_chunk_size:
                boundaries.append(i + 1)
                current_chunk_size = 1

        return boundaries

    def _create_chunks_from_boundaries(
        self,
        sentences: List[str],
        boundaries: List[int],
        parent_doc_id: str,
        metadata: Dict[str, Any]
    ) -> List[Chunk]:
        """Create chunks from sentence boundaries.

        Args:
            sentences: List of sentences
            boundaries: List of boundary indices
            parent_doc_id: Parent document ID
            metadata: Base metadata to include

        Returns:
            List of Chunk objects
        """
        chunks = []
        total_chunks = len(boundaries)

        for i, start_idx in enumerate(boundaries):
            # Determine end index
            if i < len(boundaries) - 1:
                end_idx = boundaries[i + 1]
            else:
                end_idx = len(sentences)

            # Combine sentences into chunk
            chunk_sentences = sentences[start_idx:end_idx]
            chunk_text = ' '.join(chunk_sentences)

            # Generate chunk ID
            chunk_id = self._generate_chunk_id(parent_doc_id, i)

            # Create chunk with metadata
            chunk = Chunk(
                chunk_id=chunk_id,
                text=chunk_text,
                metadata={
                    **metadata,
                    'chunk_index': i,
                    'total_chunks': total_chunks,
                    'chunk_type': 'text',
                    'num_sentences': len(chunk_sentences),
                    'start_sentence': start_idx,
                    'end_sentence': end_idx
                }
            )
            chunks.append(chunk)

        return chunks

    def get_stats(self) -> Dict[str, Any]:
        """Get chunker statistics.

        Returns:
            Dictionary with chunker stats
        """
        return {
            **super().get_stats(),
            'similarity_threshold': self.similarity_threshold,
            'min_chunk_size': self.min_chunk_size,
            'max_chunk_size': self.max_chunk_size,
            'model': self.model.get_sentence_embedding_dimension()
        }
