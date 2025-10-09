# KnowledgeBeast Incident Response Runbook

## Overview

This runbook provides step-by-step instructions for diagnosing and resolving common incidents in KnowledgeBeast production environments.

**On-Call Contact**: See PagerDuty rotation
**Escalation Path**: Team Lead → Engineering Manager → CTO
**Incident Severity Levels**:
- **P0 (Critical)**: Complete service outage, data loss risk
- **P1 (High)**: Major feature degradation, < 50% capacity
- **P2 (Medium)**: Minor feature degradation, performance issues
- **P3 (Low)**: Cosmetic issues, non-critical bugs

---

## Incident 1: High Query Latency (P99 > 500ms)

### Severity
**P1 (High)** - User experience significantly impacted

### Symptoms
- Grafana shows P99 latency > 500ms
- User complaints about slow search results
- API timeout errors increasing
- Dashboard shows high query duration histogram spikes

### Diagnosis Steps

1. **Check Grafana Dashboard**
   ```bash
   # Navigate to Grafana
   open http://localhost:3000/d/knowledgebeast-overview

   # Review panels:
   # - Query Latency (P50, P95, P99)
   # - Cache Hit Ratio
   # - ChromaDB Response Time
   ```

2. **Examine Recent Logs**
   ```bash
   # Check for slow queries
   kubectl logs -n production deployment/knowledgebeast --tail=1000 | \
     jq 'select(.query_duration_ms > 500)'

   # Look for patterns: specific projects, query types, time of day
   ```

3. **Verify Cache Performance**
   ```bash
   # Check cache hit ratio
   curl http://localhost:8000/metrics | grep cache_hit_ratio

   # Expected: > 0.90 (90%)
   # If < 0.50, cache is not effective
   ```

4. **Check ChromaDB Health**
   ```bash
   curl http://localhost:8000/health | jq '.components.chromadb'

   # Expected: {"status": "up", "latency_ms": < 50}
   ```

5. **Review Resource Utilization**
   ```bash
   # CPU and memory usage
   kubectl top pods -n production

   # Disk I/O
   kubectl exec -n production deployment/knowledgebeast -- iostat -x 1 5
   ```

### Resolution Steps

**Option A: Cache Issue (Cache hit ratio < 50%)**
1. Warm the cache with common queries:
   ```bash
   python scripts/warm_cache.py --project all --top-queries 1000
   ```

2. Increase cache capacity:
   ```bash
   # Edit deployment config
   kubectl set env deployment/knowledgebeast -n production \
     CACHE_SIZE=500  # Increase from 100 to 500

   kubectl rollout restart deployment/knowledgebeast -n production
   ```

**Option B: ChromaDB Slow Response (ChromaDB latency > 100ms)**
1. Restart ChromaDB service:
   ```bash
   kubectl rollout restart deployment/chromadb -n production

   # Wait for healthy status
   kubectl rollout status deployment/chromadb -n production
   ```

2. Check ChromaDB collection sizes:
   ```bash
   python -c "
   from knowledgebeast.core import KnowledgeBase
   kb = KnowledgeBase()
   for project in kb.list_projects():
       size = kb.get_collection_size(project)
       print(f'{project}: {size} vectors')
   "
   ```

3. If collections too large (> 1M vectors), consider partitioning

**Option C: Resource Exhaustion (CPU > 80% or Memory > 90%)**
1. Scale horizontally:
   ```bash
   kubectl scale deployment/knowledgebeast -n production --replicas=5
   ```

2. Monitor impact:
   ```bash
   watch -n 5 'curl -s http://localhost:8000/metrics | grep p99_latency'
   ```

**Option D: Embedding Model Slow (Embedding generation > 200ms)**
1. Check GPU availability:
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- nvidia-smi
   ```

2. Restart service to reload model:
   ```bash
   kubectl rollout restart deployment/knowledgebeast -n production
   ```

### Escalation Criteria
- Latency remains > 500ms after 30 minutes of mitigation
- Latency exceeds 1000ms (1 second)
- Multiple components failing simultaneously

### Prevention
- Set up predictive alerts: P99 > 150ms for 10 minutes = WARNING
- Regular cache warming cron job (every 6 hours)
- Capacity planning: Scale before 70% resource utilization
- Implement query result pagination for large result sets

---

## Incident 2: ChromaDB Unreachable

### Severity
**P0 (Critical)** - Vector search completely unavailable

### Symptoms
- `/health` endpoint shows ChromaDB status: "down"
- All queries return 500 errors
- Circuit breaker state: OPEN
- Logs show: `chromadb.errors.ConnectionError`
- Grafana shows ChromaDB latency: N/A or timeout

### Diagnosis Steps

1. **Verify ChromaDB Service Status**
   ```bash
   # Kubernetes
   kubectl get pods -n production | grep chromadb

   # Docker
   docker ps | grep chromadb

   # Check logs
   kubectl logs -n production deployment/chromadb --tail=100
   ```

2. **Test Network Connectivity**
   ```bash
   # From KnowledgeBeast pod
   kubectl exec -n production deployment/knowledgebeast -- \
     curl -v http://chromadb:8000/api/v1/heartbeat

   # Expected: HTTP 200 {"status": "ok"}
   ```

3. **Check DNS Resolution**
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- nslookup chromadb

   # Should resolve to internal service IP
   ```

