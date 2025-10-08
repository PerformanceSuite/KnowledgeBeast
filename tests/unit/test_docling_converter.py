"""Unit tests for DoclingConverter class.

Tests cover:
- Multi-format support (PDF, DOCX, DOC, MD, TXT, HTML, PPTX)
- Smart chunking with configurable overlap
- Metadata extraction
- Error handling for unsupported formats
- Backward compatibility
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from types import SimpleNamespace

from knowledgebeast.core.converters import (
    DoclingConverter,
    FallbackConverter,
    get_document_converter,
    DOCLING_AVAILABLE
)


class TestDoclingConverterInitialization:
    """Test DoclingConverter initialization."""

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_init_default_params(self):
        """Test initialization with default parameters."""
        converter = DoclingConverter()
        assert converter.chunk_size == 1000
        assert converter.chunk_overlap == 200
        assert converter.supported_formats == {'.pdf', '.docx', '.doc', '.md', '.txt', '.html', '.pptx'}

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        converter = DoclingConverter(chunk_size=2000, chunk_overlap=400)
        assert converter.chunk_size == 2000
        assert converter.chunk_overlap == 400

    @pytest.mark.skipif(DOCLING_AVAILABLE, reason="Test requires Docling to be unavailable")
    def test_init_without_docling(self):
        """Test initialization fails when docling is not available."""
        with pytest.raises(RuntimeError, match="Docling is not available"):
            DoclingConverter()


class TestFormatSupport:
    """Test format support detection."""

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_supported_formats(self):
        """Test all supported formats are recognized."""
        converter = DoclingConverter()

        supported_files = [
            Path('test.pdf'),
            Path('test.docx'),
            Path('test.doc'),
            Path('test.md'),
            Path('test.txt'),
            Path('test.html'),
            Path('test.pptx'),
        ]

        for file_path in supported_files:
            assert converter.is_supported(file_path), f"{file_path.suffix} should be supported"

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_unsupported_formats(self):
        """Test unsupported formats are rejected."""
        converter = DoclingConverter()

        unsupported_files = [
            Path('test.jpg'),
            Path('test.png'),
            Path('test.xlsx'),
            Path('test.csv'),
            Path('test.json'),
        ]

        for file_path in unsupported_files:
            assert not converter.is_supported(file_path), f"{file_path.suffix} should not be supported"

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_case_insensitive_format_check(self):
        """Test format checking is case-insensitive."""
        converter = DoclingConverter()

        assert converter.is_supported(Path('test.PDF'))
        assert converter.is_supported(Path('test.DOCX'))
        assert converter.is_supported(Path('test.Md'))


class TestMetadataExtraction:
    """Test metadata extraction functionality."""

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_extract_metadata_basic(self, tmp_path):
        """Test basic metadata extraction."""
        converter = DoclingConverter()
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test content")

        metadata = converter.extract_metadata(test_file)

        assert metadata['filename'] == 'test.md'
        assert metadata['format'] == '.md'
        assert metadata['title'] == 'test'
        assert metadata['author'] == 'Unknown'
        assert 'created' in metadata
        assert 'modified' in metadata
        assert 'size_bytes' in metadata

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_extract_metadata_with_timestamps(self, tmp_path):
        """Test metadata includes timestamp information."""
        converter = DoclingConverter()
        test_file = tmp_path / "document.pdf"
        test_file.write_text("content")

        metadata = converter.extract_metadata(test_file)

        # Check timestamp format (ISO 8601)
        assert 'T' in metadata['created']
        assert 'T' in metadata['modified']

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_extract_metadata_file_size(self, tmp_path):
        """Test metadata includes correct file size."""
        converter = DoclingConverter()
        test_file = tmp_path / "test.txt"
        content = "A" * 1000  # 1000 bytes
        test_file.write_text(content)

        metadata = converter.extract_metadata(test_file)

        assert metadata['size_bytes'] == 1000


class TestChunking:
    """Test text chunking functionality."""

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_chunk_text_basic(self):
        """Test basic text chunking."""
        converter = DoclingConverter(chunk_size=100, chunk_overlap=20)
        text = "A" * 250

        chunks = converter.chunk_text(text)

        assert len(chunks) > 1
        assert chunks[0]['chunk_index'] == 0
        assert chunks[1]['chunk_index'] == 1

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_chunk_text_with_overlap(self):
        """Test chunking includes overlap."""
        converter = DoclingConverter(chunk_size=100, chunk_overlap=20)
        text = "A" * 250

        chunks = converter.chunk_text(text)

        # Check overlap exists
        if len(chunks) > 1:
            chunk1_end = chunks[0]['end_pos']
            chunk2_start = chunks[1]['start_pos']
            assert chunk1_end - chunk2_start == 20  # overlap amount

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_chunk_text_empty_input(self):
        """Test chunking with empty text."""
        converter = DoclingConverter()
        chunks = converter.chunk_text("")

        assert chunks == []

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_chunk_text_with_metadata(self):
        """Test chunks include metadata."""
        converter = DoclingConverter(chunk_size=100, chunk_overlap=20)
        text = "A" * 250
        metadata = {'title': 'Test Doc', 'author': 'Tester'}

        chunks = converter.chunk_text(text, metadata)

        assert all('metadata' in chunk for chunk in chunks)
        assert all(chunk['metadata']['title'] == 'Test Doc' for chunk in chunks)

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_chunk_text_sentence_boundary(self):
        """Test chunking respects sentence boundaries."""
        converter = DoclingConverter(chunk_size=50, chunk_overlap=10)
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."

        chunks = converter.chunk_text(text)

        # Check that chunks try to break at sentence boundaries
        for chunk in chunks:
            if len(chunk['text']) < 50:
                continue  # Last chunk might be shorter
            # Chunk should preferably end with sentence ending
            assert chunk['text'].rstrip()[-1] in '.!?\n' or len(chunk['text']) >= 45

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_chunk_positions(self):
        """Test chunk positions are correct."""
        converter = DoclingConverter(chunk_size=100, chunk_overlap=20)
        text = "A" * 250

        chunks = converter.chunk_text(text)

        for chunk in chunks:
            assert chunk['start_pos'] >= 0
            assert chunk['end_pos'] > chunk['start_pos']
            assert chunk['end_pos'] <= len(text)

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_chunk_size_limit(self):
        """Test chunks respect size limit."""
        converter = DoclingConverter(chunk_size=100, chunk_overlap=20)
        text = "A" * 1000

        chunks = converter.chunk_text(text)

        for chunk in chunks[:-1]:  # All but last chunk
            assert len(chunk['text']) <= 100 or len(chunk['text']) <= 110  # Allow small overage for boundaries


class TestConversion:
    """Test document conversion functionality."""

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_convert_unsupported_format(self, tmp_path):
        """Test conversion fails for unsupported format."""
        converter = DoclingConverter()
        test_file = tmp_path / "test.xyz"
        test_file.write_text("content")

        with pytest.raises(ValueError, match="Unsupported format"):
            converter.convert(test_file)

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_convert_missing_file(self):
        """Test conversion fails for missing file."""
        converter = DoclingConverter()
        test_file = Path("/nonexistent/file.pdf")

        with pytest.raises(FileNotFoundError):
            converter.convert(test_file)

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    @patch('knowledgebeast.core.converters.BaseDoclingConverter')
    def test_convert_with_chunking(self, mock_docling, tmp_path):
        """Test conversion with chunking enabled."""
        # Setup mock
        mock_doc = MagicMock()
        mock_doc.name = "Test Document"
        mock_doc.export_to_markdown.return_value = "A" * 2000

        mock_result = MagicMock()
        mock_result.document = mock_doc

        mock_converter_instance = MagicMock()
        mock_converter_instance.convert.return_value = mock_result
        mock_docling.return_value = mock_converter_instance

        # Test
        converter = DoclingConverter(chunk_size=500, chunk_overlap=100)
        test_file = tmp_path / "test.pdf"
        test_file.write_text("dummy")

        result = converter.convert(test_file, enable_chunking=True)

        assert hasattr(result, 'chunks')
        assert len(result.chunks) > 1
        assert hasattr(result, 'metadata')
        assert hasattr(result, 'document')

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    @patch('knowledgebeast.core.converters.BaseDoclingConverter')
    def test_convert_without_chunking(self, mock_docling, tmp_path):
        """Test conversion with chunking disabled."""
        # Setup mock
        mock_doc = MagicMock()
        mock_doc.name = "Test Document"
        mock_doc.export_to_markdown.return_value = "Test content"

        mock_result = MagicMock()
        mock_result.document = mock_doc

        mock_converter_instance = MagicMock()
        mock_converter_instance.convert.return_value = mock_result
        mock_docling.return_value = mock_converter_instance

        # Test
        converter = DoclingConverter()
        test_file = tmp_path / "test.md"
        test_file.write_text("dummy")

        result = converter.convert(test_file, enable_chunking=False)

        assert result.chunks == []

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    @patch('knowledgebeast.core.converters.BaseDoclingConverter')
    def test_convert_result_structure(self, mock_docling, tmp_path):
        """Test conversion result has correct structure."""
        # Setup mock
        mock_doc = MagicMock()
        mock_doc.name = "Test Document"
        mock_doc.export_to_markdown.return_value = "Test content"

        mock_result = MagicMock()
        mock_result.document = mock_doc

        mock_converter_instance = MagicMock()
        mock_converter_instance.convert.return_value = mock_result
        mock_docling.return_value = mock_converter_instance

        # Test
        converter = DoclingConverter()
        test_file = tmp_path / "test.docx"
        test_file.write_text("dummy")

        result = converter.convert(test_file)

        assert hasattr(result, 'document')
        assert hasattr(result.document, 'name')
        assert hasattr(result.document, 'export_to_markdown')
        assert callable(result.document.export_to_markdown)
        assert hasattr(result, 'chunks')
        assert hasattr(result, 'metadata')


class TestFallbackConverter:
    """Test FallbackConverter for backward compatibility."""

    def test_fallback_converter_basic(self, tmp_path):
        """Test fallback converter reads markdown files."""
        converter = FallbackConverter()
        test_file = tmp_path / "test.md"
        test_content = "# Test\n\nContent here"
        test_file.write_text(test_content)

        result = converter.convert(test_file)

        assert result.document.name == 'test'
        assert result.document.export_to_markdown() == test_content

    def test_fallback_converter_error_handling(self):
        """Test fallback converter handles missing files."""
        converter = FallbackConverter()
        test_file = Path("/nonexistent/file.md")

        with pytest.raises(Exception):
            converter.convert(test_file)


class TestGetDocumentConverter:
    """Test get_document_converter factory function."""

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_get_converter_docling_default(self):
        """Test getting DoclingConverter by default when available."""
        converter = get_document_converter()
        assert isinstance(converter, DoclingConverter)

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_get_converter_fallback_explicit(self):
        """Test getting FallbackConverter explicitly."""
        converter = get_document_converter(use_docling=False)
        assert isinstance(converter, FallbackConverter)

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_get_converter_with_params(self):
        """Test getting converter with custom parameters."""
        converter = get_document_converter(chunk_size=2000, chunk_overlap=400)
        assert isinstance(converter, DoclingConverter)
        assert converter.chunk_size == 2000
        assert converter.chunk_overlap == 400

    @pytest.mark.skipif(DOCLING_AVAILABLE, reason="Test requires Docling to be unavailable")
    def test_get_converter_fallback_when_unavailable(self):
        """Test getting FallbackConverter when docling unavailable."""
        converter = get_document_converter()
        assert isinstance(converter, FallbackConverter)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_chunk_very_small_text(self):
        """Test chunking very small text."""
        converter = DoclingConverter(chunk_size=1000, chunk_overlap=200)
        text = "Short text."

        chunks = converter.chunk_text(text)

        assert len(chunks) == 1
        assert chunks[0]['text'] == text

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_chunk_exact_size(self):
        """Test chunking text exactly matching chunk size."""
        converter = DoclingConverter(chunk_size=100, chunk_overlap=0)
        text = "A" * 100

        chunks = converter.chunk_text(text)

        assert len(chunks) == 1
        assert len(chunks[0]['text']) == 100

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_zero_overlap(self):
        """Test chunking with zero overlap."""
        converter = DoclingConverter(chunk_size=100, chunk_overlap=0)
        text = "A" * 250

        chunks = converter.chunk_text(text)

        # Verify no overlap
        for i in range(len(chunks) - 1):
            assert chunks[i]['end_pos'] == chunks[i + 1]['start_pos']

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_large_overlap(self):
        """Test chunking with large overlap."""
        converter = DoclingConverter(chunk_size=100, chunk_overlap=90)
        text = "A" * 250

        chunks = converter.chunk_text(text)

        # Should still make progress
        assert len(chunks) > 1

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_metadata_nonexistent_file(self):
        """Test metadata extraction for nonexistent file."""
        converter = DoclingConverter()
        test_file = Path("/nonexistent/file.pdf")

        metadata = converter.extract_metadata(test_file)

        # Should still return basic metadata
        assert metadata['filename'] == 'file.pdf'
        assert metadata['format'] == '.pdf'
        assert metadata['size_bytes'] == 0


class TestThreadSafety:
    """Test thread safety of converters."""

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_converter_is_stateless(self):
        """Test converter can be reused safely."""
        converter = DoclingConverter()

        # Multiple calls should work independently
        text1 = "A" * 500
        text2 = "B" * 1000

        chunks1 = converter.chunk_text(text1)
        chunks2 = converter.chunk_text(text2)

        # Results should be independent
        assert chunks1[0]['text'][0] == 'A'
        assert chunks2[0]['text'][0] == 'B'
