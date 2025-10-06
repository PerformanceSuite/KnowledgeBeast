# KnowledgeBeast REST API

Production-ready REST API for KnowledgeBeast knowledge management system.

## Features

- **12 RESTful Endpoints** for complete knowledge base management
- **Rate Limiting** with slowapi (configurable per endpoint)
- **Request ID Tracking** for distributed tracing
- **Performance Monitoring** with timing middleware
- **Comprehensive Error Handling** with detailed error responses
- **OpenAPI/Swagger Documentation** at `/docs`
- **ReDoc Documentation** at `/redoc`
- **CORS Support** for cross-origin requests
- **Lifespan Management** for proper startup/shutdown
- **Pydantic v2 Validation** with comprehensive examples

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

### Run the Server

```bash
# Development mode (with hot reload)
python -m knowledgebeast.api.app

# Or with uvicorn directly
uvicorn knowledgebeast.api.app:app --reload --host 0.0.0.0 --port 8000
```

### Access Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## API Endpoints

All endpoints are versioned under `/api/v1`.

### Health & Monitoring

| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| GET | `/api/v1/health` | Health check and system status | 100/min |
| GET | `/api/v1/stats` | Detailed KB statistics | 60/min |

### Query Operations

| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| POST | `/api/v1/query` | Search knowledge base | 30/min |

### Document Ingestion

| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| POST | `/api/v1/ingest` | Ingest single document | 20/min |
| POST | `/api/v1/batch-ingest` | Batch ingest multiple documents | 10/min |

### Cache & Warming

| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| POST | `/api/v1/warm` | Trigger KB warming | 10/min |
| POST | `/api/v1/cache/clear` | Clear query cache | 20/min |

### Heartbeat Management

| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| GET | `/api/v1/heartbeat/status` | Get heartbeat status | 60/min |
| POST | `/api/v1/heartbeat/start` | Start heartbeat monitoring | 10/min |
| POST | `/api/v1/heartbeat/stop` | Stop heartbeat monitoring | 10/min |

### Collections

| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| GET | `/api/v1/collections` | List all collections | 60/min |
| GET | `/api/v1/collections/{name}` | Get collection details | 60/min |

## Usage Examples

### Health Check

```bash
curl http://localhost:8000/api/v1/health
```

Response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "kb_initialized": true,
  "timestamp": "2025-10-05T12:00:00Z"
}
```

### Query Knowledge Base

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I use librosa for audio analysis?",
    "use_cache": true
  }'
```

Response:
```json
{
  "results": [
    {
      "doc_id": "knowledge-base/audio/librosa.md",
      "content": "Librosa is a Python package...",
      "name": "Librosa Guide",
      "path": "/path/to/librosa.md",
      "kb_dir": "/knowledge-base"
    }
  ],
  "count": 1,
  "cached": false,
  "query": "How do I use librosa for audio analysis?"
}
```

### Get Statistics

```bash
curl http://localhost:8000/api/v1/stats
```

Response:
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
  "knowledge_dirs": ["/knowledge-base"],
  "total_queries": 150
}
```

### Ingest Document

```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/knowledge-base/audio/new-doc.md",
    "metadata": {
      "category": "audio",
      "tags": ["tutorial"]
    }
  }'
```

### Batch Ingest

```bash
curl -X POST http://localhost:8000/api/v1/batch-ingest \
  -H "Content-Type: application/json" \
  -d '{
    "file_paths": [
      "/knowledge-base/audio/doc1.md",
      "/knowledge-base/audio/doc2.md"
    ]
  }'
```

### Warm Knowledge Base

```bash
curl -X POST http://localhost:8000/api/v1/warm \
  -H "Content-Type: application/json" \
  -d '{
    "force_rebuild": false
  }'
```

### Clear Cache

```bash
curl -X POST http://localhost:8000/api/v1/cache/clear
```

### Start Heartbeat

```bash
curl -X POST http://localhost:8000/api/v1/heartbeat/start
```

### Get Heartbeat Status

```bash
curl http://localhost:8000/api/v1/heartbeat/status
```

### List Collections

```bash
curl http://localhost:8000/api/v1/collections
```

## Response Headers

All responses include these custom headers:

- `X-Request-ID`: Unique request identifier for tracing
- `X-Process-Time`: Request processing time in seconds

## Error Handling

All errors follow a consistent format:

```json
{
  "error": "ValidationError",
  "message": "Request validation failed",
  "detail": "query: field required",
  "status_code": 422
}
```

### HTTP Status Codes

- `200`: Success
- `400`: Bad Request (validation error, invalid input)
- `404`: Not Found (resource doesn't exist)
- `422`: Unprocessable Entity (Pydantic validation error)
- `429`: Too Many Requests (rate limit exceeded)
- `500`: Internal Server Error

## Configuration

### Environment Variables

Configure via environment variables with `KB_` prefix:

```bash
export KB_KNOWLEDGE_DIRS="/path/to/kb1,/path/to/kb2"
export KB_CACHE_FILE=".knowledge_cache.pkl"
export KB_MAX_CACHE_SIZE=100
export KB_HEARTBEAT_INTERVAL=300
export KB_AUTO_WARM=true
```

### Rate Limiting

Rate limits are configured per endpoint. Adjust in `routes.py`:

```python
@limiter.limit("30/minute")  # Customize as needed
async def query_knowledge_base(request: Request, ...):
    ...
```

### CORS

Configure CORS in `app.py` for production:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Restrict origins
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

## Architecture

### Components

1. **app.py**: FastAPI application factory with middleware and error handling
2. **routes.py**: All 12 API endpoints with rate limiting
3. **models.py**: Pydantic v2 request/response models
4. **middleware.py**: Custom middleware for request tracking, timing, and logging

### Middleware Stack (Outermost to Innermost)

1. **LoggingMiddleware**: Logs all requests/responses
2. **TimingMiddleware**: Measures request processing time
3. **RequestIDMiddleware**: Adds unique request IDs
4. **CORS**: Handles cross-origin requests
5. **Rate Limiting**: Enforces rate limits per endpoint

### Singleton Pattern

The API uses singleton pattern for:
- **KnowledgeBase**: Single instance shared across all requests
- **Heartbeat**: Single background heartbeat thread

## Production Deployment

### With Gunicorn + Uvicorn Workers

```bash
gunicorn knowledgebeast.api.app:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
```

### With Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "knowledgebeast.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Behind Nginx

```nginx
upstream knowledgebeast_api {
    server localhost:8000;
}

server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://knowledgebeast_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Request-ID $request_id;
    }
}
```

## Testing

```bash
# Run API tests
pytest tests/api/

# Test with curl
./tests/api/test_endpoints.sh
```

## Performance

- **Query Latency**: <50ms (warmed cache)
- **Cache Hit Rate**: >60% typical
- **Throughput**: 100+ req/s (single worker)
- **Memory**: ~500MB baseline + documents

## Security

- Rate limiting on all endpoints
- Request validation with Pydantic
- Security headers (X-Content-Type-Options, X-Frame-Options, etc.)
- CORS configuration
- Request ID tracking for audit logs
- Error details sanitized in production

## Monitoring

Track these metrics:

- Request latency (`X-Process-Time` header)
- Cache hit rate (`/api/v1/stats`)
- Error rates (via logs)
- Active heartbeat (`/api/v1/heartbeat/status`)

## License

MIT License - See LICENSE file for details

## Contributing

1. Fork the repository
2. Create feature branch
3. Add tests
4. Submit pull request

## Support

For issues and questions:
- GitHub Issues: https://github.com/yourusername/knowledgebeast/issues
- Documentation: https://knowledgebeast.readthedocs.io