4. **Verify Firewall Rules**
   ```bash
   # Check NetworkPolicies
   kubectl get networkpolicy -n production

   # Ensure port 8000 is allowed
   ```

### Resolution Steps

**Option A: ChromaDB Pod Crashed**
1. Check pod status:
   ```bash
   kubectl describe pod -n production -l app=chromadb
   ```

2. Restart ChromaDB:
   ```bash
   kubectl rollout restart deployment/chromadb -n production

   # Wait for ready
   kubectl wait --for=condition=ready pod -l app=chromadb -n production --timeout=300s
   ```

3. Verify health:
   ```bash
   curl http://chromadb:8000/api/v1/heartbeat
   ```

**Option B: Network Partition**
1. Check service endpoints:
   ```bash
   kubectl get endpoints chromadb -n production
   ```

2. If no endpoints, recreate service:
   ```bash
   kubectl delete service chromadb -n production
   kubectl apply -f deployments/kubernetes/chromadb-service.yaml
   ```

**Option C: Disk Full**
1. Check disk usage:
   ```bash
   kubectl exec -n production deployment/chromadb -- df -h /data
   ```

2. Clean up old snapshots:
   ```bash
   kubectl exec -n production deployment/chromadb -- \
     find /data/snapshots -mtime +30 -delete
   ```

3. Expand PersistentVolume if needed:
   ```bash
   kubectl patch pvc chromadb-data -n production \
     -p '{"spec":{"resources":{"requests":{"storage":"200Gi"}}}}'
   ```

### Fallback Mode (Graceful Degradation)

KnowledgeBeast automatically degrades to keyword-only search when ChromaDB is unavailable:

1. **Verify Degraded Mode Active**
   ```bash
   curl http://localhost:8000/api/v1/query/test-project?q=example | jq '.degraded_mode'

   # Expected: true
   ```

2. **System Behavior in Degraded Mode**
   - Vector search disabled
   - Keyword search still functional (BM25 algorithm)
   - Response includes `"degraded_mode": true` flag
   - Cached results still served
   - Alert fires: "ChromaDB Unavailable - Degraded Mode Active"

3. **Recovery from Degraded Mode**
   - Circuit breaker automatically tests ChromaDB every 30 seconds
   - When ChromaDB recovers, circuit closes
   - System automatically returns to normal mode
   - No manual intervention required

### Escalation Criteria
- ChromaDB remains down after 15 minutes
- Fallback mode not working (keyword search also failing)
- Data corruption suspected (integrity check fails)

### Prevention
- Regular health checks: ChromaDB heartbeat every 10 seconds
- Redundant ChromaDB instances (multi-AZ deployment)
- Automated disk cleanup cron job
- Capacity monitoring alerts: disk > 80% = WARNING

---

## Incident 3: Memory Leak Detected

### Severity
**P1 (High)** - Risk of OOM crash within hours

### Symptoms
- Container memory usage steadily increasing
- Grafana shows memory utilization > 90%
- Kubernetes OOMKilled events
- Logs show: `MemoryError` or `malloc failed`
- Application restarts frequently

### Diagnosis Steps

1. **Monitor Memory Growth**
   ```bash
   # Watch memory usage
   kubectl top pod -n production -l app=knowledgebeast

   # Check for continuous increase over 30 minutes
   ```

2. **Review Memory Metrics**
   ```bash
   curl http://localhost:8000/metrics | grep process_resident_memory_bytes
   ```

3. **Generate Heap Dump**
   ```bash
   # Python memory profiler
   kubectl exec -n production deployment/knowledgebeast -- \
     python -m memory_profiler scripts/dump_heap.py > heap_dump.txt
   ```

4. **Analyze Object Counts**
   ```python
   # Inside container
   import gc, sys
   gc.collect()

   # Count objects by type
   from collections import Counter
   Counter([type(obj).__name__ for obj in gc.get_objects()]).most_common(20)
   ```

5. **Check Cache Sizes**
   ```bash
   curl http://localhost:8000/api/v1/stats | jq '.cache'

   # Look for unbounded growth
   # - query_cache size
   # - embedding_cache size
   # - document cache size
   ```

### Resolution Steps

