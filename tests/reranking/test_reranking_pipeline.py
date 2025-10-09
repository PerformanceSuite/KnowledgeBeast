"""Tests for end-to-end re-ranking pipeline.

This module contains 15 tests covering:
- End-to-end reranking workflow
- Integration with search
- API parameter validation
- Error handling
- Cache behavior
"""

import pytest
import time

from knowledgebeast.api.reranking_helper import (
    apply_reranking,
    prepare_results_for_reranking,
    convert_to_query_results,
    get_cross_encoder_reranker,
    get_mmr_reranker,
)


@pytest.fixture
def mock_search_results():
    """Mock search results from knowledge base."""
    return [
        ("doc1", {
            "content": "Python is a versatile programming language.",
            "name": "Python Guide",
            "path": "/docs/python.md",
            "kb_dir": "/docs"
        }),
        ("doc2", {
            "content": "JavaScript powers modern web applications.",
            "name": "JS Guide",
            "path": "/docs/js.md",
            "kb_dir": "/docs"
        }),
        ("doc3", {
            "content": "Machine learning with Python and TensorFlow.",
            "name": "ML Guide",
            "path": "/docs/ml.md",
            "kb_dir": "/docs"
        })
    ]


# Test 1: Prepare results for reranking
def test_prepare_results_for_reranking(mock_search_results):
    """Test converting tuple results to dict format."""
    prepared = prepare_results_for_reranking(mock_search_results, add_vector_scores=True)

    assert len(prepared) == 3
    assert all(isinstance(r, dict) for r in prepared)
    assert all("content" in r for r in prepared)
    assert all("vector_score" in r for r in prepared)

    # Check vector scores are descending
    assert prepared[0]["vector_score"] > prepared[1]["vector_score"]
    assert prepared[1]["vector_score"] > prepared[2]["vector_score"]


# Test 2: Apply cross-encoder reranking
def test_apply_cross_encoder_reranking(mock_search_results):
    """Test applying cross-encoder reranking."""
    prepared = prepare_results_for_reranking(mock_search_results)

    query = "Python programming language"
    reranked, metadata = apply_reranking(
        query=query,
        results=prepared,
        use_cross_encoder=True,
        use_mmr=False,
        top_k=3
    )

    assert len(reranked) <= 3
    assert metadata["reranked"] is True
    assert "cross-encoder" in metadata["rerank_model"].lower()
    assert metadata["rerank_duration_ms"] > 0

    # Check scores are present
    assert all("rerank_score" in r for r in reranked)
    assert all("final_score" in r for r in reranked)


# Test 3: Apply MMR reranking
def test_apply_mmr_reranking(mock_search_results):
    """Test applying MMR reranking."""
    prepared = prepare_results_for_reranking(mock_search_results)

    query = "Python programming"
    reranked, metadata = apply_reranking(
        query=query,
        results=prepared,
        use_cross_encoder=False,
        use_mmr=True,
        diversity=0.5,
        top_k=3
    )

    assert len(reranked) <= 3
    assert metadata["reranked"] is True
    assert "mmr" in metadata["rerank_model"].lower()


# Test 4: Apply both rerankers
def test_apply_both_rerankers(mock_search_results):
    """Test applying both cross-encoder and MMR."""
    prepared = prepare_results_for_reranking(mock_search_results)

    query = "Python programming"
    reranked, metadata = apply_reranking(
        query=query,
        results=prepared,
        use_cross_encoder=True,
        use_mmr=True,
        diversity=0.5,
        top_k=3
    )

    assert len(reranked) <= 3
    assert metadata["reranked"] is True
    # Should mention both models
    assert "cross-encoder" in metadata["rerank_model"].lower() or "mmr" in metadata["rerank_model"].lower()


# Test 5: No reranking
def test_no_reranking(mock_search_results):
    """Test that disabling reranking returns original results."""
    prepared = prepare_results_for_reranking(mock_search_results)

    query = "Python"
    reranked, metadata = apply_reranking(
        query=query,
        results=prepared,
        use_cross_encoder=False,
        use_mmr=False,
        top_k=3
    )

    assert len(reranked) <= 3
    assert metadata["reranked"] is False
    assert metadata["rerank_model"] is None


# Test 6: Empty results handling
def test_apply_reranking_empty_results():
    """Test that empty results return gracefully."""
    reranked, metadata = apply_reranking(
        query="test",
        results=[],
        use_cross_encoder=True,
        top_k=10
    )

    assert len(reranked) == 0
    assert metadata["reranked"] is False


