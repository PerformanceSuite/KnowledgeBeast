# KnowledgeBeast Observability Stack

Production-ready Grafana dashboards, Prometheus monitoring, and distributed tracing for KnowledgeBeast.

## Quick Start

### 1. Start the Observability Stack

```bash
cd deployments
docker-compose -f docker-compose.observability.yml up -d
```

### 2. Access the Services

- **Grafana Dashboard**: http://localhost:3000
  - Username: `admin`
  - Password: `admin123` (change in production!)

- **Prometheus**: http://localhost:9090

- **Jaeger Tracing**: http://localhost:16686

- **Node Exporter**: http://localhost:9100/metrics

### 3. View the KnowledgeBeast Dashboard

Once Grafana is running:
1. Navigate to http://localhost:3000
2. Go to **Dashboards** → **KnowledgeBeast** folder
3. Open **KnowledgeBeast Overview** dashboard

The dashboard will automatically load with:
- 8 pre-configured panels
- 30-second auto-refresh
- Last 6 hours time range (configurable)

## Dashboard Panels

### Panel 1: Query Latency (P50, P95, P99)
- **Type**: Time series line graph
- **Metrics**: Query latency percentiles (P50, P95, P99)
- **Thresholds**:
  - Yellow: > 100ms
  - Red: > 500ms
- **Use Case**: Monitor query performance and identify slow queries

### Panel 2: Throughput (queries/sec)
- **Type**: Time series line graph
- **Metrics**: Request rate
- **Use Case**: Track system load and usage patterns

### Panel 3: Cache Hit Ratio (%)
- **Type**: Gauge
- **Range**: 0-100%
- **Thresholds**:
  - Red: < 50%
  - Yellow: 50-80%
  - Green: > 80%
- **Use Case**: Monitor cache effectiveness

### Panel 4: Active Projects
- **Type**: Stat panel
- **Metrics**: Count of active projects
- **Use Case**: Track system utilization

### Panel 5: Vector Search Performance
- **Type**: Heatmap
- **Metrics**: Vector search latency distribution
- **Use Case**: Identify ChromaDB performance patterns

### Panel 6: Error Rate (errors/sec)
- **Type**: Time series line graph
- **Metrics**: Error rate over time
- **Thresholds**:
  - Yellow: > 0.01 errors/sec
  - Red: > 0.1 errors/sec
- **Use Case**: Detect system errors and failures

### Panel 7: ChromaDB Collection Sizes
- **Type**: Bar chart
- **Metrics**: Document count per collection
- **Use Case**: Track vector database growth

### Panel 8: API Response Codes (2xx, 4xx, 5xx)
- **Type**: Pie chart
- **Metrics**: HTTP response code distribution
- **Colors**:
  - Green: 2xx (success)
  - Yellow: 4xx (client errors)
  - Red: 5xx (server errors)
- **Use Case**: Monitor API health

## Prometheus Alerts

### Performance Alerts

#### HighLatency_Warning
- **Trigger**: P99 latency > 150ms for 5 minutes
- **Severity**: Warning
- **Action**: Investigate query performance

#### HighLatency_Critical
- **Trigger**: P99 latency > 500ms for 2 minutes
- **Severity**: Critical
- **Action**: Immediate investigation required

#### HighErrorRate
- **Trigger**: Error rate > 1% for 5 minutes
- **Severity**: Warning
- **Action**: Check logs and recent deployments

### Infrastructure Alerts

#### ChromaDBDown
- **Trigger**: ChromaDB unreachable
- **Severity**: Critical
- **Action**: Restart ChromaDB service

#### APIServerDown
- **Trigger**: API server unreachable for 1 minute
- **Severity**: Critical
- **Action**: Restart API server

#### High5xxErrorRate
- **Trigger**: 5xx error rate > 5% for 3 minutes
- **Severity**: Critical
- **Action**: Check backend services and logs

### Resource Alerts

#### DiskSpaceWarning
- **Trigger**: Available disk space < 10GB
- **Severity**: Warning
- **Action**: Plan for capacity expansion

#### DiskSpaceCritical
- **Trigger**: Available disk space < 5GB
- **Severity**: Critical
- **Action**: Free up space immediately

#### LowCacheHitRatio
- **Trigger**: Cache hit ratio < 50% for 10 minutes
- **Severity**: Warning
- **Action**: Review cache configuration

### Vector Search Alerts

#### VectorSearchLatencyHigh
- **Trigger**: P95 vector search latency > 200ms for 5 minutes
- **Severity**: Warning
- **Action**: Check ChromaDB performance

## Configuration Files

### Prometheus Configuration
- **File**: `prometheus/prometheus.yml`
- **Features**:
  - 15-second scrape interval
  - 30-day data retention
  - Alert rule evaluation
  - WAL compression enabled

### Alert Rules
- **File**: `prometheus/alerts.yml`
- **Alert Groups**:
  - `knowledgebeast_performance` - Latency and error alerts
  - `knowledgebeast_infrastructure` - Service health alerts
  - `knowledgebeast_resources` - Resource utilization alerts
  - `knowledgebeast_availability` - Uptime alerts
  - `knowledgebeast_vector_search` - Vector search performance alerts

### Grafana Datasources
- **File**: `grafana/datasources/prometheus.yml`
- **Configured Datasources**:
  - Prometheus (default)
  - Jaeger (distributed tracing)

