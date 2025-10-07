# Comprehensive API Guide

Complete guide to the KnowledgeBeast REST API with detailed examples, authentication, error handling, and best practices.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Authentication](#authentication)
3. [Base URL and Versioning](#base-url-and-versioning)
4. [Complete Endpoint Reference](#complete-endpoint-reference)
5. [Pagination](#pagination)
6. [Error Handling](#error-handling)
7. [Rate Limiting](#rate-limiting)
8. [Client Libraries](#client-libraries)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Starting the Server

```bash
# Default settings (localhost:8000)
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

### First API Call

```bash
# Health check (no authentication required in development)
curl http://localhost:8000/api/v1/health

# With API key authentication
curl -H "X-API-Key: your_api_key_here" \
  http://localhost:8000/api/v1/health
```

---

## Authentication

All 12 API endpoints require API key authentication when `KB_API_KEY` environment variable is set.

### Setting Up API Keys

```bash
# Single API key
export KB_API_KEY="secret_key_123"

# Multiple API keys (comma-separated)
export KB_API_KEY="key1,key2,key3"
```

### Using API Keys in Requests

API keys are passed via the `X-API-Key` header:

#### cURL
```bash
curl -H "X-API-Key: your_api_key_here" \
  http://localhost:8000/api/v1/health
```

#### Python (requests)
```python
import requests

headers = {"X-API-Key": "your_api_key_here"}
response = requests.get(
    "http://localhost:8000/api/v1/health",
    headers=headers
)
```

#### JavaScript (fetch)
```javascript
const headers = {
  'X-API-Key': 'your_api_key_here',
  'Content-Type': 'application/json'
};

fetch('http://localhost:8000/api/v1/health', { headers })
  .then(res => res.json())
  .then(data => console.log(data));
```

### API Key Rate Limiting

Each API key has its own rate limit:
- **100 requests per 60-second window** (per API key)
- Rate limit headers are included in responses:
  - `X-RateLimit-Limit`: Maximum requests allowed
  - `X-RateLimit-Remaining`: Requests remaining in current window
  - `X-RateLimit-Reset`: Unix timestamp when limit resets

### Development Mode

If `KB_API_KEY` is not set, the API runs in **development mode** without authentication:

```bash
# No API key required in development
curl http://localhost:8000/api/v1/health
```

⚠️ **Production Warning**: Always set `KB_API_KEY` in production environments!

---

## Base URL and Versioning

### Base URL
```
http://localhost:8000/api/v1
```

### API Versioning

The API uses URL path versioning (`/api/v1`). Future versions will use `/api/v2`, etc.

### Interactive Documentation

KnowledgeBeast provides auto-generated interactive API documentation:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

---

## Complete Endpoint Reference

KnowledgeBeast provides **12 production-ready endpoints** organized into 5 categories:

### 1. Health Endpoints (2)

#### GET /health
Check API health status and system information.

**Rate Limit**: 100/minute

**Headers**:
```
X-API-Key: your_api_key_here
```

**Response** (200 OK):
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "kb_initialized": true,
  "timestamp": "2025-10-06T12:00:00Z"
}
```

**Status Values**:
- `healthy`: All systems operational
- `degraded`: KB initialized but some issues detected
- `unhealthy`: KB failed to initialize

**Example**:
```bash
curl -H "X-API-Key: your_api_key" \
  http://localhost:8000/api/v1/health
```

---

#### GET /stats
Get detailed knowledge base statistics and performance metrics.

**Rate Limit**: 60/minute

**Response** (200 OK):
```json
{
  "queries": 150,
  "cache_hits": 100,
  "cache_misses": 50,
  "cache_hit_rate": "66.7%",
  "warm_queries": 7,
  "last_warm_time": 2.5,
  "total_documents": 42,
  "total_terms": 1523,
  "documents": 42,
  "terms": 1523,
  "cached_queries": 25,
  "last_access_age": "5.2s ago",
  "knowledge_dirs": ["/path/to/knowledge-base"],
  "total_queries": 150
}
```

**Example**:
```bash
curl -H "X-API-Key: your_api_key" \
  http://localhost:8000/api/v1/stats
```

---

### 2. Query Endpoints (2)

#### POST /query
Search the knowledge base for relevant documents.

**Rate Limit**: 30/minute

**Request Body**:
```json
{
  "query": "How do I use librosa for audio analysis?",
  "use_cache": true,
  "limit": 10,
  "offset": 0
}
```

**Request Fields**:
- `query` (string, required): Search query (1-1000 chars)
- `use_cache` (boolean, optional): Use cached results if available (default: true)
- `limit` (integer, optional): Max results to return, 1-100 (default: 10)
- `offset` (integer, optional): Results to skip for pagination (default: 0)

**Response** (200 OK):
```json
{
  "results": [
    {
      "doc_id": "knowledge-base/audio/librosa.md",
      "content": "Librosa is a Python package for music and audio analysis...",
      "name": "Librosa Guide",
      "path": "/Users/user/knowledge-base/audio/librosa.md",
      "kb_dir": "/Users/user/knowledge-base"
    }
  ],
  "count": 1,
  "cached": false,
  "query": "librosa audio analysis"
}
```

**Example (cURL)**:
```bash
curl -X POST \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning best practices",
    "use_cache": true,
    "limit": 5
  }' \
  http://localhost:8000/api/v1/query
```

**Example (Python)**:
```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/query",
    headers={"X-API-Key": "your_api_key"},
    json={
        "query": "machine learning best practices",
        "use_cache": True,
        "limit": 5
    }
)

results = response.json()["results"]
for result in results:
    print(f"{result['name']}: {result['content'][:100]}...")
```

---

#### POST /query/paginated
Search the knowledge base with pagination support.

**Rate Limit**: 30/minute

**Request Body**:
```json
{
  "query": "audio processing techniques",
  "use_cache": true,
  "page": 1,
  "page_size": 10
}
```

**Request Fields**:
- `query` (string, required): Search query (1-1000 chars)
- `use_cache` (boolean, optional): Use cached results (default: true)
- `page` (integer, optional): Page number, 1-indexed (default: 1)
- `page_size` (integer, optional): Results per page, 1-100 (default: 10)

**Response** (200 OK):
```json
{
  "results": [
    {
      "doc_id": "knowledge-base/audio/processing.md",
      "content": "Audio processing techniques include...",
      "name": "Audio Processing Guide",
      "path": "/Users/user/knowledge-base/audio/processing.md",
      "kb_dir": "/Users/user/knowledge-base"
    }
  ],
  "count": 10,
  "cached": false,
  "query": "audio processing techniques",
  "pagination": {
    "total_results": 42,
    "total_pages": 5,
    "current_page": 1,
    "page_size": 10,
    "has_next": true,
    "has_previous": false
  }
}
```

**Example (cURL)**:
```bash
curl -X POST \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "python best practices",
    "page": 2,
    "page_size": 20
  }' \
  http://localhost:8000/api/v1/query/paginated
```

**Example (Python)**:
```python
# Paginate through all results
def get_all_results(query: str):
    all_results = []
    page = 1

    while True:
        response = requests.post(
            "http://localhost:8000/api/v1/query/paginated",
            headers={"X-API-Key": "your_api_key"},
            json={"query": query, "page": page, "page_size": 20}
        )

        data = response.json()
        all_results.extend(data["results"])

        if not data["pagination"]["has_next"]:
            break

        page += 1

    return all_results

results = get_all_results("machine learning")
print(f"Found {len(results)} total results")
```

---

### 3. Ingestion Endpoints (2)

#### POST /ingest
Add a single document to the knowledge base.

**Rate Limit**: 20/minute

**Request Body**:
```json
{
  "file_path": "/path/to/document.md",
  "metadata": {
    "author": "John Doe",
    "category": "tutorials"
  }
}
```

**Request Fields**:
- `file_path` (string, required): Absolute path to document file
- `metadata` (object, optional): Additional metadata to attach

**Supported File Types**:
- `.md` (Markdown)
- `.txt` (Text)
- `.pdf` (PDF)
- `.docx` (Word)
- `.html`, `.htm` (HTML)

**Response** (200 OK):
```json
{
  "success": true,
  "file_path": "/path/to/document.md",
  "doc_id": "/path/to/document.md",
  "message": "Successfully ingested document.md"
}
```

**Example (cURL)**:
```bash
curl -X POST \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/knowledge-base/tutorials/python-basics.md",
    "metadata": {"category": "python", "level": "beginner"}
  }' \
  http://localhost:8000/api/v1/ingest
```

**Example (Python)**:
```python
response = requests.post(
    "http://localhost:8000/api/v1/ingest",
    headers={"X-API-Key": "your_api_key"},
    json={
        "file_path": "/knowledge-base/guides/new-doc.md",
        "metadata": {"tags": ["tutorial", "advanced"]}
    }
)

print(response.json()["message"])
```

**Note**: Single file ingestion triggers a full index rebuild. For better performance with multiple files, use `/batch-ingest`.

---

#### POST /batch-ingest
Add multiple documents to the knowledge base in a single operation.

**Rate Limit**: 10/minute

**Request Body**:
```json
{
  "file_paths": [
    "/knowledge-base/doc1.md",
    "/knowledge-base/doc2.md",
    "/knowledge-base/doc3.md"
  ],
  "metadata": {
    "batch": "import-2025-10-06",
    "source": "external"
  }
}
```

**Request Fields**:
- `file_paths` (array, required): List of absolute file paths (1-100 files)
- `metadata` (object, optional): Metadata applied to all documents

**Response** (200 OK):
```json
{
  "success": true,
  "total_files": 3,
  "successful": 3,
  "failed": 0,
  "failed_files": [],
  "message": "Batch ingestion completed: 3/3 successful"
}
```

**Example (cURL)**:
```bash
curl -X POST \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "file_paths": [
      "/kb/doc1.md",
      "/kb/doc2.md"
    ],
    "metadata": {"batch": "october"}
  }' \
  http://localhost:8000/api/v1/batch-ingest
```

**Example (Python)**:
```python
import os
from pathlib import Path

# Collect all markdown files in directory
kb_dir = Path("/knowledge-base")
md_files = [str(f) for f in kb_dir.rglob("*.md")]

# Batch ingest in chunks of 50
chunk_size = 50
for i in range(0, len(md_files), chunk_size):
    chunk = md_files[i:i+chunk_size]

    response = requests.post(
        "http://localhost:8000/api/v1/batch-ingest",
        headers={"X-API-Key": "your_api_key"},
        json={
            "file_paths": chunk,
            "metadata": {"batch": f"chunk_{i//chunk_size}"}
        }
    )

    result = response.json()
    print(f"Batch {i//chunk_size}: {result['successful']}/{result['total_files']} successful")
```

---

### 4. Management Endpoints (2)

#### POST /warm
Trigger knowledge base warming to reduce query latency.

**Rate Limit**: 10/minute

**Request Body**:
```json
{
  "force_rebuild": false
}
```

**Request Fields**:
- `force_rebuild` (boolean, optional): Force index rebuild before warming (default: false)

**Response** (200 OK):
```json
{
  "success": true,
  "warm_time": 2.5,
  "queries_executed": 7,
  "documents_loaded": 42,
  "message": "Knowledge base warmed in 2.5s"
}
```

**Example (cURL)**:
```bash
curl -X POST \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"force_rebuild": true}' \
  http://localhost:8000/api/v1/warm
```

**Example (Python)**:
```python
# Warm cache on startup
response = requests.post(
    "http://localhost:8000/api/v1/warm",
    headers={"X-API-Key": "your_api_key"},
    json={"force_rebuild": False}
)

warm_result = response.json()
print(f"Warmed in {warm_result['warm_time']:.2f}s")
print(f"Loaded {warm_result['documents_loaded']} documents")
```

---

#### POST /cache/clear
Clear all cached query results.

**Rate Limit**: 20/minute

**Response** (200 OK):
```json
{
  "success": true,
  "cleared_count": 25,
  "message": "Cache cleared: 25 entries removed"
}
```

**Example (cURL)**:
```bash
curl -X POST \
  -H "X-API-Key: your_api_key" \
  http://localhost:8000/api/v1/cache/clear
```

**Example (Python)**:
```python
# Clear cache after updating documents
response = requests.post(
    "http://localhost:8000/api/v1/cache/clear",
    headers={"X-API-Key": "your_api_key"}
)

result = response.json()
print(f"Cleared {result['cleared_count']} cached queries")
```

---

### 5. Heartbeat Endpoints (3)

#### GET /heartbeat/status
Get current heartbeat status and metrics.

**Rate Limit**: 60/minute

**Response** (200 OK):
```json
{
  "running": true,
  "interval": 300,
  "heartbeat_count": 12,
  "last_heartbeat": null
}
```

**Example (cURL)**:
```bash
curl -H "X-API-Key: your_api_key" \
  http://localhost:8000/api/v1/heartbeat/status
```

---

#### POST /heartbeat/start
Start background heartbeat for continuous KB monitoring.

**Rate Limit**: 10/minute

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Heartbeat started successfully",
  "running": true
}
```

**Example (cURL)**:
```bash
curl -X POST \
  -H "X-API-Key: your_api_key" \
  http://localhost:8000/api/v1/heartbeat/start
```

**Example (Python)**:
```python
# Start heartbeat monitoring
response = requests.post(
    "http://localhost:8000/api/v1/heartbeat/start",
    headers={"X-API-Key": "your_api_key"}
)

print(response.json()["message"])
```

---

#### POST /heartbeat/stop
Stop background heartbeat monitoring.

**Rate Limit**: 10/minute

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Heartbeat stopped successfully",
  "running": false
}
```

**Example (cURL)**:
```bash
curl -X POST \
  -H "X-API-Key: your_api_key" \
  http://localhost:8000/api/v1/heartbeat/stop
```

---

### 6. Collection Endpoints (2)

#### GET /collections
Get list of all knowledge base collections.

**Rate Limit**: 60/minute

**Response** (200 OK):
```json
{
  "collections": [
    {
      "name": "default",
      "document_count": 42,
      "term_count": 1523,
      "cache_size": 25
    }
  ],
  "count": 1
}
```

**Example (cURL)**:
```bash
curl -H "X-API-Key: your_api_key" \
  http://localhost:8000/api/v1/collections
```

**Note**: Current implementation supports a single "default" collection. Multi-collection support may be added in future versions.

---

#### GET /collections/{name}
Get detailed information about a specific collection.

**Rate Limit**: 60/minute

**Path Parameters**:
- `name` (string): Collection name

**Response** (200 OK):
```json
{
  "name": "default",
  "document_count": 42,
  "term_count": 1523,
  "cache_size": 25
}
```

**Example (cURL)**:
```bash
curl -H "X-API-Key: your_api_key" \
  http://localhost:8000/api/v1/collections/default
```

---

## Pagination

KnowledgeBeast supports two pagination approaches:

### 1. Offset-Based Pagination (Legacy)

Use `limit` and `offset` parameters with `/query` endpoint:

```python
# Get results 11-20
response = requests.post(
    "http://localhost:8000/api/v1/query",
    headers={"X-API-Key": "your_api_key"},
    json={
        "query": "python",
        "limit": 10,
        "offset": 10
    }
)
```

### 2. Page-Based Pagination (Recommended)

Use `page` and `page_size` parameters with `/query/paginated` endpoint:

```python
# Get page 2 with 20 results per page
response = requests.post(
    "http://localhost:8000/api/v1/query/paginated",
    headers={"X-API-Key": "your_api_key"},
    json={
        "query": "python",
        "page": 2,
        "page_size": 20
    }
)

pagination = response.json()["pagination"]
print(f"Page {pagination['current_page']} of {pagination['total_pages']}")
print(f"Total results: {pagination['total_results']}")
```

### Pagination Best Practices

1. **Use page-based pagination** (`/query/paginated`) for better UX
2. **Cache pagination metadata** to avoid repeated full queries
3. **Set appropriate page_size** (10-50 results recommended)
4. **Handle edge cases** (empty results, page > total_pages)
5. **Show total count** to users for better navigation

**Example: Complete Pagination UI**:
```python
def paginated_search(query: str, page: int = 1, page_size: int = 20):
    response = requests.post(
        "http://localhost:8000/api/v1/query/paginated",
        headers={"X-API-Key": "your_api_key"},
        json={
            "query": query,
            "page": page,
            "page_size": page_size
        }
    )

    data = response.json()

    # Display results
    for result in data["results"]:
        print(f"- {result['name']}")

    # Display pagination info
    p = data["pagination"]
    print(f"\nPage {p['current_page']} of {p['total_pages']}")
    print(f"Showing {data['count']} of {p['total_results']} results")

    # Navigation hints
    if p["has_previous"]:
        print(f"Previous: page {p['current_page'] - 1}")
    if p["has_next"]:
        print(f"Next: page {p['current_page'] + 1}")

    return data
```

---

## Error Handling

### Standard Error Response Format

All errors follow a consistent JSON structure:

```json
{
  "error": "ValidationError",
  "message": "Query string cannot be empty",
  "detail": "Field 'query' is required and must be non-empty",
  "status_code": 400
}
```

### HTTP Status Codes

| Code | Status | Description |
|------|--------|-------------|
| 200 | OK | Request successful |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Invalid or missing API key |
| 404 | Not Found | Resource not found |
| 422 | Unprocessable Entity | Validation error |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |

### Common Error Scenarios

#### 1. Missing API Key

**Error** (401 Unauthorized):
```json
{
  "error": "Unauthorized",
  "message": "Invalid API key",
  "detail": null,
  "status_code": 401
}
```

**Solution**: Include `X-API-Key` header with valid API key.

---

#### 2. Rate Limit Exceeded

**Error** (429 Too Many Requests):
```json
{
  "error": "RateLimitExceeded",
  "message": "Rate limit exceeded. Limit: 100 requests per 60s",
  "detail": null,
  "status_code": 429
}
```

**Response Headers**:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1696608000
```

**Solution**: Wait until reset time or use exponential backoff.

---

#### 3. Invalid Query String

**Error** (422 Unprocessable Entity):
```json
{
  "error": "ValidationError",
  "message": "Request validation failed",
  "detail": "query: Query contains invalid character: <",
  "status_code": 422
}
```

**Solution**: Remove special characters (`<`, `>`, `;`, `&`, `|`, `$`, `` ` ``, newlines).

---

#### 4. File Not Found

**Error** (404 Not Found):
```json
{
  "error": "NotFound",
  "message": "File not found: /path/to/missing.md",
  "detail": null,
  "status_code": 404
}
```

**Solution**: Verify file path exists and is accessible.

---

#### 5. Invalid Page Number

**Error** (400 Bad Request):
```json
{
  "error": "BadRequest",
  "message": "Page 10 exceeds total pages 5",
  "detail": null,
  "status_code": 400
}
```

**Solution**: Request valid page number (1 to total_pages).

---

### Error Handling Best Practices

#### Python Example with Comprehensive Error Handling:

```python
import requests
from typing import Optional, Dict, Any

def safe_api_call(
    url: str,
    api_key: str,
    method: str = "GET",
    json_data: Optional[Dict] = None
) -> Optional[Dict[str, Any]]:
    """Make API call with comprehensive error handling."""

    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }

    try:
        if method == "POST":
            response = requests.post(url, headers=headers, json=json_data)
        else:
            response = requests.get(url, headers=headers)

        # Check for HTTP errors
        response.raise_for_status()

        return response.json()

    except requests.exceptions.HTTPError as e:
        error_data = e.response.json() if e.response.text else {}

        if e.response.status_code == 401:
            print(f"Authentication failed: {error_data.get('message', 'Invalid API key')}")
        elif e.response.status_code == 429:
            reset_time = e.response.headers.get('X-RateLimit-Reset')
            print(f"Rate limit exceeded. Resets at: {reset_time}")
        elif e.response.status_code == 422:
            print(f"Validation error: {error_data.get('detail', 'Invalid input')}")
        elif e.response.status_code == 404:
            print(f"Not found: {error_data.get('message', 'Resource not found')}")
        else:
            print(f"HTTP error {e.response.status_code}: {error_data.get('message', str(e))}")

        return None

    except requests.exceptions.ConnectionError:
        print("Connection failed. Is the server running?")
        return None

    except requests.exceptions.Timeout:
        print("Request timed out")
        return None

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return None

# Usage
result = safe_api_call(
    url="http://localhost:8000/api/v1/query",
    api_key="your_api_key",
    method="POST",
    json_data={"query": "machine learning"}
)

if result:
    print(f"Found {result['count']} results")
else:
    print("Query failed")
```

#### cURL Error Handling:

```bash
# Capture HTTP status code
response=$(curl -w "\n%{http_code}" \
  -H "X-API-Key: your_api_key" \
  http://localhost:8000/api/v1/health)

status_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | head -n-1)

if [ "$status_code" -eq 200 ]; then
    echo "Success: $body"
elif [ "$status_code" -eq 401 ]; then
    echo "Authentication failed"
elif [ "$status_code" -eq 429 ]; then
    echo "Rate limit exceeded"
else
    echo "Error $status_code: $body"
fi
```

---

## Rate Limiting

### Global Rate Limits

| Endpoint | Rate Limit |
|----------|------------|
| GET /health | 100/minute |
| GET /stats | 60/minute |
| POST /query | 30/minute |
| POST /query/paginated | 30/minute |
| POST /ingest | 20/minute |
| POST /batch-ingest | 10/minute |
| POST /warm | 10/minute |
| POST /cache/clear | 20/minute |
| GET /heartbeat/status | 60/minute |
| POST /heartbeat/start | 10/minute |
| POST /heartbeat/stop | 10/minute |
| GET /collections | 60/minute |
| GET /collections/{name} | 60/minute |

### Per-API-Key Rate Limiting

Each API key has additional rate limiting:
- **100 requests per 60-second window** (across all endpoints)
- Uses sliding window algorithm
- Rate limit is tracked separately per API key

### Rate Limit Headers

All responses include rate limit headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1696608000
```

### Handling Rate Limits

#### Python Example with Exponential Backoff:

```python
import time
import requests
from typing import Optional, Dict

def api_call_with_retry(
    url: str,
    api_key: str,
    max_retries: int = 3,
    base_delay: float = 1.0
) -> Optional[Dict]:
    """Make API call with exponential backoff on rate limits."""

    headers = {"X-API-Key": api_key}

    for attempt in range(max_retries):
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return response.json()

        if response.status_code == 429:
            # Rate limited - use exponential backoff
            delay = base_delay * (2 ** attempt)

            # Try to get reset time from header
            reset_time = response.headers.get('X-RateLimit-Reset')
            if reset_time:
                wait_time = int(reset_time) - int(time.time())
                delay = max(delay, wait_time)

            print(f"Rate limited. Retrying in {delay}s...")
            time.sleep(delay)
            continue

        # Other errors - don't retry
        print(f"Error {response.status_code}: {response.text}")
        return None

    print(f"Failed after {max_retries} retries")
    return None

# Usage
result = api_call_with_retry(
    url="http://localhost:8000/api/v1/stats",
    api_key="your_api_key"
)
```

### Rate Limit Configuration

Configure rate limits via environment variables:

```bash
# Global rate limit (requests per minute)
export KB_RATE_LIMIT_PER_MINUTE=100

# Rate limit storage backend
export KB_RATE_LIMIT_STORAGE="memory://"  # Default
# Or use Redis:
# export KB_RATE_LIMIT_STORAGE="redis://localhost:6379"
```

---

## Client Libraries

### Python Client

```python
import requests
from typing import List, Dict, Any, Optional

class KnowledgeBeastClient:
    """Production-ready Python client for KnowledgeBeast API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None
    ):
        self.base_url = base_url
        self.api_url = f"{base_url}/api/v1"
        self.api_key = api_key
        self.session = requests.Session()

        if api_key:
            self.session.headers.update({"X-API-Key": api_key})

    def health(self) -> Dict[str, Any]:
        """Check API health status."""
        response = self.session.get(f"{self.api_url}/health")
        response.raise_for_status()
        return response.json()

    def query(
        self,
        query: str,
        use_cache: bool = True,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Query the knowledge base."""
        response = self.session.post(
            f"{self.api_url}/query",
            json={
                "query": query,
                "use_cache": use_cache,
                "limit": limit,
                "offset": offset
            }
        )
        response.raise_for_status()
        return response.json()["results"]

    def query_paginated(
        self,
        query: str,
        page: int = 1,
        page_size: int = 10,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """Query with pagination support."""
        response = self.session.post(
            f"{self.api_url}/query/paginated",
            json={
                "query": query,
                "page": page,
                "page_size": page_size,
                "use_cache": use_cache
            }
        )
        response.raise_for_status()
        return response.json()

    def ingest(
        self,
        file_path: str,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Ingest a single document."""
        response = self.session.post(
            f"{self.api_url}/ingest",
            json={
                "file_path": file_path,
                "metadata": metadata or {}
            }
        )
        response.raise_for_status()
        return response.json()

    def batch_ingest(
        self,
        file_paths: List[str],
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Batch ingest multiple documents."""
        response = self.session.post(
            f"{self.api_url}/batch-ingest",
            json={
                "file_paths": file_paths,
                "metadata": metadata or {}
            }
        )
        response.raise_for_status()
        return response.json()

    def warm(self, force_rebuild: bool = False) -> Dict[str, Any]:
        """Warm the knowledge base."""
        response = self.session.post(
            f"{self.api_url}/warm",
            json={"force_rebuild": force_rebuild}
        )
        response.raise_for_status()
        return response.json()

    def clear_cache(self) -> Dict[str, Any]:
        """Clear query cache."""
        response = self.session.post(f"{self.api_url}/cache/clear")
        response.raise_for_status()
        return response.json()

    def stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        response = self.session.get(f"{self.api_url}/stats")
        response.raise_for_status()
        return response.json()

    def heartbeat_status(self) -> Dict[str, Any]:
        """Get heartbeat status."""
        response = self.session.get(f"{self.api_url}/heartbeat/status")
        response.raise_for_status()
        return response.json()

    def start_heartbeat(self) -> Dict[str, Any]:
        """Start heartbeat monitoring."""
        response = self.session.post(f"{self.api_url}/heartbeat/start")
        response.raise_for_status()
        return response.json()

    def stop_heartbeat(self) -> Dict[str, Any]:
        """Stop heartbeat monitoring."""
        response = self.session.post(f"{self.api_url}/heartbeat/stop")
        response.raise_for_status()
        return response.json()

    def list_collections(self) -> Dict[str, Any]:
        """List all collections."""
        response = self.session.get(f"{self.api_url}/collections")
        response.raise_for_status()
        return response.json()

    def get_collection(self, name: str) -> Dict[str, Any]:
        """Get collection information."""
        response = self.session.get(f"{self.api_url}/collections/{name}")
        response.raise_for_status()
        return response.json()

# Usage Example
if __name__ == "__main__":
    client = KnowledgeBeastClient(
        base_url="http://localhost:8000",
        api_key="your_api_key_here"
    )

    # Health check
    health = client.health()
    print(f"Status: {health['status']}")

    # Query with pagination
    results = client.query_paginated(
        query="machine learning",
        page=1,
        page_size=20
    )
    print(f"Found {results['pagination']['total_results']} results")

    # Batch ingest
    response = client.batch_ingest(
        file_paths=["/kb/doc1.md", "/kb/doc2.md"],
        metadata={"batch": "october"}
    )
    print(f"Ingested: {response['successful']}/{response['total_files']}")

    # Warm cache
    warm_result = client.warm(force_rebuild=True)
    print(f"Warmed in {warm_result['warm_time']:.2f}s")

    # Get stats
    stats = client.stats()
    print(f"Cache hit rate: {stats['cache_hit_rate']}")
```

### JavaScript/TypeScript Client

```typescript
interface KBConfig {
  baseUrl?: string;
  apiKey?: string;
}

interface QueryResult {
  doc_id: string;
  content: string;
  name: string;
  path: string;
  kb_dir: string;
}

interface PaginationMetadata {
  total_results: number;
  total_pages: number;
  current_page: number;
  page_size: number;
  has_next: boolean;
  has_previous: boolean;
}

class KnowledgeBeastClient {
  private baseUrl: string;
  private apiUrl: string;
  private apiKey?: string;

  constructor(config: KBConfig = {}) {
    this.baseUrl = config.baseUrl || 'http://localhost:8000';
    this.apiUrl = `${this.baseUrl}/api/v1`;
    this.apiKey = config.apiKey;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    };

    if (this.apiKey) {
      headers['X-API-Key'] = this.apiKey;
    }

    const response = await fetch(`${this.apiUrl}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || `HTTP ${response.status}`);
    }

    return response.json();
  }

  async health() {
    return this.request<{
      status: string;
      version: string;
      kb_initialized: boolean;
      timestamp: string;
    }>('/health');
  }

  async query(
    query: string,
    options: {
      useCache?: boolean;
      limit?: number;
      offset?: number;
    } = {}
  ) {
    return this.request<{
      results: QueryResult[];
      count: number;
      cached: boolean;
      query: string;
    }>('/query', {
      method: 'POST',
      body: JSON.stringify({
        query,
        use_cache: options.useCache ?? true,
        limit: options.limit ?? 10,
        offset: options.offset ?? 0,
      }),
    });
  }

  async queryPaginated(
    query: string,
    options: {
      page?: number;
      pageSize?: number;
      useCache?: boolean;
    } = {}
  ) {
    return this.request<{
      results: QueryResult[];
      count: number;
      cached: boolean;
      query: string;
      pagination: PaginationMetadata;
    }>('/query/paginated', {
      method: 'POST',
      body: JSON.stringify({
        query,
        page: options.page ?? 1,
        page_size: options.pageSize ?? 10,
        use_cache: options.useCache ?? true,
      }),
    });
  }

  async ingest(filePath: string, metadata?: Record<string, any>) {
    return this.request('/ingest', {
      method: 'POST',
      body: JSON.stringify({
        file_path: filePath,
        metadata,
      }),
    });
  }

  async batchIngest(filePaths: string[], metadata?: Record<string, any>) {
    return this.request('/batch-ingest', {
      method: 'POST',
      body: JSON.stringify({
        file_paths: filePaths,
        metadata,
      }),
    });
  }

  async warm(forceRebuild: boolean = false) {
    return this.request('/warm', {
      method: 'POST',
      body: JSON.stringify({
        force_rebuild: forceRebuild,
      }),
    });
  }

  async clearCache() {
    return this.request('/cache/clear', { method: 'POST' });
  }

  async stats() {
    return this.request('/stats');
  }

  async listCollections() {
    return this.request('/collections');
  }

  async getCollection(name: string) {
    return this.request(`/collections/${name}`);
  }
}

// Usage Example
const client = new KnowledgeBeastClient({
  baseUrl: 'http://localhost:8000',
  apiKey: 'your_api_key_here',
});

// Query with pagination
const results = await client.queryPaginated('machine learning', {
  page: 1,
  pageSize: 20,
});

console.log(`Found ${results.pagination.total_results} results`);
console.log(`Page ${results.pagination.current_page} of ${results.pagination.total_pages}`);

// Batch ingest
const ingestResult = await client.batchIngest([
  '/kb/doc1.md',
  '/kb/doc2.md',
]);

console.log(`Ingested: ${ingestResult.successful}/${ingestResult.total_files}`);
```

---

## Best Practices

### 1. Authentication Security

```bash
# ✅ DO: Store API keys securely
export KB_API_KEY="$(cat /secure/path/api-key.txt)"

# ✅ DO: Use different keys for different environments
export KB_API_KEY_DEV="dev_key_123"
export KB_API_KEY_PROD="prod_key_456"

# ❌ DON'T: Hardcode API keys in code
api_key = "secret_key_123"  # Bad!

# ✅ DO: Use environment variables
api_key = os.getenv("KB_API_KEY")
```

### 2. Query Optimization

```python
# ✅ DO: Use caching for repeated queries
response = client.query("common query", use_cache=True)

# ✅ DO: Use pagination for large result sets
response = client.query_paginated(
    query="broad search term",
    page=1,
    page_size=50
)

# ❌ DON'T: Request all results without pagination
response = client.query("*", limit=10000)  # Bad!

# ✅ DO: Set appropriate limits
response = client.query("specific query", limit=20)
```

### 3. Batch Operations

```python
# ✅ DO: Use batch-ingest for multiple files
client.batch_ingest(file_paths=[
    "/kb/doc1.md",
    "/kb/doc2.md",
    "/kb/doc3.md"
])

# ❌ DON'T: Ingest files one by one
for file in files:
    client.ingest(file)  # Triggers rebuild each time!

# ✅ DO: Process in chunks if > 100 files
for chunk in chunks(file_paths, size=50):
    client.batch_ingest(chunk)
```

### 4. Error Handling

```python
# ✅ DO: Handle errors gracefully
try:
    results = client.query("search term")
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 429:
        # Rate limited - implement backoff
        time.sleep(60)
        results = client.query("search term")
    else:
        logger.error(f"Query failed: {e}")
        results = []

# ✅ DO: Check response status
response = client.health()
if response["status"] != "healthy":
    logger.warning(f"KB unhealthy: {response}")
```

### 5. Performance Monitoring

```python
# ✅ DO: Monitor cache performance
stats = client.stats()
hit_rate = float(stats["cache_hit_rate"].rstrip("%"))

if hit_rate < 50:
    # Warm cache with common queries
    client.warm(force_rebuild=False)

# ✅ DO: Track query latency
import time

start = time.time()
results = client.query("test")
latency = time.time() - start

if latency > 1.0:
    logger.warning(f"Slow query: {latency:.2f}s")
```

### 6. Production Deployment

```bash
# ✅ DO: Set production environment variables
export KB_API_KEY="$(generate_secure_key)"
export KB_ALLOWED_ORIGINS="https://app.example.com,https://admin.example.com"
export KB_MAX_REQUEST_SIZE="10485760"  # 10MB
export KB_MAX_QUERY_LENGTH="5000"
export KB_RATE_LIMIT_PER_MINUTE="100"

# ✅ DO: Use HTTPS in production
# Configure reverse proxy (nginx, traefik, etc.)

# ✅ DO: Monitor health endpoint
curl https://api.example.com/api/v1/health

# ✅ DO: Set up log aggregation
# Collect logs from /var/log/knowledgebeast/
```

### 7. Cache Management

```python
# ✅ DO: Warm cache on startup
client.warm(force_rebuild=False)

# ✅ DO: Clear cache after data updates
client.batch_ingest(new_files)
client.clear_cache()  # Invalidate stale cache

# ✅ DO: Monitor cache size
stats = client.stats()
cache_size = stats["cached_queries"]

if cache_size > 1000:
    # Cache too large - consider clearing old entries
    client.clear_cache()
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. Connection Refused

**Symptom**:
```
requests.exceptions.ConnectionError: Connection refused
```

**Causes**:
- Server not running
- Wrong host/port
- Firewall blocking connection

**Solutions**:
```bash
# Check if server is running
curl http://localhost:8000/api/v1/health

# Start server if not running
knowledgebeast serve

# Check firewall
sudo ufw status
sudo ufw allow 8000

# Verify port is listening
netstat -tuln | grep 8000
```

---

#### 2. Authentication Failures

**Symptom**:
```json
{
  "error": "Unauthorized",
  "message": "Invalid API key",
  "status_code": 401
}
```

**Causes**:
- Missing `X-API-Key` header
- Invalid API key
- API key not set in environment

**Solutions**:
```bash
# Verify API key is set
echo $KB_API_KEY

# Set API key
export KB_API_KEY="your_key_here"

# Test with correct header
curl -H "X-API-Key: $KB_API_KEY" \
  http://localhost:8000/api/v1/health

# For development, unset to disable auth
unset KB_API_KEY
```

---

#### 3. Rate Limit Errors

**Symptom**:
```json
{
  "error": "RateLimitExceeded",
  "message": "Rate limit exceeded. Limit: 100 requests per 60s",
  "status_code": 429
}
```

**Solutions**:
```python
# Implement exponential backoff
import time

def query_with_backoff(query: str, max_retries: int = 3):
    for i in range(max_retries):
        try:
            return client.query(query)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                wait = 2 ** i  # Exponential backoff
                time.sleep(wait)
                continue
            raise
    raise Exception("Max retries exceeded")

# Use multiple API keys for higher throughput
api_keys = ["key1", "key2", "key3"]
key_index = 0

def get_next_client():
    global key_index
    client = KnowledgeBeastClient(api_key=api_keys[key_index])
    key_index = (key_index + 1) % len(api_keys)
    return client
```

---

#### 4. Slow Queries

**Symptom**:
- Query latency > 1 second
- Timeout errors

**Diagnostic**:
```python
# Check stats
stats = client.stats()
print(f"Total documents: {stats['total_documents']}")
print(f"Cache hit rate: {stats['cache_hit_rate']}")

# Time queries
import time

start = time.time()
results = client.query("test")
print(f"Query took: {time.time() - start:.2f}s")
```

**Solutions**:
```python
# 1. Warm the cache
client.warm(force_rebuild=False)

# 2. Enable caching
results = client.query("query", use_cache=True)

# 3. Reduce result limit
results = client.query("query", limit=10)  # Instead of 100

# 4. Rebuild index if stale
client.warm(force_rebuild=True)
```

---

#### 5. Pagination Errors

**Symptom**:
```json
{
  "error": "BadRequest",
  "message": "Page 10 exceeds total pages 5",
  "status_code": 400
}
```

**Solutions**:
```python
# Always check pagination metadata first
response = client.query_paginated("query", page=1)
total_pages = response["pagination"]["total_pages"]

# Then request valid pages
for page in range(1, total_pages + 1):
    response = client.query_paginated("query", page=page)
    # Process results...

# Handle empty results
if response["pagination"]["total_results"] == 0:
    print("No results found")
```

---

#### 6. File Ingestion Failures

**Symptom**:
```json
{
  "error": "ValidationError",
  "message": "Unsupported file type. Allowed: .md, .txt, .pdf, .docx, .html, .htm",
  "status_code": 422
}
```

**Solutions**:
```python
# Check file extension
from pathlib import Path

allowed = {'.md', '.txt', '.pdf', '.docx', '.html', '.htm'}
file_path = Path("/path/to/file.xyz")

if file_path.suffix.lower() not in allowed:
    print(f"Unsupported: {file_path.suffix}")
    # Convert or skip file

# Verify file exists
if not file_path.exists():
    print(f"File not found: {file_path}")

# Use absolute paths
file_path = file_path.resolve()
client.ingest(str(file_path))
```

---

#### 7. Cache Issues

**Symptom**:
- Stale results returned
- Cache never hits
- Memory usage high

**Diagnostic**:
```python
stats = client.stats()
print(f"Cached queries: {stats['cached_queries']}")
print(f"Cache hits: {stats['cache_hits']}")
print(f"Cache misses: {stats['cache_misses']}")
print(f"Hit rate: {stats['cache_hit_rate']}")
```

**Solutions**:
```python
# Clear stale cache
client.clear_cache()

# Disable cache for fresh results
results = client.query("query", use_cache=False)

# Rebuild and warm
client.warm(force_rebuild=True)

# Monitor cache size
if stats["cached_queries"] > 1000:
    client.clear_cache()
```

---

### Debug Mode

Enable debug logging for detailed troubleshooting:

```python
import logging

# Enable debug logs
logging.basicConfig(level=logging.DEBUG)

# Or for specific logger
logger = logging.getLogger("knowledgebeast")
logger.setLevel(logging.DEBUG)
```

```bash
# Server-side debug
KB_LOG_LEVEL=DEBUG knowledgebeast serve
```

---

### Getting Help

1. **Check Interactive Docs**: `http://localhost:8000/docs`
2. **View Logs**: Check server logs for errors
3. **Test with cURL**: Isolate issues with simple cURL commands
4. **Health Check**: Always start with `/health` endpoint
5. **Stats Endpoint**: Use `/stats` to understand KB state

---

## Performance Benchmarks

Expected performance on modern hardware:

| Metric | Target | Notes |
|--------|--------|-------|
| P50 Query Latency | < 50ms | Cached queries |
| P95 Query Latency | < 200ms | Uncached queries |
| P99 Query Latency | < 500ms | Complex queries |
| Cache Hit Rate | > 80% | With warming |
| Concurrent Throughput | > 500 q/s | 10 workers |
| Ingestion Rate | > 100 files/min | Batch ingestion |

### Performance Testing

```python
import time
import concurrent.futures

# Latency test
latencies = []
for _ in range(100):
    start = time.time()
    client.query("test query", use_cache=True)
    latencies.append(time.time() - start)

print(f"P50: {sorted(latencies)[50]:.3f}s")
print(f"P95: {sorted(latencies)[95]:.3f}s")
print(f"P99: {sorted(latencies)[99]:.3f}s")

# Throughput test
def query_worker():
    return client.query("test", use_cache=True)

start = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(query_worker) for _ in range(1000)]
    results = [f.result() for f in futures]

duration = time.time() - start
throughput = len(results) / duration
print(f"Throughput: {throughput:.1f} queries/sec")
```

---

## Related Documentation

- [REST API Endpoint Reference](../api-reference/rest-endpoints.md)
- [REST API Quick Guide](rest-api.md)
- [Python API Guide](python-api.md)
- [CLI Usage Guide](cli-usage.md)
- [Production Deployment](../deployment/production-checklist.md)
- [Docker Deployment](docker-deployment.md)

---

**Last Updated**: October 6, 2025
**API Version**: v1
**KnowledgeBeast Version**: 0.1.0+
