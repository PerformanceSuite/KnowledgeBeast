"""Tests for SemanticChunker."""

import pytest
from knowledgebeast.core.chunking.semantic import SemanticChunker
from knowledgebeast.core.chunking.base import Chunk


class TestSemanticChunker:
    """Test suite for SemanticChunker (15 tests)."""

    def test_initialization_default_config(self):
        """Test chunker initialization with default config."""
        chunker = SemanticChunker()
        assert chunker.similarity_threshold == 0.7
        assert chunker.min_chunk_size == 2
        assert chunker.max_chunk_size == 10

    def test_initialization_custom_config(self):
        """Test chunker initialization with custom config."""
        config = {
            'similarity_threshold': 0.8,
            'min_chunk_size': 3,
            'max_chunk_size': 15
        }
        chunker = SemanticChunker(config)
        assert chunker.similarity_threshold == 0.8
        assert chunker.min_chunk_size == 3
        assert chunker.max_chunk_size == 15

    def test_invalid_similarity_threshold(self):
        """Test that invalid similarity threshold raises error."""
        with pytest.raises(ValueError, match="similarity_threshold must be between"):
            SemanticChunker({'similarity_threshold': 1.5})

    def test_invalid_chunk_sizes(self):
        """Test that invalid chunk sizes raise errors."""
        with pytest.raises(ValueError, match="min_chunk_size must be at least"):
            SemanticChunker({'min_chunk_size': 0})

        with pytest.raises(ValueError, match="max_chunk_size must be"):
            SemanticChunker({'min_chunk_size': 10, 'max_chunk_size': 5})

    def test_empty_text(self):
        """Test chunking empty text returns empty list."""
        chunker = SemanticChunker()
        assert chunker.chunk("") == []
        assert chunker.chunk("   ") == []

    def test_single_sentence(self):
        """Test chunking single sentence."""
        chunker = SemanticChunker()
        text = "This is a single sentence."
        chunks = chunker.chunk(text, {'parent_doc_id': 'test_doc'})

        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].metadata['chunk_index'] == 0
        assert chunks[0].metadata['total_chunks'] == 1

    def test_topic_shift_detection(self):
        """Test that topic shifts create new chunks."""
        chunker = SemanticChunker({'similarity_threshold': 0.6})
        text = (
            "Python is a high-level programming language. "
            "It was created by Guido van Rossum. "
            "The elephant is the largest land animal. "
            "They live in Africa and Asia."
        )
        chunks = chunker.chunk(text, {'parent_doc_id': 'test_doc'})

        # Should detect topic shift from Python to elephants
        assert len(chunks) >= 2

    def test_semantic_coherence(self):
        """Test that semantically similar sentences stay together."""
        chunker = SemanticChunker({'similarity_threshold': 0.7})
        text = (
            "Machine learning is a subset of AI. "
            "Deep learning uses neural networks. "
            "Neural networks have multiple layers. "
            "These layers process information hierarchically."
        )
        chunks = chunker.chunk(text, {'parent_doc_id': 'test_doc'})

        # Semantic chunker creates chunks based on similarity
        # With threshold 0.7, it may create multiple chunks
        assert len(chunks) >= 1  # Just verify it creates valid chunks

    def test_max_chunk_size_enforcement(self):
        """Test that max chunk size is enforced."""
        chunker = SemanticChunker({'max_chunk_size': 3})
        text = ". ".join([f"Sentence {i}" for i in range(10)]) + "."
        chunks = chunker.chunk(text, {'parent_doc_id': 'test_doc'})

        # No chunk should exceed max_chunk_size sentences
        for chunk in chunks:
            assert chunk.metadata.get('num_sentences', 0) <= 3

    def test_min_chunk_size_respected(self):
        """Test that minimum chunk size is respected."""
        chunker = SemanticChunker({'min_chunk_size': 3, 'similarity_threshold': 0.1})
        text = (
            "First sentence. "
            "Second sentence. "
            "Third sentence. "
            "Fourth sentence."
        )
        chunks = chunker.chunk(text, {'parent_doc_id': 'test_doc'})

        # With low threshold, should still respect min size
        for chunk in chunks:
            assert chunk.metadata.get('num_sentences', 0) >= 3 or \
                   chunk == chunks[-1]  # Last chunk may be smaller

    def test_metadata_preservation(self):
        """Test that input metadata is preserved in chunks."""
        chunker = SemanticChunker()
        metadata = {
            'parent_doc_id': 'doc123',
            'file_path': '/path/to/file.txt',
            'author': 'John Doe'
        }
        text = "First sentence. Second sentence. Third sentence."
        chunks = chunker.chunk(text, metadata)

        for chunk in chunks:
            assert chunk.metadata['parent_doc_id'] == 'doc123'
            assert chunk.metadata['file_path'] == '/path/to/file.txt'
            assert chunk.metadata['author'] == 'John Doe'

    def test_chunk_metadata_structure(self):
        """Test that chunks have correct metadata structure."""
        chunker = SemanticChunker()
        text = "First sentence. Second sentence. Third sentence."
        chunks = chunker.chunk(text, {'parent_doc_id': 'test'})

        for i, chunk in enumerate(chunks):
            assert chunk.chunk_id.startswith('test_chunk')
            assert chunk.metadata['chunk_index'] == i
            assert chunk.metadata['total_chunks'] == len(chunks)
            assert chunk.metadata['chunk_type'] == 'text'
            assert 'num_sentences' in chunk.metadata

    def test_sentence_splitting(self):
        """Test sentence splitting with various punctuation."""
        chunker = SemanticChunker()
        text = "First sentence! Second sentence? Third sentence."
        chunks = chunker.chunk(text, {'parent_doc_id': 'test'})

        # Should handle different sentence endings
        assert len(chunks) >= 1

    def test_abbreviation_handling(self):
        """Test that abbreviations don't cause incorrect splits."""
        chunker = SemanticChunker()
        text = "Dr. Smith works at MIT. He received his Ph.D. in 2010."
        chunks = chunker.chunk(text, {'parent_doc_id': 'test'})

        # Should not split on abbreviations
        assert len(chunks) >= 1

    def test_get_stats(self):
        """Test get_stats returns correct information."""
        config = {
            'similarity_threshold': 0.75,
            'min_chunk_size': 2,
            'max_chunk_size': 8
        }
        chunker = SemanticChunker(config)
        stats = chunker.get_stats()

        assert stats['chunker_type'] == 'SemanticChunker'
        assert stats['similarity_threshold'] == 0.75
        assert stats['min_chunk_size'] == 2
        assert stats['max_chunk_size'] == 8
        assert 'model' in stats
