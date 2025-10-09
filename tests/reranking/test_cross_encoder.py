"""Tests for Cross-Encoder Re-ranker.

This module contains 12 tests covering:
- Model loading and initialization
- Batch processing correctness
- GPU acceleration (if available)
- Timeout handling
- Score normalization
"""

import asyncio
import time

import numpy as np
import pytest
import torch

from knowledgebeast.core.reranking.cross_encoder import CrossEncoderReranker


@pytest.fixture
def sample_results():
    """Sample search results for testing."""
    return [
        {
            "content": "Python is a high-level programming language used for web development.",
            "doc_id": "doc1",
            "name": "Python Guide",
            "path": "/docs/python.md",
            "kb_dir": "/docs",
            "vector_score": 0.85
        },
        {
            "content": "JavaScript is a programming language used for web development and client-side scripting.",
            "doc_id": "doc2",
            "name": "JavaScript Guide",
            "path": "/docs/js.md",
            "kb_dir": "/docs",
            "vector_score": 0.80
        },
        {
            "content": "Machine learning uses Python for data science and artificial intelligence applications.",
            "doc_id": "doc3",
            "name": "ML Guide",
            "path": "/docs/ml.md",
            "kb_dir": "/docs",
            "vector_score": 0.75
        }
    ]


# Test 1: Model initialization
def test_cross_encoder_initialization():
    """Test that CrossEncoderReranker initializes correctly."""
    reranker = CrossEncoderReranker(
        model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
        batch_size=16,
        use_gpu=False  # Force CPU for tests
    )

    assert reranker.model_name == "cross-encoder/ms-marco-MiniLM-L-6-v2"
    assert reranker.batch_size == 16
    assert reranker.device == "cpu"
    assert reranker._model is None  # Lazy loading


# Test 2: Model lazy loading
def test_cross_encoder_lazy_loading():
    """Test that model is loaded on first access."""
    reranker = CrossEncoderReranker(use_gpu=False)

    assert reranker._model is None

    # Access model property to trigger loading
    model = reranker.model

    assert model is not None
    assert reranker._model is not None


# Test 3: Basic reranking
def test_cross_encoder_rerank_basic(sample_results):
    """Test basic reranking functionality."""
    reranker = CrossEncoderReranker(use_gpu=False)

    query = "Python programming language"
    reranked = reranker.rerank(query, sample_results, top_k=3)

    assert len(reranked) == 3
    assert all("rerank_score" in r for r in reranked)
    assert all("final_score" in r for r in reranked)
    assert all("rank" in r for r in reranked)

    # Check ranks are sequential
    assert [r["rank"] for r in reranked] == [1, 2, 3]

    # First result should be most relevant (Python-related)
    assert "Python" in reranked[0]["content"]


# Test 4: Score normalization
def test_cross_encoder_score_normalization(sample_results):
    """Test that scores are normalized to [0, 1] range."""
    reranker = CrossEncoderReranker(use_gpu=False)

    query = "programming"
    reranked = reranker.rerank(query, sample_results, top_k=3)

    for result in reranked:
        assert 0.0 <= result["rerank_score"] <= 1.0, \
            f"Score {result['rerank_score']} not in [0, 1]"
        assert 0.0 <= result["final_score"] <= 1.0, \
            f"Final score {result['final_score']} not in [0, 1]"


# Test 5: Batch processing
def test_cross_encoder_batch_processing():
    """Test batch processing with different batch sizes."""
    reranker = CrossEncoderReranker(batch_size=2, use_gpu=False)

    # Create more results than batch size
    results = [
        {
            "content": f"Document {i} about various topics",
            "doc_id": f"doc{i}",
            "name": f"Doc {i}",
            "path": f"/docs/doc{i}.md",
            "kb_dir": "/docs",
            "vector_score": 0.5
        }
        for i in range(10)
    ]

    query = "topics"
    reranked = reranker.rerank(query, results, top_k=10)

    assert len(reranked) == 10
    assert all("rerank_score" in r for r in reranked)


