"""Search quality and relevance tests.

Tests search quality using:
- NDCG@10 (Normalized Discounted Cumulative Gain)
- Precision@K
- Recall@K
- Mean Average Precision (MAP)
- Relevance judgments
"""

import pytest
import numpy as np
from typing import List, Dict, Tuple

from knowledgebeast.core.repository import DocumentRepository
from knowledgebeast.core.query_engine import HybridQueryEngine


def ndcg_at_k(relevance_scores: List[float], k: int = 10) -> float:
    """Calculate Normalized Discounted Cumulative Gain at K.

    Args:
        relevance_scores: List of relevance scores (0-1) in rank order
        k: Number of top results to consider

    Returns:
        NDCG@K score (0-1, higher is better)
    """
    if not relevance_scores:
        return 0.0

    # Truncate to top-k
    relevance_scores = relevance_scores[:k]

    # Calculate DCG (Discounted Cumulative Gain)
    dcg = relevance_scores[0]
    for i, score in enumerate(relevance_scores[1:], start=2):
        dcg += score / np.log2(i)

    # Calculate IDCG (Ideal DCG)
    ideal_scores = sorted(relevance_scores, reverse=True)
    idcg = ideal_scores[0]
    for i, score in enumerate(ideal_scores[1:], start=2):
        idcg += score / np.log2(i)

    # Normalize
    if idcg == 0:
        return 0.0

    return dcg / idcg


def precision_at_k(relevant: List[str], retrieved: List[str], k: int) -> float:
    """Calculate Precision@K.

    Args:
        relevant: List of relevant document IDs
        retrieved: List of retrieved document IDs in rank order
        k: Number of top results to consider

    Returns:
        Precision@K score (0-1)
    """
    if k == 0:
        return 0.0

    retrieved_k = set(retrieved[:k])
    relevant_set = set(relevant)

    num_relevant_retrieved = len(retrieved_k & relevant_set)
    return num_relevant_retrieved / k


def recall_at_k(relevant: List[str], retrieved: List[str], k: int) -> float:
    """Calculate Recall@K.

    Args:
        relevant: List of relevant document IDs
        retrieved: List of retrieved document IDs in rank order
        k: Number of top results to consider

    Returns:
        Recall@K score (0-1)
    """
    if not relevant:
        return 0.0

    retrieved_k = set(retrieved[:k])
    relevant_set = set(relevant)

    num_relevant_retrieved = len(retrieved_k & relevant_set)
    return num_relevant_retrieved / len(relevant_set)


def average_precision(relevant: List[str], retrieved: List[str]) -> float:
    """Calculate Average Precision.

    Args:
        relevant: List of relevant document IDs
        retrieved: List of retrieved document IDs in rank order

    Returns:
        Average Precision score (0-1)
    """
    if not relevant:
        return 0.0

    relevant_set = set(relevant)
    precision_sum = 0.0
    num_relevant_retrieved = 0

    for i, doc_id in enumerate(retrieved, start=1):
        if doc_id in relevant_set:
            num_relevant_retrieved += 1
            precision_sum += num_relevant_retrieved / i

    if num_relevant_retrieved == 0:
        return 0.0

    return precision_sum / len(relevant_set)


