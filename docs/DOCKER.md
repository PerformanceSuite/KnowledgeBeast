# KnowledgeBeast Docker Guide

Complete guide for running KnowledgeBeast in Docker containers for both development and production environments.

## Table of Contents

- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Production Deployment](#production-deployment)
- [Development Setup](#development-setup)
- [Environment Variables](#environment-variables)
- [Volume Management](#volume-management)
- [Scaling and Performance](#scaling-and-performance)
- [Security Best Practices](#security-best-practices)
- [Troubleshooting](#troubleshooting)
- [Advanced Usage](#advanced-usage)

## Quick Start

### 1. Copy Environment File

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 2. Build and Run

**Production:**
```bash
make docker-build
make docker-run
```

**Development (with hot reload):**
```bash
make docker-dev
```

### 3. Access the API

- API Documentation: http://localhost:8000/docs
- API Root: http://localhost:8000/
- Health Check: http://localhost:8000/api/v1/health

### 4. View Logs

```bash
# All services
make docker-logs

# API only
make docker-logs-api

# Redis only
make docker-logs-redis
```

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- 2GB available RAM
- 5GB available disk space

Verify installation:
```bash
docker --version
docker-compose --version
```

## Production Deployment

### Architecture

The production setup includes:
- **KnowledgeBeast API**: Main FastAPI application (port 8000)
- **Redis**: Caching layer (port 6379, optional)
- **Volumes**: Persistent storage for knowledge base data

### Build Production Image

```bash
# Build multi-stage optimized image
docker build -t knowledgebeast:latest .

# Or use make
make docker-build
```

The multi-stage Dockerfile:
- **Builder stage**: Compiles dependencies and wheels
- **Runtime stage**: Minimal production image (~400MB)
- Non-root user for security
- Tini for proper signal handling
- Health checks for orchestration

### Run Production Stack

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### Production Configuration

Edit `.env` file:

```env
# Production settings
KB_LOG_LEVEL=WARNING
KB_DEBUG=false
KB_API_WORKERS=4
KB_REDIS_ENABLED=true
```

### Health Monitoring

Check container health:
```bash
# Using make
make docker-health

# Direct docker command
docker inspect --format='{{.State.Health.Status}}' knowledgebeast
```

Health check endpoint:
```bash
curl http://localhost:8000/api/v1/health
```

## Development Setup

### Development Mode Features

- Hot reload on code changes
- Development dependencies (pytest, debugpy, ipython)
- Source code mounted as volumes
- Debug port exposed (5678)
- Verbose logging (DEBUG level)

### Start Development Environment

```bash
# Interactive mode (foreground)
make docker-dev

# Daemon mode (background)
make docker-dev-daemon

# View logs
make docker-dev-logs
```

### Development Dockerfile

Uses `Dockerfile.dev` with:
- All dev dependencies installed
- Editable package installation
- No build optimization (faster rebuilds)
- Runs as root for easier file permissions

### Debugging

1. Install debugpy in container (already included)
2. Add breakpoint in code:
   ```python
   import debugpy
   debugpy.listen(("0.0.0.0", 5678))
   debugpy.wait_for_client()
   ```
3. Connect from VS Code or PyCharm to `localhost:5678`

## Environment Variables

### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `KB_DATA_DIR` | `/data` | Knowledge base data directory |
| `KB_CONFIG_DIR` | `/config` | Configuration directory |
| `KB_LOG_LEVEL` | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR) |
| `KB_DEBUG` | `false` | Enable debug mode |

### API Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `KB_API_HOST` | `0.0.0.0` | API host binding |
| `KB_API_PORT` | `8000` | API port |
| `KB_API_WORKERS` | `1` | Number of worker processes |
| `KB_API_CORS_ORIGINS` | `*` | CORS allowed origins |

### Redis Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `KB_REDIS_ENABLED` | `false` | Enable Redis caching |
| `KB_REDIS_HOST` | `redis` | Redis hostname |
| `KB_REDIS_PORT` | `6379` | Redis port |
| `KB_REDIS_DB` | `0` | Redis database number |

### Vector Database Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `KB_VECTOR_DB_PATH` | `/data/chroma_db` | ChromaDB storage path |
| `KB_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Embedding model name |
| `KB_CHUNK_SIZE` | `1000` | Text chunk size |
| `KB_CHUNK_OVERLAP` | `200` | Chunk overlap size |

See `.env.example` for complete list.

## Volume Management

### Production Volumes

```yaml
volumes:
  kb_data:        # Knowledge base data (ChromaDB, documents)
  redis_data:     # Redis persistence
  kb_logs:        # Application logs
```

### Backup Data

```bash
# Create backup
docker run --rm \
  -v knowledgebeast_kb_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/kb-data-$(date +%Y%m%d).tar.gz /data

# Restore backup
docker run --rm \
  -v knowledgebeast_kb_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/kb-data-20250101.tar.gz -C /
```

### Inspect Volumes

```bash
# List volumes
docker volume ls | grep knowledgebeast

# Inspect volume
docker volume inspect knowledgebeast_kb_data

# Browse volume contents
docker run --rm -it \
  -v knowledgebeast_kb_data:/data \
  alpine sh -c "ls -lah /data"
```

### Clean Volumes

```bash
# Remove all volumes (WARNING: Deletes all data!)
make docker-clean-all

# Remove specific volume
docker volume rm knowledgebeast_kb_data
```

## Scaling and Performance

### Horizontal Scaling

Scale API workers:
```bash
# Using docker-compose
docker-compose up -d --scale knowledgebeast=3

# Or edit docker-compose.yml
services:
  knowledgebeast:
    deploy:
      replicas: 3
```

### Performance Tuning

**Environment Variables:**
```env
# Worker processes (2-4 x CPU cores)
KB_API_WORKERS=4

# Thread pool for CPU-bound tasks
KB_THREAD_POOL_SIZE=8

# Chunk processing
KB_BATCH_SIZE=100
```

**Resource Limits:**

Add to `docker-compose.yml`:
```yaml
services:
  knowledgebeast:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          memory: 2G
```

### Redis Caching

Enable Redis for better performance:
```env
KB_REDIS_ENABLED=true
KB_ENABLE_QUERY_CACHE=true
KB_QUERY_CACHE_TTL=3600
```

### Image Size Optimization

Production image is already optimized:
- Multi-stage build: ~400MB
- Minimal base (python:3.11-slim)
- Layer caching for fast rebuilds
- Only production dependencies

Check image size:
```bash
make docker-size
```

## Security Best Practices

### 1. Non-Root User

Production Dockerfile runs as `knowledgebeast:knowledgebeast` (UID/GID 1000):
```dockerfile
USER knowledgebeast
```

### 2. Environment Variables

**Never commit `.env` to version control!**

```bash
# Add to .gitignore
echo ".env" >> .gitignore

# Use secrets management in production
docker secret create kb_api_key /path/to/api_key.txt
```

### 3. CORS Configuration

Restrict CORS origins in production:
```env
KB_API_CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

### 4. Network Isolation

Use Docker networks for service isolation:
```yaml
networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true  # No external access
```

### 5. Health Checks

Ensure health checks are configured:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 15s
```

### 6. Read-Only Filesystem

Add read-only root filesystem:
```yaml
services:
  knowledgebeast:
    read_only: true
    tmpfs:
      - /tmp
      - /app/logs
```

### 7. Security Scanning

Scan images for vulnerabilities:
```bash
# Using docker scan
docker scan knowledgebeast:latest

# Using trivy
trivy image knowledgebeast:latest
```

## Troubleshooting

### Container Won't Start

**Check logs:**
```bash
make docker-logs
docker-compose logs knowledgebeast
```

**Common issues:**
- Port already in use: Change port in `.env` or `docker-compose.yml`
- Volume permission errors: Check directory permissions
- Missing dependencies: Rebuild image

### Health Check Failing

```bash
# Check health status
make docker-health

# Test endpoint manually
docker exec knowledgebeast curl -f http://localhost:8000/api/v1/health

# Check network connectivity
docker exec knowledgebeast ping -c 3 redis
```

### Performance Issues

```bash
# Check resource usage
make docker-stats

# Check container logs for errors
make docker-logs-api

# Increase workers
# Edit .env: KB_API_WORKERS=4
docker-compose up -d
```

### Volume Data Lost

**Prevention:**
- Use named volumes (not bind mounts for data)
- Regular backups (see Volume Management)
- Don't use `docker-compose down -v` in production

**Recovery:**
- Restore from backup
- Check volume still exists: `docker volume ls`

### Redis Connection Issues

```bash
# Test Redis connection
docker exec knowledgebeast-redis redis-cli ping

# Check if Redis is enabled
docker exec knowledgebeast env | grep KB_REDIS

# Test connection from API
docker exec knowledgebeast python -c "
import redis
r = redis.Redis(host='redis', port=6379, db=0)
print(r.ping())
"
```

### Image Build Failures

```bash
# Clean build cache
docker builder prune -af

# Rebuild without cache
docker build --no-cache -t knowledgebeast:latest .

# Check for build errors
docker build --progress=plain -t knowledgebeast:latest .
```

## Advanced Usage

### Custom Dockerfile

Create `Dockerfile.custom`:
```dockerfile
FROM knowledgebeast:latest

# Add custom dependencies
RUN pip install your-package

# Add custom configuration
COPY custom-config.yaml /config/
```

Build:
```bash
docker build -f Dockerfile.custom -t knowledgebeast:custom .
```

### Docker Swarm Deployment

```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml knowledgebeast

# Scale services
docker service scale knowledgebeast_api=3
```

### Kubernetes Deployment

See `k8s/` directory for Kubernetes manifests (if available).

Basic deployment:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: knowledgebeast
spec:
  replicas: 3
  selector:
    matchLabels:
      app: knowledgebeast
  template:
    metadata:
      labels:
        app: knowledgebeast
    spec:
      containers:
      - name: knowledgebeast
        image: knowledgebeast:latest
        ports:
        - containerPort: 8000
        env:
        - name: KB_LOG_LEVEL
          value: "INFO"
```

### Using Docker Registry

```bash
# Tag for registry
docker tag knowledgebeast:latest myregistry.com/knowledgebeast:0.1.0

# Push to registry
docker push myregistry.com/knowledgebeast:0.1.0

# Pull on remote server
docker pull myregistry.com/knowledgebeast:0.1.0
```

### CI/CD Integration

**GitHub Actions:**
```yaml
name: Docker Build and Push

on:
  push:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Build image
      run: docker build -t knowledgebeast:${{ github.sha }} .
    - name: Push to registry
      run: docker push knowledgebeast:${{ github.sha }}
```

### Monitoring

**Prometheus metrics:**
```yaml
services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
```

**Grafana dashboards:**
```bash
docker run -d \
  -p 3000:3000 \
  --name grafana \
  grafana/grafana
```

## Support

For issues and questions:
- GitHub Issues: https://github.com/yourusername/knowledgebeast/issues
- Documentation: https://github.com/yourusername/knowledgebeast#readme

## License

MIT License - See LICENSE file for details.
