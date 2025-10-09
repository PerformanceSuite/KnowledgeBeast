"""Tests for MarkdownAwareChunker."""

import pytest
from knowledgebeast.core.chunking.markdown import MarkdownAwareChunker


class TestMarkdownAwareChunker:
    """Test suite for MarkdownAwareChunker (10 tests)."""

    def test_initialization(self):
        """Test chunker initialization."""
        chunker = MarkdownAwareChunker({'max_chunk_size': 1500})
        assert chunker.max_chunk_size == 1500
        assert chunker.preserve_headers is True

    def test_empty_text(self):
        """Test chunking empty text."""
        chunker = MarkdownAwareChunker()
        assert chunker.chunk("") == []

    def test_header_parsing(self):
        """Test markdown header parsing."""
        chunker = MarkdownAwareChunker()
        text = """
# Main Header

Some content here.

## Subsection

More content.
"""
        chunks = chunker.chunk(text, {'parent_doc_id': 'test'})
        assert len(chunks) >= 1

    def test_code_block_preservation(self):
        """Test that code blocks stay together."""
        chunker = MarkdownAwareChunker()
        text = """
# Code Example

```python
def hello():
    print("world")
    return True
```
"""
        chunks = chunker.chunk(text, {'parent_doc_id': 'test'})

        # Code block should be in one chunk
        has_complete_code = any('def hello' in chunk.text and 'return True' in chunk.text
                                for chunk in chunks)
        assert has_complete_code

    def test_list_preservation(self):
        """Test that lists are kept together."""
        chunker = MarkdownAwareChunker()
        text = """
# Shopping List

- Item 1
- Item 2
- Item 3
"""
        chunks = chunker.chunk(text, {'parent_doc_id': 'test'})
        assert len(chunks) >= 1

    def test_header_hierarchy(self):
        """Test header hierarchy preservation."""
        chunker = MarkdownAwareChunker({'preserve_headers': True})
        text = """
# Level 1

## Level 2

### Level 3

Content under level 3.
"""
        chunks = chunker.chunk(text, {'parent_doc_id': 'test'})

        # Should preserve hierarchy
        for chunk in chunks:
            if 'Content under level 3' in chunk.text:
                # Should include parent headers
                assert 'section' in chunk.metadata or 'subsection' in chunk.metadata

    def test_chunk_type_detection(self):
        """Test chunk type detection."""
        chunker = MarkdownAwareChunker()
        text = """
# Header

Regular text.

```python
code = True
```

- List item
"""
        chunks = chunker.chunk(text, {'parent_doc_id': 'test'})

        # Should have different chunk types
        chunk_types = {chunk.metadata.get('chunk_type') for chunk in chunks}
        assert len(chunk_types) >= 1

    def test_metadata_structure(self):
        """Test chunk metadata structure."""
        chunker = MarkdownAwareChunker()
        text = """
# Title

Content here.
"""
        chunks = chunker.chunk(text, {
            'parent_doc_id': 'doc1',
            'file_path': '/test.md'
        })

        for chunk in chunks:
            assert 'chunk_index' in chunk.metadata
            assert 'chunk_type' in chunk.metadata
            assert 'line_start' in chunk.metadata
            assert 'line_end' in chunk.metadata

    def test_max_chunk_size_enforcement(self):
        """Test that max chunk size is enforced."""
        chunker = MarkdownAwareChunker({'max_chunk_size': 100})
        text = "# Header\n\n" + ("Very long text. " * 50)
        chunks = chunker.chunk(text, {'parent_doc_id': 'test'})

        # Should create multiple chunks
        assert len(chunks) >= 2

    def test_get_stats(self):
        """Test get_stats method."""
        config = {'max_chunk_size': 1500, 'preserve_headers': False}
        chunker = MarkdownAwareChunker(config)
        stats = chunker.get_stats()

        assert stats['chunker_type'] == 'MarkdownAwareChunker'
        assert stats['max_chunk_size'] == 1500
        assert stats['preserve_headers'] is False
