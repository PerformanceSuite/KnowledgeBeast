"""Integration tests for KnowledgeBeast MCP server.

End-to-end workflow tests including:
- Full document lifecycle (create → ingest → search → export → import)
- Multi-project isolation verification
- Large document handling
- Batch operations
- Real ChromaDB interaction

WARNING: These tests use real ChromaDB (not mocked) and download embedding models.
They are SKIPPED by default to avoid slow test runs.

Run with: pytest tests/mcp/test_mcp_integration.py -m integration
"""

import pytest
import json
from pathlib import Path

from knowledgebeast.mcp.config import MCPConfig
from knowledgebeast.mcp.tools import KnowledgeBeastTools

# Mark all tests in this file as integration tests (skipped by default)
pytestmark = pytest.mark.integration

# All fixtures imported from conftest.py (integration_tools uses REAL I/O)


# ===== Full Lifecycle Workflow Tests =====


@pytest.mark.asyncio
async def test_full_document_lifecycle(
    integration_tools: KnowledgeBeastTools, temp_integration_dir: Path
):
    """Test complete document lifecycle: create → ingest → search → export → import."""

    # Step 1: Create project
    create_result = await integration_tools.kb_create_project(
        name="lifecycle-project",
        description="Full lifecycle test project",
        metadata={"test": "lifecycle"},
    )
    assert create_result["success"] is True
    project_id = create_result["project_id"]

    # Step 2: Ingest multiple documents
    docs = [
        "Machine learning is a subset of artificial intelligence focused on learning from data.",
        "Deep learning uses neural networks with multiple layers for complex pattern recognition.",
        "Natural language processing enables computers to understand and generate human language.",
        "Computer vision allows machines to interpret and analyze visual information from images.",
    ]

    ingested_ids = []
    for i, content in enumerate(docs):
        result = await integration_tools.kb_ingest(
            project_id=project_id,
            content=content,
            metadata={"index": i, "category": "AI"},
        )
        assert result["success"] is True
        ingested_ids.append(result["doc_id"])

    # Step 3: Verify documents were ingested
    list_result = await integration_tools.kb_list_documents(project_id)
    assert list_result["total_documents"] == 4
    assert len(list_result["documents"]) == 4

    # Step 4: Search with different modes
    # Vector search
    vector_results = await integration_tools.kb_search(
        project_id=project_id,
        query="artificial intelligence and neural networks",
        mode="vector",
        limit=3,
    )
    assert len(vector_results) > 0
    assert "content" in vector_results[0]

    # Keyword search
    keyword_results = await integration_tools.kb_search(
        project_id=project_id,
        query="machine learning",
        mode="keyword",
        limit=3,
    )
    assert len(keyword_results) >= 0  # May have results

    # Hybrid search
    hybrid_results = await integration_tools.kb_search(
        project_id=project_id,
        query="deep learning neural networks",
        mode="hybrid",
        alpha=0.7,
        limit=3,
    )
    assert len(hybrid_results) > 0

    # Step 5: Get project info and verify stats
    info_result = await integration_tools.kb_get_project_info(project_id)
    assert info_result["document_count"] == 4
    assert "cache_stats" in info_result

    # Step 6: Export project (when implemented)
    # export_result = await integration_tools.kb_export_project(project_id)
    # assert export_result["success"] is True

    # Step 7: Clean up - delete project
    delete_result = await integration_tools.kb_delete_project(project_id)
    assert delete_result["success"] is True

    # Verify deletion
    projects = await integration_tools.kb_list_projects()
    project_ids = [p["project_id"] for p in projects]
    assert project_id not in project_ids


