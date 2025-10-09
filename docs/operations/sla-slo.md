# KnowledgeBeast SLA & SLO Definitions

## Overview

This document defines Service Level Agreements (SLAs), Service Level Objectives (SLOs), and Service Level Indicators (SLIs) for KnowledgeBeast production environments.

**Effective Date**: 2025-10-08
**Review Frequency**: Quarterly
**Owner**: SRE Team

---

## Service Level Objectives (SLOs)

### 1. Availability SLO

**Target**: 99.9% monthly uptime (Three Nines)

**Measurement**:
```
Availability = (Total Time - Downtime) / Total Time × 100%
```

**Allowed Downtime**:
- **Monthly**: 43.2 minutes (30 days × 24 hours × 60 minutes × 0.001)
- **Weekly**: 10.08 minutes
- **Daily**: 1.44 minutes

**Definition of Downtime**:
- `/health` endpoint returns non-200 status code
- P99 latency > 5 seconds (effectively unusable)
- Error rate > 50%

**Exclusions** (not counted as downtime):
- Scheduled maintenance windows (announced 7 days in advance)
- Client-side errors (4xx responses except 429 rate limiting)
- Third-party service outages beyond our control

**Measurement Method**:
```promql
# Prometheus query for availability
avg_over_time(up{job="knowledgebeast"}[30d]) * 100
```

**Dashboard**: Grafana → KnowledgeBeast Overview → Availability Panel

---

### 2. Query Latency SLO

**Targets**:
- **P50 (Median)**: < 20ms
- **P95**: < 50ms
- **P99**: < 100ms
- **P99.9**: < 500ms

**Measurement**:
```promql
# Prometheus query
histogram_quantile(0.99,
  rate(kb_query_duration_seconds_bucket[5m])
) * 1000  # Convert to milliseconds
```

**Scope**:
- Applies to `/api/v1/query/*` endpoints
- Measured from API gateway to response
- Includes:
  - Query parsing
  - Embedding generation (if query cache miss)
  - Vector search
  - Keyword search (BM25)
  - Result ranking and formatting

**Exclusions**:
- Document ingestion operations (different SLO)
- Administrative operations
- Bulk export operations

**Breakdown by Operation Type**:

| Operation           | P50    | P95    | P99    |
|---------------------|--------|--------|--------|
| Cached Query        | < 5ms  | < 10ms | < 20ms |
| Uncached Query      | < 30ms | < 60ms | < 150ms |
| Hybrid Search       | < 40ms | < 80ms | < 200ms |
| Multi-Project Query | < 50ms | < 100ms | < 250ms |

---

### 3. Error Rate SLO

**Target**: < 0.1% (1 error per 1,000 requests)

**Measurement**:
```promql
# Prometheus query
sum(rate(http_requests_total{status=~"5.."}[5m])) /
sum(rate(http_requests_total[5m])) * 100
```

**Error Classification**:

**Counted as Errors** (impact SLO):
- 5xx server errors
- 429 rate limiting (our capacity issue)
- Timeouts (> 30 seconds)
- Circuit breaker open (service degraded)

**Not Counted as Errors** (client issues):
- 400 Bad Request (invalid input)
- 401 Unauthorized (bad credentials)
- 403 Forbidden (permissions)
- 404 Not Found (non-existent resource)

**Error Budget**:
- **Monthly**: 43,200 errors (assuming 1M requests/month)
- If budget exhausted: Feature freeze, focus on reliability

---

### 4. Search Quality SLO

**Target**: NDCG@10 > 0.90 (Normalized Discounted Cumulative Gain)

**Measurement**:
- Automated evaluation dataset: 1,000 queries with relevance judgments
- Run weekly: Compare actual ranking vs. ideal ranking
- Formula:
  ```
  NDCG@k = DCG@k / IDCG@k

  DCG@k = Σ(i=1 to k) (2^rel_i - 1) / log2(i + 1)
  ```

**Evaluation Process**:
```python
# Weekly automated evaluation
from sklearn.metrics import ndcg_score

# Load test dataset
test_queries = load_test_dataset()  # 1,000 queries

ndcg_scores = []
for query, relevant_docs in test_queries:
    results = kb.query(query, top_k=10)
    predicted_relevance = [score for _, score in results]
    true_relevance = [relevant_docs.get(doc_id, 0) for doc_id, _ in results]

    ndcg = ndcg_score([true_relevance], [predicted_relevance], k=10)
    ndcg_scores.append(ndcg)

avg_ndcg = sum(ndcg_scores) / len(ndcg_scores)
print(f"NDCG@10: {avg_ndcg:.4f}")
```

