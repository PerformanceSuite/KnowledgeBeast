# Production Security Checklist

**Quick reference for securing KnowledgeBeast deployments**

Use this checklist before and after deploying to production. Each item includes verification steps.

---

## Pre-Deployment Checklist

### 1. Authentication & Authorization

#### API Key Configuration
- [ ] **Generate strong API keys** (minimum 32 bytes entropy)
  ```bash
  # Verify key strength
  openssl rand -hex 32
  ```

- [ ] **Configure KB_API_KEY environment variable**
  ```bash
  # Verify: Should NOT be empty or default
  echo $KB_API_KEY | wc -c  # Should be > 32 characters
  ```

- [ ] **Use separate keys per environment** (dev/staging/prod)
  ```bash
  # Verify: Keys should be different
  # Development: KB_API_KEY=dev_key_...
  # Production:  KB_API_KEY=prod_key_...
  ```

- [ ] **Never commit API keys to version control**
  ```bash
  # Verify: No keys in git history
  git log --all -S "KB_API_KEY" --source --all
  grep -r "KB_API_KEY.*=" .env* .git/  # Should find nothing
  ```

### 2. Network Security

#### CORS Configuration
- [ ] **Set KB_ALLOWED_ORIGINS with exact domains**
  ```bash
  # Verify: Should NOT contain wildcard
  echo $KB_ALLOWED_ORIGINS | grep -q '\*' && echo "FAIL: Wildcard detected" || echo "PASS"
  ```

- [ ] **Test CORS enforcement**
  ```bash
  # Should reject unauthorized origin
  curl -H "Origin: https://evil.com" \
       -H "X-API-Key: $KB_API_KEY" \
       http://localhost:8000/api/v1/health -v | grep -q "Access-Control-Allow-Origin: https://evil.com" && echo "FAIL" || echo "PASS"
  ```

#### HTTPS/TLS Configuration
- [ ] **Enable HTTPS with valid certificate**
  ```bash
  # Verify TLS configuration
  curl -I https://api.example.com/api/v1/health
  # Should return: HTTP/2 200 (not HTTP/1.1)
  ```

- [ ] **Test TLS version and ciphers**
  ```bash
  # Verify TLS 1.2+ only
  nmap --script ssl-enum-ciphers -p 443 api.example.com
  # Should NOT show TLS 1.0 or TLS 1.1
  ```

- [ ] **Verify HSTS header present**
  ```bash
  curl -I https://api.example.com/api/v1/health | grep -i strict-transport-security
  # Should show: Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
  ```

- [ ] **Force HTTP to HTTPS redirect**
  ```bash
  # Verify redirect
  curl -I http://api.example.com/api/v1/health | grep -i location
  # Should show: Location: https://api.example.com/...
  ```

### 3. Request Limits & Rate Limiting

#### Request Size Limits
- [ ] **Configure KB_MAX_REQUEST_SIZE appropriately**
  ```bash
  # Verify limit is set
  echo $KB_MAX_REQUEST_SIZE
  # Recommended: 5242880 (5 MB) for API-only
  ```

- [ ] **Test request size enforcement**
  ```bash
  # Should return 413
  dd if=/dev/zero bs=1M count=11 | curl -X POST \
    -H "X-API-Key: $KB_API_KEY" \
    -H "Content-Type: application/json" \
    --data-binary @- \
    http://localhost:8000/api/v1/query -v | grep "413"
  ```

#### Rate Limiting
- [ ] **Configure rate limits based on expected traffic**
  ```bash
  # Verify rate limiting config
  grep "RATE_LIMIT" knowledgebeast/api/auth.py
  # Default: 100 requests/minute
  ```

- [ ] **Test rate limit enforcement**
  ```bash
  # Send 101 requests in 60 seconds, last should fail with 429
  for i in {1..101}; do
    curl -H "X-API-Key: $KB_API_KEY" http://localhost:8000/api/v1/health
  done
  # Last response should be: HTTP 429 Too Many Requests
  ```

### 4. Security Headers

- [ ] **Verify all security headers present**
  ```bash
  curl -I https://api.example.com/api/v1/health | grep -E "X-Content-Type-Options|X-Frame-Options|X-XSS-Protection|Content-Security-Policy"
  # Should show all 4 headers
  ```

- [ ] **Verify Content-Security-Policy**
  ```bash
  curl -I https://api.example.com/api/v1/health | grep "Content-Security-Policy"
  # Should include: default-src 'self'; object-src 'none'; frame-ancestors 'none'
  ```

- [ ] **Verify X-Frame-Options**
  ```bash
  curl -I https://api.example.com/api/v1/health | grep "X-Frame-Options"
  # Should show: X-Frame-Options: DENY
  ```

### 5. Docker Security

