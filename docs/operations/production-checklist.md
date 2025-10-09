# KnowledgeBeast Production Deployment Checklist

## Overview

This comprehensive checklist ensures safe, reliable, and repeatable production deployments for KnowledgeBeast.

**Deployment Method**: Blue/Green deployment with canary testing
**Deployment Window**: Tuesday/Thursday 10 AM - 2 PM EST (low traffic)
**Rollback SLA**: < 5 minutes

---

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist) (27 items)
2. [Deployment Checklist](#deployment-checklist) (15 items)
3. [Post-Deployment Checklist](#post-deployment-checklist) (12 items)

**Total Items**: 54

---

## Pre-Deployment Checklist

### Environment Configuration (6 items)

- [ ] **1.1** All required environment variables are documented
  ```bash
  # Verify all required env vars are in .env.template
  diff <(grep -o '^[A-Z_]*=' .env.production | sort) \
       <(grep -o '^[A-Z_]*=' .env.template | sort)
  # Output should be empty (no differences)
  ```

- [ ] **1.2** Environment variables are set in Kubernetes secrets
  ```bash
  kubectl get secret knowledgebeast-secrets -n production -o json | \
    jq -r '.data | keys[]'
  # Verify all required keys present:
  # - DATABASE_URL
  # - CHROMADB_URL
  # - API_SECRET_KEY
  # - AWS_ACCESS_KEY_ID
  # - AWS_SECRET_ACCESS_KEY
  ```

- [ ] **1.3** SSL/TLS certificates are valid for > 30 days
  ```bash
  echo | openssl s_client -connect api.knowledgebeast.com:443 2>/dev/null | \
    openssl x509 -noout -dates
  # notAfter should be > 30 days from today
  ```

- [ ] **1.4** DNS records are correctly configured
  ```bash
  dig api.knowledgebeast.com
  # Should resolve to load balancer address
  nslookup api.knowledgebeast.com
  # Should not timeout
  ```

- [ ] **1.5** Resource quotas and limits are set
  ```bash
  kubectl describe deployment knowledgebeast -n production | grep -A 5 "Limits\|Requests"
  # Verify:
  # - CPU request: 500m, limit: 2000m
  # - Memory request: 1Gi, limit: 4Gi
  ```

- [ ] **1.6** Persistent volumes are provisioned and accessible
  ```bash
  kubectl get pvc -n production
  # All PVCs should be "Bound" status
  # - knowledgebeast-data: 100Gi
  # - chromadb-data: 200Gi
  # - backup-storage: 500Gi
  ```

---

### Database & Storage (5 items)

- [ ] **2.1** Database migrations are tested in staging
  ```bash
  # Run migrations on staging
  kubectl exec -n staging deployment/knowledgebeast -- \
    python manage.py migrate --check
  # Output: "No migrations to apply" (already tested)
  ```

- [ ] **2.2** Database migrations are backwards compatible
  ```bash
  # Verify no DROP COLUMN or breaking schema changes
  git diff HEAD~1 alembic/versions/
  # Manual review: Ensure additive changes only
  ```

- [ ] **2.3** Database backup completed within last 1 hour
  ```bash
  aws s3 ls s3://knowledgebeast-backups/sqlite/ | tail -5
  # Latest backup timestamp should be < 1 hour ago
  ```

- [ ] **2.4** Backup restoration tested successfully
  ```bash
  # Restore to test environment
  LATEST_BACKUP=$(aws s3 ls s3://knowledgebeast-backups/sqlite/daily/ | tail -1 | awk '{print $4}')
  aws s3 cp s3://knowledgebeast-backups/sqlite/daily/$LATEST_BACKUP /tmp/test_restore.db.gz
  gunzip /tmp/test_restore.db.gz
  sqlite3 /tmp/test_restore.db "PRAGMA integrity_check;"
  # Output: "ok"
  ```

- [ ] **2.5** Sufficient disk space available (> 20% free)
  ```bash
  kubectl exec -n production deployment/knowledgebeast -- df -h /data
  # Available space should be > 20% of total capacity
  ```

---

### Testing & Quality Assurance (8 items)

- [ ] **3.1** All unit tests passing (100%)
  ```bash
  pytest tests/unit/ -v --cov=knowledgebeast --cov-report=term-missing
  # Coverage should be > 80%
  # All tests should pass
  ```

- [ ] **3.2** All integration tests passing (100%)
  ```bash
  pytest tests/integration/ -v
  # All tests should pass
  # No skipped tests
  ```

- [ ] **3.3** All end-to-end tests passing (100%)
  ```bash
  pytest tests/e2e/ -v
  # All tests should pass
  # Tests include: ingestion, query, multi-project scenarios
  ```

- [ ] **3.4** Performance benchmarks meet SLO targets
  ```bash
  pytest tests/performance/test_benchmarks.py -v
  # Verify:
  # - P99 latency < 100ms
  # - P50 latency < 20ms
  # - Throughput > 500 queries/sec (10 workers)
  ```

- [ ] **3.5** Security scan passed (no critical vulnerabilities)
  ```bash
  # Run Snyk security scan
  snyk test --severity-threshold=high
  # Output: "No vulnerabilities found" or only low/medium

  # Run Trivy container scan
  trivy image knowledgebeast:v2.0.0 --severity HIGH,CRITICAL
  # Output: No HIGH or CRITICAL vulnerabilities
  ```

- [ ] **3.6** Dependency audit clean (no known vulnerabilities)
  ```bash
  pip-audit --strict
  # Output: No vulnerabilities found

  # Check for outdated dependencies
  pip list --outdated
  # Review any critical updates needed
  ```

- [ ] **3.7** Load testing completed successfully
  ```bash
  # Run Locust load test for 30 minutes
  locust -f tests/load/locustfile.py --headless -u 1000 -r 100 -t 30m --host http://api.staging.knowledgebeast.com

  # Verify:
  # - 0% failure rate
  # - P95 latency < 100ms
  # - No memory leaks (stable memory usage)
  ```

- [ ] **3.8** Canary deployment tested in staging
  ```bash
  # Deploy to staging with 10% traffic
  kubectl apply -f deployments/kubernetes/canary/knowledgebeast-canary.yaml -n staging

  # Monitor for 15 minutes
  watch -n 30 'curl -s http://staging.knowledgebeast.com/metrics | grep error_rate'

  # Rollback canary if error rate > 0.5%
  ```

---

### Monitoring & Alerting (6 items)

- [ ] **4.1** Prometheus is scraping all targets
  ```bash
  # Check Prometheus targets
  curl http://prometheus.internal.knowledgebeast.com/api/v1/targets | jq '.data.activeTargets[] | select(.health!="up")'
  # Output should be empty (all targets healthy)
  ```

- [ ] **4.2** Grafana dashboards are accessible and displaying data
  ```bash
  # Open dashboard
  open http://grafana.internal.knowledgebeast.com/d/knowledgebeast-overview

  # Verify all panels show data (no "No Data" errors)
  ```

- [ ] **4.3** Alert rules are configured and tested
  ```bash
  # Check alert rules loaded
  curl http://prometheus.internal.knowledgebeast.com/api/v1/rules | \
    jq '.data.groups[].rules[] | select(.type=="alerting") | .name'

  # Should include:
  # - AvailabilitySLOBreach
  # - HighErrorRate
  # - P99LatencyCritical
  # - ChromaDBDown
  ```

- [ ] **4.4** Test alert fires correctly (non-production)
  ```bash
  # Trigger test alert in staging
  curl -X POST http://staging.knowledgebeast.com/admin/trigger-test-alert

  # Verify alert received in Slack #alerts-staging within 1 minute
  ```

- [ ] **4.5** PagerDuty integration tested
  ```bash
  # Send test page
  pd-send-event --routing-key $PAGERDUTY_KEY --event-action trigger \
    --dedup-key "deployment-test" --summary "Deployment test alert"

  # Verify on-call receives page within 2 minutes
  ```

- [ ] **4.6** Log aggregation is working (last 5 minutes of logs visible)
  ```bash
  kubectl logs -n production deployment/knowledgebeast --tail=100 --since=5m | wc -l
  # Should return > 0 (logs are being generated)
  ```

---

### Documentation & Communication (2 items)

- [ ] **5.1** Deployment runbook reviewed and up-to-date
  ```bash
  # Check runbook last modified date
  git log -1 --format=%cd docs/operations/runbook.md
  # Should be within last 30 days
  ```

- [ ] **5.2** Stakeholders notified of deployment window
  ```bash
  # Send notification to:
  # - #engineering (Slack)
  # - #customer-success (Slack)
  # - engineering@knowledgebeast.com (Email)

  # Template:
  # "Production deployment scheduled for Tuesday, Oct 8 at 10 AM EST.
  #  Expected duration: 30 minutes. Minimal disruption expected (blue/green deployment)."
  ```

---

## Deployment Checklist

### Pre-Deployment Validation (3 items)

- [ ] **6.1** Create deployment change request
  ```bash
  # File change request in Jira/ServiceNow
  # Include:
  # - Deployment date/time
  # - Version being deployed (v2.0.0)
  # - Rollback plan
  # - Estimated duration
  # - Impact assessment
  ```

- [ ] **6.2** Obtain deployment approval
  ```bash
  # Required approvals:
  # - Engineering Manager: ✅
  # - SRE Team Lead: ✅
  # - Product Manager: ✅ (for major releases)
  ```

- [ ] **6.3** Verify baseline metrics before deployment
  ```bash
  # Record baseline metrics for comparison:
  # - P99 latency: ____ ms
  # - Error rate: ____ %
  # - Throughput: ____ req/s
  # - Cache hit ratio: ____ %

  curl -s http://prometheus.internal.knowledgebeast.com/api/v1/query?query=histogram_quantile\(0.99,rate\(kb_query_duration_seconds_bucket\[5m\]\)\) | jq '.data.result[0].value[1]'
  ```

---

### Blue/Green Deployment (8 items)

- [ ] **7.1** Deploy Green environment (new version)
  ```bash
  # Apply green deployment
  kubectl apply -f deployments/kubernetes/knowledgebeast-green.yaml -n production

  # Wait for rollout to complete
  kubectl rollout status deployment/knowledgebeast-green -n production --timeout=10m
  ```

- [ ] **7.2** Verify Green environment health checks pass
  ```bash
  # Get green service endpoint
  GREEN_ENDPOINT=$(kubectl get svc knowledgebeast-green -n production -o jsonpath='{.spec.clusterIP}')

  # Health check
  curl http://$GREEN_ENDPOINT:8000/health
  # Expected: {"status": "healthy", "version": "v2.0.0"}
  ```

- [ ] **7.3** Run smoke tests against Green environment
  ```bash
  # Execute smoke tests
  pytest tests/smoke/ --base-url http://$GREEN_ENDPOINT:8000 -v

  # All tests should pass
  ```

- [ ] **7.4** Start canary deployment (10% traffic to Green)
  ```bash
  # Update Istio VirtualService to send 10% traffic to green
  kubectl apply -f deployments/kubernetes/istio/virtualservice-canary.yaml -n production

  # Verify traffic split
  kubectl get virtualservice knowledgebeast -n production -o yaml | grep -A 5 "weight"
  # Blue: 90%
  # Green: 10%
  ```

- [ ] **7.5** Monitor canary for 15 minutes
  ```bash
  # Monitor key metrics for green deployment
  watch -n 30 '
    echo "=== Green Deployment Metrics ==="
    curl -s http://prometheus.internal.knowledgebeast.com/api/v1/query?query=rate\(http_requests_total\{deployment=\"green\",status=~\"5..\"\}\[5m\]\) | jq -r ".data.result[0].value[1] // 0"
    echo "Error rate (green): ^"
    echo ""
    curl -s http://prometheus.internal.knowledgebeast.com/api/v1/query?query=histogram_quantile\(0.99,rate\(kb_query_duration_seconds_bucket\{deployment=\"green\"\}\[5m\]\)\) | jq -r ".data.result[0].value[1]"
    echo "P99 latency (green): ^"
  '

  # Criteria for proceeding:
  # - Error rate < 0.5%
  # - P99 latency < 120ms (allow 20% regression initially)
  # - No crashes or restarts
  ```

- [ ] **7.6** Gradually increase Green traffic (50%, then 100%)
  ```bash
  # 50% traffic
  kubectl apply -f deployments/kubernetes/istio/virtualservice-50-50.yaml -n production
  # Wait 10 minutes, monitor metrics

  # 100% traffic (full cutover)
  kubectl apply -f deployments/kubernetes/istio/virtualservice-green-only.yaml -n production
  ```

- [ ] **7.7** Monitor post-cutover for 15 minutes
  ```bash
  # Monitor all traffic now going to green
  watch -n 30 'curl -s http://api.knowledgebeast.com/metrics | grep -E "(error_rate|p99_latency|throughput)"'

  # Verify metrics stable
  ```

- [ ] **7.8** Decommission Blue environment
  ```bash
  # Keep blue running for 1 hour (quick rollback window)
  # After 1 hour of stable green:
  kubectl scale deployment/knowledgebeast-blue -n production --replicas=0

  # After 24 hours of stable green:
  kubectl delete deployment/knowledgebeast-blue -n production
  ```

---

### Database Migration (if applicable) (2 items)

- [ ] **8.1** Run database migrations (zero-downtime)
  ```bash
  # Execute migrations from green deployment
  kubectl exec -n production deployment/knowledgebeast-green -- \
    python manage.py migrate

  # Verify migrations applied
  kubectl exec -n production deployment/knowledgebeast-green -- \
    python manage.py showmigrations | grep "\[X\]" | wc -l
  # Count should match expected number of migrations
  ```

- [ ] **8.2** Verify Blue deployment still functional with new schema
  ```bash
  # Ensure backward compatibility
  # Blue deployment should continue working with migrated database

  curl http://$BLUE_ENDPOINT:8000/health
  # Expected: {"status": "healthy"}
  ```

---

### Rollback Preparation (2 items)

- [ ] **9.1** Document rollback procedure
  ```bash
  # Rollback steps documented:
  # 1. kubectl apply -f deployments/kubernetes/istio/virtualservice-blue-only.yaml
  # 2. Monitor for 5 minutes
  # 3. Scale down green: kubectl scale deployment/knowledgebeast-green --replicas=0
  # 4. Rollback migrations (if needed): python manage.py migrate <previous_version>
  ```

- [ ] **9.2** Test rollback procedure (dry run in staging)
  ```bash
  # Practice rollback in staging environment
  # Verify < 5 minute rollback time
  ```

---

## Post-Deployment Checklist

### Monitoring & Validation (6 items)

- [ ] **10.1** Monitor key metrics for 1 hour post-deployment
  ```bash
  # Open Grafana dashboard
  open http://grafana.internal.knowledgebeast.com/d/knowledgebeast-overview

  # Watch for:
  # - Error rate spikes
  # - Latency increases
  # - Throughput drops
  # - Memory leaks (gradual memory increase)

  # Set 1-hour timer
  ```

- [ ] **10.2** Verify SLO compliance
  ```bash
  # Check SLO metrics after 1 hour
  # - P99 latency < 100ms: ✅
  # - Error rate < 0.1%: ✅
  # - Availability: 100%: ✅
  # - Cache hit ratio > 70%: ✅
  ```

- [ ] **10.3** Run user acceptance testing (UAT)
  ```bash
  # Execute UAT test suite
  pytest tests/uat/ --base-url https://api.knowledgebeast.com -v

  # Manual spot checks:
  # - Create new project: ✅
  # - Ingest documents: ✅
  # - Query documents: ✅
  # - Multi-project search: ✅
  ```

- [ ] **10.4** Compare performance to baseline
  ```bash
  # Baseline (before deployment):
  # - P99 latency: 85ms
  # - Error rate: 0.05%
  # - Throughput: 650 req/s

  # Current (after deployment):
  # - P99 latency: _____ ms (should be within ±10% of baseline)
  # - Error rate: _____ % (should be ≤ baseline)
  # - Throughput: _____ req/s (should be ≥ baseline)
  ```

- [ ] **10.5** Check for any new errors in logs
  ```bash
  # Review error logs from last hour
  kubectl logs -n production deployment/knowledgebeast-green --since=1h | \
    grep -i "error\|exception\|traceback" | head -50

  # Investigate any new error patterns
  ```

- [ ] **10.6** Verify all dependent services are healthy
  ```bash
  # Check health of all dependencies
  curl http://api.knowledgebeast.com/health | jq '.components'

  # Expected:
  # {
  #   "chromadb": {"status": "up"},
  #   "embedding_model": {"status": "up"},
  #   "database": {"status": "up"},
  #   "disk": {"status": "up"}
  # }
  ```

---

### Communication & Documentation (4 items)

- [ ] **11.1** Update deployment log
  ```bash
  # Record deployment in deployment log
  # - Date/time: 2025-10-08 10:30 AM EST
  # - Version deployed: v2.0.0
  # - Duration: 35 minutes
  # - Issues encountered: None
  # - Rollback performed: No
  ```

- [ ] **11.2** Notify stakeholders of successful deployment
  ```bash
  # Send notification to Slack #engineering
  # "✅ Production deployment complete. v2.0.0 deployed successfully.
  #  No issues detected. Monitoring for 24 hours."
  ```

- [ ] **11.3** Update status page (if customer-facing changes)
  ```bash
  # Update https://status.knowledgebeast.com
  # "✅ All systems operational. Recent deployment completed successfully."
  ```

- [ ] **11.4** Tag release in Git
  ```bash
  git tag -a v2.0.0 -m "Production release v2.0.0 - Feature X, Bug fixes Y, Z"
  git push origin v2.0.0
  ```

---

### Incident Response Preparation (2 items)

- [ ] **12.1** Verify on-call engineer is available
  ```bash
  # Check PagerDuty schedule
  pd-oncall --schedule knowledgebeast-prod

  # Expected: On-call engineer name and contact
  ```

- [ ] **12.2** Review incident response plan (if issues arise)
  ```bash
  # If deployment causes issues:
  # 1. Assess severity (P0, P1, P2, P3)
  # 2. Create incident in PagerDuty
  # 3. Follow runbook procedures
  # 4. Consider rollback if error rate > 1% or P99 latency > 500ms
  # 5. Communicate status every 30 minutes (for P0/P1)
  ```

---

## Rollback Decision Matrix

**Rollback Immediately If**:
- ❌ Error rate > 5% for 5 minutes
- ❌ P99 latency > 1 second for 5 minutes
- ❌ Service completely unavailable
- ❌ Data corruption detected
- ❌ Security vulnerability exploited

**Consider Rollback If**:
- ⚠️ Error rate 1-5% for 10 minutes
- ⚠️ P99 latency 200-1000ms for 10 minutes
- ⚠️ Cache hit ratio drops > 30%
- ⚠️ Customer complaints about specific feature

**Monitor and Investigate If**:
- 📊 Error rate 0.1-1% (below SLO but elevated)
- 📊 P99 latency 100-200ms (slightly above SLO)
- 📊 Minor performance degradation

**Proceed Normally If**:
- ✅ Error rate < 0.1%
- ✅ P99 latency < 100ms
- ✅ All smoke tests passing
- ✅ No unusual patterns in logs

---

## Post-Deployment Monitoring Schedule

### First 1 Hour (Active Monitoring)
- Check metrics every 5 minutes
- Review logs for errors
- Respond to alerts immediately
- On-call engineer available

### First 24 Hours (Enhanced Monitoring)
- Check metrics every 30 minutes
- Daily error log review
- Monitor for memory leaks
- Keep rollback option ready

### First 7 Days (Standard Monitoring)
- Check metrics daily
- Review weekly trends
- Compare to baseline
- Plan for next deployment

---

## Deployment Best Practices

### Timing
- ✅ Deploy during low-traffic windows (Tuesday/Thursday mornings)
- ✅ Avoid Mondays (too early in week), Fridays (risk over weekend)
- ❌ Never deploy before major holidays
- ❌ Never deploy during high-traffic events

### Testing
- ✅ Test in staging environment first (prod-like)
- ✅ Run full test suite before deployment
- ✅ Use canary deployments (gradual rollout)
- ✅ Have rollback plan ready

### Communication
- ✅ Notify all stakeholders 24 hours in advance
- ✅ Update status page during deployment
- ✅ Send completion notification
- ✅ Document lessons learned

### Automation
- ✅ Use CI/CD pipelines (GitHub Actions)
- ✅ Automated testing (no manual testing)
- ✅ Automated rollback triggers (error rate threshold)
- ✅ Automated notifications (Slack, email)

---

## Appendix: Quick Reference Commands

### Deployment
```bash
# Deploy green
kubectl apply -f deployments/kubernetes/knowledgebeast-green.yaml -n production
kubectl rollout status deployment/knowledgebeast-green -n production

# Canary (10% traffic)
kubectl apply -f deployments/kubernetes/istio/virtualservice-canary.yaml -n production

# Full cutover (100% traffic)
kubectl apply -f deployments/kubernetes/istio/virtualservice-green-only.yaml -n production
```

### Rollback
```bash
# Immediate rollback to blue
kubectl apply -f deployments/kubernetes/istio/virtualservice-blue-only.yaml -n production

# Scale down green
kubectl scale deployment/knowledgebeast-green -n production --replicas=0

# Rollback migrations (if needed)
kubectl exec -n production deployment/knowledgebeast-blue -- \
  python manage.py migrate knowledgebeast <previous_migration_number>
```

### Monitoring
```bash
# Real-time metrics
watch -n 10 'curl -s http://api.knowledgebeast.com/metrics | grep -E "(error_rate|p99_latency)"'

# Error logs
kubectl logs -n production deployment/knowledgebeast-green -f | grep ERROR

# Health check
curl http://api.knowledgebeast.com/health | jq
```

---

## Revision History

| Version | Date       | Changes                                   |
|---------|------------|-------------------------------------------|
| 1.0     | 2025-10-08 | Initial production deployment checklist   |

**Maintained by**: SRE Team & DevOps
**Review Frequency**: After each major deployment
**Next Review**: After v2.1.0 deployment
