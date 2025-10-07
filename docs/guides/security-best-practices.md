# Security Best Practices Guide

**Comprehensive security guidelines for deploying and operating KnowledgeBeast in production environments.**

---

## Table of Contents

- [Overview](#overview)
- [Quick Start Security Checklist](#quick-start-security-checklist)
- [Authentication & Authorization](#authentication--authorization)
- [Network Security](#network-security)
- [Data Protection](#data-protection)
- [Input Validation](#input-validation)
- [Production Deployment Security](#production-deployment-security)
- [Monitoring & Auditing](#monitoring--auditing)
- [Docker Security](#docker-security)
- [Incident Response](#incident-response)
- [Security Testing](#security-testing)
- [Compliance & Regulations](#compliance--regulations)

---

## Overview

KnowledgeBeast implements defense-in-depth security with multiple layers of protection. This guide provides comprehensive best practices for securing your deployment across all layers.

### Security Philosophy

1. **Secure by Default**: Security features enabled out-of-the-box
2. **Defense in Depth**: Multiple overlapping security controls
3. **Least Privilege**: Minimal permissions and access rights
4. **Zero Trust**: Verify all requests, trust none
5. **Fail Secure**: Safe defaults when components fail

### Recent Security Enhancements (October 2025)

- API key authentication with multi-key support
- Environment-based CORS configuration
- Comprehensive security headers (CSP, HSTS, X-Frame-Options)
- Request size limits and rate limiting
- Pickle RCE vulnerability eliminated (JSON-only cache)
- 30+ security tests with 100% coverage

---

## Quick Start Security Checklist

**Critical (Do Before Production)**

- [ ] Set `KB_API_KEY` environment variable with strong keys
- [ ] Configure `KB_ALLOWED_ORIGINS` with exact domain(s)
- [ ] Enable HTTPS with valid TLS certificate
- [ ] Set appropriate request size limits
- [ ] Configure rate limiting
- [ ] Use non-root user in Docker containers
- [ ] Review and restrict file permissions
- [ ] Enable comprehensive logging
- [ ] Set up security monitoring and alerts

**Recommended (First Week of Production)**

- [ ] Implement API key rotation policy
- [ ] Configure reverse proxy with TLS termination
- [ ] Set up automated security scanning
- [ ] Create incident response playbook
- [ ] Configure backup and recovery procedures
- [ ] Review and harden network firewall rules
- [ ] Implement secrets management solution
- [ ] Set up centralized log aggregation

**Best Practices (Ongoing)**

- [ ] Monthly security audits and dependency updates
- [ ] Quarterly penetration testing
- [ ] Regular review of access logs
- [ ] Continuous security monitoring
- [ ] Security training for team members

---

## Authentication & Authorization

### API Key Management

KnowledgeBeast uses API key authentication via the `X-API-Key` header.

#### Generating Strong API Keys

```bash
# Generate cryptographically secure API key (Linux/macOS)
openssl rand -hex 32

# Generate API key (cross-platform with Python)
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Example output:
# vB2xZ9mK4nQ_8pL1wF6sT3yH5jR7cN0uA9dE2gV4hI6kM8oP
```

**Best Practices:**

- Use at least 32 bytes of entropy (256 bits)
- Use URL-safe characters (alphanumeric, dash, underscore)
- Store keys in environment variables, never in code
- Use different keys for different environments (dev/staging/prod)
- Never commit keys to version control

#### Multiple API Keys

Support for different clients or services:

```bash
# .env configuration
KB_API_KEY=webapp_key_abc123,mobile_key_def456,admin_key_ghi789
```

**Use Cases:**

- **Per-service keys**: Different key for web app, mobile app, admin tools
- **Per-environment keys**: Separate keys for dev, staging, production
- **Team keys**: Individual keys for team members (with rotation)
- **Client keys**: Dedicated keys for different customers/tenants

**Example Implementation:**

```python
# Map keys to specific permissions or quotas
API_KEY_PERMISSIONS = {
    "webapp_key_abc123": {"max_requests": 1000, "endpoints": ["query", "stats"]},
    "mobile_key_def456": {"max_requests": 500, "endpoints": ["query"]},
    "admin_key_ghi789": {"max_requests": 10000, "endpoints": ["*"]}
}
```

#### API Key Rotation

**Rotation Policy:**

1. **Regular rotation**: Every 90 days minimum
2. **Event-driven rotation**: Immediately upon:
   - Employee departure
   - Suspected compromise
   - Security incident
   - Major system changes

**Zero-Downtime Rotation Process:**

```bash
# Step 1: Add new key alongside old key
KB_API_KEY=old_key_123,new_key_456

# Step 2: Update clients to use new key (over days/weeks)
# Verify new key usage via logs

# Step 3: Remove old key once all clients migrated
KB_API_KEY=new_key_456
```

#### API Key Revocation

**Immediate Revocation:**

```bash
# Remove compromised key from environment variable
# Old: KB_API_KEY=key1,compromised_key2,key3
# New: KB_API_KEY=key1,key3

# Restart API server
docker restart knowledgebeast-api
```

**Audit Trail:**

```python
# Log all authentication attempts
logger.info(f"API key authenticated: {api_key[:8]}... [client={client_ip}]")
logger.warning(f"Invalid API key attempted: {api_key[:8]}... [client={client_ip}]")
```

### Rate Limiting

**Default Configuration:**

- **100 requests per minute** per API key
- Sliding window algorithm
- Per-key tracking
- HTTP 429 responses when exceeded

**Custom Rate Limits:**

```python
# In knowledgebeast/api/auth.py
RATE_LIMIT_REQUESTS = 100  # Requests allowed
RATE_LIMIT_WINDOW = 60     # Time window in seconds

# Per-endpoint rate limiting (advanced)
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/v1/query")
@limiter.limit("30/minute")  # Stricter limit for expensive queries
async def query(request: Request):
    ...
```

**Rate Limit Headers:**

```http
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1696531200
```

### Principle of Least Privilege

**Application Level:**

- Grant minimum necessary permissions
- Use separate API keys for different operations
- Implement role-based access control (RBAC)

**System Level:**

- Run containers as non-root user (UID 1000)
- Restrict file system access to necessary directories
- Use read-only file systems where possible

**Network Level:**

- Whitelist only required IP addresses
- Segment network by function (API, database, monitoring)
- Use private networks for internal communication

---

## Network Security

### CORS Configuration

**Production Configuration:**

```bash
# .env - CRITICAL: Use exact origins, never wildcard
KB_ALLOWED_ORIGINS=https://app.example.com,https://api.example.com

# ❌ NEVER use in production
KB_ALLOWED_ORIGINS=*  # Vulnerable to CSRF attacks
```

**Best Practices:**

- Specify exact scheme (https://) and domain
- Include all necessary subdomains explicitly
- Avoid wildcard origins in production
- Test CORS configuration before deployment
- Monitor CORS errors in logs

**Allowed Methods:**

KnowledgeBeast restricts CORS to only necessary methods:
- `GET` - Reading data
- `POST` - Creating/querying
- `DELETE` - Removing data
- `OPTIONS` - CORS preflight

**Restricted methods** (not allowed):
- `PUT`, `PATCH` - Use `POST` instead
- `HEAD` - Use `GET` instead

**CORS Testing:**

```bash
# Test CORS preflight
curl -X OPTIONS http://localhost:8000/api/v1/query \
  -H "Origin: https://app.example.com" \
  -H "Access-Control-Request-Method: POST" \
  -v

# Should return:
# Access-Control-Allow-Origin: https://app.example.com
# Access-Control-Allow-Methods: GET, POST, DELETE, OPTIONS
```

### HTTPS Enforcement

**Always use HTTPS in production.** HTTP traffic is vulnerable to:
- Man-in-the-middle attacks
- Session hijacking
- Credential theft
- Data tampering

#### Option 1: Reverse Proxy with TLS Termination (Recommended)

**Nginx Configuration:**

```nginx
# /etc/nginx/sites-available/knowledgebeast
server {
    listen 80;
    server_name api.example.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.example.com;

    # SSL/TLS Configuration
    ssl_certificate /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # HSTS Header (force HTTPS for 1 year)
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

    # Security Headers (defense in depth)
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Proxy Configuration
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # Buffer settings
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;

    # Request size limit
    client_max_body_size 10M;
}
```

**Caddy Configuration (Simpler Alternative):**

```caddyfile
# Caddyfile - Auto HTTPS with Let's Encrypt
api.example.com {
    reverse_proxy localhost:8000

    # Headers
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        X-XSS-Protection "1; mode=block"
        Referrer-Policy "strict-origin-when-cross-origin"
    }

    # TLS configuration
    tls {
        protocols tls1.2 tls1.3
        ciphers TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256 TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
    }
}
```

#### Option 2: Direct TLS in Application (Not Recommended for Production)

```bash
# Use reverse proxy instead, but for testing:
uvicorn knowledgebeast.api.app:app \
  --host 0.0.0.0 \
  --port 8443 \
  --ssl-keyfile /path/to/private.key \
  --ssl-certfile /path/to/certificate.crt
```

**TLS Certificate Options:**

1. **Let's Encrypt** (Free, automated):
   ```bash
   sudo certbot --nginx -d api.example.com
   ```

2. **Commercial CA** (Extended validation, support)
3. **Self-signed** (Development/testing only):
   ```bash
   openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
   ```

### Firewall Rules

**Minimal Attack Surface:**

```bash
# UFW (Ubuntu)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH (consider changing port)
sudo ufw allow 80/tcp    # HTTP (redirects to HTTPS)
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# iptables (Advanced)
iptables -A INPUT -p tcp --dport 443 -j ACCEPT
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -j DROP
```

**IP Whitelisting:**

```nginx
# nginx - Restrict to specific IPs
location /api/v1/admin {
    allow 203.0.113.0/24;   # Office network
    allow 198.51.100.42;     # Admin VPN
    deny all;

    proxy_pass http://localhost:8000;
}
```

### Network Segmentation

**Docker Networks:**

```yaml
# docker-compose.yml
version: '3.8'

networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true  # No internet access

services:
  api:
    networks:
      - frontend
      - backend

  database:
    networks:
      - backend  # Only accessible by API, not internet
```

---

## Data Protection

### Sensitive Data Handling

**Data Classification:**

1. **Public**: Documentation, marketing content
2. **Internal**: Operational data, non-sensitive logs
3. **Confidential**: Customer data, API keys
4. **Restricted**: PII, financial data, credentials

**Handling Guidelines:**

```python
# ❌ BAD: Logging sensitive data
logger.info(f"User query: {query}")  # May contain PII
logger.debug(f"API key: {api_key}")  # Credential exposure

# ✅ GOOD: Sanitized logging
logger.info(f"User query received [length={len(query)}]")
logger.debug(f"API key authenticated: {api_key[:8]}...")
```

### Cache Security

KnowledgeBeast uses **JSON-only caching** (pickle removed due to RCE vulnerability).

**Cache File Protection:**

```bash
# Secure cache file permissions
chmod 600 /data/cache.json
chown knowledgebeast:knowledgebeast /data/cache.json

# Verify cache is JSON, not pickle
file /data/cache.json  # Should show: "JSON data"
head -c 10 /data/cache.json  # Should NOT show: "\x80\x03" (pickle magic bytes)
```

**Cache Encryption (for sensitive data):**

```python
# Example: Encrypt cache at rest
import json
from cryptography.fernet import Fernet

# Generate and store key securely
encryption_key = Fernet.generate_key()
cipher = Fernet(encryption_key)

# Encrypt cache before writing
with open('cache.json', 'r') as f:
    cache_data = json.dumps(json.load(f)).encode()
encrypted_cache = cipher.encrypt(cache_data)

with open('cache.json.enc', 'wb') as f:
    f.write(encrypted_cache)
```

### File Permission Management

**Recommended Permissions:**

```bash
# Application files (read-only)
chmod -R 644 /app/knowledgebeast/*.py
chmod 755 /app/knowledgebeast  # Directory executable

# Data directory (read-write for app user only)
chmod 700 /data
chmod 600 /data/*.json
chmod 600 /data/cache.json

# Configuration files (read-only for app user)
chmod 600 /config/.env
chmod 644 /config/*.yaml

# Logs (write for app, read for monitoring)
chmod 640 /app/logs/*.log
chown knowledgebeast:monitoring /app/logs/
```

**Docker Volume Permissions:**

```yaml
# docker-compose.yml
services:
  api:
    volumes:
      - ./data:/data:rw
      - ./config:/config:ro  # Read-only
      - ./knowledge:/knowledge:ro  # Read-only
```

### Secrets Management

**Environment Variables (Basic):**

```bash
# .env - NEVER commit to git
KB_API_KEY=your_secret_api_key_here
KB_REDIS_PASSWORD=your_redis_password

# .gitignore
.env
.env.local
.env.production
*.secret
```

**Docker Secrets (Better):**

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    secrets:
      - api_key
      - redis_password
    environment:
      KB_API_KEY_FILE: /run/secrets/api_key
      KB_REDIS_PASSWORD_FILE: /run/secrets/redis_password

secrets:
  api_key:
    file: ./secrets/api_key.txt
  redis_password:
    file: ./secrets/redis_password.txt
```

**External Secrets Management (Production):**

- **HashiCorp Vault**: Enterprise secrets management
- **AWS Secrets Manager**: AWS-native solution
- **Azure Key Vault**: Azure-native solution
- **Google Secret Manager**: GCP-native solution

**Example with Vault:**

```bash
# Store secret in Vault
vault kv put secret/knowledgebeast/api_key value="secret_key_123"

# Retrieve at runtime
export KB_API_KEY=$(vault kv get -field=value secret/knowledgebeast/api_key)
```

---

## Input Validation

### Query Sanitization

**Built-in Protections:**

1. **Query length limits**: Max 10,000 characters (configurable)
2. **Character encoding validation**: UTF-8 enforcement
3. **Special character handling**: Safe escaping

**Custom Validation:**

```python
# Example: Additional query validation
import re
from fastapi import HTTPException

def validate_query(query: str) -> str:
    """Validate and sanitize user queries."""

    # Length check
    if len(query) > 10000:
        raise HTTPException(status_code=400, detail="Query too long")

    # Empty check
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Pattern validation (optional, depending on use case)
    if re.search(r'[<>]', query):
        # Strip HTML tags
        query = re.sub(r'<[^>]+>', '', query)

    # SQL injection pattern check (if using SQL backend)
    sql_patterns = [
        r'(\bDROP\b|\bDELETE\b|\bUPDATE\b|\bINSERT\b)',
        r'(--|#|\/\*)',  # SQL comments
        r"('\s*OR\s*'1'\s*=\s*'1)",  # Classic injection
    ]

    for pattern in sql_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            raise HTTPException(status_code=400, detail="Invalid query pattern")

    return query.strip()
```

### File Upload Validation

**File Type Validation:**

```python
# Example: Secure file upload handling
from pathlib import Path
import magic  # python-magic library

ALLOWED_EXTENSIONS = {'.md', '.txt', '.pdf', '.docx'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

def validate_upload(file_path: Path, content: bytes) -> None:
    """Validate uploaded file is safe."""

    # Extension check
    if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File type {file_path.suffix} not allowed")

    # Size check
    if len(content) > MAX_FILE_SIZE:
        raise ValueError(f"File size exceeds {MAX_FILE_SIZE} bytes")

    # MIME type check (prevents extension spoofing)
    mime = magic.from_buffer(content, mime=True)
    allowed_mimes = ['text/plain', 'text/markdown', 'application/pdf']
    if mime not in allowed_mimes:
        raise ValueError(f"File MIME type {mime} not allowed")

    # Virus scanning (optional, requires ClamAV)
    # scan_for_viruses(content)
```

### Path Traversal Prevention

**Built-in Protections:**

```python
# KnowledgeBeast validates all file paths
from pathlib import Path

def safe_path(user_input: str, base_dir: Path) -> Path:
    """Ensure path is within allowed directory."""

    # Resolve to absolute path
    requested_path = (base_dir / user_input).resolve()

    # Ensure within base directory
    if not str(requested_path).startswith(str(base_dir.resolve())):
        raise ValueError("Path traversal attempt detected")

    return requested_path

# Usage
base = Path("/data/knowledge")
user_file = "../../etc/passwd"  # Attack attempt
safe_file = safe_path(user_file, base)  # Raises ValueError
```

### Injection Attack Prevention

**Command Injection Prevention:**

```python
# ❌ BAD: Direct command execution
import os
filename = request.query_params.get('file')
os.system(f"cat {filename}")  # VULNERABLE

# ✅ GOOD: Use safe APIs, validate input
import subprocess
from pathlib import Path

def read_file_safe(filename: str, base_dir: Path) -> str:
    """Safely read file without command injection risk."""
    safe_file = safe_path(filename, base_dir)
    return safe_file.read_text()
```

**SQL Injection Prevention:**

```python
# ❌ BAD: String concatenation
query = f"SELECT * FROM docs WHERE title = '{user_input}'"

# ✅ GOOD: Parameterized queries
cursor.execute("SELECT * FROM docs WHERE title = ?", (user_input,))
```

**NoSQL Injection Prevention:**

```python
# ❌ BAD: Direct query insertion
db.collection.find({"$where": user_input})

# ✅ GOOD: Validated, parameterized queries
db.collection.find({"title": sanitize(user_input)})
```

---

## Production Deployment Security

### Security Headers

KnowledgeBeast automatically adds comprehensive security headers via middleware.

**Automatic Headers:**

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME type sniffing attacks |
| `X-Frame-Options` | `DENY` | Prevent clickjacking attacks |
| `X-XSS-Protection` | `1; mode=block` | Enable browser XSS protection |
| `Content-Security-Policy` | (see below) | Restrict resource loading, prevent XSS |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` | Force HTTPS for 1 year |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Control referrer information leakage |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=()` | Restrict browser features |

**Content Security Policy (CSP):**

```
default-src 'self';
script-src 'self';
style-src 'self' 'unsafe-inline';
img-src 'self' data: https:;
font-src 'self' data:;
connect-src 'self';
frame-ancestors 'none';
base-uri 'self';
form-action 'self';
object-src 'none';
upgrade-insecure-requests
```

**Custom Headers (via Reverse Proxy):**

```nginx
# Additional security headers in nginx
add_header X-Permitted-Cross-Domain-Policies "none" always;
add_header Cross-Origin-Embedder-Policy "require-corp" always;
add_header Cross-Origin-Opener-Policy "same-origin" always;
add_header Cross-Origin-Resource-Policy "same-origin" always;
```

### Request Size Limits

**Default Limits:**

```bash
# Environment variables
KB_MAX_REQUEST_SIZE=10485760    # 10 MB
KB_MAX_QUERY_LENGTH=10000       # 10k characters
```

**Use Case Specific Limits:**

```bash
# API-only service (smaller payloads)
KB_MAX_REQUEST_SIZE=5242880     # 5 MB

# File upload service (larger payloads)
KB_MAX_REQUEST_SIZE=52428800    # 50 MB

# Public API (stricter limits to prevent DoS)
KB_MAX_REQUEST_SIZE=1048576     # 1 MB
KB_MAX_QUERY_LENGTH=1000        # 1k characters
```

**413 Error Handling:**

```json
{
  "error": "RequestEntityTooLarge",
  "message": "Request body too large",
  "detail": "Maximum request size is 10485760 bytes (10MB)",
  "status_code": 413
}
```

### Timeout Configuration

**Application Timeouts:**

```bash
# .env
KB_REQUEST_TIMEOUT=30           # Request timeout (seconds)
KB_SHUTDOWN_TIMEOUT=10          # Graceful shutdown timeout
```

**Reverse Proxy Timeouts:**

```nginx
# nginx configuration
proxy_connect_timeout 60s;
proxy_send_timeout 60s;
proxy_read_timeout 60s;
send_timeout 60s;
```

### Error Message Sanitization

**Never expose sensitive information in error messages.**

```python
# ❌ BAD: Exposes internal paths and stack traces
try:
    result = process_file("/data/secret/config.json")
except Exception as e:
    return {"error": str(e)}  # May expose: "File not found: /data/secret/config.json"

# ✅ GOOD: Generic error messages
try:
    result = process_file(file_path)
except FileNotFoundError:
    logger.error(f"File not found: {file_path}", exc_info=True)
    return {"error": "Resource not found"}
except Exception as e:
    logger.error(f"Processing error: {e}", exc_info=True)
    return {"error": "Internal server error"}
```

**FastAPI Exception Handlers:**

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler - never expose stack traces."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
            "request_id": request.state.request_id
        }
    )
```

---

## Monitoring & Auditing

### Security Logging

**What to Log:**

1. **Authentication Events:**
   - Successful logins
   - Failed login attempts
   - API key usage
   - Rate limit violations

2. **Access Events:**
   - Resource access (queries, documents)
   - Administrative actions
   - Configuration changes

3. **Security Events:**
   - CORS violations
   - Invalid requests (413, 400 errors)
   - Unusual patterns (SQL injection attempts)
   - File access attempts

**Logging Best Practices:**

```python
import logging
import json
from datetime import datetime

# Structured logging
logger = logging.getLogger(__name__)

def log_security_event(event_type: str, **kwargs):
    """Log security events in structured JSON format."""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "severity": "SECURITY",
        **kwargs
    }
    logger.warning(json.dumps(log_entry))

# Usage
log_security_event(
    "authentication_failure",
    api_key_prefix=api_key[:8],
    client_ip=request.client.host,
    endpoint=request.url.path
)
```

**Log Retention:**

- **Security logs**: 1 year minimum
- **Access logs**: 90 days minimum
- **Debug logs**: 7 days

### Failed Authentication Tracking

**Implement Account Lockout:**

```python
from collections import defaultdict
import time

# Track failed attempts per IP
failed_attempts = defaultdict(list)
LOCKOUT_THRESHOLD = 5
LOCKOUT_WINDOW = 300  # 5 minutes
LOCKOUT_DURATION = 900  # 15 minutes

def check_lockout(client_ip: str) -> bool:
    """Check if IP is locked out due to failed attempts."""
    now = time.time()

    # Remove old attempts
    failed_attempts[client_ip] = [
        t for t in failed_attempts[client_ip]
        if now - t < LOCKOUT_WINDOW
    ]

    # Check if locked out
    if len(failed_attempts[client_ip]) >= LOCKOUT_THRESHOLD:
        return True

    return False

def record_failed_attempt(client_ip: str):
    """Record failed authentication attempt."""
    failed_attempts[client_ip].append(time.time())

    if len(failed_attempts[client_ip]) >= LOCKOUT_THRESHOLD:
        log_security_event(
            "account_lockout",
            client_ip=client_ip,
            attempts=len(failed_attempts[client_ip])
        )
```

### Anomaly Detection

**Simple Anomaly Detection:**

```python
# Detect unusual query patterns
def detect_query_anomalies(query: str, client_ip: str):
    """Detect potentially malicious queries."""

    # Unusually long queries
    if len(query) > 5000:
        log_security_event("anomaly_long_query", client_ip=client_ip, length=len(query))

    # Suspicious patterns
    suspicious_patterns = [
        r'<script',  # XSS attempt
        r'UNION SELECT',  # SQL injection
        r'\.\./\.\.',  # Path traversal
        r'eval\(',  # Code injection
    ]

    for pattern in suspicious_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            log_security_event(
                "anomaly_suspicious_pattern",
                client_ip=client_ip,
                pattern=pattern,
                query_prefix=query[:100]
            )
```

**Behavioral Analysis:**

```python
# Track query rate per user/IP
from collections import deque

query_history = defaultdict(lambda: deque(maxlen=100))

def detect_abnormal_behavior(client_ip: str):
    """Detect abnormal query behavior."""
    now = time.time()
    query_history[client_ip].append(now)

    # Check for unusual spike
    recent_queries = sum(1 for t in query_history[client_ip] if now - t < 60)

    if recent_queries > 50:  # 50 queries in 1 minute
        log_security_event(
            "anomaly_query_spike",
            client_ip=client_ip,
            queries_per_minute=recent_queries
        )
```

### Security Metrics

**Key Metrics to Monitor:**

```python
# Prometheus metrics example
from prometheus_client import Counter, Histogram, Gauge

# Authentication metrics
auth_attempts = Counter('kb_auth_attempts_total', 'Total authentication attempts', ['status'])
auth_failures = Counter('kb_auth_failures_total', 'Failed authentication attempts', ['reason'])

# Request metrics
request_duration = Histogram('kb_request_duration_seconds', 'Request duration', ['endpoint'])
request_size = Histogram('kb_request_size_bytes', 'Request size in bytes')

# Security event metrics
security_events = Counter('kb_security_events_total', 'Security events', ['event_type'])
rate_limit_hits = Counter('kb_rate_limit_hits_total', 'Rate limit hits', ['client'])

# Active API keys
active_api_keys = Gauge('kb_active_api_keys', 'Number of active API keys')
```

**Alert Thresholds:**

```yaml
# Example: Prometheus alerting rules
groups:
  - name: security_alerts
    rules:
      - alert: HighAuthFailureRate
        expr: rate(kb_auth_failures_total[5m]) > 10
        for: 5m
        annotations:
          summary: "High authentication failure rate detected"

      - alert: UnusualQueryVolume
        expr: rate(kb_request_duration_seconds_count[5m]) > 100
        for: 10m
        annotations:
          summary: "Unusual query volume detected"

      - alert: FrequentRateLimiting
        expr: rate(kb_rate_limit_hits_total[5m]) > 5
        for: 5m
        annotations:
          summary: "Frequent rate limiting events"
```

---

## Docker Security

### Container Hardening

**Non-Root User Execution:**

```dockerfile
# Dockerfile (already implemented)
RUN groupadd -r knowledgebeast --gid=1000 && \
    useradd -r -g knowledgebeast --uid=1000 --home-dir=/app knowledgebeast

USER knowledgebeast
```

**Read-Only Filesystem:**

```yaml
# docker-compose.yml
services:
  api:
    read_only: true
    tmpfs:
      - /tmp:size=100M
      - /app/logs:size=1G
    volumes:
      - ./data:/data:rw  # Only data directory is writable
```

**Resource Limits:**

```yaml
# docker-compose.yml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
```

**Drop Capabilities:**

```yaml
# docker-compose.yml
services:
  api:
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE  # Only if binding to port < 1024
```

### Image Security Scanning

**Scan for Vulnerabilities:**

```bash
# Using Trivy
trivy image knowledgebeast:latest

# Using Docker Scout
docker scout cves knowledgebeast:latest

# Using Snyk
snyk container test knowledgebeast:latest
```

**Automated Scanning in CI/CD:**

```yaml
# .github/workflows/security-scan.yml
name: Security Scan

on: [push, pull_request]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Build image
        run: docker build -t knowledgebeast:${{ github.sha }} .

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: knowledgebeast:${{ github.sha }}
          format: 'sarif'
          output: 'trivy-results.sarif'

      - name: Upload Trivy results to GitHub Security tab
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: 'trivy-results.sarif'
```

### Secrets in Containers

**Using Docker Secrets:**

```bash
# Create secret
echo "your_api_key_here" | docker secret create kb_api_key -

# Use in service
docker service create \
  --name knowledgebeast \
  --secret kb_api_key \
  -e KB_API_KEY_FILE=/run/secrets/kb_api_key \
  knowledgebeast:latest
```

**Using Environment Files:**

```yaml
# docker-compose.yml
services:
  api:
    env_file:
      - .env.production  # NOT committed to git
    environment:
      - KB_API_KEY=${KB_API_KEY}
```

### Network Isolation

```yaml
# docker-compose.yml
networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true  # No internet access

services:
  api:
    networks:
      - frontend
      - backend

  redis:
    networks:
      - backend  # Only accessible from backend network
```

---

## Incident Response

### Incident Response Plan

**1. Preparation:**
- Maintain contact list (security team, management)
- Document escalation procedures
- Keep backups and recovery procedures updated
- Test incident response plan quarterly

**2. Detection & Analysis:**
- Monitor security logs and alerts
- Investigate suspicious activity
- Classify severity (Critical/High/Medium/Low)
- Determine scope and impact

**3. Containment:**
- Isolate affected systems
- Revoke compromised credentials
- Block malicious IPs
- Preserve evidence for forensics

**4. Eradication:**
- Remove malware/backdoors
- Patch vulnerabilities
- Update security controls
- Verify system integrity

**5. Recovery:**
- Restore from clean backups
- Verify system functionality
- Monitor for reinfection
- Return to normal operations

**6. Lessons Learned:**
- Document incident timeline
- Identify root cause
- Implement preventive measures
- Update incident response plan

### Emergency Procedures

**Suspected API Key Compromise:**

```bash
# 1. Immediately revoke compromised key
# Edit .env, remove compromised key
KB_API_KEY=new_key_only

# 2. Restart services
docker-compose restart api

# 3. Review access logs for unauthorized usage
grep "compromised_key_prefix" /app/logs/*.log

# 4. Generate new API keys for all clients
./scripts/generate_api_keys.sh

# 5. Notify affected parties
# 6. Conduct security audit
```

**Active Attack in Progress:**

```bash
# 1. Block attacking IP immediately
sudo ufw deny from 203.0.113.42

# 2. Enable enhanced logging
export KB_LOG_LEVEL=DEBUG

# 3. Capture traffic for analysis
sudo tcpdump -i eth0 host 203.0.113.42 -w attack_capture.pcap

# 4. Review real-time logs
tail -f /app/logs/security.log | grep "203.0.113.42"

# 5. If severe, consider taking API offline temporarily
docker-compose stop api

# 6. Investigate and remediate before restoring service
```

**Data Breach:**

```bash
# 1. Isolate affected systems
docker network disconnect frontend knowledgebeast_api_1

# 2. Preserve evidence
docker exec knowledgebeast_api_1 tar -czf /tmp/evidence.tar.gz /data /app/logs
docker cp knowledgebeast_api_1:/tmp/evidence.tar.gz ./evidence_$(date +%Y%m%d_%H%M%S).tar.gz

# 3. Notify stakeholders (management, legal, customers)
# 4. Engage forensic specialists
# 5. Comply with breach notification regulations (GDPR, etc.)
```

### Communication Templates

**Security Incident Notification:**

```
Subject: SECURITY INCIDENT - [SEVERITY] - [Brief Description]

Incident ID: INC-2025-XXX
Severity: [Critical/High/Medium/Low]
Detected: [Timestamp]
Status: [Investigating/Contained/Resolved]

SUMMARY:
[Brief description of incident]

IMPACT:
- Systems affected: [List]
- Data affected: [Type and scope]
- Users affected: [Estimate]

ACTIONS TAKEN:
1. [Action 1]
2. [Action 2]

NEXT STEPS:
- [Planned action 1]
- [Planned action 2]

CONTACT:
Security Team: security@example.com
Incident Commander: [Name]

This is a security-sensitive communication. Do not forward.
```

---

## Security Testing

### Regular Security Scans

**Dependency Scanning:**

```bash
# Check for known vulnerabilities in Python packages
pip install pip-audit
pip-audit

# Check with Safety
pip install safety
safety check

# Automated scanning in CI/CD
pip-audit --format json > security-report.json
```

**Static Code Analysis:**

```bash
# Bandit - Python security linter
pip install bandit
bandit -r knowledgebeast/ -ll -i

# Example output:
# >> Issue: [B608:hardcoded_sql_expressions] Possible SQL injection
#    Severity: Medium   Confidence: Low

# Semgrep - Advanced static analysis
semgrep --config=auto knowledgebeast/
```

**Secrets Scanning:**

```bash
# Detect accidentally committed secrets
pip install detect-secrets
detect-secrets scan > .secrets.baseline

# In CI/CD
detect-secrets-hook --baseline .secrets.baseline $(git diff --cached --name-only)
```

### Penetration Testing

**Automated Tools:**

```bash
# OWASP ZAP - Web application scanner
docker run -t owasp/zap2docker-stable zap-baseline.py \
  -t https://api.example.com \
  -r zap-report.html

# Nuclei - Vulnerability scanner
nuclei -u https://api.example.com -severity high,critical

# Nikto - Web server scanner
nikto -h https://api.example.com
```

**Manual Testing Checklist:**

- [ ] Test authentication bypass attempts
- [ ] Test authorization (privilege escalation)
- [ ] Test input validation (XSS, SQLi, command injection)
- [ ] Test session management
- [ ] Test rate limiting effectiveness
- [ ] Test CORS configuration
- [ ] Test file upload security
- [ ] Test error handling (information disclosure)
- [ ] Test API endpoint security
- [ ] Test TLS/SSL configuration

### Security Test Automation

**Continuous Security Testing:**

```yaml
# .github/workflows/security-tests.yml
name: Security Tests

on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday
  push:
    branches: [ main ]

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run Bandit security scan
        run: |
          pip install bandit
          bandit -r knowledgebeast/ -f json -o bandit-report.json

      - name: Run dependency check
        run: |
          pip install pip-audit
          pip-audit --format json > pip-audit-report.json

      - name: Run secret scanning
        run: |
          pip install detect-secrets
          detect-secrets scan --all-files

      - name: Upload security reports
        uses: actions/upload-artifact@v3
        with:
          name: security-reports
          path: |
            bandit-report.json
            pip-audit-report.json
```

---

## Compliance & Regulations

### GDPR Compliance

**Data Subject Rights:**

- **Right to Access**: Provide API for users to retrieve their data
- **Right to Deletion**: Implement data deletion endpoints
- **Right to Portability**: Export data in machine-readable format
- **Right to Rectification**: Allow data updates

**Implementation Example:**

```python
# GDPR compliance endpoints
@app.post("/api/v1/gdpr/export")
async def export_user_data(user_id: str, api_key: str = Depends(get_api_key)):
    """Export all data for a user (GDPR Article 20)."""
    user_data = kb.get_user_data(user_id)
    return {
        "user_id": user_id,
        "export_date": datetime.utcnow().isoformat(),
        "data": user_data,
        "format": "JSON"
    }

@app.delete("/api/v1/gdpr/delete")
async def delete_user_data(user_id: str, api_key: str = Depends(get_api_key)):
    """Delete all data for a user (GDPR Article 17)."""
    kb.delete_user_data(user_id)
    log_security_event("gdpr_deletion", user_id=user_id)
    return {"status": "deleted", "user_id": user_id}
```

**Data Retention:**

```python
# Automated data retention policy
from datetime import datetime, timedelta

def enforce_data_retention():
    """Delete data older than retention period."""
    retention_days = 365  # Configurable
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

    deleted_count = kb.delete_data_before(cutoff_date)
    logger.info(f"Data retention: deleted {deleted_count} old records")
```

### SOC 2 Compliance

**Key Requirements:**

1. **Access Control**: API key authentication, role-based access
2. **Encryption**: TLS for data in transit, optional encryption at rest
3. **Logging**: Comprehensive audit logs
4. **Monitoring**: Security event monitoring and alerting
5. **Incident Response**: Documented procedures
6. **Backup & Recovery**: Regular backups, tested recovery

**Evidence Collection:**

```python
# Audit trail for SOC 2
def create_audit_log(event_type: str, user: str, action: str, resource: str):
    """Create immutable audit log entry."""
    audit_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "user": user,
        "action": action,
        "resource": resource,
        "result": "success"  # or "failure"
    }

    # Write to append-only log
    with open('/data/audit.log', 'a') as f:
        f.write(json.dumps(audit_entry) + '\n')
```

### HIPAA Compliance (If Handling Health Data)

**Critical Requirements:**

- **Encryption at rest**: Encrypt all data files
- **Encryption in transit**: TLS 1.2+ only
- **Access logs**: Log all PHI access
- **Minimum necessary**: Restrict data access
- **Data integrity**: Verify data hasn't been altered

```python
# Example: HIPAA-compliant encryption
from cryptography.fernet import Fernet
import hashlib

def encrypt_phi_data(data: bytes, key: bytes) -> bytes:
    """Encrypt Protected Health Information."""
    cipher = Fernet(key)
    encrypted = cipher.encrypt(data)

    # Create integrity hash
    integrity_hash = hashlib.sha256(encrypted).hexdigest()

    # Log access
    log_security_event("phi_encryption", integrity_hash=integrity_hash)

    return encrypted
```

---

## Security Configuration Examples

### Production .env Template

```bash
# KnowledgeBeast Production Security Configuration
# Copy to .env and customize

# ============================================================================
# CRITICAL SECURITY SETTINGS - CONFIGURE BEFORE DEPLOYMENT
# ============================================================================

# API Authentication (REQUIRED)
# Generate with: openssl rand -hex 32
KB_API_KEY=REPLACE_WITH_SECURE_KEY_1,REPLACE_WITH_SECURE_KEY_2

# CORS Allowed Origins (REQUIRED)
# Use exact domains, never use wildcard (*)
KB_ALLOWED_ORIGINS=https://app.example.com,https://api.example.com

# ============================================================================
# NETWORK SECURITY
# ============================================================================

# Force HTTPS
KB_HTTPS_ONLY=true

# Request Limits (DoS Protection)
KB_MAX_REQUEST_SIZE=5242880      # 5 MB for API-only
KB_MAX_QUERY_LENGTH=5000         # 5k characters

# Rate Limiting
KB_RATE_LIMIT_PER_MINUTE=60     # Adjust based on expected traffic

# ============================================================================
# DATA PROTECTION
# ============================================================================

# Data directory (ensure proper permissions)
KB_DATA_DIR=/data

# Cache file location (ensure secure permissions)
KB_CACHE_FILE=/data/cache.json

# ============================================================================
# LOGGING & MONITORING
# ============================================================================

# Log level (INFO for production, DEBUG for troubleshooting)
KB_LOG_LEVEL=INFO

# Enable request logging
KB_ENABLE_REQUEST_LOGGING=true

# Enable security event logging
KB_ENABLE_SECURITY_LOGGING=true

# ============================================================================
# APPLICATION SETTINGS
# ============================================================================

# API server
KB_API_HOST=0.0.0.0
KB_API_PORT=8000
KB_API_WORKERS=2

# Timeouts
KB_REQUEST_TIMEOUT=30
KB_SHUTDOWN_TIMEOUT=10

# ============================================================================
# OPTIONAL: REDIS (for distributed rate limiting)
# ============================================================================

# KB_REDIS_ENABLED=true
# KB_REDIS_HOST=redis
# KB_REDIS_PORT=6379
# KB_REDIS_PASSWORD=REPLACE_WITH_SECURE_PASSWORD
```

### Secure docker-compose.yml

```yaml
version: '3.8'

services:
  api:
    image: knowledgebeast:latest
    container_name: knowledgebeast-api
    restart: unless-stopped

    # Run as non-root user
    user: "1000:1000"

    # Read-only root filesystem
    read_only: true

    # Resource limits
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G

    # Drop all capabilities
    cap_drop:
      - ALL

    # Security options
    security_opt:
      - no-new-privileges:true

    # Environment from secure file
    env_file:
      - .env.production

    # Volumes (minimal, specific)
    volumes:
      - ./data:/data:rw,Z
      - ./config:/config:ro,Z
      - ./knowledge:/knowledge:ro,Z
      - /tmp  # Writable tmp for read-only filesystem

    # Network isolation
    networks:
      - frontend

    # Health check
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s

    # Logging
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

networks:
  frontend:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16

# Secrets (if using Docker secrets)
secrets:
  api_key:
    file: ./secrets/api_key.txt
```

---

## Summary

This guide covers comprehensive security best practices for KnowledgeBeast deployments:

✅ **Authentication**: API key management, rotation, revocation
✅ **Network Security**: CORS, HTTPS, TLS, firewall configuration
✅ **Data Protection**: Cache security, file permissions, secrets management
✅ **Input Validation**: Query sanitization, file upload security, injection prevention
✅ **Production Security**: Security headers, rate limiting, error sanitization
✅ **Monitoring**: Security logging, anomaly detection, metrics
✅ **Docker Security**: Container hardening, image scanning, resource limits
✅ **Incident Response**: Documented procedures, emergency protocols
✅ **Compliance**: GDPR, SOC 2, HIPAA guidelines

### Next Steps

1. **Review the Quick Start Checklist** at the top of this document
2. **Configure Critical Settings**: API keys, CORS origins, HTTPS
3. **Test Security Configuration**: Run security tests and scans
4. **Monitor and Audit**: Set up logging and alerting
5. **Regular Reviews**: Conduct monthly security audits

### Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [KnowledgeBeast Security Policy](../../SECURITY.md)
- [Deployment Guide](../deployment/security.md)

---

**Document Version**: 1.0.0
**Last Updated**: October 6, 2025
**Security Review Status**: ✅ Comprehensive
**Maintained By**: KnowledgeBeast Security Team