**Option A: Unbounded Cache Growth**
1. Set cache limits in configuration:
   ```bash
   kubectl set env deployment/knowledgebeast -n production \
     QUERY_CACHE_SIZE=1000 \
     EMBEDDING_CACHE_SIZE=5000 \
     MAX_CACHE_MEMORY_MB=2048
   ```

2. Restart with new limits:
   ```bash
   kubectl rollout restart deployment/knowledgebeast -n production
   ```

**Option B: Memory Leak in Application Code**
1. Enable memory profiling:
   ```bash
   kubectl set env deployment/knowledgebeast -n production \
     ENABLE_MEMORY_PROFILING=true \
     PROFILE_INTERVAL_SECONDS=300
   ```

2. Collect profiling data (5 minutes):
   ```bash
   kubectl logs -n production deployment/knowledgebeast -f | \
     grep "MEMORY_PROFILE" > memory_profile.log
   ```

3. Analyze with `memray` or `py-spy`:
   ```bash
   memray flamegraph memory_profile.log -o flamegraph.html
   open flamegraph.html
   ```

4. Hot-fix by restarting service:
   ```bash
   kubectl rollout restart deployment/knowledgebeast -n production
   ```

5. File bug report with heap dump and flamegraph

**Option C: Large Document Processing**
1. Implement streaming for large files:
   ```python
   # Instead of loading entire file into memory
   with open(file_path, 'r') as f:
       for chunk in iter(lambda: f.read(8192), ''):
           process_chunk(chunk)
   ```

2. Set document size limits:
   ```bash
   kubectl set env deployment/knowledgebeast -n production \
     MAX_DOCUMENT_SIZE_MB=50
   ```

### Temporary Mitigation
```bash
# Increase memory limit temporarily (buy time for investigation)
kubectl set resources deployment/knowledgebeast -n production \
  --limits=memory=8Gi --requests=memory=4Gi

# Schedule automatic restarts every 6 hours (workaround)
kubectl patch deployment knowledgebeast -n production \
  --patch '{"spec":{"template":{"metadata":{"annotations":{"restart":"every-6h"}}}}}'
```

### Escalation Criteria
- Memory leak rate > 100MB/hour
- OOM crashes occurring more than once per hour
- Root cause not identified within 2 hours

### Prevention
- Regular memory profiling in staging environment
- Load testing with `locust` to detect leaks early
- Implement memory limits and monitoring alerts
- Code review checklist: Check for circular references, unclosed file handles

---

## Incident 4: API Error Rate Spike

### Severity
**P1 (High)** - Service reliability impacted

### Symptoms
- Grafana shows error rate > 1%
- Dashboard shows spike in 5xx response codes
- Logs filled with exceptions and stack traces
- User reports of failed requests
- Sentry/error tracking showing flood of errors

### Diagnosis Steps

1. **Identify Error Patterns**
   ```bash
   # Group errors by type
   kubectl logs -n production deployment/knowledgebeast --tail=10000 | \
     jq -r 'select(.level=="ERROR") | .error_type' | sort | uniq -c | sort -rn

   # Example output:
   # 450 ValidationError
   # 120 TimeoutError
   #  45 DatabaseError
   ```

2. **Check Error Distribution**
   ```bash
   curl http://localhost:8000/metrics | grep http_requests_total

   # Compare 2xx vs 4xx vs 5xx
   ```

3. **Identify Affected Endpoints**
   ```bash
   kubectl logs -n production deployment/knowledgebeast --tail=5000 | \
     jq -r 'select(.status >= 400) | .path' | sort | uniq -c | sort -rn

   # Example:
   # 234 /api/v1/query/large-project
   #  89 /api/v1/ingest
   ```

4. **Correlate with Recent Changes**
   ```bash
   # Check recent deployments
   kubectl rollout history deployment/knowledgebeast -n production

   # Compare error spike time with deployment time
   ```

5. **Review Input Validation**
   ```bash
   # Sample failed requests
   kubectl logs -n production deployment/knowledgebeast | \
     jq 'select(.status == 400) | {path, query, error}' | head -20
   ```

### Resolution Steps

**Option A: Bad Deployment (Errors started after recent deploy)**
1. Rollback to previous version:
   ```bash
   # Check current revision
   kubectl rollout history deployment/knowledgebeast -n production

   # Rollback to previous
   kubectl rollout undo deployment/knowledgebeast -n production

   # Verify rollback
   kubectl rollout status deployment/knowledgebeast -n production
   ```

2. Monitor error rate after rollback:
   ```bash
   watch -n 10 'curl -s http://localhost:8000/metrics | grep error_rate'
   ```

3. Investigate the rolled-back code in staging

**Option B: Input Validation Issues (High 4xx error rate)**
1. Add stricter input validation:
   ```python
   # In API endpoint
   from pydantic import BaseModel, validator, Field

   class QueryRequest(BaseModel):
       query: str = Field(..., min_length=1, max_length=1000)
       project: str = Field(..., regex=r'^[a-zA-Z0-9_-]+$')

       @validator('query')
       def validate_query(cls, v):
           if not v.strip():
               raise ValueError('Query cannot be empty')
           return v.strip()
   ```

