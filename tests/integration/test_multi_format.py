"""Integration tests for multi-format document conversion.

Tests real conversion of various document formats using actual test files.
"""

import pytest
from pathlib import Path

from knowledgebeast.core.converters import (
    DoclingConverter,
    FallbackConverter,
    get_document_converter,
    DOCLING_AVAILABLE
)


# Get path to fixtures
FIXTURES_DIR = Path(__file__).parent.parent / 'fixtures'


class TestMultiFormatConversion:
    """Test conversion of multiple document formats."""

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_convert_markdown(self):
        """Test converting markdown file."""
        converter = DoclingConverter()
        test_file = FIXTURES_DIR / 'sample.md'

        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        result = converter.convert(test_file)

        assert result.document.name is not None
        content = result.document.export_to_markdown()
        assert len(content) > 0
        assert 'Sample Markdown' in content or 'markdown' in content.lower()

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_convert_text(self):
        """Test converting plain text file."""
        converter = DoclingConverter()
        test_file = FIXTURES_DIR / 'sample.txt'

        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        result = converter.convert(test_file)

        assert result.document.name is not None
        content = result.document.export_to_markdown()
        assert len(content) > 0

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_convert_html(self):
        """Test converting HTML file."""
        converter = DoclingConverter()
        test_file = FIXTURES_DIR / 'sample.html'

        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        result = converter.convert(test_file)

        assert result.document.name is not None
        content = result.document.export_to_markdown()
        assert len(content) > 0

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_convert_pdf(self):
        """Test converting PDF file."""
        converter = DoclingConverter()
        test_file = FIXTURES_DIR / 'sample.pdf'

        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        result = converter.convert(test_file)

        assert result.document.name is not None
        content = result.document.export_to_markdown()
        assert len(content) > 0

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_convert_docx(self):
        """Test converting DOCX file."""
        converter = DoclingConverter()
        test_file = FIXTURES_DIR / 'sample.docx'

        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        result = converter.convert(test_file)

        assert result.document.name is not None
        content = result.document.export_to_markdown()
        assert len(content) > 0

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_convert_doc(self):
        """Test converting DOC file."""
        converter = DoclingConverter()
        test_file = FIXTURES_DIR / 'sample.doc'

        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        result = converter.convert(test_file)

        assert result.document.name is not None
        content = result.document.export_to_markdown()
        assert len(content) > 0

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_convert_pptx(self):
        """Test converting PPTX file."""
        converter = DoclingConverter()
        test_file = FIXTURES_DIR / 'sample.pptx'

        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        result = converter.convert(test_file)

        assert result.document.name is not None
        content = result.document.export_to_markdown()
        assert len(content) > 0


class TestChunkingIntegration:
    """Test chunking with real documents."""

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_chunking_markdown_file(self):
        """Test chunking a real markdown file."""
        converter = DoclingConverter(chunk_size=500, chunk_overlap=100)
        test_file = FIXTURES_DIR / 'sample.md'

        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        result = converter.convert(test_file, enable_chunking=True)

        assert len(result.chunks) > 0
        assert all('text' in chunk for chunk in result.chunks)
        assert all('chunk_index' in chunk for chunk in result.chunks)
        assert all('metadata' in chunk for chunk in result.chunks)

        # Verify chunk indices are sequential
        for i, chunk in enumerate(result.chunks):
            assert chunk['chunk_index'] == i

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_chunking_text_file(self):
        """Test chunking a real text file."""
        converter = DoclingConverter(chunk_size=300, chunk_overlap=50)
        test_file = FIXTURES_DIR / 'sample.txt'

        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        result = converter.convert(test_file, enable_chunking=True)

        assert len(result.chunks) > 0

        # Verify chunks have metadata
        for chunk in result.chunks:
            assert 'metadata' in chunk
            assert chunk['metadata']['filename'] == 'sample.txt'
            assert chunk['metadata']['format'] == '.txt'

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_chunking_disabled(self):
        """Test conversion without chunking."""
        converter = DoclingConverter()
        test_file = FIXTURES_DIR / 'sample.md'

        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        result = converter.convert(test_file, enable_chunking=False)

        assert result.chunks == []

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_chunk_overlap_verification(self):
        """Test that chunk overlap is working correctly."""
        converter = DoclingConverter(chunk_size=200, chunk_overlap=50)
        test_file = FIXTURES_DIR / 'sample.txt'

        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        result = converter.convert(test_file, enable_chunking=True)

        if len(result.chunks) > 1:
            # Check that consecutive chunks have overlap
            for i in range(len(result.chunks) - 1):
                chunk1 = result.chunks[i]
                chunk2 = result.chunks[i + 1]

                # Overlap should be roughly the configured amount
                overlap = chunk1['end_pos'] - chunk2['start_pos']
                assert overlap >= 0, "Chunks should overlap or be adjacent"
                assert overlap <= 60, "Overlap should not exceed configured + boundary adjustment"


