"""API integration example using requests.

This example demonstrates:
- Connecting to KnowledgeBeast API
- Health checks
- Querying via REST API
- Error handling
"""

import requests
from typing import List, Dict, Any


class KnowledgeBeastClient:
    """Simple client for KnowledgeBeast REST API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        """Initialize client with base URL."""
        self.base_url = base_url
        self.api_url = f"{base_url}/api/v1"

    def health(self) -> Dict[str, Any]:
        """Check API health."""
        response = requests.get(f"{self.api_url}/health")
        response.raise_for_status()
        return response.json()

    def query(
        self,
        query: str,
        n_results: int = 5,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """Query the knowledge base."""
        response = requests.post(
            f"{self.api_url}/query",
            json={
                "query": query,
                "n_results": n_results,
                "use_cache": use_cache
            }
        )
        response.raise_for_status()
        data = response.json()
        return data["results"]

    def ingest(self, file_path: str, metadata: Dict = None) -> Dict[str, Any]:
        """Ingest a document."""
        response = requests.post(
            f"{self.api_url}/ingest",
            json={
                "file_path": file_path,
                "metadata": metadata or {}
            }
        )
        response.raise_for_status()
        return response.json()

    def stats(self) -> Dict[str, Any]:
        """Get statistics."""
        response = requests.get(f"{self.api_url}/stats")
        response.raise_for_status()
        return response.json()


def main():
    """Example API integration."""
    print("KnowledgeBeast - API Integration Example\n")

    # Initialize client
    client = KnowledgeBeastClient("http://localhost:8000")

    # Check health
    print("1. Checking API health...")
    try:
        health = client.health()
        print(f"   Status: {health['status']}")
        print(f"   Version: {health['version']}")
    except requests.exceptions.ConnectionError:
        print("   ✗ Could not connect to API. Is the server running?")
        print("   Start the server with: knowledgebeast serve")
        return
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return

    # Query knowledge base
    print("\n2. Querying knowledge base...")
    try:
        results = client.query("machine learning", n_results=3)
        print(f"   Found {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"\n   Result {i}:")
            print(f"   Text: {result['text'][:150]}...")
            print(f"   Distance: {result['distance']:.4f}")
    except Exception as e:
        print(f"   ✗ Query error: {e}")

    # Get statistics
    print("\n3. Getting statistics...")
    try:
        stats = client.stats()
        print(f"   Total documents: {stats['total_documents']}")
        print(f"   Cache hit rate: {stats['cache_stats']['hit_rate']:.2%}")
    except Exception as e:
        print(f"   ✗ Stats error: {e}")

    print("\n✓ Done!")


if __name__ == "__main__":
    main()