2. Deploy validation fix:
   ```bash
   git add knowledgebeast/api/routes.py
   git commit -m "fix: Add stricter input validation"
   git push origin feature/fix-validation

   # Create and merge PR, then deploy
   ```

**Option C: Downstream Service Failure (Timeouts, connection errors)**
1. Check ChromaDB health (see Incident 2)

2. Verify embedding service:
   ```bash
   curl http://embedding-service:5000/health
   ```

3. Implement retry logic with exponential backoff:
   ```python
   from tenacity import retry, stop_after_attempt, wait_exponential

   @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
   def query_chromadb(collection, query_embedding):
       return collection.query(query_embeddings=[query_embedding])
   ```

**Option D: Database Issues**
1. Check SQLite database integrity:
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- \
     sqlite3 /data/knowledgebeast.db "PRAGMA integrity_check;"

   # Expected: "ok"
   ```

2. Rebuild indexes if corrupted:
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- \
     sqlite3 /data/knowledgebeast.db "REINDEX;"
   ```

### Escalation Criteria
- Error rate > 5% for more than 10 minutes
- 5xx error rate > 0.5%
- Rollback does not resolve issue
- Multiple components failing

### Prevention
- Comprehensive input validation on all endpoints
- Rate limiting: 100 requests/minute per IP
- Request payload size limits: 10MB max
- Automated canary deployments (1% traffic first)
- Synthetic monitoring with expected error detection

---

## Incident 5: Disk Space Critical

### Severity
**P1 (High)** - Risk of service failure

### Symptoms
- Alert: "Disk Space < 5GB"
- Logs show: `OSError: [Errno 28] No space left on device`
- Database writes failing
- ChromaDB snapshot creation failing
- Application unable to write temp files

### Diagnosis Steps

1. **Check Disk Usage**
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- df -h

   # Identify full filesystem
   # /data         95% (475G/500G)
   ```

2. **Identify Large Files/Directories**
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- \
     du -sh /data/* | sort -rh | head -20

   # Example output:
   # 320G  /data/chromadb
   # 89G   /data/logs
   # 45G   /data/backups
   # 21G   /data/temp
   ```

3. **Check ChromaDB Snapshots**
   ```bash
   kubectl exec -n production deployment/chromadb -- \
     ls -lh /data/snapshots/

   # Look for old snapshots (> 30 days)
   ```

4. **Review Log Rotation**
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- \
     ls -lh /var/log/knowledgebeast/

   # Check for unrotated large log files
   ```

### Resolution Steps

**Option A: Clean Up Old Logs**
1. Rotate and compress logs:
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- \
     find /var/log/knowledgebeast -name "*.log" -mtime +7 -exec gzip {} \;

   kubectl exec -n production deployment/knowledgebeast -- \
     find /var/log/knowledgebeast -name "*.gz" -mtime +30 -delete
   ```

2. Verify space freed:
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- df -h /var/log
   ```

**Option B: Clean Up Old ChromaDB Snapshots**
1. List snapshots by age:
   ```bash
   kubectl exec -n production deployment/chromadb -- \
     find /data/snapshots -type f -mtime +30 -ls
   ```

2. Delete snapshots older than 30 days:
   ```bash
   kubectl exec -n production deployment/chromadb -- \
     find /data/snapshots -type f -mtime +30 -delete
   ```

3. Keep only last 7 daily backups:
   ```bash
   kubectl exec -n production deployment/chromadb -- \
     ls -t /data/snapshots/daily_* | tail -n +8 | xargs rm -f
   ```

**Option C: Clean Up Temp Files**
1. Remove old temp files:
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- \
     find /tmp -type f -mtime +1 -delete

   kubectl exec -n production deployment/knowledgebeast -- \
     find /data/temp -type f -mtime +1 -delete
   ```

**Option D: Expand Storage (Long-term solution)**
1. Resize PersistentVolume:
   ```bash
   # Edit PVC
   kubectl edit pvc knowledgebeast-data -n production

   # Change spec.resources.requests.storage to larger value
   # from: 500Gi
   # to:   1000Gi
   ```

2. Verify expansion:
   ```bash
   kubectl get pvc knowledgebeast-data -n production

   # Wait for status: Bound (resized)
   ```

### Automated Cleanup Script
```bash
#!/bin/bash
# /scripts/cleanup_disk.sh

set -e

LOG_DIR="/var/log/knowledgebeast"
SNAPSHOT_DIR="/data/snapshots"
TEMP_DIR="/data/temp"

# Compress logs older than 7 days
find $LOG_DIR -name "*.log" -mtime +7 -exec gzip {} \;

# Delete compressed logs older than 30 days
find $LOG_DIR -name "*.gz" -mtime +30 -delete

# Delete ChromaDB snapshots older than 30 days
find $SNAPSHOT_DIR -type f -mtime +30 -delete

# Delete temp files older than 1 day
find $TEMP_DIR -type f -mtime +1 -delete

# Report freed space
echo "Disk cleanup complete at $(date)"
df -h | grep /data
```

