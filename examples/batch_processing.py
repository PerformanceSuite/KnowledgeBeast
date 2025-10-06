"""Batch processing example.

This example demonstrates:
- Batch document ingestion
- Progress tracking
- Error handling
- Performance optimization
"""

from pathlib import Path
from typing import List
from tqdm import tqdm
from knowledgebeast import KnowledgeBeast, KnowledgeBeastConfig


def batch_ingest(kb: KnowledgeBeast, files: List[Path]) -> dict:
    """Ingest multiple files with progress tracking."""
    results = {
        "successful": 0,
        "failed": 0,
        "total_chunks": 0,
        "errors": []
    }

    for file in tqdm(files, desc="Ingesting documents"):
        try:
            chunks = kb.ingest_document(file)
            results["successful"] += 1
            results["total_chunks"] += chunks
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({
                "file": str(file),
                "error": str(e)
            })

    return results


def batch_query(kb: KnowledgeBeast, queries: List[str]) -> dict:
    """Execute multiple queries efficiently."""
    results = {}

    for query in tqdm(queries, desc="Running queries"):
        try:
            results[query] = kb.query(query, n_results=5)
        except Exception as e:
            results[query] = {"error": str(e)}

    return results


def main():
    """Batch processing example."""
    print("KnowledgeBeast - Batch Processing Example\n")

    # Configure for batch processing
    config = KnowledgeBeastConfig(
        data_dir=Path("./batch-data"),
        cache_size=500,  # Large cache for batch queries
        log_level="WARNING"  # Reduce logging noise
    )

    with KnowledgeBeast(config) as kb:
        # Example 1: Batch ingestion
        print("1. Batch Document Ingestion")
        print("-" * 50)

        # Find all markdown files
        docs_dir = Path("./documents")
        if docs_dir.exists():
            files = list(docs_dir.glob("**/*.md"))
            print(f"Found {len(files)} markdown files")

            if files:
                ingest_results = batch_ingest(kb, files)

                print(f"\nIngestion Results:")
                print(f"  Successful: {ingest_results['successful']}")
                print(f"  Failed: {ingest_results['failed']}")
                print(f"  Total chunks: {ingest_results['total_chunks']}")

                if ingest_results['errors']:
                    print(f"\nErrors:")
                    for error in ingest_results['errors']:
                        print(f"  - {error['file']}: {error['error']}")
        else:
            print(f"Documents directory not found: {docs_dir}")

        # Example 2: Batch queries
        print("\n2. Batch Query Processing")
        print("-" * 50)

        queries = [
            "machine learning",
            "neural networks",
            "deep learning",
            "artificial intelligence",
            "data science"
        ]

        print(f"Running {len(queries)} queries...")
        query_results = batch_query(kb, queries)

        print(f"\nQuery Results:")
        for query, results in query_results.items():
            if "error" in results:
                print(f"  {query}: ERROR - {results['error']}")
            else:
                print(f"  {query}: {len(results)} results")

        # Example 3: Cache warming
        print("\n3. Cache Warming")
        print("-" * 50)

        print("Warming cache with common queries...")
        for query in tqdm(queries, desc="Warming cache"):
            kb.query(query)

        stats = kb.get_stats()
        print(f"Cache size: {stats['cache_stats']['size']}")
        print(f"Hit rate: {stats['cache_stats']['hit_rate']:.2%}")

    print("\n✓ Batch processing complete!")


if __name__ == "__main__":
    main()