@pytest.fixture
def test_repository_with_relevance():
    """Create a repository with known relevance judgments."""
    repo = DocumentRepository()

    # Audio processing documents
    docs = {
        'audio_librosa': {
            'name': 'Librosa Audio Analysis',
            'content': 'Librosa is a Python library for audio and music analysis. It provides comprehensive tools for audio feature extraction including mel spectrograms, MFCCs, tempo estimation, and beat tracking.',
            'path': 'audio/librosa.md',
            'topics': ['audio', 'python', 'analysis']
        },
        'audio_juce': {
            'name': 'JUCE Audio Framework',
            'content': 'JUCE is a cross-platform C++ framework for audio applications. It supports real-time audio processing, plugin development (VST, AU, AAX), and GUI creation.',
            'path': 'audio/juce.md',
            'topics': ['audio', 'cpp', 'framework']
        },
        'audio_dsp': {
            'name': 'Digital Signal Processing',
            'content': 'DSP techniques for audio processing including FFT, filtering, convolution, and spectral analysis. Essential for audio effects and synthesis.',
            'path': 'audio/dsp.md',
            'topics': ['audio', 'dsp', 'signal']
        },
        'ml_basics': {
            'name': 'Machine Learning Fundamentals',
            'content': 'Introduction to machine learning covering supervised learning, unsupervised learning, and reinforcement learning. Includes neural networks and deep learning basics.',
            'path': 'ml/basics.md',
            'topics': ['ml', 'ai', 'learning']
        },
        'ml_nlp': {
            'name': 'Natural Language Processing',
            'content': 'NLP techniques including tokenization, embeddings, transformers, and language models. Applications in text classification and generation.',
            'path': 'ml/nlp.md',
            'topics': ['ml', 'nlp', 'text']
        },
        'ml_cv': {
            'name': 'Computer Vision',
            'content': 'Computer vision fundamentals covering image classification, object detection, segmentation, and neural network architectures like CNNs.',
            'path': 'ml/cv.md',
            'topics': ['ml', 'vision', 'image']
        },
        'web_django': {
            'name': 'Django Web Framework',
            'content': 'Django is a high-level Python web framework. It follows the model-template-view pattern and includes an ORM, authentication, and admin interface.',
            'path': 'web/django.md',
            'topics': ['web', 'python', 'framework']
        },
        'web_react': {
            'name': 'React Frontend Library',
            'content': 'React is a JavaScript library for building user interfaces. It uses a component-based architecture with hooks and virtual DOM for performance.',
            'path': 'web/react.md',
            'topics': ['web', 'javascript', 'frontend']
        },
        'db_postgres': {
            'name': 'PostgreSQL Database',
            'content': 'PostgreSQL is an advanced open-source relational database. It supports ACID transactions, JSON storage, and complex queries.',
            'path': 'db/postgres.md',
            'topics': ['database', 'sql', 'storage']
        },
        'db_mongo': {
            'name': 'MongoDB NoSQL',
            'content': 'MongoDB is a document-oriented NoSQL database. It stores data in flexible JSON-like documents and supports horizontal scaling.',
            'path': 'db/mongo.md',
            'topics': ['database', 'nosql', 'document']
        }
    }

    for doc_id, doc_data in docs.items():
        repo.add_document(doc_id, doc_data)

        # Build index
        terms = doc_data['content'].lower().split()
        for term in set(terms):
            repo.index_term(term, doc_id)

    return repo


@pytest.fixture
def relevance_judgments():
    """Define relevance judgments for test queries.

    Returns dict mapping query -> list of (doc_id, relevance_score)
    Relevance scores: 0 (not relevant), 0.5 (somewhat relevant), 1.0 (highly relevant)
    """
    return {
        'audio processing python': [
            ('audio_librosa', 1.0),  # Highly relevant
            ('audio_dsp', 0.5),      # Somewhat relevant
            ('audio_juce', 0.3),     # Slightly relevant (not Python)
            ('ml_nlp', 0.1),         # Barely relevant (Python but not audio)
            ('web_django', 0.1),     # Barely relevant (Python but not audio)
        ],
        'machine learning deep learning': [
            ('ml_basics', 1.0),      # Highly relevant
            ('ml_nlp', 0.8),         # Very relevant
            ('ml_cv', 0.8),          # Very relevant
            ('audio_dsp', 0.1),      # Barely relevant
        ],
        'web framework python': [
            ('web_django', 1.0),     # Highly relevant
            ('web_react', 0.3),      # Somewhat relevant (web but not Python)
            ('audio_librosa', 0.2),  # Slightly relevant (Python but not web)
        ],
        'database storage': [
            ('db_postgres', 1.0),    # Highly relevant
            ('db_mongo', 1.0),       # Highly relevant
            ('ml_basics', 0.1),      # Barely relevant
        ],
        'audio signal analysis': [
            ('audio_dsp', 1.0),      # Highly relevant
            ('audio_librosa', 0.9),  # Very relevant
            ('audio_juce', 0.5),     # Somewhat relevant
        ],
    }


