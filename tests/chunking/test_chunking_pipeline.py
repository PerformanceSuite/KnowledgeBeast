"""Tests for ChunkProcessor pipeline."""

import pytest
from knowledgebeast.core.chunk_processor import ChunkProcessor
from knowledgebeast.core.chunking.base import Chunk


class TestChunkProcessor:
    """Test suite for ChunkProcessor (15 tests)."""

    def test_initialization_default(self):
        """Test processor initialization with defaults."""
        processor = ChunkProcessor()
        assert processor.default_strategy == 'auto'
        assert len(processor.chunkers) == 4  # semantic, recursive, markdown, code

    def test_initialization_custom_config(self):
        """Test processor with custom configuration."""
        config = {
            'strategy': 'semantic',
            'chunk_size': 256,
            'semantic_similarity_threshold': 0.8
        }
        processor = ChunkProcessor(config)
        assert processor.default_strategy == 'semantic'

    def test_empty_text_processing(self):
        """Test processing empty text."""
        processor = ChunkProcessor()
        chunks = processor.process("")
        assert chunks == []

    def test_explicit_strategy_selection(self):
        """Test explicit strategy selection."""
        processor = ChunkProcessor()
        text = "Test text for chunking."

        chunks_semantic = processor.process(text, strategy='semantic',
                                           metadata={'parent_doc_id': 'test'})
        chunks_recursive = processor.process(text, strategy='recursive',
                                            metadata={'parent_doc_id': 'test'})

        # Both should produce chunks
        assert len(chunks_semantic) >= 1
        assert len(chunks_recursive) >= 1

    def test_auto_strategy_markdown(self):
        """Test auto strategy selects markdown for .md files."""
        processor = ChunkProcessor({'strategy': 'auto'})
        text = "# Header\n\nContent here."
        metadata = {'parent_doc_id': 'test', 'file_path': 'test.md'}

        chunks = processor.process(text, metadata)

        # Should use markdown strategy
        assert len(chunks) >= 1
        assert chunks[0].metadata.get('chunking_strategy') == 'markdown'

    def test_auto_strategy_code(self):
        """Test auto strategy selects code for Python files."""
        processor = ChunkProcessor({'strategy': 'auto'})
        code = "def test(): pass"
        metadata = {'parent_doc_id': 'test', 'file_path': 'test.py'}

        chunks = processor.process(code, metadata)

        # Should use code strategy
        assert len(chunks) >= 1
        assert chunks[0].metadata.get('chunking_strategy') == 'code'

    def test_auto_strategy_semantic(self):
        """Test auto strategy uses semantic for prose."""
        processor = ChunkProcessor({'strategy': 'auto'})
        text = "This is prose. It has multiple sentences. They form paragraphs. This is important. We should detect this."
        metadata = {'parent_doc_id': 'test'}

        chunks = processor.process(text, metadata)

        # Should use semantic or recursive
        assert len(chunks) >= 1
        strategy = chunks[0].metadata.get('chunking_strategy')
        assert strategy in ('semantic', 'recursive')

    def test_metadata_enrichment(self):
        """Test that chunks are enriched with metadata."""
        processor = ChunkProcessor()
        text = "Test text for chunking and metadata enrichment."
        chunks = processor.process(text, {'parent_doc_id': 'test'}, strategy='recursive')

        for chunk in chunks:
            assert 'chunking_strategy' in chunk.metadata
            assert 'char_count' in chunk.metadata
            assert 'word_count' in chunk.metadata

    def test_batch_processing(self):
        """Test batch processing of multiple documents."""
        processor = ChunkProcessor()
        documents = [
            {'text': 'First document text.', 'metadata': {'parent_doc_id': 'doc1'}},
            {'text': 'Second document text.', 'metadata': {'parent_doc_id': 'doc2'}},
            {'text': 'Third document text.', 'metadata': {'parent_doc_id': 'doc3'}},
        ]

        chunks = processor.process_batch(documents)

        # Should have chunks from all documents
        assert len(chunks) >= 3
        doc_ids = {c.metadata.get('parent_doc_id') for c in chunks}
        assert 'doc1' in doc_ids
        assert 'doc2' in doc_ids
        assert 'doc3' in doc_ids

    def test_batch_with_different_strategies(self):
        """Test batch processing with different strategies per document."""
        processor = ChunkProcessor()
        documents = [
            {
                'text': 'def test(): pass',
                'metadata': {'parent_doc_id': 'code'},
                'strategy': 'code'
            },
            {
                'text': '# Markdown\n\nContent',
                'metadata': {'parent_doc_id': 'md'},
                'strategy': 'markdown'
            },
        ]

        chunks = processor.process_batch(documents)

        strategies = {c.metadata.get('chunking_strategy') for c in chunks}
        assert 'code' in strategies
        assert 'markdown' in strategies

    def test_stats_tracking(self):
        """Test that processor tracks statistics."""
        processor = ChunkProcessor()
        processor.process("Test text 1.", {'parent_doc_id': 'test1'})
        processor.process("Test text 2.", {'parent_doc_id': 'test2'})

        stats = processor.get_stats()
        assert stats['total_documents'] == 2
        assert stats['total_chunks'] >= 2
        assert 'strategy_usage' in stats

    def test_stats_reset(self):
        """Test statistics reset functionality."""
        processor = ChunkProcessor()
        processor.process("Test text.", {'parent_doc_id': 'test'})

        processor.reset_stats()
        stats = processor.get_stats()

        assert stats['total_documents'] == 0
        assert stats['total_chunks'] == 0

    def test_fallback_strategy(self):
        """Test fallback to recursive when invalid strategy given."""
        processor = ChunkProcessor()
        chunks = processor.process(
            "Test text.",
            {'parent_doc_id': 'test'},
            strategy='invalid_strategy'
        )

        # Should fallback to recursive
        assert len(chunks) >= 1
        assert chunks[0].metadata.get('chunking_strategy') == 'recursive'

    def test_get_stats_structure(self):
        """Test get_stats returns proper structure."""
        processor = ChunkProcessor({'strategy': 'semantic'})
        stats = processor.get_stats()

        assert 'total_chunks' in stats
        assert 'total_documents' in stats
        assert 'total_bytes' in stats
        assert 'strategy_usage' in stats
        assert 'config' in stats
        assert 'available_strategies' in stats
        assert len(stats['available_strategies']) == 4

    def test_overlap_ratio_calculation(self):
        """Test overlap ratio calculation for chunks."""
        processor = ChunkProcessor({
            'chunk_size': 100,
            'chunk_overlap': 25
        })
        text = "Long text that will be split. " * 20
        chunks = processor.process(text, {'parent_doc_id': 'test'}, strategy='recursive')

        # Second chunk onwards should have overlap_ratio
        if len(chunks) > 1:
            assert 'overlap_ratio' in chunks[1].metadata
            assert 0 <= chunks[1].metadata['overlap_ratio'] <= 1
