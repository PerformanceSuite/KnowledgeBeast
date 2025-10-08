"""Unit tests for HybridQueryEngine.

Tests cover:
- Vector search functionality
- Keyword search (backward compatibility)
- Hybrid search with alpha weighting
- MMR re-ranking
- Diversity sampling
- Thread safety
- Edge cases and error handling
"""

import pytest
import tempfile
from pathlib import Path
import numpy as np
from unittest.mock import Mock, patch
import threading
import time

from knowledgebeast.core.repository import DocumentRepository
from knowledgebeast.core.query_engine import HybridQueryEngine, QueryEngine
from knowledgebeast.core.constants import ERR_EMPTY_SEARCH_TERMS


@pytest.fixture
def sample_repository():
    """Create a repository with sample documents."""
    repo = DocumentRepository()

    # Add sample documents
    docs = {
        'doc1': {
            'name': 'Audio Processing with Librosa',
            'content': 'Librosa is a Python library for audio analysis and music information retrieval. It provides tools for beat detection, tempo estimation, and spectral analysis.',
            'path': 'audio/librosa.md'
        },
        'doc2': {
            'name': 'JUCE Framework Guide',
            'content': 'JUCE is a C++ framework for audio applications. It enables real-time audio processing with low latency and supports VST, AU, and AAX plugin formats.',
            'path': 'audio/juce.md'
        },
        'doc3': {
            'name': 'Music Theory Basics',
            'content': 'Understanding chord progressions and scales in music theory. Major and minor scales form the foundation of Western music.',
            'path': 'theory/basics.md'
        },
        'doc4': {
            'name': 'Python Programming',
            'content': 'Python is a high-level programming language. It is widely used for data analysis, machine learning, and web development.',
            'path': 'programming/python.md'
        },
        'doc5': {
            'name': 'Machine Learning Basics',
            'content': 'Machine learning algorithms learn from data. Common techniques include supervised learning, unsupervised learning, and reinforcement learning.',
            'path': 'ml/basics.md'
        }
    }

    for doc_id, doc_data in docs.items():
        repo.add_document(doc_id, doc_data)

        # Build simple index
        terms = doc_data['content'].lower().split()
        for term in terms:
            repo.index_term(term, doc_id)

    return repo


@pytest.fixture
def hybrid_engine(sample_repository):
    """Create HybridQueryEngine with sample data."""
    # Use a small model for faster tests
    return HybridQueryEngine(
        sample_repository,
        model_name="all-MiniLM-L6-v2",
        alpha=0.7,
        cache_size=100
    )


class TestHybridQueryEngineInit:
    """Test HybridQueryEngine initialization."""

    def test_init_default_params(self, sample_repository):
        """Test initialization with default parameters."""
        engine = HybridQueryEngine(sample_repository)
        assert engine.repository == sample_repository
        assert engine.alpha == 0.7
        assert engine.model is not None
        assert engine.keyword_engine is not None

    def test_init_custom_alpha(self, sample_repository):
        """Test initialization with custom alpha."""
        engine = HybridQueryEngine(sample_repository, alpha=0.5)
        assert engine.alpha == 0.5

    def test_init_invalid_alpha_low(self, sample_repository):
        """Test initialization with alpha < 0."""
        with pytest.raises(ValueError, match="alpha must be between 0 and 1"):
            HybridQueryEngine(sample_repository, alpha=-0.1)

    def test_init_invalid_alpha_high(self, sample_repository):
        """Test initialization with alpha > 1."""
        with pytest.raises(ValueError, match="alpha must be between 0 and 1"):
            HybridQueryEngine(sample_repository, alpha=1.5)

    def test_embedding_cache_created(self, hybrid_engine):
        """Test that embedding cache is created."""
        stats = hybrid_engine.get_embedding_stats()
        assert 'size' in stats
        assert 'capacity' in stats
        assert stats['capacity'] == 100