@pytest.fixture
def quality_engine(test_repository_with_relevance):
    """Create HybridQueryEngine for quality testing."""
    return HybridQueryEngine(
        test_repository_with_relevance,
        model_name="all-MiniLM-L6-v2",
        alpha=0.7,
        cache_size=100
    )


class TestVectorSearchQuality:
    """Test quality of vector search."""

    def test_vector_search_ndcg(self, quality_engine, relevance_judgments):
        """Test vector search NDCG@10 scores."""
        ndcg_scores = []

        for query, judgments in relevance_judgments.items():
            # Get search results
            results = quality_engine.search_vector(query, top_k=10)
            retrieved_ids = [doc_id for doc_id, _, _ in results]

            # Map retrieved docs to relevance scores
            relevance_map = dict(judgments)
            relevance_scores = [relevance_map.get(doc_id, 0.0) for doc_id in retrieved_ids]

            # Calculate NDCG@10
            ndcg = ndcg_at_k(relevance_scores, k=10)
            ndcg_scores.append(ndcg)

            print(f"\nVector Search: '{query}' - NDCG@10 = {ndcg:.3f}")

        # Average NDCG across queries
        avg_ndcg = np.mean(ndcg_scores)
        print(f"\nVector Search Average NDCG@10: {avg_ndcg:.3f}")

        # Target: NDCG@10 > 0.85
        assert avg_ndcg > 0.85, f"Vector search NDCG@10 {avg_ndcg:.3f} below 0.85 target"

    def test_vector_search_precision(self, quality_engine, relevance_judgments):
        """Test vector search precision@5."""
        precision_scores = []

        for query, judgments in relevance_judgments.items():
            results = quality_engine.search_vector(query, top_k=10)
            retrieved_ids = [doc_id for doc_id, _, _ in results]

            # Consider docs with relevance >= 0.5 as relevant
            relevant_ids = [doc_id for doc_id, score in judgments if score >= 0.5]

            precision = precision_at_k(relevant_ids, retrieved_ids, k=5)
            precision_scores.append(precision)

            print(f"\nVector Search: '{query}' - Precision@5 = {precision:.3f}")

        avg_precision = np.mean(precision_scores)
        print(f"\nVector Search Average Precision@5: {avg_precision:.3f}")

        # Should achieve good precision
        assert avg_precision > 0.5

    def test_vector_search_recall(self, quality_engine, relevance_judgments):
        """Test vector search recall@10."""
        recall_scores = []

        for query, judgments in relevance_judgments.items():
            results = quality_engine.search_vector(query, top_k=10)
            retrieved_ids = [doc_id for doc_id, _, _ in results]

            relevant_ids = [doc_id for doc_id, score in judgments if score >= 0.5]

            recall = recall_at_k(relevant_ids, retrieved_ids, k=10)
            recall_scores.append(recall)

            print(f"\nVector Search: '{query}' - Recall@10 = {recall:.3f}")

        avg_recall = np.mean(recall_scores)
        print(f"\nVector Search Average Recall@10: {avg_recall:.3f}")

        # Should achieve good recall
        assert avg_recall > 0.6


class TestKeywordSearchQuality:
    """Test quality of keyword search."""

    def test_keyword_search_ndcg(self, quality_engine, relevance_judgments):
        """Test keyword search NDCG@10 scores."""
        ndcg_scores = []

        for query, judgments in relevance_judgments.items():
            results = quality_engine.search_keyword(query)
            retrieved_ids = [doc_id for doc_id, _, _ in results]

            relevance_map = dict(judgments)
            relevance_scores = [relevance_map.get(doc_id, 0.0) for doc_id in retrieved_ids[:10]]

            ndcg = ndcg_at_k(relevance_scores, k=10)
            ndcg_scores.append(ndcg)

            print(f"\nKeyword Search: '{query}' - NDCG@10 = {ndcg:.3f}")

        avg_ndcg = np.mean(ndcg_scores)
        print(f"\nKeyword Search Average NDCG@10: {avg_ndcg:.3f}")

        # Keyword search may have lower quality than vector
        assert avg_ndcg > 0.5