**Alerting**:
- WARNING: NDCG@10 < 0.85 for 2 consecutive weeks
- CRITICAL: NDCG@10 < 0.80

**Degradation Scenarios**:
- Embedding model change without proper testing
- Index corruption
- Algorithm bug introduced

---

### 5. Document Ingestion SLO

**Targets**:
- **Throughput**: > 100 documents/second (sustained)
- **Latency (P99)**: < 5 seconds per document
- **Success Rate**: > 99.5%

**Measurement**:
```promql
# Throughput
rate(kb_documents_ingested_total[5m])

# Latency
histogram_quantile(0.99,
  rate(kb_ingestion_duration_seconds_bucket[5m])
)

# Success rate
sum(rate(kb_ingestion_success_total[5m])) /
sum(rate(kb_ingestion_attempts_total[5m])) * 100
```

**Scope**:
- Single document ingestion
- Batch ingestion (averaged per document)
- All document types (Markdown, PDF, DOCX, etc.)

**Exclusions**:
- Extremely large documents (> 100MB)
- Network transfer time (measured from API request received)

---

### 6. Cache Performance SLO

**Targets**:
- **Query Cache Hit Ratio**: > 70%
- **Embedding Cache Hit Ratio**: > 80%
- **Cache Lookup Latency (P99)**: < 5ms

**Measurement**:
```promql
# Query cache hit ratio
kb_query_cache_hits_total /
(kb_query_cache_hits_total + kb_query_cache_misses_total) * 100

# Embedding cache hit ratio
kb_embedding_cache_hits_total /
(kb_embedding_cache_hits_total + kb_embedding_cache_misses_total) * 100
```

**Impact**:
- Cache hit ratio directly impacts overall query latency
- 90% cache hit ratio → ~10ms average query latency
- 50% cache hit ratio → ~50ms average query latency

---

## Service Level Agreements (SLAs)

### Customer-Facing Commitments

#### 1. Availability SLA

**Commitment**: 99.9% monthly uptime

**Credits for Breaches**:
- 99.0% - 99.9%: 10% service credit
- 95.0% - 99.0%: 25% service credit
- < 95.0%: 50% service credit

**Claim Process**:
- Customer submits claim within 30 days of incident
- SRE team validates with monitoring data
- Credit applied to next billing cycle

---

#### 2. Incident Response SLA

**Commitments**:

| Severity | Initial Response | Status Updates | Resolution Target |
|----------|------------------|----------------|-------------------|
| P0 (Critical) | < 15 minutes | Every 30 minutes | < 4 hours |
| P1 (High) | < 1 hour | Every 2 hours | < 24 hours |
| P2 (Medium) | < 4 hours | Daily | < 7 days |
| P3 (Low) | < 24 hours | Weekly | < 30 days |

**Initial Response** includes:
- Acknowledgment of issue
- Assigned incident commander
- Preliminary assessment

**Status Updates** include:
- Current status
- Progress made
- Next steps
- Revised ETA if needed

---

#### 3. Data Retention SLA

**Commitments**:
- **Primary Data**: Indefinite retention (until customer deletion)
- **Backups**: 30-day retention
- **Logs**: 90-day retention
- **Metrics**: 1-year retention

**Data Deletion**:
- Soft delete: Data marked as deleted, retained 30 days
- Hard delete: Data permanently removed after 30-day grace period
- Customer can request immediate hard delete (compliance)

---

#### 4. Data Recovery SLA

**Commitments**:
- **Recovery Point Objective (RPO)**: < 1 hour
- **Recovery Time Objective (RTO)**: < 4 hours

**Scope**:
- Accidental deletions
- Database corruption
- System failures
- Data center outages

**Process**:
- Customer requests recovery (ticket or call)
- SRE team initiates recovery from backup
- Validation and verification
- Data restored to production

---

## Service Level Indicators (SLIs)

### Key Metrics for SLO Tracking

#### 1. Uptime
**Metric**: `up{job="knowledgebeast"}`
**Type**: Gauge (0 or 1)
**Frequency**: 10 second scrape interval