### Dashboard Provisioning
- **File**: `grafana/provisioning/dashboards/default.yml`
- **Features**:
  - Auto-provisioning on startup
  - 30-second update interval
  - UI updates allowed

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Docker Compose Stack                    │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │   Grafana    │───▶│  Prometheus  │───▶│ KB API    │ │
│  │   :3000      │    │    :9090     │    │   :8000   │ │
│  └──────────────┘    └──────────────┘    └───────────┘ │
│         │                    │                   │       │
│         │                    │                   │       │
│         ▼                    ▼                   ▼       │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │  Dashboards  │    │ Alert Rules  │    │  Metrics  │ │
│  │   (JSON)     │    │   (YAML)     │    │  (/metrics│ │
│  └──────────────┘    └──────────────┘    └───────────┘ │
│                                                           │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │   Jaeger     │    │Node Exporter │                   │
│  │  :16686      │    │    :9100     │                   │
│  └──────────────┘    └──────────────┘                   │
│                                                           │
│  Network: knowledgebeast-observability                   │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

## Data Persistence

All data is persisted in Docker volumes:

- `knowledgebeast-prometheus-data`: Prometheus time-series data (30-day retention)
- `knowledgebeast-grafana-data`: Grafana dashboards and settings
- `knowledgebeast-jaeger-data`: Jaeger trace data

## Customization

### Changing Auto-Refresh Interval

Edit `knowledgebeast-overview.json`:
```json
{
  "refresh": "30s"  // Change to "1m", "5m", etc.
}
```

### Changing Data Retention

Edit `prometheus/prometheus.yml`:
```yaml
storage:
  tsdb:
    retention.time: 30d  # Change to 7d, 90d, etc.
```

### Adding New Panels

1. Edit `grafana/dashboards/knowledgebeast-overview.json`
2. Add new panel configuration
3. Restart Grafana: `docker-compose restart grafana`

### Adding New Alerts

1. Edit `prometheus/alerts.yml`
2. Add new alert rule under appropriate group
3. Reload Prometheus: `docker-compose exec prometheus kill -HUP 1`

## Troubleshooting

### Grafana Dashboard Not Loading

```bash
# Check Grafana logs
docker-compose logs grafana

# Restart Grafana
docker-compose restart grafana
```

### Prometheus Not Scraping Metrics

```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Verify KB API is exposing metrics
curl http://localhost:8000/metrics
```

### No Data in Panels

1. Verify KnowledgeBeast API is running
2. Check Prometheus is scraping: http://localhost:9090/targets
3. Verify datasource in Grafana: Configuration → Data Sources

### Alerts Not Firing

```bash
# Check alert rules
curl http://localhost:9090/api/v1/rules

# Check alert status
curl http://localhost:9090/api/v1/alerts
```

## Production Deployment

### Security Hardening

1. **Change default passwords**:
   ```yaml
   # In docker-compose.observability.yml
   environment:
     - GF_SECURITY_ADMIN_PASSWORD=STRONG_PASSWORD_HERE
   ```

2. **Disable anonymous access**:
   ```yaml
   - GF_AUTH_ANONYMOUS_ENABLED=false
   ```

3. **Enable HTTPS** (use reverse proxy like Nginx/Traefik)

4. **Set up Alertmanager** for alert routing to Slack/PagerDuty

### Resource Limits

Add resource limits in `docker-compose.observability.yml`:
```yaml
services:
  prometheus:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

### Backup Strategy

```bash
# Backup Prometheus data
docker run --rm -v knowledgebeast-prometheus-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/prometheus-backup.tar.gz /data

# Backup Grafana data
docker run --rm -v knowledgebeast-grafana-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/grafana-backup.tar.gz /data
```

## Testing

Run the comprehensive test suite:

```bash
cd ..
python3 -m pytest tests/dashboards/ -v
```

**Test Coverage**:
- ✅ 11 Docker Compose tests
- ✅ 11 Grafana dashboard tests
- ✅ 12 Prometheus configuration tests
- **Total: 34 tests (all passing)**

## Metrics Reference

### KnowledgeBeast Metrics

- `knowledgebeast_query_latency_seconds_bucket`: Query latency histogram
- `knowledgebeast_queries_total`: Total query count
- `knowledgebeast_cache_hits_total`: Cache hit count
- `knowledgebeast_cache_misses_total`: Cache miss count
- `knowledgebeast_errors_total`: Total error count
- `knowledgebeast_http_requests_total`: HTTP request count by status code
- `knowledgebeast_chromadb_collection_size`: ChromaDB collection document count
- `knowledgebeast_vector_search_latency_seconds_bucket`: Vector search latency histogram
- `knowledgebeast_project_documents_total`: Documents per project

### System Metrics (Node Exporter)

- `node_filesystem_avail_bytes`: Available disk space
- `node_memory_MemAvailable_bytes`: Available memory
- `node_cpu_seconds_total`: CPU usage

## Support

For issues or questions:
- **Documentation**: https://docs.knowledgebeast.io/observability
- **GitHub Issues**: https://github.com/knowledgebeast/knowledgebeast/issues
- **Slack**: #monitoring channel

## License

Same as KnowledgeBeast - see LICENSE file.
