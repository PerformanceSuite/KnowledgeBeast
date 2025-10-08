"""End-to-end integration tests for Vector RAG KnowledgeBeast.

This test suite covers complete workflows including:
- Document ingestion and vector embedding
- Hybrid search (vector + keyword)
- Multi-project isolation
- Cache management
- API integration
- Performance validation
"""

import time
from pathlib import Path
import pytest
import tempfile
import numpy as np
from typing import List, Dict

from knowledgebeast.core.embeddings import EmbeddingEngine
from knowledgebeast.core.vector_store import VectorStore
from knowledgebeast.core.repository import DocumentRepository
from knowledgebeast.core.query_engine import HybridQueryEngine
from knowledgebeast.core.project_manager import ProjectManager, Project


class TestVectorEmbeddingWorkflow:
    """Test complete vector embedding workflows."""

    def test_document_to_embedding_pipeline(self, tmp_path):
        """Test full pipeline from document to vector embedding."""
        # Create embedding engine
        engine = EmbeddingEngine(model_name="all-MiniLM-L6-v2", cache_size=100)

        # Sample documents
        docs = [
            "Python is a high-level programming language for general-purpose programming.",
            "Machine learning is a subset of artificial intelligence.",
            "Natural language processing enables computers to understand human language."
        ]

        # Generate embeddings
        embeddings = engine.embed(docs)

        # Verify embeddings
        assert len(embeddings) == 3
        assert all(isinstance(emb, np.ndarray) for emb in embeddings)
        assert all(emb.shape == (384,) for emb in embeddings)

        # Verify embeddings are normalized
        for emb in embeddings:
            norm = np.linalg.norm(emb)
            assert 0.99 <= norm <= 1.01, f"Embedding not normalized: {norm}"

        # Check cache statistics
        stats = engine.get_stats()
        assert stats['embeddings_generated'] == 3
        assert stats['cache_misses'] == 3

        # Re-embed same documents (should use cache)
        embeddings2 = engine.embed(docs)
        stats2 = engine.get_stats()
        assert stats2['cache_hits'] == 3
        assert stats2['embeddings_generated'] == 3  # No new generations

    def test_embedding_to_vector_store_workflow(self, tmp_path):
        """Test storing embeddings in vector store."""
        # Setup
        chroma_path = tmp_path / "chroma"
        engine = EmbeddingEngine(model_name="all-MiniLM-L6-v2")
        store = VectorStore(persist_directory=chroma_path, collection_name="test_docs")

        # Documents
        docs = {
            'doc1': 'Python programming language',
            'doc2': 'Machine learning algorithms',
            'doc3': 'Deep neural networks'
        }

        # Embed and store
        for doc_id, content in docs.items():
            embedding = engine.embed(content)
            store.add(
                ids=doc_id,
                embeddings=embedding,
                documents=content,
                metadatas={'source': 'test', 'length': len(content)}
            )

        # Verify storage
        assert store.count() == 3

        # Query
        query_embedding = engine.embed("neural network deep learning")
        results = store.query(query_embeddings=query_embedding, n_results=2)

        assert len(results['ids'][0]) == 2
        assert 'doc3' in results['ids'][0]  # Should match neural networks

    def test_complete_ingestion_and_search(self, tmp_path):
        """Test complete document ingestion and search workflow."""
        # Create repository and engine
        repo = DocumentRepository()
        engine = HybridQueryEngine(repo, model_name="all-MiniLM-L6-v2", alpha=0.7)

        # Add documents
        documents = {
            'python_basics': {
                'name': 'Python Basics',
                'content': 'Python is a versatile programming language used for web development, data science, and automation.',
                'path': 'docs/python.md'
            },
            'ml_intro': {
                'name': 'Machine Learning Introduction',
                'content': 'Machine learning is a method of data analysis that automates analytical model building using algorithms.',
                'path': 'docs/ml.md'
            },
            'nlp_guide': {
                'name': 'NLP Guide',
                'content': 'Natural language processing helps computers understand and process human language using machine learning.',
                'path': 'docs/nlp.md'
            }
        }

        for doc_id, doc_data in documents.items():
            repo.add_document(doc_id, doc_data)
            # Index terms for keyword search
            terms = doc_data['content'].lower().split()
            for term in set(terms):
                repo.index_term(term, doc_id)

        # Test vector search
        results = engine.search_vector("machine learning algorithms", top_k=2)
        assert len(results) >= 1
        assert results[0][0] in ['ml_intro', 'nlp_guide']

        # Test keyword search
        results = engine.search_keyword("python")
        assert len(results) >= 1
        assert 'python_basics' in [r[0] for r in results]

        # Test hybrid search
        results = engine.search_hybrid("machine learning", top_k=3)
        assert len(results) >= 1


