# Docker Deployment Guide

Deploy KnowledgeBeast using Docker and Docker Compose.

## Quick Start

```bash
# Build and run with docker-compose
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## Dockerfile

The included Dockerfile provides a production-ready image:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Install package
RUN pip install -e .

# Expose port
EXPOSE 8000

# Run server
CMD ["knowledgebeast", "serve", "--host", "0.0.0.0", "--port", "8000"]
```

## Docker Compose

The `docker-compose.yml` file configures the complete stack:

```yaml
version: '3.8'

services:
  knowledgebeast:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./documents:/app/documents
    environment:
      - KB_DATA_DIR=/app/data
      - KB_MAX_CACHE_SIZE=200
      - KB_HEARTBEAT_INTERVAL=300
    restart: unless-stopped
```

## Building the Image

### Build Locally

```bash
# Build image
docker build -t knowledgebeast:latest .

# Build with specific tag
docker build -t knowledgebeast:0.1.0 .

# Build with no cache
docker build --no-cache -t knowledgebeast:latest .
```

### Multi-stage Build (Optimized)

For smaller image size:

```dockerfile
# Build stage
FROM python:3.11-slim as builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim

WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
RUN pip install --user -e .

ENV PATH=/root/.local/bin:$PATH
EXPOSE 8000

CMD ["knowledgebeast", "serve", "--host", "0.0.0.0", "--port", "8000"]
```

## Running Containers

### Run with docker run

```bash
# Basic run
docker run -p 8000:8000 knowledgebeast

# With volume mounts
docker run -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/documents:/app/documents \
  knowledgebeast

# With environment variables
docker run -p 8000:8000 \
  -e KB_MAX_CACHE_SIZE=500 \
  -e KB_HEARTBEAT_INTERVAL=300 \
  -v $(pwd)/data:/app/data \
  knowledgebeast

# Run in background
docker run -d -p 8000:8000 \
  --name kb-server \
  -v $(pwd)/data:/app/data \
  knowledgebeast
```

### Run with docker-compose

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f knowledgebeast

# Restart service
docker-compose restart knowledgebeast

# Stop services
docker-compose down

# Remove volumes
docker-compose down -v
```

## Volume Management

### Data Persistence

```yaml
services:
  knowledgebeast:
    volumes:
      # Persistent data directory
      - kb-data:/app/data
      # Document source
      - ./documents:/app/documents:ro

volumes:
  kb-data:
    driver: local
```

### Backup Volumes

```bash
# Backup data volume
docker run --rm \
  -v kb-data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/kb-backup.tar.gz /data

# Restore data volume
docker run --rm \
  -v kb-data:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/kb-backup.tar.gz -C /
```

## Environment Variables

Configure via environment variables:

```bash
# .env file
KB_DATA_DIR=/app/data
KB_MAX_CACHE_SIZE=200
KB_HEARTBEAT_INTERVAL=300
KB_AUTO_WARM=true
KB_LOG_LEVEL=INFO
```

Use in docker-compose:

```yaml
services:
  knowledgebeast:
    env_file:
      - .env
```

## Health Checks

Add health check to docker-compose:

```yaml
services:
  knowledgebeast:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

## Production Configuration

### Resource Limits

```yaml
services:
  knowledgebeast:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

### Logging

```yaml
services:
  knowledgebeast:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Restart Policy

```yaml
services:
  knowledgebeast:
    restart: unless-stopped
```

## Networking

### Expose to External Network

```yaml
services:
  knowledgebeast:
    ports:
      - "0.0.0.0:8000:8000"
```

### Custom Network

```yaml
networks:
  kb-network:
    driver: bridge

services:
  knowledgebeast:
    networks:
      - kb-network
```

## Multi-Container Setup

### With Nginx Reverse Proxy

```yaml
version: '3.8'

services:
  knowledgebeast:
    build: .
    expose:
      - "8000"
    volumes:
      - ./data:/app/data

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - knowledgebeast

volumes:
  kb-data:
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs knowledgebeast

# Check container status
docker-compose ps

# Inspect container
docker inspect knowledgebeast
```

### Permission Issues

```bash
# Fix volume permissions
docker-compose run --rm --user root knowledgebeast \
  chown -R 1000:1000 /app/data
```

### Out of Memory

```bash
# Increase memory limit
docker-compose up -d \
  --scale knowledgebeast=1 \
  --memory=8g
```

## Useful Commands

```bash
# Execute command in running container
docker-compose exec knowledgebeast knowledgebeast stats

# Access container shell
docker-compose exec knowledgebeast bash

# View resource usage
docker stats knowledgebeast

# Prune unused images
docker image prune -a

# View container logs
docker-compose logs --tail=100 -f knowledgebeast
```

## Next Steps

- [Production Checklist](../deployment/production-checklist.md)
- [Kubernetes Deployment](../deployment/kubernetes.md)
- [REST API Guide](rest-api.md)
