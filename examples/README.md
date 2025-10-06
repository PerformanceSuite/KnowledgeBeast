# KnowledgeBeast Examples

This directory contains example scripts demonstrating various KnowledgeBeast features.

## Examples

### 1. basic_usage.py

Basic KnowledgeBeast usage:
- Initializing the knowledge base
- Ingesting documents
- Querying
- Getting statistics

```bash
python examples/basic_usage.py
```

### 2. api_integration.py

REST API integration using requests:
- Health checks
- Querying via HTTP
- Error handling

**Requirements**: API server must be running

```bash
# Terminal 1: Start server
knowledgebeast serve

# Terminal 2: Run example
python examples/api_integration.py
```

### 3. cli_workflow.sh

Complete CLI workflow:
- Initialization
- Document ingestion
- Querying
- Cache management
- Heartbeat monitoring

```bash
./examples/cli_workflow.sh
```

### 4. fastapi_integration.py

FastAPI integration example:
- Custom FastAPI app with KnowledgeBeast
- Dependency injection
- Custom endpoints

```bash
# Run the example server
python examples/fastapi_integration.py

# Or with uvicorn
uvicorn examples.fastapi_integration:app --reload

# Test endpoints
curl http://localhost:8000/health
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "machine learning", "n_results": 5}'
```

### 5. custom_config.py

Configuration examples:
- Basic configuration
- Advanced settings
- Environment-based config
- Performance optimization

```bash
python examples/custom_config.py

# With environment
ENV=production python examples/custom_config.py
```

### 6. batch_processing.py

Batch processing:
- Batch document ingestion
- Batch queries
- Progress tracking
- Cache warming

```bash
python examples/batch_processing.py
```

## Dependencies

Some examples require additional packages:

```bash
pip install tqdm requests
```

## Next Steps

- [Documentation](../docs/)
- [Getting Started](../docs/getting-started/quickstart.md)
- [Python API Guide](../docs/guides/python-api.md)
- [CLI Usage Guide](../docs/guides/cli-usage.md)
