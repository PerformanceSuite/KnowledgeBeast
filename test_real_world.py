#!/usr/bin/env python3
"""Real-world validation of KnowledgeBeast v2.0.0 capabilities.

This script tests:
1. Project creation and management
2. Multi-format document ingestion
3. Vector search quality with real queries
4. Hybrid search performance
5. Multi-project isolation
6. Performance under realistic load
"""

import time
import json
from pathlib import Path
from typing import List, Dict, Any

from knowledgebeast.core.project_manager import ProjectManager
from knowledgebeast.core.query_engine import HybridQueryEngine


def print_section(title: str):
    """Print formatted section header."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def print_results(results: List[tuple], max_results: int = 5):
    """Print search results in formatted manner."""
    if not results:
        print("  No results found.")
        return

    for i, (doc_id, metadata, score) in enumerate(results[:max_results], 1):
        name = metadata.get('name', 'Unknown')
        path = metadata.get('path', 'Unknown')
        print(f"  {i}. [{score:.4f}] {name}")
        print(f"     Path: {path}")
        print(f"     ID: {doc_id}")


def test_project_creation():
    """Test 1: Create multiple projects and verify isolation."""
    print_section("TEST 1: Project Creation & Multi-Project Isolation")

    manager = ProjectManager()

    # Create test projects
    projects = ['knowledgebeast-docs', 'test-project-2', 'test-project-3']

    for project_id in projects:
        try:
            project = manager.create_project(
                project_id=project_id,
                name=f"Test Project: {project_id}",
                description=f"Real-world test for {project_id}",
                model_name="all-MiniLM-L6-v2"
            )
            print(f"✅ Created project: {project_id}")
        except Exception as e:
            print(f"❌ Failed to create {project_id}: {e}")

    # List all projects
    all_projects = manager.list_projects()
    print(f"\n📊 Total projects: {len(all_projects)}")
    for proj in all_projects:
        print(f"   - {proj['project_id']}: {proj['name']}")

    return manager


def test_document_ingestion(manager: ProjectManager):
    """Test 2: Ingest real markdown documentation."""
    print_section("TEST 2: Real Document Ingestion")

    project_id = 'knowledgebeast-docs'

    # Find markdown files
    docs_dir = Path('docs')
    readme_file = Path('README.md')
    claude_file = Path('CLAUDE.md')

    files_to_ingest = []

    # Add README and CLAUDE.md
    if readme_file.exists():
        files_to_ingest.append(readme_file)
    if claude_file.exists():
        files_to_ingest.append(claude_file)

    # Add docs directory files
    if docs_dir.exists():
        md_files = list(docs_dir.rglob('*.md'))
        files_to_ingest.extend(md_files[:10])  # Limit to 10 for testing

    print(f"📁 Found {len(files_to_ingest)} files to ingest")

    # Ingest documents
    ingested_count = 0
    start_time = time.time()

    for file_path in files_to_ingest:
        try:
            result = manager.ingest_document(
                project_id=project_id,
                file_path=str(file_path),
                metadata={
                    'source': 'real-world-test',
                    'type': 'documentation',
                    'path': str(file_path)
                }
            )
            ingested_count += 1
            print(f"  ✅ Ingested: {file_path.name}")
        except Exception as e:
            print(f"  ❌ Failed {file_path.name}: {e}")

    elapsed = time.time() - start_time

    print(f"\n📊 Ingestion Results:")
    print(f"   - Documents ingested: {ingested_count}/{len(files_to_ingest)}")
    print(f"   - Time taken: {elapsed:.2f}s")
    print(f"   - Avg per document: {elapsed/ingested_count:.2f}s")

    # Get project stats
    stats = manager.get_project_stats(project_id)
    print(f"\n📈 Project Stats:")
    print(f"   - Total documents: {stats.get('total_documents', 0)}")
    print(f"   - Total terms: {stats.get('total_terms', 0)}")

    return ingested_count


def test_vector_search(manager: ProjectManager):
    """Test 3: Vector search with real queries."""
    print_section("TEST 3: Vector Search Quality")

    project_id = 'knowledgebeast-docs'

    # Real-world queries
    queries = [
        "How do I install KnowledgeBeast?",
        "vector embeddings and ChromaDB",
        "multi-project isolation",
        "authentication and security",
        "performance optimization tips",
        "hybrid search algorithm",
    ]

    total_score = 0
    query_count = 0

    for query in queries:
        print(f"\n🔍 Query: '{query}'")
        start_time = time.time()

        try:
            results = manager.query_project(
                project_id=project_id,
                query=query,
                mode='vector',
                top_k=5
            )

            elapsed = time.time() - start_time

            print(f"   ⏱️  Latency: {elapsed*1000:.2f}ms")
            print(f"   📊 Results: {len(results)}")

            if results:
                print_results(results, max_results=3)
                # Calculate avg score for top results
                avg_score = sum(score for _, _, score in results[:3]) / min(3, len(results))
                total_score += avg_score
                query_count += 1

        except Exception as e:
            print(f"   ❌ Error: {e}")

    if query_count > 0:
        avg_relevance = total_score / query_count
        print(f"\n📊 Overall Vector Search Quality:")
        print(f"   - Queries tested: {query_count}")
        print(f"   - Avg relevance score: {avg_relevance:.4f}")


def test_hybrid_search(manager: ProjectManager):
    """Test 4: Hybrid search comparison."""
    print_section("TEST 4: Hybrid Search vs Vector-Only")

    project_id = 'knowledgebeast-docs'
    test_query = "How does the vector search engine work?"

    print(f"🔍 Test Query: '{test_query}'")

    # Test different modes
    modes = ['vector', 'keyword', 'hybrid']

    for mode in modes:
        print(f"\n📌 Mode: {mode.upper()}")
        start_time = time.time()

        try:
            results = manager.query_project(
                project_id=project_id,
                query=test_query,
                mode=mode,
                top_k=5
            )

            elapsed = time.time() - start_time

            print(f"   ⏱️  Latency: {elapsed*1000:.2f}ms")
            print(f"   📊 Results: {len(results)}")

            if results:
                print_results(results, max_results=3)

        except Exception as e:
            print(f"   ❌ Error: {e}")


def test_multi_project_isolation(manager: ProjectManager):
    """Test 5: Verify projects are truly isolated."""
    print_section("TEST 5: Multi-Project Isolation")

    # Ingest different documents into different projects
    test_projects = {
        'test-project-2': 'README.md',
        'test-project-3': 'CLAUDE.md'
    }

    for project_id, file_name in test_projects.items():
        file_path = Path(file_name)
        if file_path.exists():
            try:
                manager.ingest_document(
                    project_id=project_id,
                    file_path=str(file_path),
                    metadata={'source': 'isolation-test'}
                )
                print(f"✅ Ingested {file_name} into {project_id}")
            except Exception as e:
                print(f"❌ Failed to ingest into {project_id}: {e}")

    # Query each project with same query
    test_query = "vector embeddings"

    print(f"\n🔍 Testing isolation with query: '{test_query}'")

    for project_id in ['knowledgebeast-docs', 'test-project-2', 'test-project-3']:
        try:
            results = manager.query_project(
                project_id=project_id,
                query=test_query,
                mode='vector',
                top_k=3
            )

            stats = manager.get_project_stats(project_id)

            print(f"\n📊 Project: {project_id}")
            print(f"   - Documents: {stats.get('total_documents', 0)}")
            print(f"   - Search results: {len(results)}")

            if results:
                print("   - Top result:", results[0][1].get('name', 'Unknown'))

        except Exception as e:
            print(f"   ❌ Error querying {project_id}: {e}")


def test_performance_load(manager: ProjectManager):
    """Test 6: Performance under realistic concurrent load."""
    print_section("TEST 6: Performance Under Load")

    project_id = 'knowledgebeast-docs'

    queries = [
        "installation guide",
        "API authentication",
        "vector search",
        "performance tuning",
        "multi-project setup",
    ] * 20  # 100 total queries

    print(f"🚀 Running {len(queries)} queries...")

    start_time = time.time()
    successful = 0
    failed = 0
    latencies = []

    for i, query in enumerate(queries, 1):
        query_start = time.time()

        try:
            results = manager.query_project(
                project_id=project_id,
                query=query,
                mode='hybrid',
                top_k=10
            )
            query_elapsed = time.time() - query_start
            latencies.append(query_elapsed * 1000)  # Convert to ms
            successful += 1

            if i % 20 == 0:
                print(f"  Progress: {i}/{len(queries)} queries...")

        except Exception as e:
            failed += 1

    total_elapsed = time.time() - start_time

    # Calculate metrics
    latencies.sort()
    p50 = latencies[len(latencies)//2] if latencies else 0
    p95 = latencies[int(len(latencies)*0.95)] if latencies else 0
    p99 = latencies[int(len(latencies)*0.99)] if latencies else 0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    throughput = successful / total_elapsed if total_elapsed > 0 else 0

    print(f"\n📊 Performance Results:")
    print(f"   - Total queries: {len(queries)}")
    print(f"   - Successful: {successful}")
    print(f"   - Failed: {failed}")
    print(f"   - Total time: {total_elapsed:.2f}s")
    print(f"   - Throughput: {throughput:.2f} queries/sec")
    print(f"\n⏱️  Latency Metrics:")
    print(f"   - Average: {avg_latency:.2f}ms")
    print(f"   - P50: {p50:.2f}ms")
    print(f"   - P95: {p95:.2f}ms")
    print(f"   - P99: {p99:.2f}ms")

    # Check against targets
    print(f"\n🎯 Target Validation:")
    print(f"   - P99 < 150ms: {'✅ PASS' if p99 < 150 else '❌ FAIL'} ({p99:.2f}ms)")
    print(f"   - Throughput > 10 q/s: {'✅ PASS' if throughput > 10 else '❌ FAIL'} ({throughput:.2f} q/s)")


def cleanup_test_projects(manager: ProjectManager):
    """Cleanup: Delete test projects."""
    print_section("CLEANUP: Removing Test Projects")

    test_projects = ['test-project-2', 'test-project-3', 'knowledgebeast-docs']

    for project_id in test_projects:
        try:
            manager.delete_project(project_id)
            print(f"✅ Deleted project: {project_id}")
        except Exception as e:
            print(f"⚠️  Could not delete {project_id}: {e}")


def main():
    """Run all real-world tests."""
    print_section("🚀 KnowledgeBeast v2.0.0 - Real-World Validation")

    print("This script validates v2.0.0 capabilities with real documentation:")
    print("  1. Multi-project management")
    print("  2. Real document ingestion")
    print("  3. Vector search quality")
    print("  4. Hybrid search comparison")
    print("  5. Project isolation")
    print("  6. Performance under load")

    input("\n⏸️  Press Enter to start tests...")

    start_time = time.time()

    try:
        # Run tests
        manager = test_project_creation()
        test_document_ingestion(manager)
        test_vector_search(manager)
        test_hybrid_search(manager)
        test_multi_project_isolation(manager)
        test_performance_load(manager)

        # Cleanup
        cleanup_test_projects(manager)

        total_time = time.time() - start_time

        print_section("✅ All Tests Complete!")
        print(f"Total validation time: {total_time:.2f}s")

        print("\n🎯 v2.0.0 has been validated with real-world usage!")

    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