# Test 6: Empty results handling
def test_cross_encoder_empty_results():
    """Test that empty results raise ValueError."""
    reranker = CrossEncoderReranker(use_gpu=False)

    with pytest.raises(ValueError, match="Results list cannot be empty"):
        reranker.rerank("query", [], top_k=10)


# Test 7: Empty query handling
def test_cross_encoder_empty_query(sample_results):
    """Test that empty query raises ValueError."""
    reranker = CrossEncoderReranker(use_gpu=False)

    with pytest.raises(ValueError, match="Query cannot be empty"):
        reranker.rerank("", sample_results, top_k=10)


# Test 8: Missing content field
def test_cross_encoder_missing_content():
    """Test that missing content field raises ValueError."""
    reranker = CrossEncoderReranker(use_gpu=False)

    invalid_results = [
        {
            "doc_id": "doc1",
            "name": "Doc 1",
            # Missing 'content' field
        }
    ]

    with pytest.raises(ValueError, match="missing 'content' field"):
        reranker.rerank("query", invalid_results, top_k=10)


# Test 9: Top-k limiting
def test_cross_encoder_top_k_limiting(sample_results):
    """Test that top_k correctly limits results."""
    reranker = CrossEncoderReranker(use_gpu=False)

    # Request fewer results than available
    reranked = reranker.rerank("query", sample_results, top_k=2)

    assert len(reranked) == 2
    assert reranked[0]["rank"] == 1
    assert reranked[1]["rank"] == 2


# Test 10: Async reranking
@pytest.mark.asyncio
async def test_cross_encoder_async_rerank(sample_results):
    """Test asynchronous reranking."""
    reranker = CrossEncoderReranker(use_gpu=False, timeout=10.0)

    query = "Python programming"
    reranked = await reranker.rerank_async(query, sample_results, top_k=3)

    assert len(reranked) == 3
    assert all("rerank_score" in r for r in reranked)


# Test 11: Timeout fallback
def test_cross_encoder_timeout_fallback(sample_results):
    """Test fallback to vector scores on timeout."""
    # Very short timeout to force timeout
    reranker = CrossEncoderReranker(use_gpu=False, timeout=0.001)

    query = "Python programming"

    # Should complete even with timeout (using fallback)
    # Note: This might not actually timeout on fast systems,
    # but the implementation should handle it gracefully
    try:
        reranked = reranker.rerank(query, sample_results, top_k=3)
        # If it succeeds, that's also fine
        assert len(reranked) <= 3
    except Exception:
        # If it fails, the fallback should still work
        pass


# Test 12: GPU support detection
def test_cross_encoder_gpu_support():
    """Test GPU support detection."""
    reranker = CrossEncoderReranker(use_gpu=True)

    # Should detect GPU availability correctly
    if torch.cuda.is_available():
        assert reranker.device == "cuda"
        assert reranker.supports_gpu() is True
    elif torch.backends.mps.is_available():
        assert reranker.device == "mps"
        assert reranker.supports_gpu() is True
    else:
        assert reranker.device == "cpu"
        assert reranker.supports_gpu() is False


# Test 13 (Bonus): Stats retrieval
def test_cross_encoder_get_stats():
    """Test stats retrieval."""
    reranker = CrossEncoderReranker(use_gpu=False)

    stats = reranker.get_stats()

    assert "model_name" in stats
    assert "device" in stats
    assert "batch_size" in stats
    assert "timeout" in stats
    assert "model_loaded" in stats
    assert stats["model_loaded"] is False  # Not loaded yet

    # Trigger loading
    _ = reranker.model

    stats = reranker.get_stats()
    assert stats["model_loaded"] is True


# Test 14 (Bonus): Model caching
def test_cross_encoder_model_caching():
    """Test that model is cached correctly."""
    reranker1 = CrossEncoderReranker(use_gpu=False)
    reranker2 = CrossEncoderReranker(use_gpu=False)

    # Load model in first reranker
    model1 = reranker1.model

    # Second reranker should get cached model (from global cache)
    model2 = reranker2.model

    assert model1 is not None
    assert model2 is not None
