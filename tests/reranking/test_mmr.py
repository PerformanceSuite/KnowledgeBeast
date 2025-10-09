"""Tests for MMR (Maximal Marginal Relevance) Re-ranker.

This module contains 8 tests covering:
- Diversity computation
- Relevance-diversity tradeoff
- Edge cases (diversity=0, diversity=1)
"""

import pytest
import numpy as np

from knowledgebeast.core.reranking.mmr import MMRReranker


@pytest.fixture
def sample_results():
    """Sample search results for testing (some similar, some diverse)."""
    return [
        {
            "content": "Python is a high-level programming language.",
            "doc_id": "doc1",
            "name": "Python Basics",
            "path": "/docs/python1.md",
            "kb_dir": "/docs",
            "vector_score": 0.90
        },
        {
            "content": "Python programming language is great for beginners.",
            "doc_id": "doc2",
            "name": "Python Intro",
            "path": "/docs/python2.md",
            "kb_dir": "/docs",
            "vector_score": 0.85
        },
        {
            "content": "Machine learning with TensorFlow and PyTorch.",
            "doc_id": "doc3",
            "name": "ML Frameworks",
            "path": "/docs/ml.md",
            "kb_dir": "/docs",
            "vector_score": 0.75
        },
        {
            "content": "JavaScript is used for web development.",
            "doc_id": "doc4",
            "name": "JavaScript",
            "path": "/docs/js.md",
            "kb_dir": "/docs",
            "vector_score": 0.70
        }
    ]


# Test 1: MMR initialization
def test_mmr_initialization():
    """Test that MMRReranker initializes correctly."""
    reranker = MMRReranker(diversity=0.5, use_gpu=False)

    assert reranker.diversity == 0.5
    assert reranker.device == "cpu"
    assert reranker._model is None  # Lazy loading


# Test 2: Invalid diversity parameter
def test_mmr_invalid_diversity():
    """Test that invalid diversity values raise ValueError."""
    with pytest.raises(ValueError, match="Diversity must be in \\[0, 1\\]"):
        MMRReranker(diversity=1.5, use_gpu=False)

    with pytest.raises(ValueError, match="Diversity must be in \\[0, 1\\]"):
        MMRReranker(diversity=-0.1, use_gpu=False)


# Test 3: Basic MMR reranking
def test_mmr_rerank_basic(sample_results):
    """Test basic MMR reranking functionality."""
    reranker = MMRReranker(diversity=0.5, use_gpu=False)

    query = "Python programming"
    reranked = reranker.rerank(query, sample_results, top_k=4)

    assert len(reranked) == 4
    assert all("mmr_score" in r for r in reranked)
    assert all("final_score" in r for r in reranked)
    assert all("rank" in r for r in reranked)

    # Check ranks are sequential
    assert [r["rank"] for r in reranked] == [1, 2, 3, 4]


# Test 4: Pure relevance (diversity=1.0)
def test_mmr_pure_relevance(sample_results):
    """Test that diversity=1.0 prioritizes pure relevance."""
    reranker = MMRReranker(diversity=1.0, use_gpu=False)

    query = "Python programming"
    reranked = reranker.rerank(query, sample_results, top_k=4)

    # With diversity=1.0, results should be sorted by relevance only
    # Both Python documents should rank highly
    python_docs = [r for r in reranked if "Python" in r["content"]]
    assert len(python_docs) >= 2  # Both Python docs should be in results

    # First result should be Python-related (most relevant)
    assert "Python" in reranked[0]["content"]


# Test 5: Pure diversity (diversity=0.0)
def test_mmr_pure_diversity(sample_results):
    """Test that diversity=0.0 maximizes diversity."""
    reranker = MMRReranker(diversity=0.0, use_gpu=False)

    query = "Python programming"
    reranked = reranker.rerank(query, sample_results, top_k=4)

    # With diversity=0.0, should select maximally diverse documents
    # The two similar Python documents should not both be at the top
    # Check that we have diverse topics in top results
    top_2 = reranked[:2]

    # Both should not be about Python (diversity should spread topics)
    python_count = sum(1 for r in top_2 if "Python programming language" in r["content"])
    assert python_count <= 1, "Diversity=0 should not select both similar Python docs in top 2"


# Test 6: Balanced diversity (diversity=0.5)
def test_mmr_balanced_diversity(sample_results):
    """Test that diversity=0.5 balances relevance and diversity."""
    reranker = MMRReranker(diversity=0.5, use_gpu=False)

    query = "Python programming"
    reranked = reranker.rerank(query, sample_results, top_k=4)

    # With balanced diversity, should get a mix
    # Should have Python content (relevant) but also diverse topics
    python_count = sum(1 for r in reranked if "Python" in r["content"])

    assert python_count > 0, "Should have at least one relevant Python doc"
    assert python_count < len(reranked), "Should not have only Python docs (need diversity)"


# Test 7: Empty results handling
def test_mmr_empty_results():
    """Test that empty results raise ValueError."""
    reranker = MMRReranker(diversity=0.5, use_gpu=False)

    with pytest.raises(ValueError, match="Results list cannot be empty"):
        reranker.rerank("query", [], top_k=10)


# Test 8: Empty query handling
def test_mmr_empty_query(sample_results):
    """Test that empty query raises ValueError."""
    reranker = MMRReranker(diversity=0.5, use_gpu=False)

    with pytest.raises(ValueError, match="Query cannot be empty"):
        reranker.rerank("", sample_results, top_k=10)


# Test 9 (Bonus): Missing content field
def test_mmr_missing_content():
    """Test that missing content field raises ValueError."""
    reranker = MMRReranker(diversity=0.5, use_gpu=False)

    invalid_results = [
        {
            "doc_id": "doc1",
            "name": "Doc 1",
            # Missing 'content' field
        }
    ]

    with pytest.raises(ValueError, match="missing 'content' field"):
        reranker.rerank("query", invalid_results, top_k=10)


# Test 10 (Bonus): Top-k limiting
def test_mmr_top_k_limiting(sample_results):
    """Test that top_k correctly limits results."""
    reranker = MMRReranker(diversity=0.5, use_gpu=False)

    # Request fewer results than available
    reranked = reranker.rerank("query", sample_results, top_k=2)

    assert len(reranked) == 2
    assert reranked[0]["rank"] == 1
    assert reranked[1]["rank"] == 2


# Test 11 (Bonus): Stats retrieval
def test_mmr_get_stats():
    """Test stats retrieval."""
    reranker = MMRReranker(diversity=0.7, use_gpu=False)

    stats = reranker.get_stats()

    assert "model_name" in stats
    assert "diversity" in stats
    assert "device" in stats
    assert "model_loaded" in stats
    assert stats["diversity"] == 0.7
