"""Example client for streaming query results from KnowledgeBeast.

This example demonstrates how to consume Server-Sent Events from the
streaming query endpoint.
"""

import asyncio
import json
from typing import AsyncIterator

import httpx


async def stream_query_results(
    project_id: str,
    query: str,
    api_key: str,
    base_url: str = "http://localhost:8000",
    top_k: int = 50
) -> None:
    """Stream query results from a project using Server-Sent Events.

    Args:
        project_id: Project identifier
        query: Search query
        api_key: API key for authentication
        base_url: Base URL of the API server
        top_k: Number of results to retrieve

    Example:
        >>> await stream_query_results(
        ...     project_id="abc123",
        ...     query="machine learning",
        ...     api_key="your-api-key",
        ...     top_k=100
        ... )
    """
    url = f"{base_url}/api/v2/{project_id}/query/stream"

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            url,
            json={"query": query, "limit": top_k},
            headers={"X-API-Key": api_key},
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])

                        if data['event'] == 'start':
                            print(f"\n🚀 Stream started at {data['timestamp']}")
                            print(f"   Project: {data['project_id']}")
                            print(f"   Query: {data['query']}\n")

                        elif data['event'] == 'result':
                            result = data['data']
                            print(f"📄 Result {result['index'] + 1}:")
                            print(f"   ID: {result['id']}")
                            print(f"   Score: {result['score']:.4f}")
                            print(f"   Document: {result['document'][:100]}...")
                            if result.get('metadata'):
                                print(f"   Metadata: {result['metadata']}")
                            print()

                        elif data['event'] == 'done':
                            print(f"✅ Stream complete!")
                            print(f"   Total results: {data['total_results']}")
                            print(f"   Completed at: {data['timestamp']}")

                        elif data['event'] == 'error':
                            print(f"❌ Error: {data['error']}")
                            print(f"   Type: {data['type']}")

                    except json.JSONDecodeError as e:
                        print(f"⚠️  Failed to parse event: {e}")
                        print(f"   Line: {line}")


async def stream_with_custom_handler(
    project_id: str,
    query: str,
    api_key: str,
    base_url: str = "http://localhost:8000",
    top_k: int = 50
) -> AsyncIterator[dict]:
    """Stream query results and yield parsed events.

    This is a more flexible version that yields events for custom processing.

    Args:
        project_id: Project identifier
        query: Search query
        api_key: API key for authentication
        base_url: Base URL of the API server
        top_k: Number of results to retrieve

    Yields:
        Parsed event dictionaries

    Example:
        >>> async for event in stream_with_custom_handler(
        ...     project_id="abc123",
        ...     query="deep learning",
        ...     api_key="your-api-key"
        ... ):
        ...     if event['event'] == 'result':
        ...         process_result(event['data'])
    """
    url = f"{base_url}/api/v2/{project_id}/query/stream"

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            url,
            json={"query": query, "limit": top_k},
            headers={"X-API-Key": api_key},
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        yield data
                    except json.JSONDecodeError:
                        continue


async def collect_stream_results(
    project_id: str,
    query: str,
    api_key: str,
    base_url: str = "http://localhost:8000",
    top_k: int = 50
) -> list[dict]:
    """Collect all streaming results into a list.

    Args:
        project_id: Project identifier
        query: Search query
        api_key: API key for authentication
        base_url: Base URL of the API server
        top_k: Number of results to retrieve

    Returns:
        List of all result documents

    Example:
        >>> results = await collect_stream_results(
        ...     project_id="abc123",
        ...     query="neural networks",
        ...     api_key="your-api-key"
        ... )
        >>> print(f"Collected {len(results)} results")
    """
    results = []

    async for event in stream_with_custom_handler(
        project_id, query, api_key, base_url, top_k
    ):
        if event['event'] == 'result':
            results.append(event['data'])
        elif event['event'] == 'error':
            raise RuntimeError(f"Stream error: {event['error']}")

    return results


async def main():
    """Example usage of streaming client."""
    # Configuration
    PROJECT_ID = "your-project-id"
    API_KEY = "your-api-key"
    BASE_URL = "http://localhost:8000"

    # Example 1: Stream and print results
    print("=" * 60)
    print("Example 1: Stream and print results")
    print("=" * 60)

    await stream_query_results(
        project_id=PROJECT_ID,
        query="machine learning algorithms",
        api_key=API_KEY,
        base_url=BASE_URL,
        top_k=10
    )

    # Example 2: Custom event handling
    print("\n" + "=" * 60)
    print("Example 2: Custom event handling")
    print("=" * 60)

    result_count = 0
    async for event in stream_with_custom_handler(
        project_id=PROJECT_ID,
        query="deep learning frameworks",
        api_key=API_KEY,
        base_url=BASE_URL,
        top_k=5
    ):
        if event['event'] == 'start':
            print(f"Started streaming query: {event['query']}")
        elif event['event'] == 'result':
            result_count += 1
            print(f"Received result {result_count}")
        elif event['event'] == 'done':
            print(f"Completed: {event['total_results']} total results")

    # Example 3: Collect all results
    print("\n" + "=" * 60)
    print("Example 3: Collect all results")
    print("=" * 60)

    results = await collect_stream_results(
        project_id=PROJECT_ID,
        query="natural language processing",
        api_key=API_KEY,
        base_url=BASE_URL,
        top_k=10
    )

    print(f"Collected {len(results)} results")
    for i, result in enumerate(results[:3], 1):
        print(f"\nResult {i}:")
        print(f"  Score: {result['score']:.4f}")
        print(f"  Preview: {result['document'][:80]}...")


if __name__ == "__main__":
    asyncio.run(main())