#### Container Configuration
- [ ] **Run as non-root user**
  ```bash
  # Verify user in Dockerfile
  grep "^USER" Dockerfile
  # Should show: USER knowledgebeast
  ```

- [ ] **Verify user in running container**
  ```bash
  docker exec knowledgebeast-api whoami
  # Should show: knowledgebeast (not root)
  ```

- [ ] **Enable read-only filesystem (if possible)**
  ```bash
  # Verify in docker-compose.yml
  grep "read_only: true" docker-compose.yml
  ```

- [ ] **Drop unnecessary capabilities**
  ```bash
  # Verify in docker-compose.yml
  grep -A 2 "cap_drop:" docker-compose.yml
  # Should show: - ALL
  ```

- [ ] **Set resource limits**
  ```bash
  # Verify limits configured
  docker inspect knowledgebeast-api | jq '.[0].HostConfig.Memory'
  # Should NOT be 0 (unlimited)
  ```

#### Image Security
- [ ] **Scan image for vulnerabilities**
  ```bash
  # Using Trivy
  trivy image knowledgebeast:latest --severity HIGH,CRITICAL
  # Should show: 0 HIGH, 0 CRITICAL vulnerabilities
  ```

- [ ] **Verify base image is up-to-date**
  ```bash
  grep "^FROM" Dockerfile
  # Should use recent Python version (3.11+ as of 2025)
  ```

### 6. Secrets Management

- [ ] **Verify .env file has correct permissions**
  ```bash
  ls -la .env
  # Should show: -rw------- (600) or -rw-r----- (640)
  ```

- [ ] **Ensure .env is in .gitignore**
  ```bash
  grep "^\.env$" .gitignore
  # Should find .env
  ```

- [ ] **Verify no secrets in Docker image**
  ```bash
  docker history knowledgebeast:latest --no-trunc | grep -i "api_key\|password\|secret"
  # Should find nothing
  ```

### 7. File Permissions

- [ ] **Data directory permissions**
  ```bash
  ls -ld /data
  # Should show: drwx------ or drwxr-x--- (700 or 750)
  ```

- [ ] **Cache file permissions**
  ```bash
  ls -l /data/cache.json
  # Should show: -rw------- (600)
  ```

- [ ] **Log file permissions**
  ```bash
  ls -l /app/logs/*.log
  # Should show: -rw-r----- (640) owned by app:monitoring
  ```

### 8. Logging & Monitoring

- [ ] **Configure appropriate log level**
  ```bash
  echo $KB_LOG_LEVEL
  # Production: INFO
  # Troubleshooting: DEBUG (temporary)
  ```

- [ ] **Verify security event logging enabled**
  ```bash
  # Check for security logs
  grep "SECURITY" /app/logs/*.log
  # Should show authentication events
  ```

- [ ] **Set up log rotation**
  ```bash
  # Verify logrotate configuration
  cat /etc/logrotate.d/knowledgebeast
  ```

- [ ] **Configure log retention**
  ```bash
  # Security logs: 1 year minimum
  # Access logs: 90 days minimum
  ```

### 9. Backup & Recovery

- [ ] **Configure automated backups**
  ```bash
  # Verify backup script exists
  ls -l /scripts/backup.sh
  ```

- [ ] **Test backup restoration**
  ```bash
  # Restore from backup and verify integrity
  ./scripts/restore.sh backup_20251006.tar.gz
  ```

- [ ] **Verify backup encryption**
  ```bash
  # Backups should be encrypted
  file backup.tar.gz.gpg
  # Should show: GPG encrypted data
  ```

### 10. Network & Firewall

- [ ] **Configure firewall rules**
  ```bash
  # Verify only necessary ports open
  sudo ufw status
  # Should show: 22/tcp, 80/tcp, 443/tcp ALLOW
  ```

- [ ] **Verify no unnecessary services exposed**
  ```bash
  sudo netstat -tuln | grep LISTEN
  # Should only show: 22, 80, 443, 8000 (internal)
  ```

- [ ] **Test external port access**
  ```bash
  # From external machine
  nmap -p 1-65535 api.example.com
  # Should only show: 80, 443 open
  ```

---

## Post-Deployment Checklist

### 1. Security Testing

- [ ] **Run vulnerability scan**
  ```bash
  # OWASP ZAP baseline scan
  docker run -t owasp/zap2docker-stable zap-baseline.py \
    -t https://api.example.com
  ```

- [ ] **Test authentication bypass**
  ```bash
  # Should return 403 Forbidden
  curl https://api.example.com/api/v1/stats
  # Without X-API-Key header
  ```

- [ ] **Test CORS restrictions**
  ```bash
  # Should NOT include Access-Control-Allow-Origin for evil.com
  curl -H "Origin: https://evil.com" https://api.example.com/api/v1/health -v
  ```