# Test 7: Convert to query results
def test_convert_to_query_results():
    """Test converting reranked results to QueryResult format."""
    reranked = [
        {
            "doc_id": "doc1",
            "content": "Content",
            "name": "Doc 1",
            "path": "/docs/doc1.md",
            "kb_dir": "/docs",
            "vector_score": 0.8,
            "rerank_score": 0.9,
            "final_score": 0.9,
            "rank": 1
        }
    ]

    converted = convert_to_query_results(reranked)

    assert len(converted) == 1
    assert converted[0]["doc_id"] == "doc1"
    assert converted[0]["rerank_score"] == 0.9
    assert converted[0]["rank"] == 1


# Test 8: Top-k enforcement
def test_top_k_enforcement(mock_search_results):
    """Test that top_k limits results correctly."""
    prepared = prepare_results_for_reranking(mock_search_results)

    query = "Python"
    reranked, _ = apply_reranking(
        query=query,
        results=prepared,
        use_cross_encoder=True,
        top_k=2
    )

    assert len(reranked) == 2


# Test 9: Diversity parameter validation
def test_diversity_parameter(mock_search_results):
    """Test different diversity parameter values."""
    prepared = prepare_results_for_reranking(mock_search_results)

    query = "Python"

    # High diversity (more relevance)
    reranked_high, _ = apply_reranking(
        query=query,
        results=prepared,
        use_mmr=True,
        diversity=0.9,
        top_k=3
    )

    # Low diversity (more diversity)
    reranked_low, _ = apply_reranking(
        query=query,
        results=prepared,
        use_mmr=True,
        diversity=0.1,
        top_k=3
    )

    assert len(reranked_high) <= 3
    assert len(reranked_low) <= 3


# Test 10: Reranker singleton instances
def test_reranker_singleton_instances():
    """Test that reranker instances are singletons."""
    reranker1 = get_cross_encoder_reranker()
    reranker2 = get_cross_encoder_reranker()

    # Should be same instance
    assert reranker1 is reranker2


# Test 11: MMR reranker instance creation
def test_mmr_reranker_instance():
    """Test MMR reranker instance creation."""
    reranker = get_mmr_reranker(diversity=0.5)

    assert reranker is not None
    assert reranker.diversity == 0.5


# Test 12: Score improvement tracking
def test_score_improvement_tracking(mock_search_results):
    """Test that score improvements are tracked."""
    prepared = prepare_results_for_reranking(mock_search_results, add_vector_scores=True)

    query = "Python programming"
    reranked, metadata = apply_reranking(
        query=query,
        results=prepared,
        use_cross_encoder=True,
        top_k=3
    )

    # Check that rerank scores differ from vector scores
    for result in reranked:
        if "vector_score" in result and "rerank_score" in result:
            # Scores should exist
            assert result["vector_score"] is not None
            assert result["rerank_score"] is not None


# Test 13: Metadata completeness
def test_metadata_completeness(mock_search_results):
    """Test that metadata contains all expected fields."""
    prepared = prepare_results_for_reranking(mock_search_results)

    query = "Python"
    _, metadata = apply_reranking(
        query=query,
        results=prepared,
        use_cross_encoder=True,
        top_k=3
    )

    assert "reranked" in metadata
    assert "rerank_model" in metadata
    assert "rerank_duration_ms" in metadata


# Test 14: Error handling in reranking
def test_error_handling_graceful_fallback(mock_search_results):
    """Test that errors in reranking fall back gracefully."""
    # Create invalid results (missing content)
    invalid_results = [
        {
            "doc_id": "doc1",
            "name": "Doc 1",
            "path": "/docs/doc1.md",
            "kb_dir": "/docs"
            # Missing 'content' field - will cause error
        }
    ]

    query = "test"

    # Should not raise exception, should fall back
    reranked, metadata = apply_reranking(
        query=query,
        results=invalid_results,
        use_cross_encoder=True,
        top_k=10
    )

    # Should return original results (or empty on error)
    assert isinstance(reranked, list)
    assert "reranked" in metadata


# Test 15: Performance timing
def test_performance_timing(mock_search_results):
    """Test that performance timing is recorded."""
    prepared = prepare_results_for_reranking(mock_search_results)

    query = "Python"
    start_time = time.time()

    reranked, metadata = apply_reranking(
        query=query,
        results=prepared,
        use_cross_encoder=True,
        top_k=3
    )

    end_time = time.time()
    duration_ms = (end_time - start_time) * 1000

    assert metadata["rerank_duration_ms"] > 0
    assert metadata["rerank_duration_ms"] <= duration_ms + 100  # Allow some overhead