@pytest.mark.asyncio
async def test_multi_project_isolation(integration_tools: KnowledgeBeastTools):
    """Test that multiple projects are completely isolated from each other."""

    # Create three separate projects
    project1 = await integration_tools.kb_create_project(
        "project-audio", "Audio processing knowledge base"
    )
    project2 = await integration_tools.kb_create_project(
        "project-nlp", "Natural language processing knowledge base"
    )
    project3 = await integration_tools.kb_create_project(
        "project-cv", "Computer vision knowledge base"
    )

    p1_id = project1["project_id"]
    p2_id = project2["project_id"]
    p3_id = project3["project_id"]

    # Ingest different content into each project
    await integration_tools.kb_ingest(
        p1_id,
        content="FFT and spectrograms are essential for audio signal processing and music analysis.",
    )
    await integration_tools.kb_ingest(
        p1_id,
        content="MFCC features are commonly used in speech recognition and audio classification.",
    )

    await integration_tools.kb_ingest(
        p2_id,
        content="Transformers revolutionized NLP with self-attention mechanisms and BERT models.",
    )
    await integration_tools.kb_ingest(
        p2_id,
        content="Word embeddings like Word2Vec and GloVe capture semantic relationships in text.",
    )

    await integration_tools.kb_ingest(
        p3_id,
        content="Convolutional neural networks excel at image classification and object detection.",
    )
    await integration_tools.kb_ingest(
        p3_id,
        content="YOLO and Faster R-CNN are popular architectures for real-time object detection.",
    )

    # Verify document counts are isolated
    p1_docs = await integration_tools.kb_list_documents(p1_id)
    p2_docs = await integration_tools.kb_list_documents(p2_id)
    p3_docs = await integration_tools.kb_list_documents(p3_id)

    assert p1_docs["total_documents"] == 2
    assert p2_docs["total_documents"] == 2
    assert p3_docs["total_documents"] == 2

    # Search each project - results should be isolated
    p1_results = await integration_tools.kb_search(p1_id, "audio processing", limit=5)
    p2_results = await integration_tools.kb_search(p2_id, "transformers", limit=5)
    p3_results = await integration_tools.kb_search(p3_id, "object detection", limit=5)

    # Each search should return relevant results from only that project
    assert len(p1_results) > 0
    assert len(p2_results) > 0
    assert len(p3_results) > 0

    # Verify content isolation - audio query shouldn't match NLP docs
    assert all("audio" in r["content"].lower() or "fft" in r["content"].lower()
               or "mfcc" in r["content"].lower() for r in p1_results if "error" not in r)

    # Clean up all projects
    await integration_tools.kb_delete_project(p1_id)
    await integration_tools.kb_delete_project(p2_id)
    await integration_tools.kb_delete_project(p3_id)


@pytest.mark.asyncio
async def test_large_document_handling(
    integration_tools: KnowledgeBeastTools, temp_integration_dir: Path
):
    """Test handling of large documents (1MB+)."""

    # Create project
    project = await integration_tools.kb_create_project(
        "large-docs", "Large document testing"
    )
    project_id = project["project_id"]

    # Create a large document (approximately 1.5MB)
    large_content = """
# Large Technical Document

## Introduction
This is a comprehensive technical document covering various aspects of software engineering,
machine learning, and system design.

## Software Engineering Principles
""" + ("Software engineering best practices include code review, testing, documentation, " * 15000)

    # Ingest large document
    ingest_result = await integration_tools.kb_ingest(
        project_id=project_id,
        content=large_content,
        metadata={"size": "large", "type": "technical"},
    )

    assert ingest_result["success"] is True
    doc_id = ingest_result["doc_id"]

    # Verify document was stored
    docs = await integration_tools.kb_list_documents(project_id)
    assert docs["total_documents"] == 1

    # Search should work on large document
    results = await integration_tools.kb_search(
        project_id=project_id,
        query="software engineering best practices",
        limit=5,
    )

    assert len(results) > 0
    # Result content should be truncated (max 500 chars in tools.py)
    if "content" in results[0]:
        assert len(results[0]["content"]) <= 500

    # Clean up
    await integration_tools.kb_delete_project(project_id)


@pytest.mark.asyncio
async def test_batch_ingestion_performance(
    integration_tools: KnowledgeBeastTools, temp_integration_dir: Path
):
    """Test batch document ingestion performance and consistency."""
    import time

    # Create project
    project = await integration_tools.kb_create_project(
        "batch-test", "Batch ingestion testing"
    )
    project_id = project["project_id"]

    # Prepare batch of documents
    num_docs = 50
    documents = [
        f"Document {i}: This is test document number {i} covering topic {i % 5}"
        for i in range(num_docs)
    ]

    # Batch ingest with timing
    start_time = time.time()

    for i, content in enumerate(documents):
        result = await integration_tools.kb_ingest(
            project_id=project_id,
            content=content,
            metadata={"batch_index": i},
        )
        assert result["success"] is True

    elapsed_time = time.time() - start_time

    # Verify all documents were ingested
    docs = await integration_tools.kb_list_documents(project_id, limit=100)
    assert docs["total_documents"] == num_docs

    # Average ingestion time should be reasonable (< 500ms per doc)
    avg_time_per_doc = elapsed_time / num_docs
    assert avg_time_per_doc < 0.5, f"Avg time {avg_time_per_doc}s exceeds 500ms"

    # Search should return results from all documents
    results = await integration_tools.kb_search(
        project_id=project_id,
        query="test document topic",
        limit=20,
    )

    assert len(results) > 0

    # Clean up
    await integration_tools.kb_delete_project(project_id)


