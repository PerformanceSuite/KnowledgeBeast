"""Base chunker interface for KnowledgeBeast."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import hashlib


@dataclass
class Chunk:
    """Represents a chunk of text with metadata.

    Attributes:
        chunk_id: Unique identifier for this chunk
        text: The chunk content
        metadata: Additional metadata (section, file_path, line_start, etc.)
    """
    chunk_id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate chunk data."""
        if not self.chunk_id:
            raise ValueError("chunk_id cannot be empty")
        if not self.text:
            raise ValueError("text cannot be empty")

    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk to dictionary representation.

        Returns:
            Dictionary with chunk_id, text, and metadata
        """
        return {
            'chunk_id': self.chunk_id,
            'text': self.text,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Chunk':
        """Create chunk from dictionary.

        Args:
            data: Dictionary with chunk_id, text, and metadata

        Returns:
            Chunk instance
        """
        return cls(
            chunk_id=data['chunk_id'],
            text=data['text'],
            metadata=data.get('metadata', {})
        )


class BaseChunker(ABC):
    """Abstract base class for text chunking strategies.

    All chunkers must implement the chunk() method to split text
    into semantically meaningful pieces with rich metadata.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize chunker with configuration.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}

    @abstractmethod
    def chunk(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Chunk]:
        """Split text into chunks with metadata.

        Args:
            text: Input text to chunk
            metadata: Optional metadata to attach to chunks (file_path, etc.)

        Returns:
            List of Chunk objects with text and metadata
        """
        pass

    def _generate_chunk_id(self, parent_doc_id: str, chunk_index: int) -> str:
        """Generate unique chunk ID.

        Args:
            parent_doc_id: Parent document identifier
            chunk_index: Index of chunk within document

        Returns:
            Unique chunk identifier
        """
        return f"{parent_doc_id}_chunk{chunk_index}"

    def _hash_text(self, text: str) -> str:
        """Generate hash of text content for deduplication.

        Args:
            text: Text to hash

        Returns:
            SHA256 hash of text
        """
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

    def chunk_batch(self, documents: List[Dict[str, Any]]) -> List[Chunk]:
        """Chunk multiple documents in batch.

        Args:
            documents: List of documents with 'text' and optional 'metadata'

        Returns:
            List of all chunks from all documents
        """
        all_chunks = []
        for doc in documents:
            text = doc.get('text', '')
            metadata = doc.get('metadata', {})
            chunks = self.chunk(text, metadata)
            all_chunks.extend(chunks)
        return all_chunks

    def get_stats(self) -> Dict[str, Any]:
        """Get chunker statistics.

        Returns:
            Dictionary with chunker stats
        """
        return {
            'chunker_type': self.__class__.__name__,
            'config': self.config
        }