class TestMetadataIntegration:
    """Test metadata extraction with real files."""

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_metadata_extraction_markdown(self):
        """Test metadata extraction from markdown file."""
        converter = DoclingConverter()
        test_file = FIXTURES_DIR / 'sample.md'

        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        result = converter.convert(test_file)

        metadata = result.metadata
        assert metadata['filename'] == 'sample.md'
        assert metadata['format'] == '.md'
        assert metadata['title'] == 'sample'
        assert 'created' in metadata
        assert 'modified' in metadata
        assert metadata['size_bytes'] > 0

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_metadata_extraction_pdf(self):
        """Test metadata extraction from PDF file."""
        converter = DoclingConverter()
        test_file = FIXTURES_DIR / 'sample.pdf'

        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        result = converter.convert(test_file)

        metadata = result.metadata
        assert metadata['filename'] == 'sample.pdf'
        assert metadata['format'] == '.pdf'
        assert 'created' in metadata
        assert 'modified' in metadata

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_metadata_in_chunks(self):
        """Test that chunks include metadata."""
        converter = DoclingConverter(chunk_size=300, chunk_overlap=50)
        test_file = FIXTURES_DIR / 'sample.md'

        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        result = converter.convert(test_file, enable_chunking=True)

        for chunk in result.chunks:
            assert 'metadata' in chunk
            assert chunk['metadata']['filename'] == 'sample.md'
            assert chunk['metadata']['format'] == '.md'


class TestBackwardCompatibility:
    """Test backward compatibility with FallbackConverter."""

    def test_fallback_converter_markdown(self):
        """Test FallbackConverter still works for markdown."""
        converter = FallbackConverter()
        test_file = FIXTURES_DIR / 'sample.md'

        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        result = converter.convert(test_file)

        assert result.document.name == 'sample'
        content = result.document.export_to_markdown()
        assert len(content) > 0

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_get_converter_returns_docling(self):
        """Test get_document_converter returns DoclingConverter when available."""
        converter = get_document_converter()

        assert isinstance(converter, DoclingConverter)

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_get_converter_can_return_fallback(self):
        """Test get_document_converter can return FallbackConverter explicitly."""
        converter = get_document_converter(use_docling=False)

        assert isinstance(converter, FallbackConverter)


class TestErrorHandling:
    """Test error handling with real scenarios."""

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_unsupported_format_error(self):
        """Test error for unsupported file format."""
        converter = DoclingConverter()
        test_file = FIXTURES_DIR / 'sample.jpg'  # Unsupported

        # Create a dummy file
        test_file.parent.mkdir(parents=True, exist_ok=True)
        if not test_file.exists():
            test_file.write_bytes(b'fake image data')

        with pytest.raises(ValueError, match="Unsupported format"):
            converter.convert(test_file)

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_missing_file_error(self):
        """Test error for missing file."""
        converter = DoclingConverter()
        test_file = FIXTURES_DIR / 'nonexistent.pdf'

        with pytest.raises(FileNotFoundError):
            converter.convert(test_file)

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_corrupted_file_handling(self, tmp_path):
        """Test handling of corrupted files."""
        converter = DoclingConverter()
        test_file = tmp_path / 'corrupted.pdf'
        test_file.write_bytes(b'This is not a valid PDF')

        # Should raise RuntimeError for conversion failure
        with pytest.raises(RuntimeError, match="Conversion failed"):
            converter.convert(test_file)


class TestEndToEndWorkflow:
    """Test complete end-to-end conversion workflows."""

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_complete_conversion_workflow(self):
        """Test complete workflow: load, convert, chunk, extract metadata."""
        # Initialize converter with custom settings
        converter = DoclingConverter(chunk_size=500, chunk_overlap=100)

        test_file = FIXTURES_DIR / 'sample.md'
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        # Convert document
        result = converter.convert(test_file, enable_chunking=True)

        # Verify all components
        assert result.document is not None
        assert result.document.name is not None
        assert callable(result.document.export_to_markdown)

        content = result.document.export_to_markdown()
        assert len(content) > 0

        assert len(result.chunks) > 0
        assert all('text' in chunk for chunk in result.chunks)

        assert result.metadata is not None
        assert result.metadata['filename'] == 'sample.md'

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_batch_conversion(self):
        """Test converting multiple files in sequence."""
        converter = DoclingConverter()

        test_files = [
            FIXTURES_DIR / 'sample.md',
            FIXTURES_DIR / 'sample.txt',
            FIXTURES_DIR / 'sample.html',
        ]

        results = []
        for test_file in test_files:
            if test_file.exists():
                result = converter.convert(test_file)
                results.append(result)

        assert len(results) > 0
        assert all(hasattr(r, 'document') for r in results)
        assert all(hasattr(r, 'metadata') for r in results)

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_different_chunk_sizes(self):
        """Test conversion with different chunk sizes."""
        test_file = FIXTURES_DIR / 'sample.md'
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        # Small chunks
        converter_small = DoclingConverter(chunk_size=100, chunk_overlap=20)
        result_small = converter_small.convert(test_file, enable_chunking=True)

        # Large chunks
        converter_large = DoclingConverter(chunk_size=1000, chunk_overlap=200)
        result_large = converter_large.convert(test_file, enable_chunking=True)

        # Small chunks should produce more chunks
        if len(result_small.chunks) > 0 and len(result_large.chunks) > 0:
            assert len(result_small.chunks) >= len(result_large.chunks)


class TestPerformance:
    """Test performance characteristics."""

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_converter_reusability(self):
        """Test that converter can be reused efficiently."""
        converter = DoclingConverter()

        test_files = [
            FIXTURES_DIR / 'sample.md',
            FIXTURES_DIR / 'sample.txt',
        ]

        # Convert multiple files with same converter
        for test_file in test_files:
            if test_file.exists():
                result = converter.convert(test_file)
                assert result is not None

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
    def test_large_chunk_count(self):
        """Test handling of files that produce many chunks."""
        converter = DoclingConverter(chunk_size=50, chunk_overlap=10)
        test_file = FIXTURES_DIR / 'sample.md'

        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        result = converter.convert(test_file, enable_chunking=True)

        # Should handle many chunks efficiently
        assert len(result.chunks) < 1000  # Reasonable limit
        assert all('chunk_index' in chunk for chunk in result.chunks)