- [ ] **Test rate limiting**
  ```bash
  # Rapid requests should trigger 429
  for i in {1..150}; do
    curl -H "X-API-Key: $KB_API_KEY" https://api.example.com/api/v1/health &
  done
  wait
  # Some should return: HTTP 429 Too Many Requests
  ```

- [ ] **Test input validation**
  ```bash
  # SQL injection attempt (should be rejected)
  curl -X POST https://api.example.com/api/v1/query \
    -H "X-API-Key: $KB_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"query": "test OR 1=1--"}'
  # Should return valid response (query sanitized)
  ```

- [ ] **Test request size limits**
  ```bash
  # Oversized request should return 413
  # (tested in pre-deployment)
  ```

### 2. Monitoring Setup

- [ ] **Verify health check endpoint**
  ```bash
  curl https://api.example.com/api/v1/health
  # Should return: {"status": "healthy"}
  ```

- [ ] **Configure uptime monitoring**
  ```bash
  # Set up external monitoring (e.g., UptimeRobot, Pingdom)
  # Alert on: downtime, slow response, certificate expiration
  ```

- [ ] **Set up security alerts**
  ```bash
  # Configure alerts for:
  # - Failed authentication attempts (>10/min)
  # - Rate limit violations (>5/min)
  # - 413 errors (>10/min)
  # - Unusual traffic patterns
  ```

- [ ] **Configure log aggregation**
  ```bash
  # Ship logs to centralized system (e.g., ELK, Splunk, CloudWatch)
  # Verify logs are being received
  ```

### 3. Access Control Review

- [ ] **Review API key usage**
  ```bash
  # Check which keys are actively used
  grep "API key authenticated" /app/logs/*.log | cut -d':' -f8 | sort | uniq -c
  ```

- [ ] **Verify no default credentials**
  ```bash
  # Ensure KB_API_KEY is not default/example value
  echo $KB_API_KEY | grep -qi "example\|default\|test\|demo" && echo "FAIL: Default key detected" || echo "PASS"
  ```

- [ ] **Document API key ownership**
  ```markdown
  # API Key Registry
  - web_app_key_abc123: Production web application (Owner: Team A)
  - mobile_key_def456: Mobile app (Owner: Team B)
  - admin_key_ghi789: Administrative tasks (Owner: DevOps)
  ```

### 4. Compliance Verification

- [ ] **GDPR compliance (if applicable)**
  ```bash
  # Verify data export endpoint exists
  curl -X POST https://api.example.com/api/v1/gdpr/export \
    -H "X-API-Key: $KB_API_KEY" \
    -d '{"user_id": "test_user"}'
  ```

- [ ] **Data retention policy configured**
  ```python
  # Verify automatic data cleanup
  grep "enforce_data_retention" /app/scripts/*.py
  ```

- [ ] **Audit logging enabled**
  ```bash
  # Verify audit.log exists and is being written
  tail -f /data/audit.log
  ```

### 5. Incident Response Readiness

- [ ] **Document emergency contacts**
  ```markdown
  # Emergency Contacts
  - Security Team: security@example.com
  - On-call: +1-555-0100
  - Incident Commander: John Doe
  ```

- [ ] **Create runbook for common incidents**
  ```markdown
  # Incident Runbooks
  - API key compromise: docs/runbooks/api-key-compromise.md
  - DDoS attack: docs/runbooks/ddos-response.md
  - Data breach: docs/runbooks/data-breach-response.md
  ```

- [ ] **Test incident response procedures**
  ```bash
  # Simulate API key compromise
  # 1. Revoke key
  # 2. Check logs for unauthorized access
  # 3. Generate new key
  # 4. Update clients
  # Document time to complete each step
  ```

### 6. Performance & Availability

- [ ] **Load test under expected traffic**
  ```bash
  # Using Apache Bench
  ab -n 10000 -c 100 -H "X-API-Key: $KB_API_KEY" https://api.example.com/api/v1/health
  # Verify: No 5xx errors, P99 latency < 100ms
  ```

- [ ] **Verify auto-scaling (if configured)**
  ```bash
  # Generate load and verify scaling
  # Monitor: CPU, memory, request latency
  ```

- [ ] **Test failover (if using redundancy)**
  ```bash
  # Stop primary instance, verify traffic shifts to secondary
  ```

### 7. Documentation

- [ ] **Update deployment documentation**
  ```markdown
  # Production Deployment - October 6, 2025
  - Version: v0.1.0
  - Deployment date: 2025-10-06
  - Deployed by: Jane Smith
  - Configuration: production
  - Security checklist: ✅ Complete
  ```

- [ ] **Document configuration changes**
  ```markdown
  # Configuration Changes
  - KB_API_KEY: Rotated (previous key revoked)
  - KB_ALLOWED_ORIGINS: Updated to production domains
  - KB_MAX_REQUEST_SIZE: Set to 5MB
  - Rate limiting: 60 requests/minute
  ```

