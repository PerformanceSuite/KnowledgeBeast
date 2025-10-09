"""Tests for OpenTelemetry tracing integration.

This module tests distributed tracing functionality across all instrumented
components of KnowledgeBeast.
"""

import pytest
import time
import numpy as np
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from knowledgebeast.core.cache import LRUCache
from knowledgebeast.core.embeddings import EmbeddingEngine
from knowledgebeast.core.vector_store import VectorStore
from knowledgebeast.core.query_engine import HybridQueryEngine
from knowledgebeast.core.repository import DocumentRepository
from knowledgebeast.utils.observability import (
    get_tracer,
    setup_opentelemetry,
    set_request_id,
    get_request_id,
)


@pytest.fixture(scope="function", autouse=False)
def span_exporter():
    """Create an in-memory span exporter for testing."""
    # Create new provider for testing
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Set provider - this will generate a warning but tests will work
    trace.set_tracer_provider(provider)

    yield exporter

    # Cleanup
    exporter.clear()


@pytest.fixture
def embedding_engine():
    """Create embedding engine for testing."""
    return EmbeddingEngine(model_name="all-MiniLM-L6-v2", cache_size=10)


@pytest.fixture
def vector_store(tmp_path):
    """Create vector store for testing."""
    return VectorStore(persist_directory=tmp_path / "chroma_test", collection_name="test")


@pytest.fixture
def hybrid_engine(tmp_path):
    """Create hybrid query engine for testing."""
    repo = DocumentRepository()
    repo.add_document("doc1", {"name": "Test Doc 1", "content": "Machine learning is awesome"})
    repo.add_document("doc2", {"name": "Test Doc 2", "content": "Python programming tutorial"})
    return HybridQueryEngine(repo, cache_size=10)