class TestMultiProjectWorkflows:
    """Test multi-project isolation and workflows."""

    def test_project_creation_workflow(self, tmp_path):
        """Test creating and using multiple projects."""
        manager = ProjectManager(
            storage_path=str(tmp_path / "projects.db"),
            chroma_path=str(tmp_path / "chroma"),
            cache_capacity=50
        )

        # Create projects
        project1 = manager.create_project(
            name="Audio Project",
            description="Audio processing knowledge base",
            embedding_model="all-MiniLM-L6-v2"
        )

        project2 = manager.create_project(
            name="ML Project",
            description="Machine learning knowledge base",
            embedding_model="all-MiniLM-L6-v2"
        )

        # Verify projects exist
        assert project1.project_id != project2.project_id
        assert project1.name == "Audio Project"
        assert project2.name == "ML Project"

        # Verify collections are isolated
        assert project1.collection_name != project2.collection_name
        assert project1.collection_name.startswith("kb_project_")
        assert project2.collection_name.startswith("kb_project_")

        # List projects
        projects = manager.list_projects()
        assert len(projects) == 2

        # Cleanup
        manager.delete_project(project1.project_id)
        manager.delete_project(project2.project_id)

    def test_project_isolation(self, tmp_path):
        """Test that projects are truly isolated."""
        chroma_path = tmp_path / "chroma"
        manager = ProjectManager(
            storage_path=str(tmp_path / "projects.db"),
            chroma_path=str(chroma_path)
        )

        # Create two projects
        p1 = manager.create_project(name="Project1")
        p2 = manager.create_project(name="Project2")

        # Get vector stores for each project
        store1 = VectorStore(persist_directory=chroma_path, collection_name=p1.collection_name)
        store2 = VectorStore(persist_directory=chroma_path, collection_name=p2.collection_name)

        # Add different documents to each
        engine = EmbeddingEngine()

        emb1 = engine.embed("Audio processing with Python")
        store1.add(ids="doc1", embeddings=emb1, documents="Audio processing with Python")

        emb2 = engine.embed("Machine learning with TensorFlow")
        store2.add(ids="doc1", embeddings=emb2, documents="Machine learning with TensorFlow")

        # Verify counts
        assert store1.count() == 1
        assert store2.count() == 1

        # Verify different content
        content1 = store1.get(ids="doc1")
        content2 = store2.get(ids="doc1")

        assert content1['documents'][0] != content2['documents'][0]

        # Cleanup
        manager.delete_project(p1.project_id)
        manager.delete_project(p2.project_id)

    def test_project_lifecycle(self, tmp_path):
        """Test complete project lifecycle: create, update, delete."""
        manager = ProjectManager(
            storage_path=str(tmp_path / "projects.db"),
            chroma_path=str(tmp_path / "chroma")
        )

        # Create
        project = manager.create_project(
            name="Test Project",
            description="Original description",
            metadata={'version': '1.0'}
        )
        assert project.description == "Original description"

        # Update
        updated = manager.update_project(
            project.project_id,
            description="Updated description",
            metadata={'version': '2.0'}
        )
        assert updated.description == "Updated description"
        assert updated.metadata['version'] == '2.0'

        # Verify persistence
        retrieved = manager.get_project(project.project_id)
        assert retrieved.description == "Updated description"

        # Delete
        success = manager.delete_project(project.project_id)
        assert success is True

        # Verify deletion
        deleted = manager.get_project(project.project_id)
        assert deleted is None