**Schedule as CronJob:**
```yaml
# deployments/kubernetes/cleanup-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: disk-cleanup
spec:
  schedule: "0 2 * * *"  # 2 AM daily
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: cleanup
            image: knowledgebeast:latest
            command: ["/scripts/cleanup_disk.sh"]
```

### Escalation Criteria
- Disk usage > 95%
- Cannot free up minimum 10GB space
- Storage expansion not possible
- Service experiencing write failures

### Prevention
- Automated daily cleanup cron job
- Log rotation configured (max 10 files, 100MB each)
- Monitoring alerts: disk > 80% = WARNING, > 90% = CRITICAL
- Regular review of storage growth trends

---

## Incident 6: Embedding Model Failure

### Severity
**P2 (Medium)** - Ingestion disabled, queries still work

### Symptoms
- Logs show: `RuntimeError: Embedding model failed to load`
- `/health` endpoint: `embedding_model: {"status": "down"}`
- Document ingestion failing with 500 errors
- Queries work (using existing embeddings)
- Alert: "Embedding Model Unavailable"

### Diagnosis Steps

1. **Check Model Health**
   ```bash
   curl http://localhost:8000/health | jq '.components.embedding_model'

   # Expected: {"status": "up", "model": "all-MiniLM-L6-v2"}
   # Actual: {"status": "down", "error": "Model file not found"}
   ```

2. **Verify Model Files**
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- \
     ls -lh /models/

   # Check for:
   # - model.safetensors
   # - config.json
   # - tokenizer.json
   ```

3. **Check GPU Availability**
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- nvidia-smi

   # If GPU-enabled deployment
   # Verify GPU memory and utilization
   ```

4. **Review Model Loading Logs**
   ```bash
   kubectl logs -n production deployment/knowledgebeast | \
     grep "embedding_model" | tail -50
   ```

### Resolution Steps

**Option A: Model Files Missing or Corrupted**
1. Download model from Hugging Face:
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- \
     python -c "
   from sentence_transformers import SentenceTransformer
   model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
   model.save('/models/all-MiniLM-L6-v2')
   "
   ```

2. Restart service to reload model:
   ```bash
   kubectl rollout restart deployment/knowledgebeast -n production
   ```

3. Verify model loaded:
   ```bash
   curl http://localhost:8000/health | jq '.components.embedding_model.status'
   # Expected: "up"
   ```

**Option B: GPU Out of Memory**
1. Check GPU memory:
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- \
     nvidia-smi --query-gpu=memory.used,memory.total --format=csv
   ```

2. Fallback to CPU inference:
   ```bash
   kubectl set env deployment/knowledgebeast -n production \
     EMBEDDING_DEVICE=cpu

   kubectl rollout restart deployment/knowledgebeast -n production
   ```

3. Note: CPU inference is slower (100ms vs 10ms per embedding)

**Option C: Model Version Mismatch**
1. Check model version in config:
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- \
     cat /models/config.json | jq '.model_type'
   ```

2. Update to correct model version:
   ```bash
   kubectl set env deployment/knowledgebeast -n production \
     EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
   ```

**Option D: ONNX Runtime Issue (If using ONNX)**
1. Verify ONNX runtime:
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- \
     python -c "import onnxruntime; print(onnxruntime.__version__)"
   ```

2. Reinstall ONNX runtime:
   ```bash
   pip install --force-reinstall onnxruntime-gpu
   ```

### Fallback Strategy
While embedding model is down:
- **Queries**: Continue using existing vector embeddings (no impact)
- **Ingestion**: Queue documents for processing when model recovers
  ```python
  # Implement dead letter queue
  if not embedding_model_available():
      enqueue_for_later(document_id)
      return {"status": "queued", "reason": "embedding_model_unavailable"}
  ```

### Escalation Criteria
- Model cannot be reloaded after 30 minutes
- Fallback to CPU not feasible (too slow)
- Ingestion backlog exceeds 10,000 documents

### Prevention
- Model files included in Docker image (not downloaded at runtime)
- Health check on startup: Fail fast if model won't load
- GPU memory monitoring alerts
- Multiple embedding model replicas (HA setup)

---

## Incident 7: Cache Hit Ratio Drop

### Severity
**P2 (Medium)** - Performance degradation

### Symptoms
- Grafana shows cache hit ratio < 50% (normal: > 90%)
- Query latency increasing
- ChromaDB load increasing
- Metrics show high cache eviction rate
- Dashboard: `kb_embedding_cache_misses_total` spiking