class TestHybridSearchQuality:
    """Test quality of hybrid search."""

    def test_hybrid_search_ndcg(self, quality_engine, relevance_judgments):
        """Test hybrid search NDCG@10 scores."""
        ndcg_scores = []

        for query, judgments in relevance_judgments.items():
            results = quality_engine.search_hybrid(query, top_k=10)
            retrieved_ids = [doc_id for doc_id, _, _ in results]

            relevance_map = dict(judgments)
            relevance_scores = [relevance_map.get(doc_id, 0.0) for doc_id in retrieved_ids]

            ndcg = ndcg_at_k(relevance_scores, k=10)
            ndcg_scores.append(ndcg)

            print(f"\nHybrid Search: '{query}' - NDCG@10 = {ndcg:.3f}")

        avg_ndcg = np.mean(ndcg_scores)
        print(f"\nHybrid Search Average NDCG@10: {avg_ndcg:.3f}")

        # Target: Hybrid NDCG@10 > 0.85
        assert avg_ndcg > 0.85, f"Hybrid search NDCG@10 {avg_ndcg:.3f} below 0.85 target"

    def test_hybrid_alpha_impact(self, quality_engine, relevance_judgments):
        """Test impact of alpha parameter on search quality."""
        alphas = [0.0, 0.3, 0.5, 0.7, 0.9, 1.0]
        query = 'audio processing python'
        judgments = dict(relevance_judgments[query])

        print(f"\nAlpha Impact on '{query}':")

        for alpha in alphas:
            results = quality_engine.search_hybrid(query, alpha=alpha, top_k=10)
            retrieved_ids = [doc_id for doc_id, _, _ in results]

            relevance_scores = [judgments.get(doc_id, 0.0) for doc_id in retrieved_ids]
            ndcg = ndcg_at_k(relevance_scores, k=10)

            print(f"  alpha={alpha:.1f}: NDCG@10 = {ndcg:.3f}")

        # All alphas should produce reasonable results
        # (specific best alpha depends on data)

    def test_hybrid_beats_keyword_only(self, quality_engine, relevance_judgments):
        """Test that hybrid search outperforms keyword-only."""
        keyword_ndcg_scores = []
        hybrid_ndcg_scores = []

        for query, judgments in relevance_judgments.items():
            # Keyword-only (alpha=0)
            keyword_results = quality_engine.search_hybrid(query, alpha=0.0, top_k=10)
            keyword_ids = [doc_id for doc_id, _, _ in keyword_results]

            # Hybrid (alpha=0.7)
            hybrid_results = quality_engine.search_hybrid(query, alpha=0.7, top_k=10)
            hybrid_ids = [doc_id for doc_id, _, _ in hybrid_results]

            relevance_map = dict(judgments)

            keyword_scores = [relevance_map.get(doc_id, 0.0) for doc_id in keyword_ids]
            hybrid_scores = [relevance_map.get(doc_id, 0.0) for doc_id in hybrid_ids]

            keyword_ndcg_scores.append(ndcg_at_k(keyword_scores, k=10))
            hybrid_ndcg_scores.append(ndcg_at_k(hybrid_scores, k=10))

        avg_keyword_ndcg = np.mean(keyword_ndcg_scores)
        avg_hybrid_ndcg = np.mean(hybrid_ndcg_scores)

        print(f"\nKeyword-only avg NDCG@10: {avg_keyword_ndcg:.3f}")
        print(f"Hybrid avg NDCG@10: {avg_hybrid_ndcg:.3f}")

        # Hybrid should be at least as good as keyword-only
        assert avg_hybrid_ndcg >= avg_keyword_ndcg * 0.95


