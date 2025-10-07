# KnowledgeBeast FAQ

Frequently asked questions about KnowledgeBeast - a production-ready knowledge management system with RAG capabilities.

## Quick Answers

| Question | Answer |
|----------|--------|
| **What is KnowledgeBeast?** | A high-performance knowledge management system with RAG capabilities, vector search, and intelligent caching. |
| **What are the system requirements?** | Python 3.11+, 2GB+ RAM, 1GB+ disk space for embeddings. |
| **What file formats are supported?** | PDF, Markdown (.md), Text (.txt), Word (.docx), HTML (.html) |
| **How fast can it process queries?** | Cached queries: <10ms, Cold queries: ~80ms (P99 latency) |
| **Is it thread-safe?** | Yes, 100% thread-safe with comprehensive concurrency testing. |
| **How do I install it?** | `pip install knowledgebeast` |
| **Does it require authentication?** | API endpoints require `X-API-Key` header with valid API key. |
| **Can I use it with Docker?** | Yes, Docker and docker-compose are fully supported. |
| **Is HTTPS supported?** | Yes, configure with `KB_HTTPS_ONLY=true` environment variable. |
| **How do I contribute?** | Fork the repo, create a feature branch, add tests, and submit a PR. |

---

## Table of Contents

- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Usage](#usage)
- [Performance](#performance)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Deployment](#deployment)

---

## Getting Started

### What is KnowledgeBeast?

KnowledgeBeast is a production-ready knowledge management system with RAG (Retrieval-Augmented Generation) capabilities. It provides semantic search over your documents using state-of-the-art embeddings, with features like intelligent caching, thread-safe operations, and high-performance query processing.

Built for speed and reliability, KnowledgeBeast offers multiple interfaces (Python API, CLI, REST API, Web UI) and is optimized for concurrent workloads with 5-10x throughput improvements through advanced lock optimization techniques.

**Learn more:** [README.md](../README.md)

### How does it differ from other RAG systems?

KnowledgeBeast stands out with:
- **Production-ready**: Comprehensive error handling, logging, and monitoring out of the box
- **High performance**: P99 query latency <100ms, cached queries <10ms, 800+ queries/sec throughput
- **Thread safety**: Fully thread-safe with zero data corruption under concurrent load
- **Intelligent caching**: LRU cache with configurable size and cache warming strategies
- **Multiple interfaces**: Python SDK, CLI, REST API, and beautiful web UI
- **Easy deployment**: Docker support, systemd integration, and production checklists

**Learn more:** [Architecture Overview](architecture/overview.md)

### What are the system requirements?

**Minimum Requirements:**
- Python 3.11 or higher
- 2GB RAM (4GB+ recommended for production)
- 1GB+ disk space for embeddings and data storage
- pip (Python package manager)

**Recommended for Production:**
- 4GB+ RAM for larger caches and concurrent processing
- 2+ CPU cores for parallel query processing
- SSD storage for better I/O performance
- Linux/macOS (Windows also supported)

**Learn more:** [Installation Guide](getting-started/installation.md)

### How do I install it?

**From PyPI (Recommended):**
```bash
pip install knowledgebeast
```

**From Source:**
```bash
git clone https://github.com/yourusername/knowledgebeast
cd knowledgebeast
pip install -e .
```

**With Development Dependencies:**
```bash
pip install -e ".[dev]"
# or
make dev
```

**Verify Installation:**
```bash
knowledgebeast version
knowledgebeast health
```

**Learn more:** [Installation Guide](getting-started/installation.md)

---

## Configuration

### What environment variables are required?

**No environment variables are strictly required** - KnowledgeBeast works with sensible defaults. However, you can customize behavior:

**Core Settings:**
- `KB_DATA_DIR` - Data directory path (default: `./data`)
- `KB_CACHE_SIZE` - LRU cache size (default: `100`)
- `KB_HEARTBEAT_INTERVAL` - Heartbeat interval in seconds (default: `60.0`)

**Security Settings:**
- `KB_API_KEY` - API key(s) for authentication (comma-separated for multiple keys)
- `KB_ALLOWED_ORIGINS` - CORS allowed origins (comma-separated)
- `KB_HTTPS_ONLY` - Enforce HTTPS (default: `false`)

**Advanced Settings:**
- `KB_MAX_REQUEST_SIZE` - Max request body size in bytes (default: `10MB`)
- `KB_RATE_LIMIT_PER_MINUTE` - Rate limit per API key (default: `100`)

**Learn more:** [Configuration Guide](getting-started/configuration.md) | [Security Guide](deployment/security.md)

### How do I configure multiple knowledge directories?

You can configure multiple knowledge directories in several ways:

**Via Environment Variable:**
```bash
export KB_KNOWLEDGE_DIRS="./docs,./papers,./articles"
```

**Via Python API:**
```python
from pathlib import Path
from knowledgebeast import KnowledgeBeast, KnowledgeBeastConfig

config = KnowledgeBeastConfig(
    data_dir=Path("./my-data")
)

kb = KnowledgeBeast(config)

# Ingest from multiple directories
kb.ingest_document("./docs/file1.pdf")
kb.ingest_document("./papers/file2.pdf")
```

**Via CLI:**
```bash
knowledgebeast add ./docs/ --recursive
knowledgebeast add ./papers/ --recursive
```

**Learn more:** [Configuration Guide](getting-started/configuration.md)

### How do I set up authentication?

API authentication uses API keys passed via the `X-API-Key` header:

**1. Set API Key(s):**
```bash
# Single API key
export KB_API_KEY="your_secret_api_key_here"

# Multiple API keys (comma-separated)
export KB_API_KEY="web_key_123,mobile_key_456,admin_key_789"

# Or use .env file
echo "KB_API_KEY=your_secret_api_key_here" > .env
```

**2. Use API Key in Requests:**
```bash
curl http://localhost:8000/api/v1/query \
  -H "X-API-Key: your_secret_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"query": "machine learning"}'
```

**3. Rate Limiting:**
- 100 requests per minute per API key (configurable)
- Rate limit headers in responses: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

**Learn more:** [REST API Guide](guides/rest-api.md) | [Security Guide](deployment/security.md)

### What's the recommended cache size?

Cache size depends on your usage patterns:

**Small Cache (50-100 entries):**
- Low memory usage (~5-10MB)
- Development environments
- Infrequent repeated queries
```python
config = KnowledgeBeastConfig(cache_size=50)
```

**Medium Cache (100-200 entries) - Default:**
- Balanced memory/performance
- Most production use cases
- ~10-20MB memory
```python
config = KnowledgeBeastConfig(cache_size=100)
```

**Large Cache (500-1000 entries):**
- High-traffic applications
- Frequent repeated queries
- 50-100MB memory
```python
config = KnowledgeBeastConfig(cache_size=500)
```

**Pro Tip:** Monitor cache hit rate with `kb.get_stats()` - aim for >80% hit rate. Warm cache after ingestion with common queries.

**Learn more:** [Configuration Guide](getting-started/configuration.md) | [Caching Strategy](architecture/caching-strategy.md)

---

## Usage

### How do I ingest documents?

**CLI Method:**
```bash
# Single document
knowledgebeast ingest document.pdf

# Multiple documents from directory
knowledgebeast add ./documents/ --recursive

# Custom data directory
knowledgebeast ingest document.pdf --data-dir ./my-data
```

**Python API Method:**
```python
from knowledgebeast import KnowledgeBeast

with KnowledgeBeast() as kb:
    # Single document
    chunks = kb.ingest_document("document.pdf")
    print(f"Ingested {chunks} chunks")

    # Multiple documents
    for doc in ["paper1.pdf", "paper2.pdf", "notes.md"]:
        kb.ingest_document(doc)
```

**REST API Method:**
```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_key" \
  -d '{"file_path": "/path/to/document.pdf"}'
```

**Learn more:** [Quick Start Guide](getting-started/quickstart.md) | [Python API Guide](guides/python-api.md)

### What file formats are supported?

KnowledgeBeast supports multiple document formats via Docling:

**Supported Formats:**
- **PDF** (.pdf) - Research papers, reports, books
- **Markdown** (.md) - Documentation, notes
- **Text** (.txt) - Plain text documents
- **Word** (.docx) - Microsoft Word documents
- **HTML** (.html) - Web pages, articles

**Processing:**
- Automatic format detection
- Smart chunking with configurable size (default: 1000 chars)
- Metadata extraction (source, page numbers, custom fields)
- Preserves document structure

**Example:**
```python
# All formats work the same way
kb.ingest_document("research.pdf")
kb.ingest_document("README.md")
kb.ingest_document("notes.txt")
kb.ingest_document("report.docx")
kb.ingest_document("article.html")
```

**Learn more:** [Quick Start Guide](getting-started/quickstart.md)

### How does the query syntax work?

**Basic Query:**
```bash
# Simple text query
knowledgebeast query "machine learning"

# Get more results
knowledgebeast query "neural networks" -n 20

# Disable cache for fresh results
knowledgebeast query "deep learning" --no-cache
```

**Python API:**
```python
# Basic query
results = kb.query("machine learning")

# Specify number of results
results = kb.query("neural networks", n_results=10)

# Disable cache
results = kb.query("deep learning", use_cache=False)

# Process results
for result in results:
    print(f"Text: {result['text']}")
    print(f"Source: {result['metadata']['source']}")
    print(f"Distance: {result['distance']}")  # Lower is better
```

**Query Tips:**
- Use natural language questions: "What is machine learning?"
- Specific terms work better: "neural network architectures" vs "AI"
- Distance <0.5 indicates high relevance
- Combine with filtering for better results

**Learn more:** [Python API Guide](guides/python-api.md) | [CLI Usage Guide](guides/cli-usage.md)

### How do I use pagination?

Pagination is handled via the `n_results` parameter:

**CLI:**
```bash
# Get top 10 results
knowledgebeast query "machine learning" -n 10

# Get top 50 results
knowledgebeast query "AI research" -n 50
```

**Python API:**
```python
# Paginated queries
page_size = 10
results = kb.query("machine learning", n_results=page_size)

# Filter by distance for quality control
high_quality = [r for r in results if r['distance'] < 0.5]

# Custom pagination
def paginated_query(kb, query, page=1, page_size=10):
    all_results = kb.query(query, n_results=page * page_size)
    start = (page - 1) * page_size
    end = page * page_size
    return all_results[start:end]

# Usage
page1 = paginated_query(kb, "machine learning", page=1)
page2 = paginated_query(kb, "machine learning", page=2)
```

**REST API:**
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_key" \
  -d '{"query": "machine learning", "n_results": 20}'
```

**Learn more:** [Python API Guide](guides/python-api.md)

---

## Performance

### How fast can it process queries?

**Performance Benchmarks:**

| Metric | Target | Typical Performance |
|--------|--------|---------------------|
| P99 Query Latency | <100ms | ~80ms |
| P99 Cached Query | <10ms | ~5ms |
| Concurrent Throughput (10 workers) | >500 q/s | ~800 q/s |
| Concurrent Throughput (50 workers) | >300 q/s | ~600 q/s |
| Cache Hit Ratio | >90% | ~95% |

**Ingestion Performance:**
- Small docs (<10 pages): 1-2 seconds
- Medium docs (10-50 pages): 3-10 seconds
- Large docs (50+ pages): 10-30 seconds

**Memory Usage:**
- Base (model loading): ~500MB
- Per 1000 documents: ~200MB
- Cache (100 queries): ~10MB

**Learn more:** [Performance Guide](architecture/performance.md)

### How do I optimize performance?

**1. Choose the Right Embedding Model:**
```python
# Fastest, smallest (80MB) - default
config = KnowledgeBeastConfig(embedding_model="all-MiniLM-L6-v2")

# Better quality, larger (420MB)
config = KnowledgeBeastConfig(embedding_model="all-mpnet-base-v2")

# Optimized for Q&A (420MB)
config = KnowledgeBeastConfig(embedding_model="multi-qa-mpnet-base-dot-v1")
```

**2. Optimize Chunk Size:**
```python
# Small chunks - more precise, slower
config = KnowledgeBeastConfig(chunk_size=500, chunk_overlap=100)

# Medium chunks - balanced (default)
config = KnowledgeBeastConfig(chunk_size=1000, chunk_overlap=200)

# Large chunks - faster, less precise
config = KnowledgeBeastConfig(chunk_size=2000, chunk_overlap=400)
```

**3. Enable and Warm Cache:**
```python
# Larger cache for high-traffic apps
config = KnowledgeBeastConfig(cache_size=500)

# Warm cache after ingestion
common_queries = ["ML basics", "neural networks", "deep learning"]
for query in common_queries:
    kb.query(query)  # Populates cache
```

**4. Use Batch Operations:**
```python
# Process documents in batches
for batch in batches(documents, size=10):
    for doc in batch:
        kb.ingest_document(doc)
```

**Learn more:** [Performance Guide](architecture/performance.md) | [Configuration Guide](getting-started/configuration.md)

### What affects query latency?

**Factors Affecting Latency:**

**1. Cache Status** (biggest impact):
- Cached query: <10ms
- Uncached query: 100-500ms
- Solution: Warm cache with common queries

**2. Number of Results:**
- 5 results: ~80ms
- 20 results: ~150ms
- 50 results: ~300ms
- Solution: Request only needed results

**3. Index Size:**
- <1000 docs: Fast (<100ms)
- 1000-10000 docs: Medium (100-300ms)
- >10000 docs: Slower (>300ms)
- Solution: Optimize chunk size, partition data

**4. Embedding Model:**
- MiniLM (80MB): Fastest
- MPNet (420MB): 2-3x slower but better quality

**5. System Resources:**
- RAM: More cache = better performance
- CPU: More cores = better concurrent throughput
- Storage: SSD vs HDD makes difference

**Monitor Performance:**
```python
stats = kb.get_stats()
print(f"Cache hit rate: {stats['cache_stats']['hit_rate']:.2%}")
# Aim for >80% hit rate
```

**Learn more:** [Performance Guide](architecture/performance.md)

### How does caching work?

KnowledgeBeast uses a **thread-safe LRU (Least Recently Used) cache**:

**How It Works:**
1. Query arrives → Check cache for exact match
2. If cached → Return in <10ms
3. If not cached → Process query (~100ms) → Store in cache
4. When cache full → Evict least recently used entry

**Cache Features:**
- Thread-safe with `threading.Lock()` on all operations
- Configurable size (default: 100 entries)
- ~95% hit rate in typical usage
- Cache warming support
- Secure JSON format (no pickle vulnerabilities)

**Usage:**
```python
# Configure cache size
config = KnowledgeBeastConfig(cache_size=200)

# Check cache stats
stats = kb.get_stats()
cache_stats = stats['cache_stats']
print(f"Hit rate: {cache_stats['hit_rate']:.2%}")
print(f"Size: {cache_stats['size']}/{cache_stats['capacity']}")

# Clear cache
kb.clear_cache()

# Warm cache
for query in common_queries:
    kb.query(query, use_cache=True)  # Important: use_cache=True!
```

**Learn more:** [Caching Strategy](architecture/caching-strategy.md) | [CLAUDE.md](../CLAUDE.md)

---

## Security

### How is data secured?

KnowledgeBeast implements multiple security layers:

**1. API Authentication:**
- Required `X-API-Key` header for all API endpoints
- Support for multiple API keys
- Rate limiting (100 req/min per key, configurable)

**2. CORS Protection:**
- Configurable allowed origins (no wildcards in production)
- Restricted HTTP methods (GET, POST, DELETE only)
- Default: localhost origins for development

**3. Security Headers:**
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Content-Security-Policy` (strict CSP)
- `Strict-Transport-Security` (HSTS for HTTPS)

**4. Request Limits:**
- Max request body: 10MB (configurable)
- Max query length: 10,000 chars
- Protection against DoS attacks

**5. Secure Caching:**
- JSON-only format (no pickle deserialization)
- Automatic migration from legacy pickle caches

**Learn more:** [Security Guide](deployment/security.md)

### How does authentication work?

**Setup:**
```bash
# Set API key
export KB_API_KEY="your_secret_key_here"

# Multiple keys (comma-separated)
export KB_API_KEY="web_key,mobile_key,admin_key"
```

**Usage:**
```bash
# All API requests require X-API-Key header
curl http://localhost:8000/api/v1/health \
  -H "X-API-Key: your_secret_key_here"

curl -X POST http://localhost:8000/api/v1/query \
  -H "X-API-Key: your_secret_key_here" \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'
```

**Rate Limiting:**
- 100 requests/minute per API key (default)
- Configurable via `KB_RATE_LIMIT_PER_MINUTE`
- Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- Returns `429 Too Many Requests` when exceeded

**Best Practices:**
- Never commit API keys to version control
- Use environment variables or secret management
- Rotate keys regularly in production
- Use different keys for different environments
- Monitor rate limits to detect abuse

**Learn more:** [REST API Guide](guides/rest-api.md) | [Security Guide](deployment/security.md)

### Can I use HTTPS?

Yes, HTTPS is fully supported and recommended for production:

**Enable HTTPS:**
```bash
export KB_HTTPS_ONLY=true
```

**Configure Reverse Proxy (Recommended):**
```nginx
server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $host;
    }
}
```

**HSTS (HTTP Strict Transport Security):**
- Automatically enabled when HTTPS detected
- Max age: 1 year
- Includes subdomains
- Preload enabled

**Learn more:** [Security Guide](deployment/security.md) | [Production Checklist](deployment/production-checklist.md)

### What about CORS?

**Configuration:**
```bash
# Single origin
export KB_ALLOWED_ORIGINS=https://app.example.com

# Multiple origins (comma-separated)
export KB_ALLOWED_ORIGINS=https://app.example.com,https://api.example.com
```

**Default (Development):**
- `http://localhost:3000`
- `http://localhost:8000`
- `http://localhost:8080`
- `http://127.0.0.1:3000`
- `http://127.0.0.1:8000`
- `http://127.0.0.1:8080`

**Allowed Methods:**
- GET, POST, DELETE, OPTIONS only
- PUT, PATCH, HEAD are blocked

**Production Best Practices:**
- Never use wildcard (`*`) origins
- Specify exact allowed origins
- Review CORS logs regularly
- Test CORS configuration before deployment

**Learn more:** [Security Guide](deployment/security.md)

---

## Troubleshooting

### Why are my queries slow?

**Diagnosis:**
```bash
# Check cache hit rate
knowledgebeast stats

# Look for:
# - Cache hit rate < 80% → Cache not warmed
# - Cache size = 0 → Cache disabled
# - Large index → Need optimization
```

**Common Causes & Fixes:**

**1. Cache Not Warmed:**
```python
# Warm cache with common queries
common_queries = ["ML", "AI", "neural networks"]
for query in common_queries:
    kb.query(query, use_cache=True)  # Important!
```

**2. Cache Disabled:**
```python
# Ensure cache is enabled
results = kb.query("test", use_cache=True)  # Not False!
```

**3. Too Many Results:**
```bash
# Request fewer results
knowledgebeast query "test" -n 5  # Instead of -n 50
```

**4. Large Index:**
```python
# Optimize chunk size
config = KnowledgeBeastConfig(chunk_size=1500)  # Larger chunks
```

**5. Resource Constraints:**
- Increase RAM for larger cache
- Use faster storage (SSD)
- More CPU cores for concurrent queries

**Learn more:** [Performance Guide](architecture/performance.md)

### Why can't I ingest documents?

**Common Issues:**

**1. File Not Found:**
```bash
# Check file path
ls -la /path/to/document.pdf

# Use absolute path
knowledgebeast ingest /absolute/path/to/document.pdf
```

**2. Unsupported Format:**
```bash
# Check supported formats: .pdf, .md, .txt, .docx, .html
# Convert unsupported formats first
```

**3. Permission Denied:**
```bash
# Check file permissions
chmod +r document.pdf

# Check data directory permissions
chmod -R u+w ./data
```

**4. Memory Issues:**
```bash
# For large files, monitor memory
# Reduce chunk size if needed
knowledgebeast ingest large.pdf --chunk-size 500
```

**5. Dependency Issues:**
```bash
# Reinstall dependencies
pip install --upgrade knowledgebeast
pip install --upgrade docling chromadb
```

**Debug Mode:**
```bash
# Run with verbose logging
knowledgebeast -v ingest document.pdf
```

**Learn more:** [Quick Start Guide](getting-started/quickstart.md)

### How do I fix authentication errors?

**Error: "Missing API Key"**
```bash
# Solution: Set KB_API_KEY
export KB_API_KEY="your_key_here"

# Or use .env file
echo "KB_API_KEY=your_key" > .env
```

**Error: "Invalid API Key"**
```bash
# Check if key is correct
echo $KB_API_KEY

# Ensure header is correct
curl -H "X-API-Key: your_key" http://localhost:8000/api/v1/health
# Not: "API-Key" or "Authorization"
```

**Error: "Rate Limit Exceeded (429)"**
```bash
# Wait for rate limit reset (check X-RateLimit-Reset header)
# Or increase rate limit
export KB_RATE_LIMIT_PER_MINUTE=200

# Or use different API key
```

**Error: "CORS Policy Error"**
```bash
# Add your origin to allowed list
export KB_ALLOWED_ORIGINS=https://yourapp.com

# Check browser console for exact origin
```

**Learn more:** [REST API Guide](guides/rest-api.md) | [Security Guide](deployment/security.md)

### What if cache gets corrupted?

**Symptoms:**
- Inconsistent query results
- Errors when retrieving cached queries
- Cache hit rate = 0%

**Solutions:**

**1. Clear Cache (Recommended):**
```bash
# CLI
knowledgebeast clear-cache --yes

# Python API
kb.clear_cache()
```

**2. Delete Cache File:**
```bash
# Find cache file (default: .knowledge_cache.pkl or .knowledge_cache.json)
rm .knowledge_cache.json

# Or in custom location
rm /path/to/cache/file.json
```

**3. Rebuild from Scratch:**
```bash
# Clear everything
knowledgebeast clear --yes
knowledgebeast clear-cache --yes

# Re-ingest documents
knowledgebeast add ./documents/ --recursive

# Warm cache
knowledgebeast warm
```

**4. Check for Legacy Pickle Caches:**
```bash
# System automatically migrates pickle to JSON
# Look for warning: "Legacy pickle cache detected"
# No action needed - automatic migration
```

**Prevention:**
- Use JSON cache format (automatic since v0.2.0)
- Regular cache clearing in production
- Monitor cache stats

**Learn more:** [Caching Strategy](architecture/caching-strategy.md) | [Security Guide](deployment/security.md)

---

## Development

### How do I contribute?

**1. Fork & Clone:**
```bash
git clone https://github.com/yourusername/knowledgebeast
cd knowledgebeast
```

**2. Setup Development Environment:**
```bash
make dev
# or
pip install -e ".[dev]"
```

**3. Create Feature Branch:**
```bash
git checkout -b feature/amazing-feature
```

**4. Make Changes:**
- Follow code style guidelines (Black, Ruff, MyPy)
- Add tests for new functionality (aim for 80%+ coverage)
- Update documentation as needed
- Use conventional commits: `feat:`, `fix:`, `docs:`, etc.

**5. Run Tests:**
```bash
make test
make lint
make format
```

**6. Submit Pull Request:**
- Clear description of changes
- Link to related issues
- Include screenshots/examples if applicable

**Learn more:** [CONTRIBUTING.md](../CONTRIBUTING.md) | [Development Setup](contributing/development-setup.md)

### How do I run tests?

**Run All Tests:**
```bash
make test
```

**Run Specific Test Categories:**
```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Performance benchmarks
pytest tests/performance/ -v

# Concurrency tests
pytest tests/concurrency/ -v

# Security tests
pytest tests/security/ -v
```

**With Coverage:**
```bash
pytest --cov=knowledgebeast --cov-report=html
open htmlcov/index.html
```

**Watch Mode (Development):**
```bash
pytest-watch
```

**Performance Benchmarks:**
```bash
pytest tests/performance/test_benchmarks.py -v --benchmark-only
```

**Learn more:** [Testing Guide](contributing/testing.md)

### What's the architecture?

KnowledgeBeast follows a layered architecture:

```
┌─────────────────────────────────────┐
│   Interfaces (CLI, API, Web UI)     │
├─────────────────────────────────────┤
│   Core Engine (Query, Ingestion)    │
├─────────────────────────────────────┤
│   Storage Layer (ChromaDB, Cache)   │
├─────────────────────────────────────┤
│   Foundation (Docling, Embeddings)  │
└─────────────────────────────────────┘
```

**Core Components:**

**1. Knowledge Engine (`KnowledgeBeast`):**
- Document ingestion with Docling
- Vector search with ChromaDB
- Thread-safe LRU caching
- Background heartbeat monitoring

**2. Interfaces:**
- **CLI**: Click-based command-line interface
- **REST API**: FastAPI with authentication & rate limiting
- **Python SDK**: Context manager support
- **Web UI**: Responsive interface at `/ui`

**3. Storage:**
- **ChromaDB**: Vector embeddings and similarity search
- **LRU Cache**: Thread-safe query result caching
- **Metadata**: JSON format, no pickle

**4. Thread Safety:**
- Snapshot pattern for lock optimization
- RLock for main engine
- Lock for LRU cache
- 5-10x concurrent throughput improvement

**Learn more:** [Architecture Overview](architecture/overview.md) | [Core Engine](architecture/core-engine.md) | [CLAUDE.md](../CLAUDE.md)

### How do I add new features?

**1. Plan Your Feature:**
- Check existing issues and discussions
- Create an issue describing the feature
- Get feedback from maintainers

**2. Follow Development Workflow:**
```bash
# Create feature branch
git checkout -b feature/my-feature

# Make changes with tests
# - Add feature code in knowledgebeast/
# - Add tests in tests/
# - Update docs in docs/
```

**3. Implement with Best Practices:**
```python
# Follow existing patterns
# - Type hints for all functions
# - Google-style docstrings
# - Error handling with logging
# - Thread safety if applicable

from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

def my_feature(param: str) -> List[Dict[str, Any]]:
    """Brief description.

    Detailed description of what this does.

    Args:
        param: Description of parameter

    Returns:
        List of dictionaries containing results

    Raises:
        ValueError: If param is invalid
    """
    try:
        # Implementation
        pass
    except Exception as e:
        logger.error(f"Error in my_feature: {e}")
        raise
```

**4. Test Thoroughly:**
```bash
# Add unit tests
pytest tests/unit/test_my_feature.py -v

# Add integration tests if needed
pytest tests/integration/test_my_feature.py -v

# Check coverage
pytest --cov=knowledgebeast --cov-report=term-missing
```

**5. Update Documentation:**
- Add docstrings to code
- Update relevant .md files in docs/
- Add examples to guides
- Update FAQ if applicable

**6. Submit PR:**
- Follow conventional commits
- Include tests and docs
- Link to related issues

**Learn more:** [CONTRIBUTING.md](../CONTRIBUTING.md) | [Code Style Guide](contributing/code-style.md)

---

## Deployment

### How do I deploy to production?

**Production Checklist:**

**1. Security Configuration:**
```bash
# Set strong API keys
export KB_API_KEY="$(openssl rand -hex 32)"

# Configure CORS (no wildcards!)
export KB_ALLOWED_ORIGINS=https://yourdomain.com

# Enable HTTPS enforcement
export KB_HTTPS_ONLY=true

# Set rate limits
export KB_RATE_LIMIT_PER_MINUTE=100
```

**2. Performance Tuning:**
```bash
# Larger cache for production
export KB_CACHE_SIZE=500

# Optimize for your use case
export KB_CHUNK_SIZE=1500
export KB_CHUNK_OVERLAP=300
```

**3. Deployment Options:**

**Docker (Recommended):**
```bash
docker-compose up -d
```

**Systemd Service:**
```bash
sudo systemctl enable knowledgebeast
sudo systemctl start knowledgebeast
```

**Kubernetes:**
```bash
kubectl apply -f k8s/deployment.yaml
```

**4. Monitoring:**
- Enable heartbeat monitoring
- Set up logging aggregation
- Configure alerts for errors
- Monitor cache hit rate

**5. Reverse Proxy:**
- Use nginx/Apache for TLS termination
- Enable security headers
- Configure rate limiting
- Set up HTTPS

**Learn more:** [Production Checklist](deployment/production-checklist.md) | [Docker Deployment](deployment/docker.md) | [Kubernetes](deployment/kubernetes.md)

### How do I use Docker?

**Quick Start:**
```bash
# Using docker-compose (easiest)
docker-compose up -d

# Or build and run manually
docker build -t knowledgebeast .
docker run -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -e KB_API_KEY="your_key" \
  knowledgebeast
```

**Production Docker Compose:**
```yaml
version: '3.8'
services:
  knowledgebeast:
    image: knowledgebeast:latest
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./cache:/app/cache
    environment:
      - KB_API_KEY=${KB_API_KEY}
      - KB_ALLOWED_ORIGINS=https://yourdomain.com
      - KB_HTTPS_ONLY=true
      - KB_CACHE_SIZE=500
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

**Useful Commands:**
```bash
# View logs
docker-compose logs -f

# Restart service
docker-compose restart

# Run health check
docker-compose exec knowledgebeast knowledgebeast health

# Access shell
docker-compose exec knowledgebeast /bin/bash
```

**Learn more:** [Docker Deployment](deployment/docker.md) | [DOCKER.md](DOCKER.md)

### How do I scale it?

**Vertical Scaling (Single Instance):**
```bash
# Increase resources
# - More RAM → Larger cache (500-1000 entries)
# - More CPU cores → Better concurrent throughput
# - SSD storage → Faster I/O

# Optimize configuration
export KB_CACHE_SIZE=1000
export KB_CHUNK_SIZE=1500
```

**Horizontal Scaling (Multiple Instances):**

**1. Load Balancer Setup:**
```nginx
upstream knowledgebeast {
    least_conn;  # Use least connections
    server kb1:8000;
    server kb2:8000;
    server kb3:8000;
}

server {
    listen 443 ssl;
    location / {
        proxy_pass http://knowledgebeast;
    }
}
```

**2. Shared Storage:**
```yaml
# docker-compose.yml
services:
  kb1:
    volumes:
      - shared-data:/app/data
  kb2:
    volumes:
      - shared-data:/app/data

volumes:
  shared-data:
    driver: nfs
```

**3. Kubernetes Deployment:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: knowledgebeast
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: knowledgebeast
        image: knowledgebeast:latest
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
```

**Scaling Considerations:**
- Cache is per-instance (not shared)
- ChromaDB data should be on shared volume
- Use consistent hashing for query routing
- Monitor per-instance metrics

**Learn more:** [Kubernetes Deployment](deployment/kubernetes.md) | [Performance Guide](architecture/performance.md)

### What about monitoring?

**Built-in Monitoring:**

**1. Heartbeat Service:**
```bash
# Start background monitoring
knowledgebeast heartbeat start --interval 300

# Check status
knowledgebeast heartbeat status

# Python API
kb.start_heartbeat(interval=300)
status = kb.get_heartbeat_status()
```

**2. Statistics API:**
```python
stats = kb.get_stats()
print(f"Documents: {stats['total_documents']}")
print(f"Cache hit rate: {stats['cache_stats']['hit_rate']:.2%}")
print(f"Heartbeat running: {stats['heartbeat_running']}")
```

**3. Health Checks:**
```bash
# CLI health check
knowledgebeast health

# API endpoint
curl http://localhost:8000/api/v1/health \
  -H "X-API-Key: your_key"
```

**External Monitoring:**

**Prometheus Metrics (Example):**
```python
from prometheus_client import Counter, Histogram, Gauge

query_counter = Counter('kb_queries_total', 'Total queries')
query_latency = Histogram('kb_query_duration_seconds', 'Query latency')
cache_hit_rate = Gauge('kb_cache_hit_rate', 'Cache hit rate')

# Track metrics
@query_latency.time()
def query_with_metrics(kb, query):
    query_counter.inc()
    results = kb.query(query)
    stats = kb.get_stats()
    cache_hit_rate.set(stats['cache_stats']['hit_rate'])
    return results
```

**Key Metrics to Monitor:**
- Query latency (P50, P95, P99)
- Cache hit rate (aim for >80%)
- Error rate
- API rate limits
- Memory usage
- Disk usage

**Learn more:** [Production Checklist](deployment/production-checklist.md)

---

## Additional Resources

**Documentation:**
- [README](../README.md) - Project overview
- [Getting Started](getting-started/quickstart.md) - Quick start guide
- [Architecture](architecture/overview.md) - System architecture
- [API Reference](api-reference/python-sdk.md) - Complete API docs

**Guides:**
- [Python API](guides/python-api.md) - Python SDK guide
- [CLI Usage](guides/cli-usage.md) - Command-line interface
- [REST API](guides/rest-api.md) - REST API reference
- [Docker](guides/docker-deployment.md) - Docker deployment

**Community:**
- [GitHub Issues](https://github.com/yourusername/knowledgebeast/issues) - Bug reports & feature requests
- [Discussions](https://github.com/yourusername/knowledgebeast/discussions) - Questions & ideas
- [Contributing](../CONTRIBUTING.md) - How to contribute

**Support:**
- Review documentation in `docs/` directory
- Search or create an issue on GitHub
- Check the discussions forum

---

**Last Updated:** October 6, 2025
**Version:** 1.0.0

*Have a question not answered here? [Open an issue](https://github.com/yourusername/knowledgebeast/issues) and we'll add it to the FAQ!*
