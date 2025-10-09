# KnowledgeBeast Multi-Project API Reference

**Version:** 2.3.0
**Base URL:** `http://localhost:8000/api/v2`
**Authentication:** Global API Key (Header: `X-API-Key`) + Project-level API Keys

---

## Table of Contents

- [Authentication](#authentication)
- [Project Management](#project-management)
- [Project Operations](#project-operations)
- [Project API Key Management](#project-api-key-management)
- [Monitoring](#monitoring)
- [Error Responses](#error-responses)

---

## Authentication

### Global API Key

All API v2 endpoints require a global API key for authentication.

**Header:**
```
X-API-Key: your-global-api-key-here
```

**Setting the Global API Key:**
```bash
export KB_API_KEY="your-secret-key-12345"
```

### Project-scoped API Keys

For fine-grained access control, create project-scoped API keys with specific permissions.

**Scopes:**
- `read` - Query project data
- `write` - Ingest documents
- `admin` - Full project access

---

## Project Management

### Create Project

Create a new isolated knowledge base project.

**Endpoint:** `POST /api/v2/projects`
**Rate Limit:** 10 requests/minute

**Request Body:**
```json
{
  "name": "Audio ML Project",
  "description": "Audio processing and machine learning knowledge base",
  "embedding_model": "all-MiniLM-L6-v2",
  "metadata": {
    "owner": "user@example.com",
    "tags": ["audio", "ml"]
  }
}
```

**Response:** `201 Created`
```json
{
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Audio ML Project",
  "description": "Audio processing and machine learning knowledge base",
  "collection_name": "kb_project_550e8400-e29b-41d4-a716-446655440000",
  "embedding_model": "all-MiniLM-L6-v2",
  "created_at": "2025-10-09T12:00:00",
  "updated_at": "2025-10-09T12:00:00",
  "metadata": {
    "owner": "user@example.com",
    "tags": ["audio", "ml"]
  }
}
```

**Metrics Recorded:**
- `kb_project_creations_total` (counter)

---

### List Projects

Retrieve all projects.

**Endpoint:** `GET /api/v2/projects`
**Rate Limit:** 60 requests/minute

**Response:** `200 OK`
```json
{
  "projects": [
    {
      "project_id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Audio ML Project",
      "description": "Audio processing",
      "collection_name": "kb_project_550e8400-e29b-41d4-a716-446655440000",
      "embedding_model": "all-MiniLM-L6-v2",
      "created_at": "2025-10-09T12:00:00",
      "updated_at": "2025-10-09T12:00:00",
      "metadata": {}
    }
  ],
  "count": 1
}
```

---

### Get Project Details

Retrieve detailed information about a specific project.

**Endpoint:** `GET /api/v2/projects/{project_id}`
**Rate Limit:** 60 requests/minute

**Path Parameters:**
- `project_id` (string, required) - Project identifier

**Response:** `200 OK`
```json
{
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Audio ML Project",
  "description": "Audio processing knowledge base",
  "collection_name": "kb_project_550e8400-e29b-41d4-a716-446655440000",
  "embedding_model": "all-MiniLM-L6-v2",
  "created_at": "2025-10-09T12:00:00",
  "updated_at": "2025-10-09T12:00:00",
  "metadata": {
    "owner": "user@example.com"
  }
}
```

**Status Codes:**
- `200 OK` - Project found
- `404 Not Found` - Project does not exist

---

### Update Project

Update project metadata.

**Endpoint:** `PUT /api/v2/projects/{project_id}`
**Rate Limit:** 20 requests/minute

**Path Parameters:**
- `project_id` (string, required) - Project identifier

**Request Body:**
```json
{
  "name": "Updated Project Name",
  "description": "Updated description",
  "embedding_model": "all-MiniLM-L6-v2",
  "metadata": {
    "updated": true
  }
}
```

**Response:** `200 OK` (Same as Get Project Details)

**Metrics Recorded:**
- `kb_project_updates_total` (counter)

**Status Codes:**
- `200 OK` - Project updated
- `404 Not Found` - Project does not exist
- `400 Bad Request` - Invalid update data

---

### Delete Project

Delete a project and all its resources (documents, embeddings, API keys).

**Endpoint:** `DELETE /api/v2/projects/{project_id}`
**Rate Limit:** 10 requests/minute

**Path Parameters:**
- `project_id` (string, required) - Project identifier

**Response:** `200 OK`
```json
{
  "success": true,
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Project 550e8400-e29b-41d4-a716-446655440000 deleted successfully"
}
```

**Metrics Recorded:**
- `kb_project_deletions_total` (counter)

**Status Codes:**
- `200 OK` - Project deleted
- `404 Not Found` - Project does not exist

---

## Project Operations

### Query Project

Search within a specific project's knowledge base using vector similarity.

**Endpoint:** `POST /api/v2/projects/{project_id}/query`
**Rate Limit:** 30 requests/minute

**Path Parameters:**
- `project_id` (string, required) - Project identifier

**Request Body:**
```json
{
  "query": "audio processing techniques",
  "use_cache": true,
  "limit": 10,
  "rerank": false,
  "rerank_top_k": 50,
  "diversity": null
}
```

**Response:** `200 OK`
```json
{
  "results": [
    {
      "doc_id": "doc_1728480000000",
      "content": "Audio processing involves...",
      "name": "audio_guide.md",
      "path": "/path/to/audio_guide.md",
      "kb_dir": "/path/to",
      "vector_score": 0.87,
      "rerank_score": null,
      "final_score": 0.87,
      "rank": 1
    }
  ],
  "count": 1,
  "cached": false,
  "query": "audio processing techniques"
}
```

**Metrics Recorded:**
- `kb_project_queries_total{project_id, status}` (counter)
- `kb_project_query_duration_seconds{project_id}` (histogram)
- `kb_project_cache_hits_total{project_id}` (counter, if cached)
- `kb_project_cache_misses_total{project_id}` (counter, if not cached)

**Status Codes:**
- `200 OK` - Query successful
- `404 Not Found` - Project does not exist
- `400 Bad Request` - Invalid query parameters

---

### Ingest Document

Add a document to a project's knowledge base.

**Endpoint:** `POST /api/v2/projects/{project_id}/ingest`
**Rate Limit:** 20 requests/minute

**Path Parameters:**
- `project_id` (string, required) - Project identifier

**Request Body (File):**
```json
{
  "file_path": "/path/to/document.md",
  "metadata": {
    "category": "audio",
    "tags": ["tutorial"]
  }
}
```

**Request Body (Direct Content):**
```json
{
  "content": "Document content here...",
  "metadata": {
    "category": "audio"
  }
}
```

**Response:** `200 OK`
```json
{
  "success": true,
  "file_path": "/path/to/document.md",
  "doc_id": "doc_1728480000000",
  "message": "Document successfully ingested into project Audio ML Project"
}
```

**Metrics Recorded:**
- `kb_project_ingests_total{project_id, status}` (counter)
- `kb_project_errors_total{project_id, error_type}` (counter, on error)

**Status Codes:**
- `200 OK` - Document ingested
- `404 Not Found` - Project or file not found
- `400 Bad Request` - Invalid request (neither file_path nor content provided)

---

## Project API Key Management

### Create API Key

Generate a new project-scoped API key with specific permissions.

**Endpoint:** `POST /api/v2/projects/{project_id}/api-keys`
**Rate Limit:** 10 requests/minute

**Path Parameters:**
- `project_id` (string, required) - Project identifier

**Request Body:**
```json
{
  "name": "Mobile App Key",
  "scopes": ["read"],
  "expires_days": 90
}
```

**Response:** `201 Created`
```json
{
  "key_id": "key_abc123xyz",
  "api_key": "kb_vL9x2K8pQ7mR4nS6tU0wY1zA3bC5dE7fG9h",
  "project_id": "proj_123",
  "name": "Mobile App Key",
  "scopes": ["read"],
  "created_at": "2025-10-09T12:00:00",
  "expires_at": "2026-01-09T12:00:00"
}
```

**Important:**
- The `api_key` field is **only returned once** at creation time
- Store the key securely - it cannot be retrieved again
- Keys are SHA-256 hashed in the database

**Scopes:**
- `read` - Query access only
- `write` - Ingest documents (implies read)
- `admin` - Full project access (implies read + write)

**Status Codes:**
- `201 Created` - API key created
- `404 Not Found` - Project does not exist
- `400 Bad Request` - Invalid scopes or parameters

---

### List API Keys

List all API keys for a project (excluding raw keys).

**Endpoint:** `GET /api/v2/projects/{project_id}/api-keys`
**Rate Limit:** 60 requests/minute

**Path Parameters:**
- `project_id` (string, required) - Project identifier

**Response:** `200 OK`
```json
{
  "project_id": "proj_123",
  "api_keys": [
    {
      "key_id": "key_abc123",
      "name": "Mobile App Key",
      "scopes": ["read"],
      "created_at": "2025-10-09T12:00:00",
      "expires_at": "2026-01-09T12:00:00",
      "revoked": false,
      "last_used_at": "2025-10-09T14:30:00",
      "created_by": "admin@example.com"
    }
  ],
  "count": 1
}
```

**Note:** Raw API keys are **never** included in list responses.

---

### Revoke API Key

Revoke an API key to immediately disable access.

**Endpoint:** `DELETE /api/v2/projects/{project_id}/api-keys/{key_id}`
**Rate Limit:** 20 requests/minute

**Path Parameters:**
- `project_id` (string, required) - Project identifier
- `key_id` (string, required) - API key identifier

**Response:** `200 OK`
```json
{
  "success": true,
  "key_id": "key_abc123",
  "message": "API key key_abc123 revoked successfully"
}
```

**Note:**
- Revoked keys are soft-deleted (audit trail preserved)
- Revoked keys are immediately invalid for all requests

**Status Codes:**
- `200 OK` - Key revoked
- `404 Not Found` - Project or key does not exist

---

## Monitoring

### Prometheus Metrics Endpoint

Access Prometheus metrics for monitoring and observability.

**Endpoint:** `GET /metrics`
**Authentication:** None (public endpoint)

**Response:** `200 OK`
```
# HELP kb_project_queries_total Total queries per project
# TYPE kb_project_queries_total counter
kb_project_queries_total{project_id="proj_123",status="success"} 150.0

# HELP kb_project_query_duration_seconds Query latency per project in seconds
# TYPE kb_project_query_duration_seconds histogram
kb_project_query_duration_seconds_bucket{le="0.01",project_id="proj_123"} 10.0
kb_project_query_duration_seconds_sum{project_id="proj_123"} 45.2
kb_project_query_duration_seconds_count{project_id="proj_123"} 150.0

# HELP kb_project_cache_hits_total Cache hits per project
# TYPE kb_project_cache_hits_total counter
kb_project_cache_hits_total{project_id="proj_123"} 120.0

# HELP kb_project_cache_misses_total Cache misses per project
# TYPE kb_project_cache_misses_total counter
kb_project_cache_misses_total{project_id="proj_123"} 30.0

# HELP kb_project_ingests_total Total documents ingested per project
# TYPE kb_project_ingests_total counter
kb_project_ingests_total{project_id="proj_123",status="success"} 42.0

# HELP kb_project_errors_total Total errors per project
# TYPE kb_project_errors_total counter
kb_project_errors_total{project_id="proj_123",error_type="QueryError"} 2.0

# HELP kb_project_api_key_validations_total Total API key validation attempts per project
# TYPE kb_project_api_key_validations_total counter
kb_project_api_key_validations_total{project_id="proj_123",result="success"} 500.0

# HELP kb_project_api_keys_active Number of active (non-revoked) API keys per project
# TYPE kb_project_api_keys_active gauge
kb_project_api_keys_active{project_id="proj_123"} 3.0

# HELP kb_project_creations_total Total number of projects created
# TYPE kb_project_creations_total counter
kb_project_creations_total 5.0

# HELP kb_project_updates_total Total number of project updates
# TYPE kb_project_updates_total counter
kb_project_updates_total 12.0

# HELP kb_project_deletions_total Total number of projects deleted
# TYPE kb_project_deletions_total counter
kb_project_deletions_total 1.0
```

**Available Metrics:**

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `kb_project_queries_total` | Counter | `project_id`, `status` | Total queries per project |
| `kb_project_query_duration_seconds` | Histogram | `project_id` | Query latency distribution |
| `kb_project_cache_hits_total` | Counter | `project_id` | Cache hits per project |
| `kb_project_cache_misses_total` | Counter | `project_id` | Cache misses per project |
| `kb_project_ingests_total` | Counter | `project_id`, `status` | Documents ingested |
| `kb_project_errors_total` | Counter | `project_id`, `error_type` | Errors by type |
| `kb_project_documents_total` | Gauge | `project_id` | Total documents in project |
| `kb_project_api_key_validations_total` | Counter | `project_id`, `result` | API key validations |
| `kb_project_api_keys_active` | Gauge | `project_id` | Active API keys count |
| `kb_project_creations_total` | Counter | - | Total projects created |
| `kb_project_updates_total` | Counter | - | Total project updates |
| `kb_project_deletions_total` | Counter | - | Total projects deleted |

---

## Error Responses

All error responses follow a standard format:

**Error Response Format:**
```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common Status Codes

| Code | Description | Example |
|------|-------------|---------|
| `200 OK` | Request successful | Document ingested, query returned results |
| `201 Created` | Resource created | Project or API key created |
| `400 Bad Request` | Invalid request parameters | Missing required field, invalid scope |
| `401 Unauthorized` | Invalid API key | Wrong API key value |
| `403 Forbidden` | Missing API key | No `X-API-Key` header provided |
| `404 Not Found` | Resource not found | Project, file, or key does not exist |
| `429 Too Many Requests` | Rate limit exceeded | Too many requests in time window |
| `500 Internal Server Error` | Server error | Database error, collection error |

### Rate Limiting Headers

When rate limited (status `429`), responses include:

```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1728480060
```

---

## Examples

### Complete Workflow Example

```bash
# 1. Create a project
curl -X POST http://localhost:8000/api/v2/projects \
  -H "X-API-Key: your-global-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Audio ML Project",
    "description": "Audio processing knowledge base"
  }'

# Response: {"project_id": "proj_abc123", ...}

# 2. Create a project API key
curl -X POST http://localhost:8000/api/v2/projects/proj_abc123/api-keys \
  -H "X-API-Key: your-global-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Read-Only Key",
    "scopes": ["read"],
    "expires_days": 30
  }'

# Response: {"api_key": "kb_xxx...", ...}
# SAVE THIS KEY - it won't be shown again!

# 3. Ingest a document
curl -X POST http://localhost:8000/api/v2/projects/proj_abc123/ingest \
  -H "X-API-Key: your-global-key" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Librosa is a Python package for audio analysis...",
    "metadata": {"category": "audio"}
  }'

# 4. Query the project
curl -X POST http://localhost:8000/api/v2/projects/proj_abc123/query \
  -H "X-API-Key: your-global-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "audio analysis",
    "limit": 5
  }'

# 5. List API keys
curl -X GET http://localhost:8000/api/v2/projects/proj_abc123/api-keys \
  -H "X-API-Key: your-global-key"

# 6. Revoke API key
curl -X DELETE http://localhost:8000/api/v2/projects/proj_abc123/api-keys/key_abc123 \
  -H "X-API-Key: your-global-key"

# 7. Check metrics
curl http://localhost:8000/metrics | grep project
```

---

## Version History

- **v2.3.0** (2025-10-09): Multi-project API with security and observability
  - Project-scoped API keys with granular permissions
  - Prometheus metrics for all project operations
  - Project isolation with ChromaDB collections
  - Rate limiting on all endpoints

---

**Documentation last updated:** October 9, 2025
