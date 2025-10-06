# Performance Guide

## Benchmarks

### Ingestion Performance
- Small docs (< 10 pages): ~1-2 seconds
- Medium docs (10-50 pages): ~3-10 seconds
- Large docs (50+ pages): ~10-30 seconds

### Query Performance
- Cold query: 100-500ms
- Cached query: <10ms
- Bulk queries (10): ~2-5 seconds

### Memory Usage
- Base: ~500MB (model loading)
- Per 1000 documents: ~200MB
- Cache (100 queries): ~10MB

## Optimization Tips

### 1. Choose Right Embedding Model
- `all-MiniLM-L6-v2`: Fastest, smallest (80MB)
- `all-mpnet-base-v2`: Better quality (420MB)

### 2. Optimize Chunk Size
- Smaller chunks (500): More precise, slower
- Larger chunks (2000): Faster, less precise
- Default (1000): Balanced

### 3. Enable Caching
- Always use cache in production
- Increase cache size for high-traffic apps
- Warm cache after ingestion

### 4. Batch Operations
- Ingest documents in batches
- Use batch query for multiple searches

### 5. Resource Allocation
- Recommended: 4GB RAM minimum
- CPU: 2+ cores for parallel processing
- Storage: 2-3x document size

## Monitoring

Track these metrics:
- Query latency (p50, p95, p99)
- Cache hit rate
- Memory usage
- Disk usage

## Scaling Strategies

### Vertical Scaling
- Increase RAM for larger cache
- More CPU cores for parallel processing

### Horizontal Scaling
- Run multiple instances behind load balancer
- Share persistent volume for ChromaDB

### Database Optimization
- Regular index optimization
- Prune old documents
- Monitor collection size