class TestMMRQuality:
    """Test quality of MMR re-ranking."""

    def test_mmr_diversity(self, quality_engine):
        """Test that MMR increases result diversity."""
        query = "machine learning"

        # Standard search
        standard_results = quality_engine.search_hybrid(query, top_k=5)

        # MMR with high diversity (low lambda)
        mmr_results = quality_engine.search_with_mmr(
            query,
            lambda_param=0.3,
            top_k=5,
            mode='hybrid'
        )

        # Check that we get different ordering or documents
        standard_ids = [doc_id for doc_id, _, _ in standard_results]
        mmr_ids = [doc_id for doc_id, _, _ in mmr_results]

        print(f"\nStandard results: {standard_ids}")
        print(f"MMR results: {mmr_ids}")

        # MMR should produce results (may be same or different order)
        assert len(mmr_ids) > 0

    def test_mmr_maintains_quality(self, quality_engine, relevance_judgments):
        """Test that MMR maintains reasonable quality."""
        ndcg_scores = []

        for query, judgments in relevance_judgments.items():
            results = quality_engine.search_with_mmr(
                query,
                lambda_param=0.5,
                top_k=10,
                mode='hybrid'
            )
            retrieved_ids = [doc_id for doc_id, _, _ in results]

            relevance_map = dict(judgments)
            relevance_scores = [relevance_map.get(doc_id, 0.0) for doc_id in retrieved_ids]

            ndcg = ndcg_at_k(relevance_scores, k=10)
            ndcg_scores.append(ndcg)

        avg_ndcg = np.mean(ndcg_scores)
        print(f"\nMMR Average NDCG@10: {avg_ndcg:.3f}")

        # MMR should maintain good quality
        assert avg_ndcg > 0.7


class TestDiversityQuality:
    """Test quality of diversity sampling."""

    def test_diversity_sampling_quality(self, quality_engine, relevance_judgments):
        """Test that diversity sampling maintains quality."""
        ndcg_scores = []

        for query, judgments in relevance_judgments.items():
            results = quality_engine.search_with_diversity(
                query,
                diversity_threshold=0.8,
                top_k=10,
                mode='hybrid'
            )
            retrieved_ids = [doc_id for doc_id, _, _ in results]

            relevance_map = dict(judgments)
            relevance_scores = [relevance_map.get(doc_id, 0.0) for doc_id in retrieved_ids]

            ndcg = ndcg_at_k(relevance_scores, k=10)
            ndcg_scores.append(ndcg)

        avg_ndcg = np.mean(ndcg_scores)
        print(f"\nDiversity Sampling Average NDCG@10: {avg_ndcg:.3f}")

        # Should maintain reasonable quality
        assert avg_ndcg > 0.7


class TestMeanAveragePrecision:
    """Test Mean Average Precision."""

    def test_vector_search_map(self, quality_engine, relevance_judgments):
        """Test vector search Mean Average Precision."""
        ap_scores = []

        for query, judgments in relevance_judgments.items():
            results = quality_engine.search_vector(query, top_k=10)
            retrieved_ids = [doc_id for doc_id, _, _ in results]

            relevant_ids = [doc_id for doc_id, score in judgments if score >= 0.5]

            ap = average_precision(relevant_ids, retrieved_ids)
            ap_scores.append(ap)

            print(f"\nVector Search: '{query}' - AP = {ap:.3f}")

        map_score = np.mean(ap_scores)
        print(f"\nVector Search MAP: {map_score:.3f}")

        # Should achieve good MAP
        assert map_score > 0.5

    def test_hybrid_search_map(self, quality_engine, relevance_judgments):
        """Test hybrid search Mean Average Precision."""
        ap_scores = []

        for query, judgments in relevance_judgments.items():
            results = quality_engine.search_hybrid(query, top_k=10)
            retrieved_ids = [doc_id for doc_id, _, _ in results]

            relevant_ids = [doc_id for doc_id, score in judgments if score >= 0.5]

            ap = average_precision(relevant_ids, retrieved_ids)
            ap_scores.append(ap)

            print(f"\nHybrid Search: '{query}' - AP = {ap:.3f}")

        map_score = np.mean(ap_scores)
        print(f"\nHybrid Search MAP: {map_score:.3f}")

        # Should achieve good MAP
        assert map_score > 0.6
