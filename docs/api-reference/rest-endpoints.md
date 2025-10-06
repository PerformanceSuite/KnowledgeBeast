# REST API Reference

Complete reference for KnowledgeBeast REST API endpoints.

## Base URL

```
http://localhost:8000/api/v1
```

## Endpoints

### GET /health

Health check.

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

### POST /query

Query knowledge base.

**Request:**
```json
{
  "query": "machine learning",
  "n_results": 5,
  "use_cache": true
}
```

**Response:**
```json
{
  "results": [...],
  "cached": false
}
```

### POST /ingest

Ingest document.

**Request:**
```json
{
  "file_path": "/path/to/doc.pdf",
  "metadata": {}
}
```

**Response:**
```json
{
  "success": true,
  "chunks": 42,
  "message": "Success"
}
```

### GET /stats

Get statistics.

**Response:**
```json
{
  "total_documents": 42,
  "cache_stats": {...},
  "heartbeat_running": true
}
```

### DELETE /clear

Clear knowledge base.

**Response:**
```json
{
  "message": "Knowledge base cleared successfully"
}
```

For interactive docs, visit: `http://localhost:8000/docs`