### Diagnosis Steps

1. **Check Current Cache Hit Ratio**
   ```bash
   curl http://localhost:8000/metrics | grep cache_hit_ratio

   # kb_query_cache_hit_ratio 0.42
   # kb_embedding_cache_hit_ratio 0.38
   ```

2. **Review Cache Configuration**
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- \
     env | grep CACHE

   # QUERY_CACHE_SIZE=100
   # EMBEDDING_CACHE_SIZE=1000
   ```

3. **Analyze Cache Eviction Rate**
   ```bash
   curl http://localhost:8000/metrics | grep cache_evictions_total

   # High evictions = cache too small
   ```

4. **Identify Query Patterns**
   ```bash
   kubectl logs -n production deployment/knowledgebeast --tail=10000 | \
     jq -r 'select(.cache_hit != null) | {query: .query, hit: .cache_hit}' | \
     head -100

   # Look for:
   # - Highly diverse queries (low repetition)
   # - Large result sets (hard to cache)
   ```

5. **Check Cache Memory Usage**
   ```bash
   curl http://localhost:8000/api/v1/stats | jq '.cache_memory_mb'

   # Compare to configured limit
   ```

### Resolution Steps

**Option A: Cache Size Too Small**
1. Increase cache capacity:
   ```bash
   kubectl set env deployment/knowledgebeast -n production \
     QUERY_CACHE_SIZE=500 \
     EMBEDDING_CACHE_SIZE=5000

   kubectl rollout restart deployment/knowledgebeast -n production
   ```

2. Monitor impact:
   ```bash
   watch -n 30 'curl -s http://localhost:8000/metrics | grep cache_hit_ratio'
   ```

**Option B: Poor Cache Key Strategy**
1. Review cache key generation:
   ```python
   # Bad: Too specific, low hit rate
   cache_key = f"{query}_{project}_{timestamp}_{user_id}"

   # Good: More general, higher hit rate
   cache_key = f"{normalize_query(query)}_{project}"
   ```

2. Implement query normalization:
   ```python
   def normalize_query(query: str) -> str:
       # Lowercase, remove extra whitespace, sort terms
       terms = sorted(query.lower().split())
       return ' '.join(terms)
   ```

**Option C: Cache Warming Needed**
1. Identify top queries:
   ```bash
   kubectl logs -n production deployment/knowledgebeast --tail=50000 | \
     jq -r '.query' | sort | uniq -c | sort -rn | head -100 > top_queries.txt
   ```

2. Warm cache with top queries:
   ```bash
   python scripts/warm_cache.py --queries-file top_queries.txt --project all
   ```

3. Schedule regular cache warming:
   ```yaml
   # CronJob every 6 hours
   apiVersion: batch/v1
   kind: CronJob
   metadata:
     name: cache-warmer
   spec:
     schedule: "0 */6 * * *"
     jobTemplate:
       spec:
         template:
           spec:
             containers:
             - name: warmer
               image: knowledgebeast:latest
               command: ["python", "scripts/warm_cache.py", "--top-queries", "1000"]
   ```

**Option D: High Query Diversity (Fundamental limitation)**
If queries are truly unique:
1. Analyze query diversity:
   ```bash
   total_queries=$(kubectl logs -n production deployment/knowledgebeast --tail=10000 | jq -r '.query' | wc -l)
   unique_queries=$(kubectl logs -n production deployment/knowledgebeast --tail=10000 | jq -r '.query' | sort -u | wc -l)

   diversity_ratio=$(echo "scale=2; $unique_queries / $total_queries" | bc)
   echo "Query diversity: $diversity_ratio"

   # If > 0.80, caching won't help much
   ```

2. Focus on embedding cache instead:
   ```bash
   # Increase embedding cache (more stable than query cache)
   kubectl set env deployment/knowledgebeast -n production \
     EMBEDDING_CACHE_SIZE=10000
   ```

3. Implement partial result caching:
   ```python
   # Cache intermediate results (embeddings, not full results)
   embedding = cache.get(f"embedding:{query}")
   if embedding is None:
       embedding = model.encode(query)
       cache.put(f"embedding:{query}", embedding)
   ```

### Escalation Criteria
- Cache hit ratio < 30% after optimization attempts
- Cache-related performance impact > 100ms on P99 latency
- Memory exhaustion due to cache size increase

### Prevention
- Baseline cache hit ratio: Establish SLO (> 70%)
- Alert on sustained low hit ratio: < 50% for 30 minutes
- Regular analysis of query patterns
- A/B testing of cache strategies in staging

---

## Incident 8: Database Corruption

### Severity
**P0 (Critical)** - Data integrity at risk

### Symptoms
- SQLite errors in logs: `database disk image is malformed`
- Project list API returns incomplete results
- Document metadata missing or incorrect
- Integrity check fails: `PRAGMA integrity_check` returns errors
- Application crashes on database operations
- Alert: "Database Integrity Check Failed"

### Diagnosis Steps

1. **Run Integrity Check**
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- \
     sqlite3 /data/knowledgebeast.db "PRAGMA integrity_check;"

   # Healthy output: "ok"
   # Corrupted output: List of errors
   ```