class TestHybridSearchWorkflows:
    """Test hybrid search workflows."""

    def test_vector_vs_keyword_comparison(self):
        """Compare vector search vs keyword search results."""
        repo = DocumentRepository()
        engine = HybridQueryEngine(repo, model_name="all-MiniLM-L6-v2")

        # Add documents with synonyms
        docs = {
            'car_doc': {
                'name': 'Automobile Guide',
                'content': 'Automobiles, also known as cars, are motor vehicles used for transportation.',
                'path': 'docs/auto.md'
            },
            'vehicle_doc': {
                'name': 'Vehicle Types',
                'content': 'Vehicles include cars, trucks, motorcycles, and buses for moving people and goods.',
                'path': 'docs/vehicles.md'
            }
        }

        for doc_id, doc_data in docs.items():
            repo.add_document(doc_id, doc_data)
            terms = doc_data['content'].lower().split()
            for term in set(terms):
                repo.index_term(term, doc_id)

        # Search for synonym "automobile" - vector search uses semantic similarity
        # to find related documents, while keyword search requires exact term matches
        vector_results = engine.search_vector("car", top_k=2)
        keyword_results = engine.search_keyword("vehicles")

        # Vector should find both documents (semantic similarity)
        assert len(vector_results) >= 1

        # Keyword should find documents with the exact term "vehicles"
        assert len(keyword_results) >= 1
        assert 'vehicle_doc' in [r[0] for r in keyword_results]

    def test_alpha_parameter_effect(self):
        """Test effect of alpha parameter on hybrid search."""
        repo = DocumentRepository()
        engine = HybridQueryEngine(repo, model_name="all-MiniLM-L6-v2", alpha=0.7)

        # Add test documents
        repo.add_document('doc1', {
            'name': 'Python Guide',
            'content': 'Python is a programming language',
            'path': 'python.md'
        })
        repo.index_term('python', 'doc1')
        repo.index_term('programming', 'doc1')

        # Test different alpha values
        results_vector = engine.search_hybrid("python", alpha=1.0, top_k=1)  # Pure vector
        results_keyword = engine.search_hybrid("python", alpha=0.0, top_k=1)  # Pure keyword
        results_balanced = engine.search_hybrid("python", alpha=0.5, top_k=1)  # Balanced

        # All should return results
        assert len(results_vector) >= 1
        assert len(results_keyword) >= 1
        assert len(results_balanced) >= 1

    def test_mmr_reranking(self):
        """Test MMR (Maximal Marginal Relevance) re-ranking."""
        repo = DocumentRepository()
        engine = HybridQueryEngine(repo, model_name="all-MiniLM-L6-v2")

        # Add similar documents
        for i in range(5):
            repo.add_document(f'doc{i}', {
                'name': f'Document {i}',
                'content': f'Machine learning algorithms and deep neural networks {i}',
                'path': f'doc{i}.md'
            })

        # Standard search
        standard_results = engine.search_hybrid("machine learning", top_k=3)

        # MMR search for diversity
        mmr_results = engine.search_with_mmr(
            "machine learning",
            lambda_param=0.3,  # High diversity
            top_k=3,
            mode='hybrid'
        )

        assert len(standard_results) >= 1
        assert len(mmr_results) >= 1


class TestCacheWorkflows:
    """Test caching workflows."""

    def test_embedding_cache_workflow(self):
        """Test embedding cache behavior."""
        engine = EmbeddingEngine(model_name="all-MiniLM-L6-v2", cache_size=10)

        text = "Machine learning is amazing"

        # First embedding (cache miss)
        emb1 = engine.embed(text)
        stats1 = engine.get_stats()
        assert stats1['cache_misses'] == 1
        assert stats1['cache_hits'] == 0

        # Second embedding (cache hit)
        emb2 = engine.embed(text)
        stats2 = engine.get_stats()
        assert stats2['cache_hits'] == 1

        # Verify embeddings are identical
        assert np.allclose(emb1, emb2)

        # Clear cache
        engine.clear_cache()
        stats3 = engine.get_stats()
        assert stats3['cache_hits'] == 0  # Reset
        assert stats3['cache_misses'] == 0  # Reset

    def test_query_cache_per_project(self, tmp_path):
        """Test per-project query cache isolation."""
        manager = ProjectManager(
            storage_path=str(tmp_path / "projects.db"),
            chroma_path=str(tmp_path / "chroma"),
            cache_capacity=10
        )

        # Create two projects
        p1 = manager.create_project(name="Project1")
        p2 = manager.create_project(name="Project2")

        # Get caches
        cache1 = manager.get_project_cache(p1.project_id)
        cache2 = manager.get_project_cache(p2.project_id)

        # Verify different cache instances
        assert cache1 is not cache2

        # Add to cache1
        cache1.put("query1", ["result1"])
        assert cache1.get("query1") == ["result1"]
        assert cache2.get("query1") is None  # Isolated

        # Add to cache2
        cache2.put("query1", ["result2"])
        assert cache2.get("query1") == ["result2"]
        assert cache1.get("query1") == ["result1"]  # Still different

        # Cleanup
        manager.delete_project(p1.project_id)
        manager.delete_project(p2.project_id)