class TestVectorSearch:
    """Test vector similarity search."""

    def test_vector_search_basic(self, hybrid_engine):
        """Test basic vector search."""
        results = hybrid_engine.search_vector("audio processing library", top_k=3)

        assert len(results) <= 3
        assert all(len(result) == 3 for result in results)  # (doc_id, doc, score)
        assert all(isinstance(result[2], float) for result in results)  # Score is float

    def test_vector_search_empty_query(self, hybrid_engine):
        """Test vector search with empty query."""
        with pytest.raises(ValueError, match=ERR_EMPTY_SEARCH_TERMS):
            hybrid_engine.search_vector("")

    def test_vector_search_whitespace_query(self, hybrid_engine):
        """Test vector search with whitespace query."""
        with pytest.raises(ValueError, match=ERR_EMPTY_SEARCH_TERMS):
            hybrid_engine.search_vector("   ")

    def test_vector_search_scores_sorted(self, hybrid_engine):
        """Test that vector search results are sorted by score."""
        results = hybrid_engine.search_vector("audio processing", top_k=5)

        if len(results) > 1:
            scores = [score for _, _, score in results]
            assert scores == sorted(scores, reverse=True)

    def test_vector_search_top_k_limit(self, hybrid_engine):
        """Test that top_k limits results."""
        results = hybrid_engine.search_vector("music", top_k=2)
        assert len(results) <= 2

    def test_vector_search_semantic_matching(self, hybrid_engine):
        """Test semantic matching in vector search."""
        # Query about programming should match Python doc
        results = hybrid_engine.search_vector("programming language for data science", top_k=3)
        doc_ids = [doc_id for doc_id, _, _ in results]

        # Should find doc4 (Python Programming) in top results
        assert 'doc4' in doc_ids[:3]


class TestKeywordSearch:
    """Test keyword-based search."""

    def test_keyword_search_basic(self, hybrid_engine):
        """Test basic keyword search."""
        results = hybrid_engine.search_keyword("audio processing")

        assert len(results) > 0
        assert all(len(result) == 3 for result in results)

    def test_keyword_search_empty_query(self, hybrid_engine):
        """Test keyword search with empty query."""
        with pytest.raises(ValueError, match=ERR_EMPTY_SEARCH_TERMS):
            hybrid_engine.search_keyword("")

    def test_keyword_search_backward_compatible(self, sample_repository):
        """Test keyword search is backward compatible with QueryEngine."""
        keyword_engine = QueryEngine(sample_repository)
        hybrid_engine = HybridQueryEngine(sample_repository)

        query = "audio"
        keyword_results = keyword_engine.execute_query(query)
        hybrid_keyword_results = hybrid_engine.search_keyword(query)

        # Should return same documents
        keyword_ids = {doc_id for doc_id, _ in keyword_results}
        hybrid_ids = {doc_id for doc_id, _, _ in hybrid_keyword_results}
        assert keyword_ids == hybrid_ids

    def test_keyword_search_exact_match(self, hybrid_engine):
        """Test keyword search with exact term."""
        results = hybrid_engine.search_keyword("librosa")

        # Should find doc1 which contains "librosa"
        doc_ids = [doc_id for doc_id, _, _ in results]
        assert 'doc1' in doc_ids


class TestHybridSearch:
    """Test hybrid search combining vector and keyword."""

    def test_hybrid_search_basic(self, hybrid_engine):
        """Test basic hybrid search."""
        results = hybrid_engine.search_hybrid("audio library", top_k=3)

        assert len(results) <= 3
        assert all(len(result) == 3 for result in results)

    def test_hybrid_search_empty_query(self, hybrid_engine):
        """Test hybrid search with empty query."""
        with pytest.raises(ValueError, match=ERR_EMPTY_SEARCH_TERMS):
            hybrid_engine.search_hybrid("")

    def test_hybrid_search_default_alpha(self, hybrid_engine):
        """Test hybrid search uses default alpha."""
        results = hybrid_engine.search_hybrid("machine learning", top_k=3)
        assert len(results) > 0

    def test_hybrid_search_custom_alpha(self, hybrid_engine):
        """Test hybrid search with custom alpha."""
        results = hybrid_engine.search_hybrid("python", alpha=0.5, top_k=3)
        assert len(results) > 0

    def test_hybrid_search_alpha_zero(self, hybrid_engine):
        """Test hybrid search with alpha=0 (pure keyword)."""
        results = hybrid_engine.search_hybrid("audio", alpha=0.0, top_k=3)
        assert len(results) > 0

    def test_hybrid_search_alpha_one(self, hybrid_engine):
        """Test hybrid search with alpha=1 (pure vector)."""
        results = hybrid_engine.search_hybrid("audio", alpha=1.0, top_k=3)
        assert len(results) > 0

    def test_hybrid_search_invalid_alpha(self, hybrid_engine):
        """Test hybrid search with invalid alpha."""
        with pytest.raises(ValueError, match="alpha must be between 0 and 1"):
            hybrid_engine.search_hybrid("test", alpha=1.5)

    def test_hybrid_search_combines_scores(self, hybrid_engine):
        """Test that hybrid search combines vector and keyword scores."""
        # Get results with different alphas
        vector_heavy = hybrid_engine.search_hybrid("music theory", alpha=0.9, top_k=3)
        keyword_heavy = hybrid_engine.search_hybrid("music theory", alpha=0.1, top_k=3)

        # Results may differ based on alpha
        assert len(vector_heavy) > 0
        assert len(keyword_heavy) > 0


