"""Tests for CodeAwareChunker."""

import pytest
from knowledgebeast.core.chunking.code import CodeAwareChunker, Language


class TestCodeAwareChunker:
    """Test suite for CodeAwareChunker (8 tests)."""

    def test_initialization(self):
        """Test chunker initialization."""
        chunker = CodeAwareChunker({'max_chunk_size': 50})
        assert chunker.max_chunk_size == 50
        assert chunker.preserve_imports is True

    def test_empty_text(self):
        """Test chunking empty code."""
        chunker = CodeAwareChunker()
        assert chunker.chunk("") == []

    def test_python_function_detection(self):
        """Test Python function boundary detection."""
        chunker = CodeAwareChunker()
        code = """
import os

def hello():
    print("Hello")
    return True

def goodbye():
    print("Goodbye")
"""
        chunks = chunker.chunk(code, {
            'parent_doc_id': 'test',
            'language': 'python'
        })

        # Should detect both functions
        assert len(chunks) >= 2
        func_names = {c.metadata.get('code_unit_name') for c in chunks}
        assert 'hello' in func_names or 'goodbye' in func_names

    def test_python_class_detection(self):
        """Test Python class detection."""
        chunker = CodeAwareChunker()
        code = """
class MyClass:
    def __init__(self):
        self.value = 0

    def method(self):
        return self.value
"""
        chunks = chunker.chunk(code, {
            'parent_doc_id': 'test',
            'language': 'python'
        })

        # Should detect class
        assert len(chunks) >= 1
        has_class = any(c.metadata.get('code_unit_type') == 'class' for c in chunks)
        assert has_class

    def test_language_detection_from_extension(self):
        """Test language detection from file extension."""
        chunker = CodeAwareChunker()
        code = "def test(): pass"

        chunks = chunker.chunk(code, {
            'parent_doc_id': 'test',
            'file_path': '/path/to/file.py'
        })

        assert len(chunks) >= 1
        assert chunks[0].metadata.get('language') == 'python'

    def test_import_preservation(self):
        """Test that imports are preserved with chunks."""
        chunker = CodeAwareChunker({'preserve_imports': True})
        code = """
import os
import sys

def function():
    pass
"""
        chunks = chunker.chunk(code, {
            'parent_doc_id': 'test',
            'language': 'python'
        })

        # Imports should be included
        has_imports = any('import os' in c.text for c in chunks)
        assert has_imports

    def test_metadata_structure(self):
        """Test chunk metadata structure."""
        chunker = CodeAwareChunker()
        code = """
def test_function():
    return 42
"""
        chunks = chunker.chunk(code, {
            'parent_doc_id': 'doc1',
            'language': 'python'
        })

        for chunk in chunks:
            assert 'chunk_type' in chunk.metadata
            assert chunk.metadata['chunk_type'] == 'code'
            assert 'code_unit_type' in chunk.metadata
            assert 'code_unit_name' in chunk.metadata
            assert 'language' in chunk.metadata

    def test_get_stats(self):
        """Test get_stats method."""
        config = {'max_chunk_size': 75, 'preserve_imports': False}
        chunker = CodeAwareChunker(config)
        stats = chunker.get_stats()

        assert stats['chunker_type'] == 'CodeAwareChunker'
        assert stats['max_chunk_size'] == 75
        assert stats['preserve_imports'] is False
        assert 'supported_languages' in stats