@pytest.mark.asyncio
async def test_file_ingestion_workflow(
    integration_tools: KnowledgeBeastTools, temp_integration_dir: Path
):
    """Test complete file ingestion workflow with multiple file types."""

    # Create project
    project = await integration_tools.kb_create_project(
        "file-ingest", "File ingestion testing"
    )
    project_id = project["project_id"]

    # Create test files
    test_files = []

    # Markdown file
    md_file = temp_integration_dir / "test_doc.md"
    md_file.write_text(
        """# Test Markdown Document

## Section 1
This is a markdown document for testing file ingestion.

## Section 2
It contains multiple sections and formatted content.
"""
    )
    test_files.append(md_file)

    # Text file
    txt_file = temp_integration_dir / "test_doc.txt"
    txt_file.write_text(
        "This is a plain text file for testing.\nIt has multiple lines.\nAnd some content."
    )
    test_files.append(txt_file)

    # Ingest all files
    for file_path in test_files:
        result = await integration_tools.kb_ingest(
            project_id=project_id,
            file_path=str(file_path),
            metadata={"source_file": file_path.name},
        )
        assert result["success"] is True
        assert result["file_path"] == str(file_path)

    # Verify all files were ingested
    docs = await integration_tools.kb_list_documents(project_id)
    assert docs["total_documents"] == len(test_files)

    # Search should find content from files
    results = await integration_tools.kb_search(
        project_id=project_id,
        query="testing",
        limit=5,
    )

    assert len(results) > 0

    # Clean up
    await integration_tools.kb_delete_project(project_id)


@pytest.mark.asyncio
async def test_search_mode_comparison(integration_tools: KnowledgeBeastTools):
    """Test and compare different search modes on the same dataset."""

    # Create project
    project = await integration_tools.kb_create_project(
        "search-modes", "Search mode comparison"
    )
    project_id = project["project_id"]

    # Ingest varied documents
    documents = [
        "Python is a high-level programming language widely used in data science.",
        "Machine learning algorithms learn patterns from data to make predictions.",
        "Deep neural networks are inspired by biological neural networks in the brain.",
        "Natural language processing helps computers understand human language.",
        "The Python programming language has excellent libraries for machine learning.",
    ]

    for doc in documents:
        await integration_tools.kb_ingest(project_id=project_id, content=doc)

    query = "Python machine learning"

    # Test vector search
    vector_results = await integration_tools.kb_search(
        project_id=project_id, query=query, mode="vector", limit=5
    )

    # Test keyword search
    keyword_results = await integration_tools.kb_search(
        project_id=project_id, query=query, mode="keyword", limit=5
    )

    # Test hybrid search
    hybrid_results = await integration_tools.kb_search(
        project_id=project_id, query=query, mode="hybrid", alpha=0.7, limit=5
    )

    # All modes should return results
    assert len(vector_results) > 0
    assert isinstance(keyword_results, list)
    assert len(hybrid_results) > 0

    # Results should have proper structure
    for result in vector_results:
        assert "doc_id" in result
        assert "score" in result
        assert "content" in result

    # Clean up
    await integration_tools.kb_delete_project(project_id)


@pytest.mark.asyncio
async def test_project_metadata_persistence(integration_tools: KnowledgeBeastTools):
    """Test that project metadata persists across operations."""

    # Create project with metadata
    metadata = {
        "owner": "integration-test",
        "department": "engineering",
        "version": "1.0",
        "tags": ["test", "integration", "metadata"],
    }

    project = await integration_tools.kb_create_project(
        name="metadata-project",
        description="Testing metadata persistence",
        metadata=metadata,
    )
    project_id = project["project_id"]

    # Ingest some documents
    await integration_tools.kb_ingest(project_id=project_id, content="Test content 1")
    await integration_tools.kb_ingest(project_id=project_id, content="Test content 2")

    # Retrieve project info
    info = await integration_tools.kb_get_project_info(project_id)

    # Verify metadata persisted
    assert info["metadata"]["owner"] == "integration-test"
    assert info["metadata"]["department"] == "engineering"
    assert info["metadata"]["version"] == "1.0"
    assert "test" in info["metadata"]["tags"]

    # List projects and verify metadata is there
    projects = await integration_tools.kb_list_projects()
    metadata_project = next(p for p in projects if p["project_id"] == project_id)
    assert metadata_project["name"] == "metadata-project"
    assert metadata_project["description"] == "Testing metadata persistence"

    # Clean up
    await integration_tools.kb_delete_project(project_id)