class TestOpenTelemetryTracing:
    """Test suite for OpenTelemetry tracing functionality."""

    def test_tracer_initialization(self, span_exporter):
        """Test that tracer is properly initialized."""
        tracer = get_tracer()
        assert tracer is not None
        assert isinstance(tracer, trace.Tracer)

    def test_span_creation_and_attributes(self, span_exporter):
        """Test creating spans with attributes."""
        tracer = get_tracer()

        with tracer.start_as_current_span("test_span") as span:
            span.set_attribute("test.attribute", "test_value")
            span.set_attribute("test.number", 42)
            span.set_attribute("test.boolean", True)

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1

        test_span = spans[0]
        assert test_span.name == "test_span"
        assert test_span.attributes["test.attribute"] == "test_value"
        assert test_span.attributes["test.number"] == 42
        assert test_span.attributes["test.boolean"] is True

    def test_nested_span_hierarchy(self, span_exporter):
        """Test nested span creation and parent-child relationship."""
        tracer = get_tracer()

        with tracer.start_as_current_span("parent_span") as parent:
            parent.set_attribute("level", "parent")

            with tracer.start_as_current_span("child_span") as child:
                child.set_attribute("level", "child")

                with tracer.start_as_current_span("grandchild_span") as grandchild:
                    grandchild.set_attribute("level", "grandchild")

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 3

        # Spans are exported in order of completion (LIFO)
        grandchild, child, parent = spans

        assert parent.name == "parent_span"
        assert child.name == "child_span"
        assert grandchild.name == "grandchild_span"

        # Verify parent-child relationships
        assert child.parent.span_id == parent.context.span_id
        assert grandchild.parent.span_id == child.context.span_id

    def test_embedding_engine_traces(self, span_exporter, embedding_engine):
        """Test that embedding operations create proper spans."""
        # Generate embeddings
        text = "Hello world"
        embedding = embedding_engine.embed(text)

        spans = span_exporter.get_finished_spans()

        # Should have at least embedding.generate span
        assert len(spans) >= 1

        # Find embedding.generate span
        generate_spans = [s for s in spans if s.name == "embedding.generate"]
        assert len(generate_spans) == 1

        gen_span = generate_spans[0]
        assert gen_span.attributes["embedding.model"] == "all-MiniLM-L6-v2"
        assert gen_span.attributes["embedding.batch_size"] == 1
        assert gen_span.attributes["embedding.use_cache"] is True
        assert gen_span.attributes["embedding.results_count"] == 1

    def test_embedding_batch_traces(self, span_exporter, embedding_engine):
        """Test batch embedding operations create appropriate spans."""
        texts = ["First text", "Second text", "Third text"]
        embeddings = embedding_engine.embed(texts)

        spans = span_exporter.get_finished_spans()
        generate_spans = [s for s in spans if s.name == "embedding.generate"]

        assert len(generate_spans) == 1
        gen_span = generate_spans[0]

        assert gen_span.attributes["embedding.batch_size"] == 3
        assert gen_span.attributes["embedding.results_count"] == 3

    def test_embedding_cache_hit_traces(self, span_exporter, embedding_engine):
        """Test that cache hits are properly traced."""
        text = "Cached text"

        # First call - cache miss
        span_exporter.clear()
        _ = embedding_engine.embed(text)

        first_spans = span_exporter.get_finished_spans()
        first_gen = [s for s in first_spans if s.name == "embedding.generate"][0]
        assert first_gen.attributes["embedding.cache_misses"] == 1
        assert first_gen.attributes["embedding.cache_hits"] == 0

        # Second call - cache hit
        span_exporter.clear()
        _ = embedding_engine.embed(text)

        second_spans = span_exporter.get_finished_spans()
        second_gen = [s for s in second_spans if s.name == "embedding.generate"][0]
        assert second_gen.attributes["embedding.cache_hits"] == 1
        assert second_gen.attributes["embedding.cache_misses"] == 0

    def test_vector_store_query_traces(self, span_exporter, vector_store):
        """Test vector store query operations create spans."""
        # Add a document
        embedding = np.random.rand(384).astype(np.float32)
        vector_store.add(
            ids="test_doc",
            embeddings=embedding,
            documents="Test document",
            metadatas={"type": "test"}
        )

        # Query
        span_exporter.clear()
        query_embedding = np.random.rand(384).astype(np.float32)
        results = vector_store.query(query_embedding, n_results=5)

        spans = span_exporter.get_finished_spans()
        query_spans = [s for s in spans if s.name == "vector_store.query"]

        assert len(query_spans) == 1
        query_span = query_spans[0]

        assert query_span.attributes["vector_store.collection"] == "test"
        assert query_span.attributes["vector_store.n_results"] == 5
        assert query_span.attributes["vector_store.num_queries"] == 1

    def test_hybrid_search_traces(self, span_exporter, hybrid_engine):
        """Test hybrid search creates complete span hierarchy."""
        query = "machine learning"

        results = hybrid_engine.search_hybrid(query, top_k=5)

        spans = span_exporter.get_finished_spans()

        # Should have multiple spans for hybrid search
        hybrid_spans = [s for s in spans if "query" in s.name]
        assert len(hybrid_spans) > 0

        # Find main hybrid search span
        main_span = [s for s in hybrid_spans if s.name == "query.hybrid_search"]
        assert len(main_span) == 1

        search_span = main_span[0]
        assert "query.text" in search_span.attributes
        assert search_span.attributes["query.type"] == "hybrid"
        assert search_span.attributes["query.top_k"] == 5

    def test_span_duration_recorded(self, span_exporter):
        """Test that span duration is properly recorded."""
        tracer = get_tracer()

        with tracer.start_as_current_span("timed_span") as span:
            time.sleep(0.01)  # 10ms

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1

        timed_span = spans[0]
        # Duration is in nanoseconds
        duration_ms = (timed_span.end_time - timed_span.start_time) / 1_000_000
        assert duration_ms >= 10  # At least 10ms

    def test_error_traces_capture_exceptions(self, span_exporter):
        """Test that errors are properly captured in traces."""
        tracer = get_tracer()

        try:
            with tracer.start_as_current_span("error_span") as span:
                span.set_attribute("test.will_fail", True)
                raise ValueError("Test error")
        except ValueError:
            pass

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1

        error_span = spans[0]
        assert error_span.status.is_ok is False

        # Check that exception was recorded
        events = error_span.events
        assert len(events) > 0
        exception_event = events[0]
        assert exception_event.name == "exception"

    def test_trace_context_propagation(self, span_exporter):
        """Test that trace context is properly propagated."""
        tracer = get_tracer()

        with tracer.start_as_current_span("root_span") as root:
            root_span_id = root.get_span_context().span_id

            with tracer.start_as_current_span("child_span") as child:
                # Child should have same trace ID but different span ID
                assert child.get_span_context().trace_id == root.get_span_context().trace_id
                assert child.get_span_context().span_id != root_span_id

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 2

        # All spans should have same trace ID
        trace_ids = [s.context.trace_id for s in spans]
        assert len(set(trace_ids)) == 1

    def test_request_id_context(self):
        """Test request ID context management."""
        # Initially no request ID
        assert get_request_id() is None

        # Set request ID
        request_id = "test-request-123"
        set_request_id(request_id)

        # Verify retrieval
        assert get_request_id() == request_id

        # Clear by setting None
        set_request_id(None)
        assert get_request_id() is None

    def test_span_attributes_validation(self, span_exporter):
        """Test that span attributes follow conventions."""
        tracer = get_tracer()

        with tracer.start_as_current_span("attribute_test") as span:
            # Test various attribute types
            span.set_attribute("string.attr", "value")
            span.set_attribute("int.attr", 42)
            span.set_attribute("float.attr", 3.14)
            span.set_attribute("bool.attr", True)

        spans = span_exporter.get_finished_spans()
        test_span = spans[0]

        assert test_span.attributes["string.attr"] == "value"
        assert test_span.attributes["int.attr"] == 42
        assert abs(test_span.attributes["float.attr"] - 3.14) < 0.01
        assert test_span.attributes["bool.attr"] is True

    def test_concurrent_traces_isolation(self, span_exporter):
        """Test that concurrent operations maintain trace isolation."""
        import threading

        def create_trace(name: str):
            tracer = get_tracer()
            with tracer.start_as_current_span(f"concurrent_{name}") as span:
                span.set_attribute("thread", name)
                time.sleep(0.01)

        threads = []
        for i in range(5):
            t = threading.Thread(target=create_trace, args=(f"thread_{i}",))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 5

        # Each span should have unique trace ID (since they're independent)
        thread_attrs = [s.attributes["thread"] for s in spans]
        assert len(set(thread_attrs)) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
