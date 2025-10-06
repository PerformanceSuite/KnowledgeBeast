"""Basic usage example for KnowledgeBeast.

This example demonstrates:
- Initializing KnowledgeBeast
- Ingesting a document
- Querying the knowledge base
- Processing results
"""

from pathlib import Path
from knowledgebeast import KnowledgeBeast, KnowledgeBeastConfig


def main():
    """Basic usage example."""
    print("KnowledgeBeast - Basic Usage Example\n")

    # Initialize with default configuration
    print("1. Initializing KnowledgeBeast...")
    kb = KnowledgeBeast()

    # Or use custom configuration
    # config = KnowledgeBeastConfig(
    #     data_dir=Path("./my-data"),
    #     cache_size=200,
    #     embedding_model="all-mpnet-base-v2"
    #     )
    # kb = KnowledgeBeast(config)

    # Ingest a document
    print("2. Ingesting document...")
    try:
        # Replace with your document path
        doc_path = Path("README.md")
        if doc_path.exists():
            chunks = kb.ingest_document(doc_path)
            print(f"   ✓ Ingested {chunks} chunks from {doc_path.name}")
        else:
            print(f"   ⚠ Document not found: {doc_path}")
    except Exception as e:
        print(f"   ✗ Ingestion error: {e}")

    # Query the knowledge base
    print("\n3. Querying knowledge base...")
    query_text = "knowledge management"
    results = kb.query(query_text, n_results=3)

    print(f"\n   Found {len(results)} results for '{query_text}':\n")

    # Process results
    for i, result in enumerate(results, 1):
        print(f"   Result {i}:")
        print(f"   Text: {result['text'][:200]}...")
        print(f"   Source: {result['metadata']['source']}")
        print(f"   Distance: {result['distance']:.4f}")
        print()

    # Get statistics
    print("4. Statistics:")
    stats = kb.get_stats()
    print(f"   Total documents: {stats['total_documents']}")
    print(f"   Cache size: {stats['cache_stats']['size']}")
    print(f"   Cache hits: {stats['cache_stats']['hits']}")
    print(f"   Hit rate: {stats['cache_stats']['hit_rate']:.2%}")

    # Cleanup
    print("\n5. Cleaning up...")
    kb.shutdown()
    print("   ✓ Done!")


if __name__ == "__main__":
    main()
