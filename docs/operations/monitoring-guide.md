# KnowledgeBeast Monitoring & Alerting Guide

## Overview

This guide provides comprehensive information on monitoring KnowledgeBeast production systems, interpreting metrics, and responding to alerts.

**Monitoring Stack**:
- **Prometheus**: Metrics collection and storage
- **Grafana**: Visualization and dashboards
- **Jaeger**: Distributed tracing
- **Alertmanager**: Alert routing and management

**Access**:
- Grafana: https://grafana.internal.knowledgebeast.com
- Prometheus: https://prometheus.internal.knowledgebeast.com
- Jaeger: https://jaeger.internal.knowledgebeast.com

---

## Table of Contents

1. [Dashboard Tour](#dashboard-tour)
2. [Key Metrics Explained](#key-metrics-explained)
3. [Alert Response Matrix](#alert-response-matrix)
4. [Troubleshooting Flowcharts](#troubleshooting-flowcharts)
5. [Metric Collection](#metric-collection)

---

## Dashboard Tour

### Main Dashboard: KnowledgeBeast Overview

**Location**: Grafana → Dashboards → KnowledgeBeast Overview

**Time Range**: Default 6 hours, adjustable

#### Panel 1: Service Status (Top Row)

**Visualization**: Stat panel
**Metrics Displayed**:
- Overall Status: 🟢 Healthy | 🟡 Degraded | 🔴 Unhealthy
- Uptime: 99.95%
- Active Requests: 1,234
- Request Rate: 456 req/s

**Interpretation**:
```
🟢 Healthy: All systems operational
  - Health endpoint: 200 OK
  - Error rate: < 0.1%
  - P99 latency: < 100ms
  - All dependencies: UP

🟡 Degraded: Some degradation, service still functional
  - CircuitBreaker: HALF_OPEN or OPEN (with fallback working)
  - Error rate: 0.1% - 1%
  - P99 latency: 100-500ms
  - Some dependencies: DOWN (graceful degradation active)

🔴 Unhealthy: Critical service issues
  - Health endpoint: non-200 status
  - Error rate: > 1%
  - P99 latency: > 500ms
  - Critical dependencies: DOWN (no fallback)
```

**Normal Patterns**:
- Uptime: > 99.9% monthly
- Request rate: 200-800 req/s (varies by time of day)
- Active requests: < 5,000 (healthy connection pool)

**Abnormal Patterns**:
- Uptime: < 99.9% (SLO breach)
- Request rate: sudden spike (> 2x baseline) or drop (< 50% baseline)
- Active requests: > 10,000 (connection leak or attack)

---

#### Panel 2: Query Latency Percentiles

**Visualization**: Time series line graph
**Metrics**: P50, P95, P99, P99.9
**Query**:
```promql
# P50
histogram_quantile(0.50, rate(kb_query_duration_seconds_bucket[5m])) * 1000

# P95
histogram_quantile(0.95, rate(kb_query_duration_seconds_bucket[5m])) * 1000

# P99
histogram_quantile(0.99, rate(kb_query_duration_seconds_bucket[5m])) * 1000

# P99.9
histogram_quantile(0.999, rate(kb_query_duration_seconds_bucket[5m])) * 1000
```

**Threshold Lines**:
- P50: 20ms (yellow), 50ms (red)
- P95: 50ms (yellow), 100ms (red)
- P99: 100ms (yellow), 150ms (red)

**Screenshot Example**:
```
P99 Latency Over Time
│
│      /\
│     /  \___           <- Spike at 14:30 (deployment)
│____/       \____
│
└──────────────────────> Time
10:00  12:00  14:00  16:00
```

**Interpretation**:

**Normal Pattern**:
- P50: 10-20ms (most queries are cached or simple)
- P95: 30-50ms (includes uncached queries)
- P99: 60-100ms (includes complex queries, cold cache)
- All percentiles relatively stable

**Abnormal Pattern: Sudden Spike**
```
Symptoms:
- P99 jumps from 80ms to 300ms
- P50 still normal (10-20ms)

Likely Causes:
- Cache eviction (cache hit ratio drop)
- Slow query introduced (check query logs)
- ChromaDB performance degradation
- Resource contention (CPU/memory)

Investigation:
1. Check cache hit ratio panel
2. Review slow query logs (see Troubleshooting)
3. Check ChromaDB panel for elevated latency
```

**Abnormal Pattern: Gradual Increase**
```
Symptoms:
- All percentiles slowly increasing over hours/days
- P50: 10ms → 30ms
- P99: 80ms → 200ms

Likely Causes:
- Memory leak (garbage collection pressure)
- Index fragmentation
- Disk I/O degradation
- Data growth without scaling

Investigation:
1. Check memory usage panel
2. Review disk I/O metrics
3. Check document count trend
```

---

#### Panel 3: Throughput (Requests Per Second)

**Visualization**: Time series area graph
**Metrics**: Total requests, successful requests, failed requests
**Query**:
```promql
# Total requests
sum(rate(http_requests_total[5m]))

# Successful (2xx)
sum(rate(http_requests_total{status=~"2.."}[5m]))

# Client errors (4xx)
sum(rate(http_requests_total{status=~"4.."}[5m]))

# Server errors (5xx)
sum(rate(http_requests_total{status=~"5.."}[5m]))
```

**Normal Patterns**:
- **Daily Cycle**: Higher during business hours (9 AM - 5 PM)
  - Peak: 800 req/s
  - Off-peak: 200 req/s
- **Weekly Cycle**: Lower on weekends
- **Steady Growth**: Gradual increase over months (user growth)

**Abnormal Patterns**:

**Traffic Spike**:
```
Symptoms:
- Sudden 5x-10x increase in request rate
- Example: 500 req/s → 5,000 req/s in minutes

Likely Causes:
- Marketing campaign launched
- API abuse / attack
- Retry storm (client-side bug)

Actions:
1. Check if spike is legitimate (new campaign?)
2. Review request patterns (single IP? single endpoint?)
3. Enable rate limiting if abuse detected
4. Scale horizontally if legitimate traffic
```

**Traffic Drop**:
```
Symptoms:
- Sudden 50%+ decrease in request rate
- Example: 500 req/s → 100 req/s

Likely Causes:
- Outage (users can't connect)
- DNS issue
- Load balancer misconfiguration
- Client-side outage

Actions:
1. Check health endpoint externally
2. Verify DNS resolution
3. Check load balancer logs
```

---

#### Panel 4: Error Rate

**Visualization**: Time series line graph (%)
**Metric**: Percentage of 5xx responses
**Query**:
```promql
sum(rate(http_requests_total{status=~"5.."}[5m])) /
sum(rate(http_requests_total[5m])) * 100
```

**Thresholds**:
- Green: < 0.1%
- Yellow: 0.1% - 1%
- Red: > 1%

**SLO Target**: < 0.1%

**Interpretation**:

**Normal State**: Error rate < 0.1%
- Occasional 5xx errors due to transient issues
- Example: 1 error per 1,000 requests

**Warning State**: Error rate 0.1% - 1%
- Degraded state, but most requests succeed
- Example: 5 errors per 1,000 requests
- **Action**: Investigate logs, identify error patterns

**Critical State**: Error rate > 1%
- Significant service degradation
- Example: 10+ errors per 1,000 requests
- **Action**: Immediate incident response, page on-call

**Common Error Patterns**:

```yaml
Pattern 1: Intermittent Spikes
- Error rate spikes to 5% for 1-2 minutes, then returns to normal
- Cause: Transient dependency failure (ChromaDB restart, network blip)
- Action: Monitor, retry logic should handle

Pattern 2: Sustained Elevation
- Error rate stays at 2-3% for extended period
- Cause: Partial service degradation (some pods failing)
- Action: Check pod health, restart failed pods

Pattern 3: Gradual Increase
- Error rate slowly climbs from 0.1% to 2% over hours
- Cause: Resource exhaustion, memory leak
- Action: Review resource metrics, consider restart
```

---

#### Panel 5: Cache Hit Ratio

**Visualization**: Gauge (0-100%)
**Metrics**: Query cache, embedding cache
**Query**:
```promql
# Query cache hit ratio
rate(kb_query_cache_hits_total[5m]) /
(rate(kb_query_cache_hits_total[5m]) + rate(kb_query_cache_misses_total[5m])) * 100

# Embedding cache hit ratio
rate(kb_embedding_cache_hits_total[5m]) /
(rate(kb_embedding_cache_hits_total[5m]) + rate(kb_embedding_cache_misses_total[5m])) * 100
```

**Thresholds**:
- Green: > 70%
- Yellow: 50-70%
- Red: < 50%

**Target**: > 80% for both caches

**Interpretation**:

**Excellent (> 90%)**:
- Most queries are cached
- Average query latency: < 10ms
- Minimal ChromaDB load

**Good (70-90%)**:
- Healthy cache utilization
- Average query latency: 20-30ms
- Normal ChromaDB load

**Poor (< 70%)**:
- Cache not effective
- Average query latency: > 50ms
- High ChromaDB load

**Why Cache Hit Ratio Drops**:

1. **Cache Size Too Small**
   - Evicting entries too quickly
   - Solution: Increase cache capacity

2. **High Query Diversity**
   - Users issuing unique queries (low repetition)
   - Solution: Focus on embedding cache instead

3. **Cache Recently Cleared**
   - Service restart, cache warmup needed
   - Solution: Automated cache warming

4. **Cache Key Strategy**
   - Poor cache key design (too specific)
   - Solution: Normalize queries for better hit rate

**Troubleshooting Low Cache Hit Ratio**: See [Troubleshooting Flowcharts](#troubleshooting-flowcharts)

---

#### Panel 6: ChromaDB Performance

**Visualization**: Time series line graph
**Metrics**: Query latency, collection sizes, query rate
**Query**:
```promql
# ChromaDB query latency (P99)
histogram_quantile(0.99, rate(kb_chromadb_query_duration_seconds_bucket[5m])) * 1000

# Collection sizes (documents per collection)
kb_chromadb_collection_size

# ChromaDB query rate
rate(kb_chromadb_queries_total[5m])
```

**Normal Patterns**:
- Query latency (P99): 20-50ms
- Collection sizes: Stable or slowly growing
- Query rate: Proportional to overall request rate

**Abnormal Patterns**:

**High Latency**:
```
Symptoms:
- ChromaDB P99 latency > 100ms

Causes:
- Large collections (> 1M vectors)
- Insufficient resources (CPU/memory)
- Network issues

Actions:
1. Check collection sizes (partition if needed)
2. Review ChromaDB pod resources
3. Consider ChromaDB scaling
```

**High Query Rate with Low Overall Traffic**:
```
Symptoms:
- ChromaDB query rate high but API request rate normal

Causes:
- Cache hit ratio drop (falling back to ChromaDB)
- Multi-query searches (fan-out)

Actions:
1. Check cache hit ratio
2. Review query patterns (fan-out queries?)
```

---

#### Panel 7: Active Projects and Documents

**Visualization**: Stat panel
**Metrics**: Total projects, total documents, documents per project
**Query**:
```promql
kb_projects_total
kb_documents_total
kb_documents_total / kb_projects_total  # Avg docs per project
```

**Normal Patterns**:
- Steady growth in projects and documents
- Avg docs per project: 100-10,000

**Abnormal Patterns**:

**Sudden Drop in Documents**:
```
Symptoms:
- kb_documents_total drops by 10%+

Causes:
- Mass deletion (user action or bug)
- Database corruption

Actions:
1. Check audit logs for deletions
2. Run database integrity check
3. Restore from backup if corruption
```

**Explosive Growth**:
```
Symptoms:
- Documents growing 10x faster than normal

Causes:
- Bulk import
- Duplicate document ingestion bug

Actions:
1. Verify legitimate bulk import
2. Check for duplicate documents
3. Monitor storage capacity
```

---

#### Panel 8: API Response Codes

**Visualization**: Pie chart
**Metrics**: Distribution of 2xx, 3xx, 4xx, 5xx responses
**Query**:
```promql
sum by (status) (rate(http_requests_total[5m]))
```

**Healthy Distribution**:
- 2xx (Success): > 95%
- 3xx (Redirect): < 1%
- 4xx (Client Error): 2-4%
- 5xx (Server Error): < 0.1%

**Abnormal Distributions**:

**High 4xx Rate (> 10%)**:
```
Causes:
- Input validation issues
- Authentication failures
- Resource not found (bad client requests)

Actions:
1. Review 4xx breakdown (400 vs 401 vs 404)
2. Check for API changes breaking clients
3. Improve input validation error messages
```

**High 5xx Rate (> 1%)**:
```
Causes:
- Service degradation
- Dependency failures

Actions:
1. Immediate investigation (see runbook)
2. Check service health
3. Review error logs
```

---

## Key Metrics Explained

### Latency Metrics

#### Why Percentiles Matter

**Average (Mean) Latency**: Misleading
```
Example:
- 95% of queries: 10ms
- 5% of queries: 1000ms
- Average: 59.5ms

Problem: Average suggests "good" but 5% of users experience terrible latency
```

**Percentile Latency**: User-centric
```
P50 (Median): 50% of queries faster, 50% slower
- P50 = 10ms means "half of users see < 10ms latency"

P99: 99% of queries faster, 1% slower
- P99 = 100ms means "99% of users see < 100ms latency"
- Only 1% of users experience > 100ms

P99.9: 99.9% of queries faster, 0.1% slower
- Catches the absolute worst-case scenarios
```

**Which Percentile to Focus On**:
- **P50**: Represents "typical" user experience
- **P95**: Good indicator of overall performance
- **P99**: What we promise in SLO (most important)
- **P99.9**: Edge cases, outliers

---

### Query Latency Breakdown

**Typical Query Components**:
```
Total Latency (P99: 80ms):
├── API Gateway (5ms)
├── Authentication/Authorization (2ms)
├── Query Parsing (1ms)
├── Embedding Generation (15ms)  <- Cached: 0ms, Uncached: 50ms
├── Vector Search (ChromaDB) (30ms)
├── Keyword Search (BM25) (10ms)
├── Result Ranking (5ms)
├── Response Serialization (2ms)
└── Network Transmission (10ms)
```

**Optimization Priorities**:
1. **Embedding Generation** (highest impact)
   - Cache embeddings: 50ms → 0ms
   - Use faster model: 50ms → 15ms

2. **Vector Search** (second highest)
   - Optimize ChromaDB settings: 30ms → 20ms
   - Partition large collections: 50ms → 30ms

3. **Keyword Search** (medium impact)
   - Already fast (10ms)
   - Limited optimization potential

---

### Cache Metrics Deep Dive

**Cache Hit Ratio Formula**:
```
Hit Ratio = Hits / (Hits + Misses) * 100%

Example:
- Hits: 900
- Misses: 100
- Hit Ratio: 900 / (900 + 100) * 100% = 90%
```

**Cache Performance Impact**:
```
Latency with cache hits vs misses:

Cache Hit:
- Embedding lookup: 0ms (cached)
- Total query latency: ~20ms

Cache Miss:
- Embedding generation: 50ms
- Total query latency: ~70ms

Impact of 90% vs 50% hit ratio:
- 90% hit ratio: 0.9 * 20ms + 0.1 * 70ms = 25ms avg
- 50% hit ratio: 0.5 * 20ms + 0.5 * 70ms = 45ms avg

80% improvement in average latency!
```

---

### Error Rate Calculation

**Error Rate Formula**:
```promql
Error Rate (%) = (5xx errors / total requests) * 100
```

**Error Budget Consumption**:
```
Monthly error budget: 0.1% (SLO)
= 43.2 minutes of errors (out of 30 days)
= 1.44 minutes per day

If error rate = 0.5% for 1 hour:
- Error budget consumed: 0.5% * 60 min * 0.1% / 100% = 18 minutes
- Remaining budget: 43.2 - 18 = 25.2 minutes
```

---

## Alert Response Matrix

### Critical Alerts (PagerDuty)

#### Alert: AvailabilitySLOBreach

**Trigger**: Monthly availability < 99.9%
**Severity**: Critical (P0)
**Page**: Yes

**Response Steps**:
1. Acknowledge alert in PagerDuty (< 5 minutes)
2. Join incident Slack channel #incidents
3. Check Grafana for outage timeframe
4. Identify root cause (see runbook)
5. Execute recovery procedure
6. Update status page every 30 minutes

**Escalation**: If not resolved in 1 hour, escalate to VP Engineering

---

#### Alert: HighErrorRate

**Trigger**: Error rate > 1% for 5 minutes
**Severity**: Critical (P0)
**Page**: Yes

**Response Steps**:
1. Acknowledge alert
2. Check error rate panel (is it still elevated?)
3. Review error logs:
   ```bash
   kubectl logs -n production deployment/knowledgebeast --tail=1000 | \
     jq 'select(.level=="ERROR")' | head -50
   ```
4. Identify error pattern:
   - All errors same type? (e.g., ChromaDB connection error)
   - Specific endpoint? (e.g., /api/v1/query)
5. Execute relevant runbook procedure
6. Monitor error rate for 15 minutes after mitigation

**Common Causes**:
- Bad deployment (rollback)
- ChromaDB failure (see Incident 2 in runbook)
- Database corruption (see Incident 8 in runbook)

---

#### Alert: P99LatencyCritical

**Trigger**: P99 latency > 500ms for 5 minutes
**Severity**: Critical (P1)
**Page**: Yes

**Response Steps**:
1. Acknowledge alert
2. Check latency panel (which percentiles affected?)
3. Check cache hit ratio (dropped?)
4. Check ChromaDB latency (elevated?)
5. Execute relevant runbook procedure (see Incident 1)
6. Monitor P99 latency after mitigation

**Troubleshooting Flowchart**: See [High Latency Diagnosis](#flowchart-1-high-latency-diagnosis)

---

#### Alert: ChromaDBDown

**Trigger**: ChromaDB health check fails
**Severity**: Critical (P0)
**Page**: Yes

**Response Steps**:
1. Acknowledge alert
2. Verify ChromaDB is actually down:
   ```bash
   kubectl get pods -n production | grep chromadb
   curl http://chromadb:8000/api/v1/heartbeat
   ```
3. Check if graceful degradation active:
   ```bash
   curl http://localhost:8000/api/v1/query/test?q=example | jq '.degraded_mode'
   ```
4. Execute runbook Incident 2 (ChromaDB Unreachable)
5. Verify recovery:
   ```bash
   curl http://localhost:8000/health | jq '.components.chromadb.status'
   ```

---

### Warning Alerts (Slack)

#### Alert: LatencySLOWarning

**Trigger**: P99 latency > 80ms for 10 minutes
**Severity**: Warning (P2)
**Page**: No (Slack only)

**Response Steps**:
1. Review latency trend (increasing or stable?)
2. Check cache hit ratio
3. Check recent deployments (potential regression?)
4. If stable at 80-100ms: Monitor, no immediate action
5. If increasing: Investigate proactively (prevent critical alert)

---

#### Alert: CacheHitRatioLow

**Trigger**: Cache hit ratio < 70% for 30 minutes
**Severity**: Warning (P2)
**Page**: No

**Response Steps**:
1. Check cache configuration (size, eviction policy)
2. Review query diversity (unique queries?)
3. Warm cache if needed:
   ```bash
   python scripts/warm_cache.py --project all --top-queries 1000
   ```
4. Consider increasing cache size if consistently low

**Troubleshooting Flowchart**: See [Low Cache Hit Ratio](#flowchart-2-low-cache-hit-ratio)

---

#### Alert: DiskSpaceWarning

**Trigger**: Disk usage > 80%
**Severity**: Warning (P2)
**Page**: No

**Response Steps**:
1. Check disk usage breakdown:
   ```bash
   kubectl exec -n production deployment/knowledgebeast -- du -sh /data/*
   ```
2. Identify largest consumers (logs, backups, data)
3. Execute cleanup if safe:
   ```bash
   /scripts/cleanup_disk.sh
   ```
4. Plan for disk expansion if growth trend continues

---

## Troubleshooting Flowcharts

### Flowchart 1: High Latency Diagnosis

```
┌─────────────────────────┐
│ P99 Latency > 100ms?    │
└─────────┬───────────────┘
          │ Yes
          ▼
┌─────────────────────────┐
│ Check Cache Hit Ratio   │
└─────────┬───────────────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
  < 50%       > 70%
    │           │
    │           └─────────────┐
    ▼                         ▼
┌─────────────────────────┐  ┌─────────────────────────┐
│ Cache Issue             │  │ Check ChromaDB Latency  │
│ - Warm cache            │  └─────────┬───────────────┘
│ - Increase capacity     │            │
│ - Review key strategy   │      ┌─────┴─────┐
└─────────────────────────┘      │           │
                                 ▼           ▼
                               > 50ms      < 30ms
                                 │           │
                                 ▼           ▼
                        ┌─────────────────────────┐  ┌─────────────────────────┐
                        │ ChromaDB Issue          │  │ Check Resource Usage    │
                        │ - Restart ChromaDB      │  │ - CPU > 80%?            │
                        │ - Check collection size │  │ - Memory > 90%?         │
                        │ - Scale horizontally    │  │ - Disk I/O saturated?   │
                        └─────────────────────────┘  └─────────┬───────────────┘
                                                               │
                                                               ▼
                                                     ┌─────────────────────────┐
                                                     │ Resource Issue          │
                                                     │ - Scale pods            │
                                                     │ - Check for memory leak │
                                                     │ - Optimize queries      │
                                                     └─────────────────────────┘
```

---

### Flowchart 2: Low Cache Hit Ratio

```
┌─────────────────────────┐
│ Cache Hit Ratio < 70%?  │
└─────────┬───────────────┘
          │ Yes
          ▼
┌─────────────────────────┐
│ Check Cache Size        │
└─────────┬───────────────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
  Small       Large
  < 500       > 1000
    │           │
    ▼           └─────────────┐
┌─────────────────────────┐  │
│ Increase Cache Size     │  │
│ QUERY_CACHE_SIZE=1000   │  │
└─────────────────────────┘  │
                             ▼
                   ┌─────────────────────────┐
                   │ Check Query Diversity   │
                   └─────────┬───────────────┘
                             │
                       ┌─────┴─────┐
                       │           │
                       ▼           ▼
                     High        Low
                   > 80% unique  < 30% unique
                       │           │
                       ▼           ▼
            ┌─────────────────────────┐  ┌─────────────────────────┐
            │ Fundamental Limitation  │  │ Cache Key Issue         │
            │ - Focus on embedding    │  │ - Normalize queries     │
            │   cache instead         │  │ - Remove timestamp      │
            │ - Accept lower ratio    │  │   from cache key        │
            └─────────────────────────┘  └─────────────────────────┘
```

---

### Flowchart 3: Search Quality Degradation

```
┌─────────────────────────┐
│ NDCG@10 < 0.85?         │
└─────────┬───────────────┘
          │ Yes
          ▼
┌─────────────────────────┐
│ Check Recent Changes    │
│ - Model updated?        │
│ - Algorithm changed?    │
│ - Index rebuilt?        │
└─────────┬───────────────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
  Yes         No
    │           │
    ▼           └─────────────┐
┌─────────────────────────┐  │
│ Rollback Change         │  │
│ - Revert to prev model  │  │
│ - Restore prev algo     │  │
└─────────────────────────┘  │
                             ▼
                   ┌─────────────────────────┐
                   │ Check Data Quality      │
                   └─────────┬───────────────┘
                             │
                       ┌─────┴─────┐
                       │           │
                       ▼           ▼
                   Corrupted    Clean
                       │           │
                       ▼           ▼
            ┌─────────────────────────┐  ┌─────────────────────────┐
            │ Data Corruption         │  │ Gradual Drift           │
            │ - Run integrity check   │  │ - Retrain model         │
            │ - Restore from backup   │  │ - Update relevance      │
            │ - Rebuild index         │  │   judgments             │
            └─────────────────────────┘  └─────────────────────────┘
```

---

## Metric Collection

### Prometheus Scrape Configuration

**File**: `deployments/prometheus/prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'knowledgebeast-prod'
    region: 'us-east-1'

scrape_configs:
  - job_name: 'knowledgebeast'
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          names:
            - production
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        regex: knowledgebeast
        action: keep
      - source_labels: [__meta_kubernetes_pod_name]
        target_label: pod
      - source_labels: [__meta_kubernetes_namespace]
        target_label: namespace
    metrics_path: '/metrics'
    scrape_interval: 10s

  - job_name: 'chromadb'
    static_configs:
      - targets: ['chromadb:8000']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

---

### Custom Metrics

**File**: `knowledgebeast/utils/metrics.py`

```python
from prometheus_client import Counter, Histogram, Gauge

# Query metrics
query_duration = Histogram(
    'kb_query_duration_seconds',
    'Query latency in seconds',
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
)

# Cache metrics
cache_hits = Counter('kb_query_cache_hits_total', 'Query cache hits')
cache_misses = Counter('kb_query_cache_misses_total', 'Query cache misses')

# System metrics
active_projects = Gauge('kb_projects_total', 'Total number of active projects')
total_documents = Gauge('kb_documents_total', 'Total number of indexed documents')

# ChromaDB metrics
chromadb_query_duration = Histogram(
    'kb_chromadb_query_duration_seconds',
    'ChromaDB query latency',
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2]
)

# Usage example
def query(search_terms: str):
    with query_duration.time():
        # ... query logic ...
        if cached:
            cache_hits.inc()
        else:
            cache_misses.inc()
        return results
```

---

## Appendix: Useful Prometheus Queries

### Service Health
```promql
# Overall uptime (last 30 days)
avg_over_time(up{job="knowledgebeast"}[30d]) * 100

# Current request rate
sum(rate(http_requests_total[5m]))

# Success rate
sum(rate(http_requests_total{status=~"2.."}[5m])) /
sum(rate(http_requests_total[5m])) * 100
```

### Latency Analysis
```promql
# P99 latency by endpoint
histogram_quantile(0.99,
  sum by (path, le) (rate(kb_query_duration_seconds_bucket[5m]))
)

# Latency distribution
sum by (le) (rate(kb_query_duration_seconds_bucket[5m]))
```

### Cache Performance
```promql
# Cache hit ratio over time
rate(kb_query_cache_hits_total[5m]) /
(rate(kb_query_cache_hits_total[5m]) + rate(kb_query_cache_misses_total[5m])) * 100

# Cache eviction rate
rate(kb_cache_evictions_total[5m])
```

### Resource Usage
```promql
# Memory usage
container_memory_usage_bytes{pod=~"knowledgebeast.*"} / 1024^3

# CPU usage
rate(container_cpu_usage_seconds_total{pod=~"knowledgebeast.*"}[5m])

# Disk usage
(1 - node_filesystem_avail_bytes / node_filesystem_size_bytes) * 100
```

---

## Revision History

| Version | Date       | Changes                                   |
|---------|------------|-------------------------------------------|
| 1.0     | 2025-10-08 | Initial monitoring and alerting guide     |

**Maintained by**: SRE Team
**Review Frequency**: Quarterly
**Next Review**: 2026-01-08