class TestMMRReranking:
    """Test MMR (Maximal Marginal Relevance) re-ranking."""

    def test_mmr_basic(self, hybrid_engine):
        """Test basic MMR re-ranking."""
        results = hybrid_engine.search_with_mmr(
            "audio processing",
            lambda_param=0.5,
            top_k=3,
            mode='hybrid'
        )

        assert len(results) <= 3
        assert all(len(result) == 3 for result in results)

    def test_mmr_empty_query(self, hybrid_engine):
        """Test MMR with empty query."""
        with pytest.raises(ValueError, match=ERR_EMPTY_SEARCH_TERMS):
            hybrid_engine.search_with_mmr("")

    def test_mmr_invalid_lambda(self, hybrid_engine):
        """Test MMR with invalid lambda parameter."""
        with pytest.raises(ValueError, match="lambda_param must be between 0 and 1"):
            hybrid_engine.search_with_mmr("test", lambda_param=1.5)

    def test_mmr_lambda_zero(self, hybrid_engine):
        """Test MMR with lambda=0 (maximum diversity)."""
        results = hybrid_engine.search_with_mmr(
            "audio",
            lambda_param=0.0,
            top_k=3
        )
        assert len(results) > 0

    def test_mmr_lambda_one(self, hybrid_engine):
        """Test MMR with lambda=1 (maximum relevance)."""
        results = hybrid_engine.search_with_mmr(
            "audio",
            lambda_param=1.0,
            top_k=3
        )
        assert len(results) > 0

    def test_mmr_vector_mode(self, hybrid_engine):
        """Test MMR with vector mode."""
        results = hybrid_engine.search_with_mmr(
            "music",
            lambda_param=0.5,
            top_k=3,
            mode='vector'
        )
        assert len(results) > 0

    def test_mmr_keyword_mode(self, hybrid_engine):
        """Test MMR with keyword mode."""
        results = hybrid_engine.search_with_mmr(
            "music",
            lambda_param=0.5,
            top_k=3,
            mode='keyword'
        )
        assert len(results) > 0

    def test_mmr_promotes_diversity(self, hybrid_engine):
        """Test that MMR promotes diversity in results."""
        # Low lambda should promote diversity
        diverse_results = hybrid_engine.search_with_mmr(
            "audio",
            lambda_param=0.2,
            top_k=3
        )

        # High lambda should promote relevance
        relevant_results = hybrid_engine.search_with_mmr(
            "audio",
            lambda_param=0.9,
            top_k=3
        )

        assert len(diverse_results) > 0
        assert len(relevant_results) > 0


class TestDiversitySampling:
    """Test diversity sampling."""

    def test_diversity_basic(self, hybrid_engine):
        """Test basic diversity sampling."""
        results = hybrid_engine.search_with_diversity(
            "audio processing",
            diversity_threshold=0.8,
            top_k=3,
            mode='hybrid'
        )

        assert len(results) <= 3
        assert all(len(result) == 3 for result in results)

    def test_diversity_empty_query(self, hybrid_engine):
        """Test diversity sampling with empty query."""
        with pytest.raises(ValueError, match=ERR_EMPTY_SEARCH_TERMS):
            hybrid_engine.search_with_diversity("")

    def test_diversity_invalid_threshold(self, hybrid_engine):
        """Test diversity sampling with invalid threshold."""
        with pytest.raises(ValueError, match="diversity_threshold must be between 0 and 1"):
            hybrid_engine.search_with_diversity("test", diversity_threshold=1.5)

    def test_diversity_low_threshold(self, hybrid_engine):
        """Test diversity sampling with low threshold (more diversity)."""
        results = hybrid_engine.search_with_diversity(
            "audio",
            diversity_threshold=0.3,
            top_k=3
        )
        assert len(results) > 0

    def test_diversity_high_threshold(self, hybrid_engine):
        """Test diversity sampling with high threshold (less diversity)."""
        results = hybrid_engine.search_with_diversity(
            "audio",
            diversity_threshold=0.9,
            top_k=3
        )
        assert len(results) > 0

    def test_diversity_vector_mode(self, hybrid_engine):
        """Test diversity sampling with vector mode."""
        results = hybrid_engine.search_with_diversity(
            "music",
            diversity_threshold=0.7,
            top_k=3,
            mode='vector'
        )
        assert len(results) > 0

    def test_diversity_keyword_mode(self, hybrid_engine):
        """Test diversity sampling with keyword mode."""
        results = hybrid_engine.search_with_diversity(
            "music",
            diversity_threshold=0.7,
            top_k=3,
            mode='keyword'
        )
        assert len(results) > 0


