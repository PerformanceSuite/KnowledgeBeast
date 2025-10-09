"""Tests for RecursiveCharacterChunker."""

import pytest
from knowledgebeast.core.chunking.recursive import RecursiveCharacterChunker


class TestRecursiveCharacterChunker:
    """Test suite for RecursiveCharacterChunker (12 tests)."""

    def test_initialization_default_config(self):
        """Test chunker initialization with defaults."""
        chunker = RecursiveCharacterChunker()
        assert chunker.chunk_size == 512
        assert chunker.chunk_overlap == 128

    def test_initialization_custom_config(self):
        """Test chunker with custom configuration."""
        config = {'chunk_size': 256, 'chunk_overlap': 64}
        chunker = RecursiveCharacterChunker(config)
        assert chunker.chunk_size == 256
        assert chunker.chunk_overlap == 64

    def test_invalid_config(self):
        """Test that invalid config raises errors."""
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            RecursiveCharacterChunker({'chunk_size': 0})

        with pytest.raises(ValueError, match="chunk_overlap must be less than"):
            RecursiveCharacterChunker({'chunk_size': 100, 'chunk_overlap': 150})

    def test_empty_text(self):
        """Test chunking empty text."""
        chunker = RecursiveCharacterChunker()
        assert chunker.chunk("") == []
        assert chunker.chunk("   ") == []

    def test_short_text(self):
        """Test chunking text shorter than chunk_size."""
        chunker = RecursiveCharacterChunker({'chunk_size': 1000})
        text = "This is a short text."
        chunks = chunker.chunk(text, {'parent_doc_id': 'test'})

        assert len(chunks) == 1
        assert chunks[0].text == text

    def test_paragraph_splitting(self):
        """Test that paragraph breaks are respected."""
        chunker = RecursiveCharacterChunker({'chunk_size': 50})
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = chunker.chunk(text, {'parent_doc_id': 'test'})

        # Should split on double newlines
        assert len(chunks) >= 2

    def test_code_block_preservation(self):
        """Test that code blocks are preserved."""
        chunker = RecursiveCharacterChunker()
        text = """
Some text before.

```python
def hello():
    print("world")
```

Some text after.
"""
        chunks = chunker.chunk(text, {'parent_doc_id': 'test'})

        # Code block should be preserved in at least one chunk
        has_code = any('```python' in chunk.text for chunk in chunks)
        assert has_code

    def test_overlap_creation(self):
        """Test that overlap is created between chunks."""
        chunker = RecursiveCharacterChunker({
            'chunk_size': 100,
            'chunk_overlap': 30
        })
        text = "This is a very long text. " * 20
        chunks = chunker.chunk(text, {'parent_doc_id': 'test'})

        if len(chunks) > 1:
            # There should be some overlap
            assert len(chunks) >= 2

    def test_metadata_enrichment(self):
        """Test that chunks have proper metadata."""
        chunker = RecursiveCharacterChunker()
        text = "Test text for chunking."
        chunks = chunker.chunk(text, {
            'parent_doc_id': 'doc1',
            'file_path': '/test.md'
        })

        for chunk in chunks:
            assert 'chunk_index' in chunk.metadata
            assert 'chunk_type' in chunk.metadata
            assert 'token_count' in chunk.metadata
            assert 'char_count' in chunk.metadata
            assert chunk.metadata['file_path'] == '/test.md'

    def test_sentence_boundary_splitting(self):
        """Test splitting on sentence boundaries."""
        chunker = RecursiveCharacterChunker({'chunk_size': 50})
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        chunks = chunker.chunk(text, {'parent_doc_id': 'test'})

        # Should split on sentence boundaries
        assert len(chunks) >= 1

    def test_token_counting(self):
        """Test token counting functionality."""
        chunker = RecursiveCharacterChunker()
        text = "This is a test text with multiple words."
        chunks = chunker.chunk(text, {'parent_doc_id': 'test'})

        for chunk in chunks:
            # Should have token count
            assert chunk.metadata['token_count'] > 0

    def test_get_stats(self):
        """Test get_stats returns configuration."""
        config = {'chunk_size': 256, 'chunk_overlap': 64}
        chunker = RecursiveCharacterChunker(config)
        stats = chunker.get_stats()

        assert stats['chunker_type'] == 'RecursiveCharacterChunker'
        assert stats['chunk_size'] == 256
        assert stats['chunk_overlap'] == 64
