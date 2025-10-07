# KnowledgeBeast Troubleshooting Guide

**Version:** 0.1.0
**Last Updated:** October 6, 2025

This comprehensive guide helps you diagnose and resolve common issues in KnowledgeBeast. Each section includes symptoms, root causes, solutions, and prevention strategies.

---

## Table of Contents

1. [Installation Issues](#installation-issues)
2. [Configuration Issues](#configuration-issues)
3. [API Issues](#api-issues)
4. [Performance Issues](#performance-issues)
5. [Data Issues](#data-issues)
6. [Testing Issues](#testing-issues)
7. [Docker Issues](#docker-issues)
8. [Diagnostics Commands](#diagnostics-commands)
9. [Getting Help](#getting-help)

---

## Installation Issues

### 1.1 Dependency Conflicts

**Symptoms:**
- `pip install` fails with conflict errors
- Import errors for `docling`, `fastapi`, or other dependencies
- Version mismatch warnings

**Root Cause:**
- Conflicting package versions in environment
- Python version incompatibility (requires Python 3.11+)
- Missing system dependencies for docling

**Solution:**
```bash
# Check Python version (must be 3.11+)
python --version

# Create clean virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip

# Install from requirements
pip install -r requirements.txt

# Or install with development dependencies
pip install -e ".[dev]"
```

**Prevention:**
- Always use virtual environments
- Pin exact versions in production (use `requirements.txt`)
- Run `pip check` after installation to verify dependencies

### 1.2 Docling Installation Failures

**Symptoms:**
- `ImportError: No module named 'docling'`
- Docling import succeeds but conversion fails
- Warning: "Docling not available, using fallback converter"

**Root Cause:**
- Docling has complex dependencies (PyTorch, transformers, etc.)
- System architecture incompatibility (M1/M2 Macs, ARM)
- Missing C++ compiler for native extensions

**Solution:**
```bash
# Install docling with dependencies
pip install docling>=2.5.5

# For Apple Silicon (M1/M2):
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cpu

# Verify installation
python -c "from docling.document_converter import DocumentConverter; print('Docling OK')"

# If still failing, use fallback converter (automatic)
# KnowledgeBeast will fall back to simple markdown reader
```

**Prevention:**
- Document system requirements in deployment docs
- Use Docker for consistent environments
- Test in staging environment before production

### 1.3 Missing CLI Command

**Symptoms:**
- `knowledgebeast: command not found`
- CLI works in development but not after install

**Root Cause:**
- Package not installed in editable mode
- Virtual environment not activated
- PATH not configured correctly

**Solution:**
```bash
# Install in editable mode
pip install -e .

# Verify installation
which knowledgebeast
knowledgebeast --version

# If still not found, use module syntax
python -m knowledgebeast.cli.commands --help
```

**Prevention:**
- Always activate virtual environment before running commands
- Add `venv/bin` to PATH or use full path to binary

---

## Configuration Issues

### 2.1 Knowledge Directory Not Found

**Symptoms:**
- Warning: "Skipping non-existent directory: /path/to/kb"
- Zero documents loaded after ingestion
- Empty query results

**Root Cause:**
- Knowledge base directory doesn't exist
- Incorrect path in configuration
- Permission issues accessing directory

**Solution:**
```bash
# Check if directory exists
ls -la /path/to/knowledge-base

# Create directory if missing
mkdir -p knowledge-base

# Add sample documents
echo "# Test Document" > knowledge-base/test.md

# Verify with health check
knowledgebeast health --data-dir ./data

# Or check configuration
python -c "from knowledgebeast.core.config import KnowledgeBeastConfig; c = KnowledgeBeastConfig(); c.print_config()"
```

**Environment Variable Override:**
```bash
# Set custom knowledge directory
export KB_KNOWLEDGE_DIRS="/path/to/kb1,/path/to/kb2"
knowledgebeast query "test"
```

**Prevention:**
- Use absolute paths in production
- Validate paths in configuration
- Add health checks to deployment scripts

### 2.2 Cache File Permission Errors

**Symptoms:**
- `PermissionError: [Errno 13] Permission denied: '.knowledge_cache.pkl'`
- Cache not being saved/loaded
- Slow performance on repeated queries

**Root Cause:**
- Insufficient permissions to write cache file
- Cache directory doesn't exist
- File locked by another process

**Solution:**
```bash
# Check cache file permissions
ls -la .knowledge_cache.pkl

# Fix permissions
chmod 644 .knowledge_cache.pkl

# Remove corrupted cache
rm .knowledge_cache.pkl

# Clear cache via CLI
knowledgebeast clear-cache --yes

# Specify custom cache location with write permissions
export KB_CACHE_FILE="/tmp/kb_cache.pkl"
```

**Prevention:**
- Store cache in user-writable directory
- Use `/tmp` or `~/.cache` for cache files
- Add cache directory to `.gitignore`

### 2.3 Invalid Configuration Values

**Symptoms:**
- `ValueError: max_cache_size must be positive`
- `ValueError: heartbeat_interval must be at least 10 seconds`
- `ValueError: At least one knowledge directory must be specified`

**Root Cause:**
- Invalid values in environment variables
- Configuration validation failing
- Type conversion errors (string to int)

**Solution:**
```python
# Valid configuration example
from knowledgebeast.core.config import KnowledgeBeastConfig

config = KnowledgeBeastConfig(
    knowledge_dirs=[Path("knowledge-base")],
    max_cache_size=100,  # Must be positive
    heartbeat_interval=300,  # Must be >= 10
    max_workers=4  # Must be positive
)

# Validate before use
config.print_config()
```

**Environment Variables:**
```bash
# Valid values
export KB_MAX_CACHE_SIZE="100"
export KB_HEARTBEAT_INTERVAL="300"
export KB_MAX_WORKERS="4"

# Invalid (will raise errors)
export KB_MAX_CACHE_SIZE="0"  # Must be > 0
export KB_HEARTBEAT_INTERVAL="5"  # Must be >= 10
```

**Prevention:**
- Validate configuration on startup
- Use type hints and Pydantic models
- Add unit tests for configuration validation

---

## API Issues

### 3.1 Authentication Failures

**Symptoms:**
- `401 Unauthorized: Invalid API key`
- All API requests rejected
- "WWW-Authenticate: ApiKey" header in response

**Root Cause:**
- Missing or invalid API key
- API key not configured
- Rate limit exceeded

**Solution:**
```bash
# Check if authentication is enabled
curl http://localhost:8000/health

# Set API key (if authentication enabled)
export KB_API_KEY="your-api-key-here"

# Test with API key
curl -H "X-API-Key: your-api-key" http://localhost:8000/health

# Disable authentication for development
export KB_DISABLE_AUTH="true"
knowledgebeast serve
```

**Rate Limit Error (429):**
```bash
# Rate limit exceeded response includes headers:
# X-RateLimit-Limit: 60
# X-RateLimit-Remaining: 0
# X-RateLimit-Reset: 1696521600

# Wait for rate limit window to reset (60 seconds default)
# Or increase limit in configuration
```

**Prevention:**
- Store API keys in environment variables, not code
- Use API key management system in production
- Implement proper rate limiting
- Monitor authentication failures

### 3.2 CORS Errors

**Symptoms:**
- Browser console: "Access-Control-Allow-Origin" error
- Frontend cannot connect to API
- OPTIONS requests failing

**Root Cause:**
- CORS not configured for frontend origin
- Missing CORS middleware
- Incorrect origin configuration

**Solution:**
```python
# Add CORS middleware in knowledgebeast/api/app.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://your-frontend.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Development Mode (Allow All):**
```python
# WARNING: Only for development!
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Prevention:**
- Configure CORS from environment variables
- Use specific origins in production
- Test with actual frontend early

### 3.3 Request Timeout

**Symptoms:**
- `504 Gateway Timeout`
- Requests hang indefinitely
- "Connection timeout" errors

**Root Cause:**
- Large document ingestion taking too long
- Query on unwarmed cache
- Blocking operations in async endpoints
- Insufficient server resources

**Solution:**
```bash
# Increase timeout in uvicorn
uvicorn knowledgebeast.api.app:app --timeout-keep-alive 120

# Pre-warm cache before queries
curl -X POST http://localhost:8000/warm

# Use pagination for large result sets
curl -X POST http://localhost:8000/query/paginated \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "page": 1, "page_size": 10}'

# Check server resources
htop  # CPU and memory usage
```

**Prevention:**
- Always warm cache on startup
- Use async operations for long-running tasks
- Implement request timeouts in client
- Monitor server performance

### 3.4 500 Internal Server Error

**Symptoms:**
- Generic 500 error
- Cryptic error message
- API crashes

**Root Cause:**
- Unhandled exception in endpoint
- Database/cache corruption
- Out of memory

**Solution:**
```bash
# Check server logs
tail -f /var/log/knowledgebeast/error.log

# Enable debug mode
export KB_DEBUG="true"
uvicorn knowledgebeast.api.app:app --reload --log-level debug

# Check memory usage
free -h

# Restart with clean state
rm .knowledge_cache.pkl
knowledgebeast serve
```

**Common Error Patterns:**
```
# ValueError: Search terms cannot be empty
# → Client sent empty query string

# FileNotFoundError: File not found
# → Document path invalid in ingest request

# MemoryError
# → Cache too large or memory leak
```

**Prevention:**
- Add comprehensive error handling
- Log all exceptions with stack traces
- Monitor memory usage
- Use request validation (Pydantic)

---

## Performance Issues

### 4.1 Slow Queries

**Symptoms:**
- Query latency > 100ms (P99)
- First query very slow
- Progressive slowdown over time

**Root Cause:**
- Cache not warmed
- Large document index
- Lock contention (poor concurrency)
- Memory fragmentation

**Solution:**
```bash
# Warm up cache on startup
knowledgebeast warm

# Check performance metrics
knowledgebeast benchmark --output report.html

# Monitor query latency
curl http://localhost:8000/stats | jq '.cache_hit_rate'

# Clear cache and rebuild
knowledgebeast clear-cache --yes
knowledgebeast warm
```

**Configuration Optimization:**
```python
config = KnowledgeBeastConfig(
    max_cache_size=200,  # Increase cache size
    auto_warm=True,  # Always warm on startup
    max_workers=8,  # More workers for ingestion
)
```

**Check Performance Targets:**
```
✓ P99 Query Latency < 100ms
✓ P99 Cached Query < 10ms
✓ Throughput > 500 queries/sec (10 workers)
✓ Cache Hit Ratio > 90%
```

**Prevention:**
- Always use cache warming
- Monitor performance metrics
- Use the snapshot pattern (see CLAUDE.md)
- Profile slow queries

### 4.2 High Memory Usage

**Symptoms:**
- Memory usage > 1GB
- Out of memory errors
- System swap thrashing

**Root Cause:**
- Large cache not evicting
- Memory leak in long-running process
- Too many concurrent requests
- Large documents not chunked

**Solution:**
```bash
# Check memory usage
ps aux | grep knowledgebeast

# Use memory profiling
pip install memory-profiler
python -m memory_profiler -m knowledgebeast.api.app

# Reduce cache size
export KB_MAX_CACHE_SIZE="50"

# Limit concurrent workers
export KB_MAX_WORKERS="2"

# Restart service periodically
systemctl restart knowledgebeast
```

**Monitor Memory:**
```python
import psutil

def check_memory():
    process = psutil.Process()
    mem_mb = process.memory_info().rss / 1024 / 1024
    if mem_mb > 1000:
        logger.warning(f"High memory usage: {mem_mb:.1f}MB")
```

**Prevention:**
- Set memory limits in Docker/systemd
- Clear cache periodically
- Use LRU eviction (already implemented)
- Profile memory in CI/CD

### 4.3 Thread Safety Issues

**Symptoms:**
- Race conditions
- Inconsistent query results
- "Cache size exceeds capacity" errors
- Stats don't add up (hits + misses != queries)

**Root Cause:**
- Missing locks on shared data
- Lock held during I/O operations
- Improper lock ordering

**Solution:**
```python
# KnowledgeBeast uses proper locking (see CLAUDE.md)
# But if you're extending, ensure thread safety:

from threading import Lock

class MyExtension:
    def __init__(self):
        self._lock = Lock()
        self.data = {}

    def safe_operation(self):
        with self._lock:
            # All shared data access protected
            return self.data.copy()  # Return copy, not reference
```

**Testing Thread Safety:**
```bash
# Run concurrency tests
pytest tests/concurrency/test_thread_safety.py -v

# Stress test
python tests/performance/stress_test.py --workers 50 --duration 60
```

**Prevention:**
- Follow locking best practices in CLAUDE.md
- Use thread-safe components (LRUCache)
- Test with concurrent load
- Minimize lock scope

### 4.4 Lock Contention

**Symptoms:**
- Throughput drops with concurrent load
- Latency spikes under load
- Poor scaling with workers

**Root Cause:**
- Lock held during long operations
- Single global lock (not using snapshot pattern)

**Solution:**
```python
# Use snapshot pattern (already implemented in KnowledgeBase.query)
# This allows concurrent queries without blocking

# BAD (don't do this):
with self._lock:
    results = self.search(terms)  # Holds lock during search
    return results

# GOOD (already implemented):
with self._lock:
    snapshot = dict(self.index)  # Quick snapshot

results = self.search(snapshot)  # Search without lock
return results
```

**Benchmark Improvements:**
- 5-10x throughput improvement with snapshot pattern
- Lock held < 1ms vs 50-100ms
- Zero data corruption

**Prevention:**
- Use snapshot pattern for read-heavy operations
- Minimize lock scope
- Benchmark concurrency regularly

---

## Data Issues

### 5.1 Cache Corruption

**Symptoms:**
- `json.JSONDecodeError` when loading cache
- "Cache file invalid or corrupt" warning
- Queries return stale results

**Root Cause:**
- Process killed during cache write
- Disk full during save
- Concurrent writes to cache file

**Solution:**
```bash
# Remove corrupted cache
rm .knowledge_cache.pkl

# Rebuild index
knowledgebeast warm

# Check disk space
df -h

# Verify cache integrity
python -c "
import json
with open('.knowledge_cache.pkl', 'r') as f:
    data = json.load(f)
    print(f'Documents: {len(data[\"documents\"])}')
    print(f'Terms: {len(data[\"index\"])}')
"
```

**Atomic Cache Writes (already implemented):**
```python
# KnowledgeBeast uses atomic writes:
# 1. Write to .tmp file
# 2. Atomic rename to final location
# This prevents corruption on crash
```

**Prevention:**
- Use atomic writes (already implemented)
- Monitor disk space
- Regular cache validation
- Backup cache files

### 5.2 Stale Index

**Symptoms:**
- New documents not appearing in queries
- Deleted documents still showing up
- File count mismatch in stats

**Root Cause:**
- Cache not invalidated after file changes
- Staleness detection not working
- Manual file changes bypassing ingestion

**Solution:**
```bash
# Force rebuild index
knowledgebeast warm --force-rebuild

# Or via API
curl -X POST http://localhost:8000/warm \
  -H "Content-Type: application/json" \
  -d '{"force_rebuild": true}'

# Check cache staleness
python -c "
from pathlib import Path
from knowledgebeast.core.engine import KnowledgeBase
from knowledgebeast.core.config import KnowledgeBeastConfig

config = KnowledgeBeastConfig()
kb = KnowledgeBase(config)
cache_path = Path(config.cache_file)
is_stale = kb._is_cache_stale(cache_path)
print(f'Cache is stale: {is_stale}')
"
```

**Automatic Staleness Detection:**
- Checks file modification times
- Detects file count changes
- Rebuilds automatically on startup

**Prevention:**
- Use ingestion API for all changes
- Monitor file changes (inotify)
- Schedule periodic rebuilds
- Use `auto_warm=True` (default)

### 5.3 File Permission Issues

**Symptoms:**
- `PermissionError: [Errno 13]` during ingestion
- Some documents missing after ingestion
- "Failed to ingest" errors

**Root Cause:**
- Insufficient permissions to read source files
- Files owned by different user
- SELinux or AppArmor restrictions

**Solution:**
```bash
# Check file permissions
ls -la knowledge-base/

# Fix permissions
chmod -R 644 knowledge-base/*.md
chmod 755 knowledge-base/

# Check user ownership
ls -l knowledge-base/

# Change ownership if needed
sudo chown -R knowledgebeast:knowledgebeast knowledge-base/

# Run as correct user
sudo -u knowledgebeast knowledgebeast query "test"
```

**Docker Permission Issues:**
```bash
# Use user namespace in Docker
docker run --user 1000:1000 knowledgebeast

# Or fix ownership in Dockerfile
RUN chown -R knowledgebeast:knowledgebeast /app/knowledge-base
```

**Prevention:**
- Use consistent user/group across environments
- Document permission requirements
- Add permission checks to health endpoint
- Use Docker volumes with correct permissions

### 5.4 Empty Query Results

**Symptoms:**
- All queries return zero results
- Documents loaded but no matches
- Index appears empty

**Root Cause:**
- Search terms not matching indexed terms
- Case sensitivity issues
- Empty documents or invalid markdown
- Converter failing silently

**Solution:**
```bash
# Check index statistics
knowledgebeast stats

# Verify documents loaded
python -c "
from knowledgebeast.core.engine import KnowledgeBase
from knowledgebeast.core.config import KnowledgeBeastConfig

kb = KnowledgeBase(KnowledgeBeastConfig())
kb.ingest_all()
print(f'Documents: {len(kb.documents)}')
print(f'Terms: {len(kb.index)}')
print(f'Sample terms: {list(kb.index.keys())[:10]}')
"

# Try simple query
knowledgebeast query "the" --no-cache

# Check document content
python -c "
from knowledgebeast.core.engine import KnowledgeBase
from knowledgebeast.core.config import KnowledgeBeastConfig

kb = KnowledgeBase(KnowledgeBeastConfig())
kb.ingest_all()
for doc_id, doc in list(kb.documents.items())[:3]:
    print(f'{doc_id}: {doc[\"content\"][:100]}...')
"
```

**Prevention:**
- Validate documents during ingestion
- Log failed conversions
- Add sample queries to warming
- Test with known good documents

---

## Testing Issues

### 6.1 Test Failures

**Symptoms:**
- Tests fail in CI but pass locally
- Intermittent test failures
- "Fixture not found" errors

**Root Cause:**
- Environment differences
- Timing issues (race conditions)
- Missing test dependencies
- Stale test data

**Solution:**
```bash
# Install test dependencies
pip install -e ".[dev]"

# Run with verbose output
pytest -v --tb=short

# Run specific test
pytest tests/core/test_engine.py::TestQuerying::test_query_basic -v

# Clean up test artifacts
rm -rf .pytest_cache
rm -rf tests/__pycache__

# Run with fresh state
pytest --cache-clear
```

**CI/CD Configuration:**
```yaml
# .github/workflows/test.yml
- name: Run tests
  run: |
    pip install -e ".[dev]"
    pytest --cov=knowledgebeast --cov-report=xml
```

**Prevention:**
- Use fixtures for test isolation
- Mock external dependencies
- Add retries for timing-sensitive tests
- Clean up test data in teardown

### 6.2 Mock Issues

**Symptoms:**
- Mocks not being called
- "Mock has no attribute" errors
- Unexpected method calls

**Root Cause:**
- Incorrect mock path
- Mock not properly configured
- Import order issues

**Solution:**
```python
# Correct mock path (where object is used, not defined)
@patch('knowledgebeast.cli.commands.KnowledgeBase')
def test_query(mock_kb_class):
    mock_kb = Mock()
    mock_kb_class.return_value = mock_kb
    # Now test will use mock

# Configure mock properly
mock_kb = Mock()
mock_kb.query.return_value = [('doc1', {'content': 'test'})]
mock_kb.__enter__ = Mock(return_value=mock_kb)
mock_kb.__exit__ = Mock(return_value=False)

# Verify calls
mock_kb.query.assert_called_once_with('test', use_cache=True)
```

**Prevention:**
- Use `patch` at import location
- Configure all required methods
- Verify mock usage in tests
- Use `spec=True` for strict mocking

### 6.3 Fixture Errors

**Symptoms:**
- `pytest.fixture` not found
- Fixture scope issues
- Teardown not running

**Root Cause:**
- Incorrect fixture usage
- Missing conftest.py
- Scope mismatch

**Solution:**
```python
# Define fixture in conftest.py
@pytest.fixture
def kb_config():
    """Provide test configuration."""
    return KnowledgeBeastConfig(
        knowledge_dirs=[Path("test_kb")],
        auto_warm=False,
        verbose=False
    )

# Use fixture in test
def test_something(kb_config):
    kb = KnowledgeBase(kb_config)
    assert kb.config == kb_config

# Use different scopes
@pytest.fixture(scope="session")  # Once per test session
@pytest.fixture(scope="module")   # Once per module
@pytest.fixture(scope="function") # Once per test (default)
```

**Prevention:**
- Place common fixtures in conftest.py
- Use appropriate scope
- Document fixture dependencies
- Add fixture teardown

---

## Docker Issues

### 7.1 Container Startup Failures

**Symptoms:**
- Container exits immediately
- "Error: No such file or directory"
- Permission denied errors

**Root Cause:**
- Missing files in container
- Incorrect working directory
- Permission issues
- Port conflicts

**Solution:**
```bash
# Check container logs
docker logs knowledgebeast

# Run with interactive shell
docker run -it knowledgebeast /bin/bash

# Check file structure
docker exec knowledgebeast ls -la /app

# Fix permissions in Dockerfile
RUN chown -R knowledgebeast:knowledgebeast /app

# Use correct working directory
WORKDIR /app
```

**Common Dockerfile Issues:**
```dockerfile
# BAD: Files not copied
FROM python:3.11
CMD ["knowledgebeast", "serve"]  # Files missing!

# GOOD: Copy files first
FROM python:3.11
COPY . /app
WORKDIR /app
RUN pip install -e .
CMD ["knowledgebeast", "serve"]
```

**Prevention:**
- Test Docker builds locally
- Use multi-stage builds
- Add health checks to Dockerfile
- Document required volumes

### 7.2 Network Issues

**Symptoms:**
- Cannot connect to container
- "Connection refused" from host
- Services cannot reach API

**Root Cause:**
- Port not published
- Wrong host binding (127.0.0.1 vs 0.0.0.0)
- Firewall rules
- Docker network misconfiguration

**Solution:**
```bash
# Publish ports correctly
docker run -p 8000:8000 knowledgebeast

# Bind to all interfaces in container
knowledgebeast serve --host 0.0.0.0 --port 8000

# Check port is listening
docker exec knowledgebeast netstat -tlnp | grep 8000

# Test from host
curl http://localhost:8000/health

# Check Docker network
docker network ls
docker network inspect bridge
```

**Docker Compose:**
```yaml
services:
  knowledgebeast:
    ports:
      - "8000:8000"
    environment:
      - KB_HOST=0.0.0.0
```

**Prevention:**
- Always bind to 0.0.0.0 in containers
- Use docker-compose for multi-service setups
- Test networking in CI
- Document port mappings

### 7.3 Volume Mount Issues

**Symptoms:**
- Knowledge base empty in container
- Changes not persisted
- "No such file or directory" in mounted path

**Root Cause:**
- Volume not mounted
- Incorrect mount path
- Permission issues on volume
- SELinux context issues

**Solution:**
```bash
# Mount volume correctly
docker run -v $(pwd)/knowledge-base:/app/knowledge-base knowledgebeast

# Check mount inside container
docker exec knowledgebeast ls -la /app/knowledge-base

# Fix SELinux context (Fedora/RHEL)
docker run -v $(pwd)/knowledge-base:/app/knowledge-base:Z knowledgebeast

# Use named volume
docker volume create kb-data
docker run -v kb-data:/app/knowledge-base knowledgebeast

# Check volume contents
docker volume inspect kb-data
```

**Docker Compose:**
```yaml
services:
  knowledgebeast:
    volumes:
      - ./knowledge-base:/app/knowledge-base:ro  # Read-only
      - kb-cache:/app/.cache  # Named volume for cache

volumes:
  kb-cache:
```

**Prevention:**
- Use named volumes for persistence
- Document volume requirements
- Test with mounted volumes
- Set correct permissions in entrypoint

### 7.4 Build Failures

**Symptoms:**
- `docker build` fails
- "No matching distribution found"
- Build takes very long

**Root Cause:**
- Dependency installation failures
- Network issues during build
- Large context size
- Missing .dockerignore

**Solution:**
```bash
# Add .dockerignore
cat > .dockerignore <<EOF
venv/
__pycache__/
*.pyc
.git/
.pytest_cache/
*.egg-info/
dist/
build/
EOF

# Use build cache
docker build -t knowledgebeast .

# Build with no cache
docker build --no-cache -t knowledgebeast .

# Use BuildKit for better caching
DOCKER_BUILDKIT=1 docker build -t knowledgebeast .

# Check build context size
docker build --progress=plain -t knowledgebeast . 2>&1 | grep "transferring context"
```

**Multi-stage Build:**
```dockerfile
# Stage 1: Build
FROM python:3.11 AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim
COPY --from=builder /root/.local /root/.local
COPY . /app
WORKDIR /app
CMD ["knowledgebeast", "serve"]
```

**Prevention:**
- Use .dockerignore
- Leverage layer caching
- Pin base image versions
- Use multi-stage builds

---

## Diagnostics Commands

### Health Check Endpoints

```bash
# Basic health check
curl http://localhost:8000/health

# Expected response
{
  "status": "healthy",
  "version": "0.1.0",
  "kb_initialized": true,
  "timestamp": "2025-10-06T12:00:00Z"
}

# Get detailed statistics
curl http://localhost:8000/stats

# Check heartbeat status
curl http://localhost:8000/heartbeat/status
```

### CLI Diagnostics

```bash
# Run health check
knowledgebeast health

# Show configuration
python -c "from knowledgebeast.core.config import KnowledgeBeastConfig; KnowledgeBeastConfig().print_config()"

# Show statistics
knowledgebeast stats --detailed

# Test query
knowledgebeast query "test" --no-cache

# Benchmark performance
knowledgebeast benchmark --output report.txt
```

### Log File Locations

```bash
# Default log location
~/.knowledgebeast/logs/knowledgebeast.log

# Docker logs
docker logs knowledgebeast

# Systemd logs
journalctl -u knowledgebeast -f

# Application logs (in code)
import logging
logger = logging.getLogger("knowledgebeast")
# Check logger.handlers for active handlers
```

### Debug Mode Activation

```bash
# Enable debug logging (CLI)
knowledgebeast --verbose query "test"

# Enable debug logging (API)
export KB_LOG_LEVEL="DEBUG"
uvicorn knowledgebeast.api.app:app --log-level debug

# Python logging configuration
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Performance Profiling

```bash
# Run benchmark suite
knowledgebeast benchmark --output report.html
open report.html  # View in browser

# Profile specific endpoint
pip install py-spy
py-spy record -o profile.svg -- python -m uvicorn knowledgebeast.api.app:app

# Memory profiling
pip install memory-profiler
python -m memory_profiler -m knowledgebeast.cli.commands query "test"

# CPU profiling
python -m cProfile -o profile.stats -m knowledgebeast.cli.commands query "test"
python -c "import pstats; pstats.Stats('profile.stats').sort_stats('cumulative').print_stats(20)"
```

### Database/Cache Inspection

```bash
# Inspect cache contents
python -c "
import json
with open('.knowledge_cache.pkl', 'r') as f:
    cache = json.load(f)
    print(f'Documents: {len(cache[\"documents\"])}')
    print(f'Index terms: {len(cache[\"index\"])}')
    print(f'Sample documents: {list(cache[\"documents\"].keys())[:5]}')
"

# Check cache size
du -h .knowledge_cache.pkl

# Validate cache integrity
python -c "
from knowledgebeast.core.engine import KnowledgeBase
from knowledgebeast.core.config import KnowledgeBeastConfig
kb = KnowledgeBase(KnowledgeBeastConfig())
stats = kb.get_stats()
print(f'Documents: {stats[\"documents\"]}')
print(f'Terms: {stats[\"terms\"]}')
print(f'Cache hit rate: {stats[\"cache_hit_rate\"]}')
"
```

---

## Getting Help

### Before Opening an Issue

1. **Check this troubleshooting guide** for your specific issue
2. **Search existing issues** on GitHub
3. **Gather diagnostic information**:
   ```bash
   knowledgebeast --version
   knowledgebeast health
   python --version
   pip list | grep -E "(docling|fastapi|knowledgebeast)"
   ```

### Opening an Issue

Include the following information:

```markdown
**Environment:**
- KnowledgeBeast version: 0.1.0
- Python version: 3.11.5
- OS: macOS 14.0 / Ubuntu 22.04 / Windows 11
- Docker version (if applicable): 24.0.5

**Description:**
[Clear description of the issue]

**Steps to Reproduce:**
1. Step one
2. Step two
3. Step three

**Expected Behavior:**
[What you expected to happen]

**Actual Behavior:**
[What actually happened]

**Logs:**
```
[Paste relevant logs here]
```

**Configuration:**
```yaml
[Paste configuration or environment variables]
```
```

### Community Resources

- **Documentation**: https://github.com/PerformanceSuite/KnowledgeBeast/docs
- **Issue Tracker**: https://github.com/PerformanceSuite/KnowledgeBeast/issues
- **Discussions**: https://github.com/PerformanceSuite/KnowledgeBeast/discussions
- **Discord**: [Coming soon]

### Commercial Support

For priority support, consulting, or custom development, contact: [support@knowledgebeast.com]

---

## Quick Reference

### Most Critical Issues

| Issue | Quick Fix | Reference |
|-------|-----------|-----------|
| Empty queries | `knowledgebeast warm` | [5.4](#54-empty-query-results) |
| Slow performance | Check cache warming | [4.1](#41-slow-queries) |
| Permission errors | Fix cache file permissions | [2.2](#22-cache-file-permission-errors) |
| API 401 errors | Set `KB_API_KEY` or disable auth | [3.1](#31-authentication-failures) |
| Cache corruption | Delete cache and rebuild | [5.1](#51-cache-corruption) |

### Emergency Commands

```bash
# Nuclear option: Reset everything
rm .knowledge_cache.pkl
knowledgebeast clear-cache --yes
knowledgebeast warm

# Quick health check
knowledgebeast health && echo "✓ System OK" || echo "✗ System has issues"

# Restart service
docker restart knowledgebeast
# OR
systemctl restart knowledgebeast

# Check if service is responding
curl -f http://localhost:8000/health || echo "Service down"
```

---

**Last Updated:** October 6, 2025
**Version:** 0.1.0
**Maintainer:** KnowledgeBeast Team