#### 2. Request Latency
**Metric**: `kb_query_duration_seconds`
**Type**: Histogram
**Buckets**: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]

#### 3. Request Rate
**Metric**: `http_requests_total`
**Type**: Counter
**Labels**: `method`, `path`, `status`

#### 4. Error Rate
**Metric**: `http_requests_total{status=~"5.."}`
**Type**: Counter
**Calculation**: Errors / Total Requests

#### 5. Cache Hit Ratio
**Metrics**:
- `kb_query_cache_hits_total` (counter)
- `kb_query_cache_misses_total` (counter)
**Calculation**: Hits / (Hits + Misses)

#### 6. Search Quality
**Metric**: `kb_ndcg_score` (custom gauge, updated weekly)
**Type**: Gauge
**Range**: 0.0 - 1.0

---

## Error Budget

### Concept

Error budget = (1 - SLO) × Total Time

**Example**:
- SLO: 99.9% availability
- Error budget: 0.1% = 43.2 minutes/month
- This is our "allowed" downtime

### Error Budget Policy

**100% - 90% Budget Remaining** (0-4.32 minutes used):
- ✅ Ship new features aggressively
- ✅ Experiment with new technologies
- ✅ Tolerate some risk

**90% - 50% Budget Remaining** (4.32-21.6 minutes used):
- ⚠️ Slow down feature velocity
- ⚠️ Increase testing rigor
- ⚠️ Review incident trends

**50% - 0% Budget Remaining** (21.6-43.2 minutes used):
- 🚨 **FEATURE FREEZE**
- 🚨 Focus exclusively on reliability
- 🚨 Require VP approval for any non-reliability work
- 🚨 Daily incident reviews

**Budget Exhausted** (> 43.2 minutes):
- 🔥 **CRITICAL STATE**
- 🔥 All hands on deck for reliability
- 🔥 Executive incident review
- 🔥 Postmortem required
- 🔥 No new features until budget replenishes next month

### Error Budget Burn Rate

**Fast Burn** (budget consumed in < 7 days):
- Alert: "Error budget will be exhausted in X days"
- Action: Immediate incident investigation
- Escalate to VP Engineering

**Slow Burn** (budget consumed over full month):
- Normal operational state
- Continue with planned work

**Tracking**:
```promql
# Error budget remaining (percentage)
(1 - (
  (30 * 24 * 60 - sum(up{job="knowledgebeast"} == 0)) /
  (30 * 24 * 60)
)) / 0.001 * 100

# Expected: 0-100%
# < 0% = budget exhausted
```

---

## SLO Dashboard

### Grafana Panels

**Panel 1: Availability (Past 30 Days)**
```promql
avg_over_time(up{job="knowledgebeast"}[30d]) * 100
```
- Gauge visualization
- Green: > 99.9%
- Yellow: 99.0% - 99.9%
- Red: < 99.0%

**Panel 2: Query Latency Percentiles**
```promql
# P50
histogram_quantile(0.50, rate(kb_query_duration_seconds_bucket[5m]))

# P95
histogram_quantile(0.95, rate(kb_query_duration_seconds_bucket[5m]))

# P99
histogram_quantile(0.99, rate(kb_query_duration_seconds_bucket[5m]))
```
- Time series line graph
- Threshold lines at 20ms (P50), 50ms (P95), 100ms (P99)

**Panel 3: Error Rate (Past 24 Hours)**
```promql
sum(rate(http_requests_total{status=~"5.."}[5m])) /
sum(rate(http_requests_total[5m])) * 100
```
- Time series area graph
- Threshold line at 0.1%

**Panel 4: Error Budget Remaining**
```promql
(43.2 - sum(increase(up{job="knowledgebeast"} == 0)[30d:1m]) / 60) / 43.2 * 100
```
- Gauge visualization
- Shows percentage of budget remaining

**Panel 5: Cache Hit Ratio**
```promql
rate(kb_query_cache_hits_total[5m]) /
(rate(kb_query_cache_hits_total[5m]) + rate(kb_query_cache_misses_total[5m])) * 100
```
- Gauge visualization
- Threshold at 70%

---

## SLO Review Process

### Weekly SLO Review

**Every Monday 10:00 AM**

Agenda:
1. Review past week's SLO performance
2. Identify any SLO breaches
3. Discuss error budget burn rate
4. Review incidents and their impact
5. Assign action items