2. **Check Database File**
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- \
     ls -lh /data/knowledgebeast.db

   # Verify file size is reasonable
   # Check file permissions (should be 644)
   ```

3. **Identify Corruption Scope**
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- \
     sqlite3 /data/knowledgebeast.db "
       SELECT COUNT(*) FROM projects;
       SELECT COUNT(*) FROM documents;
       SELECT COUNT(*) FROM metadata;
     "

   # Compare with expected counts
   ```

4. **Review Recent Activity**
   ```bash
   kubectl logs -n production deployment/knowledgebeast --tail=5000 | \
     grep -i "database\|sqlite\|disk"

   # Look for:
   # - Disk full errors before corruption
   # - Sudden pod terminations during writes
   # - Checkpoint failures
   ```

5. **Check Backup Availability**
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- \
     ls -lht /backups/knowledgebeast.db.* | head -10

   # Verify recent backups exist
   ```

### Resolution Steps

**Option A: Minor Corruption (Recoverable with VACUUM)**
1. Stop write operations:
   ```bash
   kubectl scale deployment/knowledgebeast -n production --replicas=0
   ```

2. Run VACUUM to rebuild database:
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- \
     sqlite3 /data/knowledgebeast.db "VACUUM;"
   ```

3. Rebuild indexes:
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- \
     sqlite3 /data/knowledgebeast.db "REINDEX;"
   ```

4. Verify integrity:
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- \
     sqlite3 /data/knowledgebeast.db "PRAGMA integrity_check;"
   ```

5. Restart service:
   ```bash
   kubectl scale deployment/knowledgebeast -n production --replicas=3
   ```

**Option B: Severe Corruption (Restore from Backup)**
1. **Identify Latest Good Backup**
   ```bash
   for backup in /backups/knowledgebeast.db.*; do
       echo "Checking $backup"
       sqlite3 $backup "PRAGMA integrity_check;"
   done

   # Find the most recent backup that passes integrity check
   ```

2. **Stop Application**
   ```bash
   kubectl scale deployment/knowledgebeast -n production --replicas=0
   ```

3. **Backup Corrupted Database (for investigation)**
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- \
     cp /data/knowledgebeast.db /data/corrupted_$(date +%Y%m%d_%H%M%S).db
   ```

4. **Restore from Backup**
   ```bash
   # Copy backup to primary location
   kubectl exec -n production deployment/knowledgebeast -- \
     cp /backups/knowledgebeast.db.20251008_0200 /data/knowledgebeast.db

   # Set correct permissions
   kubectl exec -n production deployment/knowledgebeast -- \
     chmod 644 /data/knowledgebeast.db
   ```

5. **Verify Restored Database**
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- \
     sqlite3 /data/knowledgebeast.db "
       PRAGMA integrity_check;
       SELECT COUNT(*) FROM projects;
       SELECT COUNT(*) FROM documents;
     "
   ```

6. **Restart Application**
   ```bash
   kubectl scale deployment/knowledgebeast -n production --replicas=3
   kubectl rollout status deployment/knowledgebeast -n production
   ```

7. **Verify Service Health**
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/api/v1/projects | jq '.projects | length'
   ```

**Option C: Partial Data Recovery**
If backup is old, attempt partial recovery:

1. **Export Uncorrupted Tables**
   ```bash
   sqlite3 /data/knowledgebeast.db ".mode insert" ".output recovery.sql" \
     "SELECT * FROM projects WHERE rowid IN (SELECT rowid FROM projects);"
   ```

2. **Create New Database**
   ```bash
   sqlite3 /data/knowledgebeast_new.db < schema.sql
   ```

3. **Import Recovered Data**
   ```bash
   sqlite3 /data/knowledgebeast_new.db < recovery.sql
   ```

4. **Merge with Backup**
   ```bash
   # Use application logic to merge recovered data with backup data
   python scripts/merge_databases.py \
     --backup /backups/knowledgebeast.db.20251008_0200 \
     --recovery /data/knowledgebeast_new.db \
     --output /data/knowledgebeast.db
   ```

### Data Loss Assessment

After restoration, quantify data loss:

```bash
# Compare document counts
current_docs=$(sqlite3 /data/knowledgebeast.db "SELECT COUNT(*) FROM documents;")
backup_docs=$(sqlite3 /backups/knowledgebeast.db.20251008_0200 "SELECT COUNT(*) FROM documents;")

lost_docs=$((current_docs - backup_docs))
echo "Documents lost: $lost_docs"