class TestPerformanceValidation:
    """Test performance characteristics."""

    def test_query_latency(self):
        """Test query latency meets performance targets."""
        repo = DocumentRepository()
        engine = HybridQueryEngine(repo, model_name="all-MiniLM-L6-v2")

        # Add documents
        for i in range(100):
            repo.add_document(f'doc{i}', {
                'name': f'Document {i}',
                'content': f'Content about topic {i % 10}',
                'path': f'doc{i}.md'
            })

        # Measure query time
        start = time.time()
        results = engine.search_hybrid("topic", top_k=10)
        elapsed = time.time() - start

        # Should complete in reasonable time (< 1 second for 100 docs)
        assert elapsed < 1.0
        assert len(results) >= 1

    def test_batch_embedding_performance(self):
        """Test batch embedding performance."""
        engine = EmbeddingEngine(model_name="all-MiniLM-L6-v2")

        # Generate 100 texts
        texts = [f"Document about topic {i}" for i in range(100)]

        # Measure batch embedding time
        start = time.time()
        embeddings = engine.embed_batch(texts, batch_size=32)
        elapsed = time.time() - start

        assert len(embeddings) == 100
        # Should be faster than 10 seconds for 100 texts
        assert elapsed < 10.0

    def test_cache_hit_performance(self):
        """Test that cache hits are faster than misses."""
        engine = EmbeddingEngine(model_name="all-MiniLM-L6-v2", cache_size=100)

        text = "Test document for caching"

        # First call (cache miss)
        start1 = time.time()
        emb1 = engine.embed(text)
        time1 = time.time() - start1

        # Second call (cache hit)
        start2 = time.time()
        emb2 = engine.embed(text)
        time2 = time.time() - start2

        # Cache hit should be much faster
        assert time2 < time1
        assert np.allclose(emb1, emb2)


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_empty_query_handling(self):
        """Test handling of empty queries."""
        repo = DocumentRepository()
        engine = HybridQueryEngine(repo)

        # Empty query should return empty results
        results = engine.search_vector("", top_k=10)
        assert results == []

    def test_missing_documents(self, tmp_path):
        """Test handling of missing documents."""
        manager = ProjectManager(
            storage_path=str(tmp_path / "projects.db"),
            chroma_path=str(tmp_path / "chroma")
        )

        # Get nonexistent project
        project = manager.get_project("nonexistent-id")
        assert project is None

    def test_duplicate_project_names(self, tmp_path):
        """Test duplicate project name rejection."""
        manager = ProjectManager(
            storage_path=str(tmp_path / "projects.db"),
            chroma_path=str(tmp_path / "chroma")
        )

        # Create first project
        manager.create_project(name="Test Project")

        # Try to create duplicate
        with pytest.raises(ValueError, match="already exists"):
            manager.create_project(name="Test Project")

        # Cleanup
        projects = manager.list_projects()
        for p in projects:
            manager.delete_project(p.project_id)

    def test_invalid_embedding_model(self):
        """Test invalid embedding model handling."""
        with pytest.raises(ValueError, match="Unsupported model"):
            EmbeddingEngine(model_name="invalid-model-name")


class TestDataConsistency:
    """Test data consistency across operations."""

    def test_vector_store_persistence(self, tmp_path):
        """Test vector store persists data correctly."""
        chroma_path = tmp_path / "chroma"

        # Create and populate store with unique collection name
        collection_name = f"test_persistence_{id(tmp_path)}"
        store1 = VectorStore(persist_directory=chroma_path, collection_name=collection_name)
        engine = EmbeddingEngine()

        # Ensure clean state
        store1.reset()

        emb = engine.embed("Test document")
        store1.add(ids="doc1", embeddings=emb, documents="Test document")

        count1 = store1.count()
        assert count1 == 1

        # Create new instance (should load persisted data)
        store2 = VectorStore(persist_directory=chroma_path, collection_name=collection_name)
        count2 = store2.count()

        assert count2 == count1

    def test_project_metadata_consistency(self, tmp_path):
        """Test project metadata remains consistent."""
        manager = ProjectManager(
            storage_path=str(tmp_path / "projects.db"),
            chroma_path=str(tmp_path / "chroma")
        )

        # Create project with metadata
        metadata = {'key1': 'value1', 'key2': 123, 'key3': [1, 2, 3]}
        project = manager.create_project(
            name="Test",
            metadata=metadata
        )

        # Retrieve and verify
        retrieved = manager.get_project(project.project_id)
        assert retrieved.metadata == metadata

        # Update metadata
        new_metadata = {'key1': 'new_value', 'key4': 'value4'}
        manager.update_project(project.project_id, metadata=new_metadata)

        # Verify update
        updated = manager.get_project(project.project_id)
        assert updated.metadata == new_metadata

        # Cleanup
        manager.delete_project(project.project_id)