Attendees:
- SRE Team Lead
- Engineering Manager
- On-Call Engineer (rotating)

Output:
- Weekly SLO report (Slack #slo-reports)
- Action items tracked in Jira

---

### Monthly SLO Report

**First Friday of Each Month**

Report Contents:
1. **Executive Summary**
   - Overall SLO compliance: ✅ or ❌
   - Error budget status: X% remaining
   - Key wins and challenges

2. **Detailed Metrics**
   - Availability: 99.95% (✅ exceeds 99.9% target)
   - P99 Latency: 85ms (✅ under 100ms target)
   - Error Rate: 0.08% (✅ under 0.1% target)
   - Search Quality (NDCG@10): 0.92 (✅ exceeds 0.90 target)

3. **Incidents Summary**
   - Total incidents: 3 (2 P2, 1 P3)
   - Total downtime: 12.5 minutes (28.9% of budget)
   - Mean Time to Recovery (MTTR): 25 minutes

4. **Trends**
   - Availability trend: ↑ improving
   - Latency trend: → stable
   - Error rate trend: ↓ decreasing

5. **Action Items**
   - [ ] Reduce cache miss latency (target: 30ms → 20ms)
   - [ ] Implement automated canary deployments
   - [ ] Add redundancy for ChromaDB

Distribution:
- Engineering team
- Product Management
- Executive leadership

---

## SLO Alerting

### Alert Rules

**Critical Alerts** (PagerDuty):

```yaml
# availability-critical.yaml
- alert: AvailabilitySLOBreach
  expr: |
    avg_over_time(up{job="knowledgebeast"}[30d]) < 0.999
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Availability SLO breached ({{ $value }}%)"
    description: "Monthly availability is {{ $value }}%, below 99.9% target"

- alert: ErrorBudgetCritical
  expr: |
    error_budget_remaining_percent < 10
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Error budget critical: {{ $value }}% remaining"
    description: "Only {{ $value }}% of error budget remains this month"
```

**Warning Alerts** (Slack):

```yaml
- alert: LatencySLOWarning
  expr: |
    histogram_quantile(0.99,
      rate(kb_query_duration_seconds_bucket[5m])
    ) > 0.080  # 80ms (warning at 80% of 100ms target)
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "P99 latency elevated: {{ $value }}s"
    description: "P99 latency is {{ $value }}s, approaching 100ms SLO"

- alert: CacheHitRatioLow
  expr: |
    rate(kb_query_cache_hits_total[5m]) /
    (rate(kb_query_cache_hits_total[5m]) + rate(kb_query_cache_misses_total[5m])) < 0.70
  for: 30m
  labels:
    severity: warning
  annotations:
    summary: "Cache hit ratio low: {{ $value }}%"
```

---

## Appendix: SLO Calculation Examples

### Example 1: Monthly Availability

**Scenario**: Service was down for 60 minutes in September

```
Total time in September: 30 days × 24 hours × 60 minutes = 43,200 minutes
Downtime: 60 minutes
Uptime: 43,200 - 60 = 43,140 minutes

Availability = 43,140 / 43,200 = 0.998611 = 99.86%
```

**Result**: ❌ SLO breach (< 99.9%)
**Impact**: Error budget exceeded by 16.8 minutes
**Action**: Feature freeze, focus on reliability

---

### Example 2: Error Rate

**Scenario**: 1,000,000 requests in a day, 500 returned 5xx errors

```
Error rate = 500 / 1,000,000 = 0.0005 = 0.05%
```

**Result**: ✅ SLO met (< 0.1%)
**Remaining error budget**: 0.1% - 0.05% = 0.05% (500 more errors allowed)

---

### Example 3: P99 Latency

**Scenario**: Latency distribution for 1,000 queries

```
Sorted latencies: [5ms, 8ms, 10ms, ..., 95ms, 120ms, 150ms]
P99 = 99th percentile = latency of 990th request = 95ms
```

**Result**: ✅ SLO met (< 100ms)

---

## Revision History

| Version | Date       | Changes                                   |
|---------|------------|-------------------------------------------|
| 1.0     | 2025-10-08 | Initial SLA/SLO definitions               |

**Maintained by**: SRE Team
**Review Frequency**: Quarterly
**Next Review**: 2026-01-08