- [ ] **Update runbooks and procedures**
  ```markdown
  # Updated Procedures
  - API key rotation: Every 90 days
  - Security scans: Weekly automated, monthly manual review
  - Dependency updates: Monthly
  - Certificate renewal: Automated via Let's Encrypt
  ```

---

## Ongoing Security Maintenance

### Weekly Tasks
- [ ] Review security logs for anomalies
- [ ] Check for failed authentication attempts
- [ ] Verify backups are running successfully
- [ ] Review rate limiting metrics

### Monthly Tasks
- [ ] Run dependency vulnerability scan (`pip-audit`)
- [ ] Review and update firewall rules
- [ ] Test backup restoration
- [ ] Review API key usage and rotate if needed
- [ ] Check TLS certificate expiration (if not auto-renewed)

### Quarterly Tasks
- [ ] Full security audit
- [ ] Penetration testing (internal or external)
- [ ] Review and update incident response procedures
- [ ] Disaster recovery drill
- [ ] Security training for team

### Annual Tasks
- [ ] Comprehensive security assessment
- [ ] Third-party security audit
- [ ] Update security policies and procedures
- [ ] Review compliance requirements (GDPR, SOC 2, etc.)

---

## Quick Reference: Critical Security Settings

```bash
# .env.production - Minimum required security configuration

# API Authentication (REQUIRED)
KB_API_KEY=<64-char-hex-string>  # openssl rand -hex 32

# CORS (REQUIRED)
KB_ALLOWED_ORIGINS=https://app.example.com,https://api.example.com

# HTTPS (REQUIRED for production)
KB_HTTPS_ONLY=true

# Request Limits (Recommended)
KB_MAX_REQUEST_SIZE=5242880      # 5 MB
KB_MAX_QUERY_LENGTH=5000         # 5k chars

# Rate Limiting (Recommended)
KB_RATE_LIMIT_PER_MINUTE=60

# Logging (Recommended)
KB_LOG_LEVEL=INFO
KB_ENABLE_REQUEST_LOGGING=true
```

---

## Verification Script

```bash
#!/bin/bash
# security-verification.sh - Automated security checks

echo "KnowledgeBeast Security Verification"
echo "====================================="
echo ""

# Check 1: API Key configured
if [ -z "$KB_API_KEY" ]; then
  echo "❌ FAIL: KB_API_KEY not set"
else
  echo "✅ PASS: KB_API_KEY configured"
fi

# Check 2: CORS configured
if echo "$KB_ALLOWED_ORIGINS" | grep -q '\*'; then
  echo "❌ FAIL: CORS contains wildcard"
elif [ -z "$KB_ALLOWED_ORIGINS" ]; then
  echo "⚠️  WARN: KB_ALLOWED_ORIGINS not set (using defaults)"
else
  echo "✅ PASS: CORS properly configured"
fi

# Check 3: HTTPS enforcement
if [ "$KB_HTTPS_ONLY" = "true" ]; then
  echo "✅ PASS: HTTPS enforcement enabled"
else
  echo "⚠️  WARN: HTTPS enforcement not enabled"
fi

# Check 4: Request size limits
if [ -n "$KB_MAX_REQUEST_SIZE" ]; then
  echo "✅ PASS: Request size limit configured"
else
  echo "⚠️  WARN: Using default request size limit"
fi

# Check 5: Security headers
echo ""
echo "Checking security headers..."
HEADERS=$(curl -sI http://localhost:8000/api/v1/health)

if echo "$HEADERS" | grep -q "X-Content-Type-Options"; then
  echo "✅ PASS: X-Content-Type-Options header present"
else
  echo "❌ FAIL: X-Content-Type-Options header missing"
fi

if echo "$HEADERS" | grep -q "Content-Security-Policy"; then
  echo "✅ PASS: Content-Security-Policy header present"
else
  echo "❌ FAIL: Content-Security-Policy header missing"
fi

# Check 6: File permissions
echo ""
echo "Checking file permissions..."
if [ -f ".env" ]; then
  PERMS=$(stat -c "%a" .env 2>/dev/null || stat -f "%A" .env 2>/dev/null)
  if [ "$PERMS" = "600" ] || [ "$PERMS" = "640" ]; then
    echo "✅ PASS: .env permissions secure ($PERMS)"
  else
    echo "❌ FAIL: .env permissions insecure ($PERMS)"
  fi
fi

echo ""
echo "Verification complete!"
```

---

**Checklist Version**: 1.0.0
**Last Updated**: October 6, 2025
**Related Documents**:
- [Security Best Practices Guide](../guides/security-best-practices.md)
- [Security Configuration](./security.md)
- [SECURITY.md](../../SECURITY.md)
