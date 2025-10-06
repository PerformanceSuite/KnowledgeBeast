# REST API Guide

Complete guide to using the KnowledgeBeast REST API.

## Base URL

```
http://localhost:8000/api/v1
```

## Starting the Server

```bash
# Default settings
knowledgebeast serve

# Custom host and port
knowledgebeast serve --host 0.0.0.0 --port 8080

# Development mode with auto-reload
knowledgebeast serve --reload
```

Or with uvicorn directly:

```bash
uvicorn knowledgebeast.api.app:app --host 0.0.0.0 --port 8000
```

## Authentication

Currently, the API does not require authentication. For production deployments, consider adding:
- API keys
- JWT tokens
- OAuth2

See [Production Checklist](../deployment/production-checklist.md) for security recommendations.

## Endpoints

### Health Check

**GET** `/api/v1/health`

Check API health status.

```bash
curl http://localhost:8000/api/v1/health
```

Response:
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

### Query Knowledge Base

**POST** `/api/v1/query`

Search the knowledge base.

Request:
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning",
    "n_results": 5,
    "use_cache": true
  }'
```

Response:
```json
{
  "results": [
    {
      "text": "Machine learning is...",
      "metadata": {
        "source": "ml-intro.pdf",
        "page": 1
      },
      "distance": 0.234
    }
  ],
  "cached": false
}
```

### Ingest Document

**POST** `/api/v1/ingest`

Add a document to the knowledge base.

Request:
```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/path/to/document.pdf",
    "metadata": {
      "author": "John Doe",
      "category": "ML"
    }
  }'
```

Response:
```json
{
  "success": true,
  "chunks": 42,
  "message": "Successfully ingested 42 chunks from document.pdf"
}
```

### Get Statistics

**GET** `/api/v1/stats`

Get knowledge base statistics.

```bash
curl http://localhost:8000/api/v1/stats
```

Response:
```json
{
  "total_documents": 42,
  "cache_stats": {
    "size": 15,
    "hits": 120,
    "misses": 30,
    "hit_rate": 0.80
  },
  "heartbeat_running": true,
  "collection_name": "knowledge_base",
  "embedding_model": "all-MiniLM-L6-v2"
}
```

### Clear Knowledge Base

**DELETE** `/api/v1/clear`

Clear all documents.

```bash
curl -X DELETE http://localhost:8000/api/v1/clear
```

Response:
```json
{
  "message": "Knowledge base cleared successfully"
}
```

## Rate Limiting

The API includes rate limiting to prevent abuse:

- Health endpoint: 100 requests/minute
- Query endpoint: 30 requests/minute
- Ingest endpoint: 20 requests/minute
- Stats endpoint: 60 requests/minute

## Error Handling

### Error Response Format

```json
{
  "detail": "Error message",
  "status_code": 400
}
```

### HTTP Status Codes

- `200 OK` - Request successful
- `400 Bad Request` - Invalid request
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error

### Example Error Handling

```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/query",
    json={"query": "test"}
)

if response.status_code == 200:
    data = response.json()
    print(data["results"])
elif response.status_code == 400:
    print(f"Bad request: {response.json()['detail']}")
elif response.status_code == 500:
    print(f"Server error: {response.json()['detail']}")
```

## Python Client Example

```python
import requests
from typing import List, Dict, Any

class KnowledgeBeastClient:
    """Python client for KnowledgeBeast API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api/v1"

    def health(self) -> Dict[str, Any]:
        """Check health status."""
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
        return response.json()["results"]

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

# Usage
client = KnowledgeBeastClient()

# Check health
health = client.health()
print(f"Status: {health['status']}")

# Query
results = client.query("machine learning", n_results=10)
for result in results:
    print(result["text"])

# Get stats
stats = client.stats()
print(f"Documents: {stats['total_documents']}")
```

## JavaScript/TypeScript Client

```typescript
class KnowledgeBeastClient {
  constructor(private baseUrl: string = 'http://localhost:8000') {}

  async health(): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/v1/health`);
    return response.json();
  }

  async query(
    query: string,
    nResults: number = 5,
    useCache: boolean = true
  ): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/v1/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, n_results: nResults, use_cache: useCache })
    });
    return response.json();
  }

  async ingest(filePath: string, metadata: object = {}): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/v1/ingest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_path: filePath, metadata })
    });
    return response.json();
  }

  async stats(): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/v1/stats`);
    return response.json();
  }
}

// Usage
const client = new KnowledgeBeastClient();

// Query
const results = await client.query('machine learning', 10);
console.log(results);
```

## API Documentation

Interactive API documentation is available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Next Steps

- [Python API Guide](python-api.md)
- [CLI Usage Guide](cli-usage.md)
- [Docker Deployment](docker-deployment.md)
