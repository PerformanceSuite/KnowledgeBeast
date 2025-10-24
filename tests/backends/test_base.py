"""Tests for VectorBackend abstract base class."""

import pytest
from abc import ABC
from knowledgebeast.backends.base import VectorBackend


def test_vector_backend_is_abstract():
    """VectorBackend should be abstract and not instantiable."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        VectorBackend()


def test_vector_backend_has_required_methods():
    """VectorBackend should define all required abstract methods."""
    required_methods = [
        "add_documents",
        "query_vector",
        "query_keyword",
        "query_hybrid",
        "delete_documents",
        "get_statistics",
        "get_health",
        "close",
    ]

    for method_name in required_methods:
        assert hasattr(VectorBackend, method_name), f"Missing method: {method_name}"
        method = getattr(VectorBackend, method_name)
        assert getattr(method, '__isabstractmethod__', False), f"{method_name} should be abstract"


def test_vector_backend_signature():
    """VectorBackend should have expected method signatures."""
    import inspect

    # Check add_documents signature
    sig = inspect.signature(VectorBackend.add_documents)
    params = list(sig.parameters.keys())
    assert 'ids' in params
    assert 'embeddings' in params
    assert 'documents' in params
    assert 'metadatas' in params