# Identify time range of lost data
sqlite3 /data/knowledgebeast.db "
  SELECT MIN(created_at), MAX(created_at)
  FROM documents
  WHERE id NOT IN (SELECT id FROM documents);
"
```

### Escalation Criteria
- Corruption affects > 10% of data
- No viable backup available (backup also corrupted)
- Recovery time exceeds 4 hours (RTO breach)
- Data loss exceeds 1 hour (RPO breach)

### Prevention

1. **Enable WAL Mode** (Write-Ahead Logging)
   ```sql
   PRAGMA journal_mode=WAL;
   ```
   - Better concurrency
   - Reduced corruption risk
   - Atomic commits

2. **Automated Hourly Backups**
   ```yaml
   apiVersion: batch/v1
   kind: CronJob
   metadata:
     name: db-backup
   spec:
     schedule: "0 * * * *"  # Every hour
     jobTemplate:
       spec:
         template:
           spec:
             containers:
             - name: backup
               image: knowledgebeast:latest
               command:
               - /bin/bash
               - -c
               - |
                 timestamp=$(date +%Y%m%d_%H%M%S)
                 sqlite3 /data/knowledgebeast.db ".backup /backups/knowledgebeast.db.$timestamp"
                 # Keep only last 7 days
                 find /backups -name "knowledgebeast.db.*" -mtime +7 -delete
   ```

3. **Regular Integrity Checks**
   ```yaml
   apiVersion: batch/v1
   kind: CronJob
   metadata:
     name: db-integrity-check
   spec:
     schedule: "*/30 * * * *"  # Every 30 minutes
     jobTemplate:
       spec:
         template:
           spec:
             containers:
             - name: integrity-check
               image: knowledgebeast:latest
               command:
               - /bin/bash
               - -c
               - |
                 result=$(sqlite3 /data/knowledgebeast.db "PRAGMA integrity_check;")
                 if [ "$result" != "ok" ]; then
                   echo "ALERT: Database integrity check failed: $result"
                   # Send alert to PagerDuty/Slack
                   exit 1
                 fi
   ```

4. **Replicated Database**
   - Use PostgreSQL instead of SQLite for production
   - Implement master-replica setup
   - Automatic failover on corruption

---

## Emergency Contact Information

### On-Call Rotation
- **PagerDuty**: https://knowledgebeast.pagerduty.com
- **Primary On-Call**: Check PagerDuty schedule
- **Secondary On-Call**: Check PagerDuty schedule

### Escalation Path
1. **On-Call Engineer** (0-15 minutes)
2. **Team Lead** (15-60 minutes)
3. **Engineering Manager** (1-4 hours)
4. **CTO** (> 4 hours or critical data loss)

### Key Resources
- **Grafana**: http://grafana.internal.knowledgebeast.com
- **Prometheus**: http://prometheus.internal.knowledgebeast.com
- **Jaeger (Tracing)**: http://jaeger.internal.knowledgebeast.com
- **Sentry (Errors)**: http://sentry.io/knowledgebeast
- **GitHub**: https://github.com/org/knowledgebeast
- **Documentation**: https://docs.knowledgebeast.com

### Communication Channels
- **Incident Channel**: #incidents (Slack)
- **On-Call Channel**: #on-call (Slack)
- **Status Page**: https://status.knowledgebeast.com

---

## Post-Incident Process

After resolving any incident:

1. **Update Status Page**
   - Mark incident as resolved
   - Provide brief summary of resolution

2. **Document Incident**
   ```markdown
   # Incident Report: [Title]

   **Date**: 2025-10-08
   **Severity**: P1
   **Duration**: 45 minutes
   **Impact**: 1,234 failed requests

   ## Timeline
   - 14:23 - Alert fired: High error rate
   - 14:25 - On-call paged
   - 14:30 - Investigation started
   - 14:45 - Root cause identified (bad deployment)
   - 14:50 - Rolled back to previous version
   - 15:08 - Incident resolved

   ## Root Cause
   Deployment v2.1.3 introduced a bug in input validation...

   ## Resolution
   Rolled back to v2.1.2...

   ## Action Items
   - [ ] Fix validation bug in v2.1.4
   - [ ] Add test coverage for this scenario
   - [ ] Improve canary deployment process
   ```

3. **Schedule Postmortem** (within 48 hours)
   - Blameless culture
   - Focus on systemic improvements
   - Identify action items

4. **Update Runbook**
   - Add new scenario if novel incident
   - Improve resolution steps based on learnings

---

## Revision History

| Version | Date       | Changes                                      |
|---------|------------|----------------------------------------------|
| 1.0     | 2025-10-08 | Initial runbook with 8 incident scenarios    |

**Maintained by**: SRE Team
**Review Frequency**: Quarterly
**Next Review**: 2026-01-08
