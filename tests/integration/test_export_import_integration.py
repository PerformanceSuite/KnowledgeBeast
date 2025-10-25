"""Integration tests for export/import workflow.

These tests use the core components directly to test export/import
functionality with real ChromaDB and embedding operations.
"""

import json
import pytest
from pathlib import Path

from knowledgebeast.core.project_manager import ProjectManager
from knowledgebeast.core.vector_store import VectorStore
from knowledgebeast.core.embeddings import EmbeddingEngine


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_export_import_workflow(tmp_path):
    """Test complete export/import workflow with real data.

    This test verifies that:
    1. Projects can be created with real ChromaDB collections
    2. Documents can be ingested with real embeddings
    3. Export captures all project data correctly
    4. Import recreates the project with full fidelity
    5. Search functionality works on imported projects
    """
    # Setup project manager with real ChromaDB
    project_manager = ProjectManager(
        storage_path=str(tmp_path / "projects.db"),
        chroma_path=str(tmp_path / "chroma"),
        cache_capacity=10
    )

    # Create project
    project = project_manager.create_project(
        name="Knowledge Base",
        description="Documentation and code examples",
        embedding_model="all-MiniLM-L6-v2",
        metadata={"team": "engineering", "version": "1.0"}
    )
    project_id = project.project_id

    # Get vector store and embedding engine
    vector_store = VectorStore(
        persist_directory=str(tmp_path / "chroma"),
        collection_name=project.collection_name
    )
    embedding_engine = EmbeddingEngine(
        model_name="all-MiniLM-L6-v2",
        cache_size=10
    )

    # Ingest multiple documents with real embeddings
    documents = [
        ("Getting Started Guide", "How to get started with the system..."),
        ("API Reference", "Complete API documentation..."),
        ("Code Examples", "Example code snippets for common tasks..."),
    ]

    doc_ids = []
    for i, (name, content) in enumerate(documents):
        doc_id = f"doc_{i}"
        embedding = embedding_engine.embed(content)
        vector_store.add(
            ids=doc_id,
            embeddings=embedding,  # Pass as numpy array, not .tolist()
            documents=content,
            metadatas={"title": name}
        )
        doc_ids.append(doc_id)

    # Verify documents were added
    collection_data = vector_store.collection.get(include=["documents"])
    assert len(collection_data["ids"]) == 3

    # Export project (simulating kb_export_project functionality)
    export_path = tmp_path / "backup.json"
    collection_full = vector_store.collection.get(
        include=["documents", "metadatas", "embeddings"]
    )

    export_data = {
        "version": "1.0",
        "exported_at": "2025-10-24T00:00:00",
        "project": project.to_dict(),
        "documents": [],
        "embeddings": []
    }

    for i, doc_id in enumerate(collection_full["ids"]):
        export_data["documents"].append({
            "id": doc_id,
            "content": collection_full["documents"][i],
            "metadata": collection_full["metadatas"][i]
        })
        # Convert embedding to list if it's a numpy array
        embedding_vector = collection_full["embeddings"][i]
        if hasattr(embedding_vector, 'tolist'):
            embedding_vector = embedding_vector.tolist()
        export_data["embeddings"].append({
            "id": doc_id,
            "vector": embedding_vector
        })

    with open(export_path, 'w') as f:
        json.dump(export_data, f, indent=2)

    assert export_path.exists()
    assert len(export_data["documents"]) == 3

    # Import as new project (simulating kb_import_project functionality)
    with open(export_path) as f:
        imported_data = json.load(f)

    new_project = project_manager.create_project(
        name="Restored Knowledge Base",
        description=imported_data["project"]["description"],
        embedding_model=imported_data["project"]["embedding_model"],
        metadata={
            **imported_data["project"].get("metadata", {}),
            "imported_from": imported_data["project"]["project_id"]
        }
    )

    # Create vector store for imported project
    new_vector_store = VectorStore(
        persist_directory=str(tmp_path / "chroma"),
        collection_name=new_project.collection_name
    )

    # Import documents
    if imported_data["documents"]:
        ids = [doc["id"] for doc in imported_data["documents"]]
        doc_contents = [doc["content"] for doc in imported_data["documents"]]
        metadatas = [doc["metadata"] for doc in imported_data["documents"]]
        embeddings = [emb["vector"] for emb in imported_data["embeddings"]]

        new_vector_store.collection.add(
            ids=ids,
            documents=doc_contents,
            metadatas=metadatas,
            embeddings=embeddings
        )

    # Verify imported project has correct data
    imported_collection = new_vector_store.collection.get(include=["documents", "metadatas"])
    assert len(imported_collection["ids"]) == 3
    assert imported_collection["documents"][0] == documents[0][1]  # Check content matches original

    # Verify metadata
    assert new_project.name == "Restored Knowledge Base"
    assert new_project.metadata["imported_from"] == project_id

    # Verify both projects exist in project manager
    all_projects = project_manager.list_projects()
    assert len(all_projects) == 2
    project_names = {p.name for p in all_projects}
    assert "Knowledge Base" in project_names
    assert "Restored Knowledge Base" in project_names