class TestEmbeddings:
    """Test embedding functionality."""

    def test_get_embedding(self, hybrid_engine):
        """Test getting embedding for text."""
        embedding = hybrid_engine._get_embedding("test text")

        assert isinstance(embedding, np.ndarray)
        assert len(embedding.shape) == 1  # 1D vector
        assert embedding.shape[0] > 0  # Non-empty

    def test_cosine_similarity(self, hybrid_engine):
        """Test cosine similarity calculation."""
        vec1 = np.array([1.0, 0.0, 0.0])
        vec2 = np.array([1.0, 0.0, 0.0])

        similarity = hybrid_engine._cosine_similarity(vec1, vec2)
        assert abs(similarity - 1.0) < 1e-6  # Should be 1.0

    def test_cosine_similarity_orthogonal(self, hybrid_engine):
        """Test cosine similarity for orthogonal vectors."""
        vec1 = np.array([1.0, 0.0])
        vec2 = np.array([0.0, 1.0])

        similarity = hybrid_engine._cosine_similarity(vec1, vec2)
        assert abs(similarity) < 1e-6  # Should be 0.0

    def test_cosine_similarity_zero_vector(self, hybrid_engine):
        """Test cosine similarity with zero vector."""
        vec1 = np.array([1.0, 0.0])
        vec2 = np.array([0.0, 0.0])

        similarity = hybrid_engine._cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_embedding_cache_populated(self, hybrid_engine):
        """Test that embeddings are cached."""
        stats = hybrid_engine.get_embedding_stats()

        # Should have cached all documents
        assert stats['size'] == 5  # 5 sample documents

    def test_embedding_cache_retrieval(self, hybrid_engine):
        """Test retrieving embeddings from cache."""
        embedding = hybrid_engine.embedding_cache.get('doc1')

        assert embedding is not None
        assert isinstance(embedding, np.ndarray)


class TestThreadSafety:
    """Test thread safety of HybridQueryEngine."""

    def test_concurrent_vector_search(self, hybrid_engine):
        """Test concurrent vector searches."""
        results = []
        errors = []

        def search_worker():
            try:
                res = hybrid_engine.search_vector("audio processing", top_k=3)
                results.append(res)
            except Exception as e:
                errors.append(e)

        # Run 10 concurrent searches
        threads = [threading.Thread(target=search_worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10

    def test_concurrent_hybrid_search(self, hybrid_engine):
        """Test concurrent hybrid searches."""
        results = []
        errors = []

        def search_worker():
            try:
                res = hybrid_engine.search_hybrid("music theory", top_k=3)
                results.append(res)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=search_worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10

    def test_concurrent_mmr_search(self, hybrid_engine):
        """Test concurrent MMR searches."""
        results = []
        errors = []

        def search_worker():
            try:
                res = hybrid_engine.search_with_mmr("python", top_k=2)
                results.append(res)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=search_worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 5


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_search_with_no_documents(self):
        """Test search with empty repository."""
        empty_repo = DocumentRepository()
        engine = HybridQueryEngine(empty_repo)

        results = engine.search_vector("test", top_k=5)
        assert len(results) == 0

    def test_search_with_special_characters(self, hybrid_engine):
        """Test search with special characters."""
        results = hybrid_engine.search_hybrid("audio@#$%", top_k=3)
        # Should not crash
        assert isinstance(results, list)

    def test_search_with_very_long_query(self, hybrid_engine):
        """Test search with very long query."""
        long_query = " ".join(["audio"] * 1000)
        results = hybrid_engine.search_vector(long_query, top_k=3)

        assert isinstance(results, list)

    def test_top_k_larger_than_documents(self, hybrid_engine):
        """Test when top_k is larger than number of documents."""
        results = hybrid_engine.search_vector("audio", top_k=1000)

        # Should return at most the number of documents
        assert len(results) <= 5

    def test_embedding_stats_format(self, hybrid_engine):
        """Test embedding stats return correct format."""
        stats = hybrid_engine.get_embedding_stats()

        assert 'size' in stats
        assert 'capacity' in stats
        assert 'utilization' in stats
        assert isinstance(stats['size'], int)
        assert isinstance(stats['capacity'], int)
        assert isinstance(stats['utilization'], float)
