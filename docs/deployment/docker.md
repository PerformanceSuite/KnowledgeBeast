# Docker Deployment

See [Docker Deployment Guide](../guides/docker-deployment.md) for complete details.

## Quick Start

```bash
docker-compose up -d
```

## Configuration

Use environment variables or volume mounts:

```yaml
services:
  knowledgebeast:
    environment:
      - KB_MAX_CACHE_SIZE=200
    volumes:
      - ./data:/app/data
```

## Next Steps

- [Docker Deployment Guide](../guides/docker-deployment.md)
- [Production Checklist](production-checklist.md)