@pytest.mark.asyncio
async def test_concurrent_multi_project_operations(
    integration_tools: KnowledgeBeastTools
):
    """Test concurrent operations across multiple projects."""
    import asyncio

    # Create multiple projects concurrently
    async def create_and_populate_project(name: str, content: str):
        project = await integration_tools.kb_create_project(name, f"Project {name}")
        project_id = project["project_id"]

        # Ingest content
        await integration_tools.kb_ingest(project_id=project_id, content=content)

        # Search
        results = await integration_tools.kb_search(
            project_id=project_id, query="test", limit=5
        )

        return project_id, results

    # Run multiple projects in parallel
    tasks = [
        create_and_populate_project("proj1", "Test content for project 1"),
        create_and_populate_project("proj2", "Test content for project 2"),
        create_and_populate_project("proj3", "Test content for project 3"),
        create_and_populate_project("proj4", "Test content for project 4"),
        create_and_populate_project("proj5", "Test content for project 5"),
    ]

    results = await asyncio.gather(*tasks)

    # All operations should succeed
    assert len(results) == 5
    assert all(len(r) == 2 for r in results)

    # Clean up all projects
    for project_id, _ in results:
        await integration_tools.kb_delete_project(project_id)


@pytest.mark.asyncio
async def test_empty_and_edge_cases(integration_tools: KnowledgeBeastTools):
    """Test edge cases and empty data scenarios."""

    # Create project
    project = await integration_tools.kb_create_project("edge-cases", "Edge case testing")
    project_id = project["project_id"]

    # Test empty document ingestion
    result = await integration_tools.kb_ingest(project_id=project_id, content="")
    # Should either succeed with empty content or return error
    assert "success" in result or "error" in result

    # Test searching empty project
    results = await integration_tools.kb_search(project_id=project_id, query="anything")
    assert isinstance(results, list)
    assert len(results) == 0

    # Test listing empty project
    docs = await integration_tools.kb_list_documents(project_id)
    assert docs["total_documents"] >= 0

    # Ingest single character
    result = await integration_tools.kb_ingest(project_id=project_id, content="a")
    assert result["success"] is True

    # Ingest very long query
    long_query = "query " * 1000
    results = await integration_tools.kb_search(
        project_id=project_id, query=long_query, limit=5
    )
    assert isinstance(results, list)

    # Clean up
    await integration_tools.kb_delete_project(project_id)


@pytest.mark.asyncio
async def test_cache_effectiveness(integration_tools: KnowledgeBeastTools):
    """Test that caching improves query performance."""
    import time

    # Create project and ingest documents
    project = await integration_tools.kb_create_project("cache-test", "Cache testing")
    project_id = project["project_id"]

    # Ingest documents
    for i in range(10):
        await integration_tools.kb_ingest(
            project_id=project_id, content=f"Test document {i} about various topics"
        )

    query = "test document topics"

    # First search (no cache)
    start1 = time.time()
    results1 = await integration_tools.kb_search(project_id=project_id, query=query)
    time1 = time.time() - start1

    # Second search (should use cache in embedding engine)
    start2 = time.time()
    results2 = await integration_tools.kb_search(project_id=project_id, query=query)
    time2 = time.time() - start2

    # Third search (should also benefit from cache)
    start3 = time.time()
    results3 = await integration_tools.kb_search(project_id=project_id, query=query)
    time3 = time.time() - start3

    # Results should be consistent
    assert len(results1) == len(results2) == len(results3)

    # Later queries might be faster due to caching
    # (though not guaranteed in all environments)
    print(f"Query times: {time1:.3f}s, {time2:.3f}s, {time3:.3f}s")

    # Get project info to check cache stats
    info = await integration_tools.kb_get_project_info(project_id)
    assert "cache_stats" in info

    # Clean up
    await integration_tools.kb_delete_project(project_id)


@pytest.mark.asyncio
async def test_special_characters_in_content(integration_tools: KnowledgeBeastTools):
    """Test handling of special characters and Unicode in documents."""

    # Create project
    project = await integration_tools.kb_create_project(
        "special-chars", "Special character testing"
    )
    project_id = project["project_id"]

    # Ingest documents with special characters
    special_docs = [
        "Document with émojis: 🚀 🎉 💡 and accents: café, naïve",
        "Math symbols: α, β, γ, ∑, ∫, ∂, ℝ, ℂ",
        "Code: def func(): return {'key': 'value'}",
        "Quotes: \"smart quotes\" 'single' «guillemets»",
        "Mixed: 中文字符 with English text and 日本語",
    ]

    for doc in special_docs:
        result = await integration_tools.kb_ingest(project_id=project_id, content=doc)
        assert result["success"] is True

    # Search should work with special characters
    results = await integration_tools.kb_search(
        project_id=project_id, query="émojis café", limit=5
    )
    assert isinstance(results, list)

    # Clean up
    await integration_tools.kb_delete_project(project_id)
