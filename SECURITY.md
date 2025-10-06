# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please report it responsibly.

### How to Report

**DO NOT** create a public GitHub issue for security vulnerabilities.

Instead:

1. **Email**: Send details to [security@example.com](mailto:security@example.com)
2. **Include**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)
3. **Response Time**: We aim to respond within 48 hours

### What to Expect

1. **Acknowledgment**: We'll acknowledge your report within 48 hours
2. **Investigation**: We'll investigate and validate the issue
3. **Fix**: We'll develop and test a fix
4. **Release**: We'll release a security patch
5. **Disclosure**: We'll publicly disclose the issue (after fix is released)
6. **Credit**: You'll be credited in the security advisory (unless you prefer otherwise)

## Security Hardening

KnowledgeBeast includes comprehensive security hardening:

### Implemented Security Features

#### 1. CORS Protection
- **Environment-based configuration**: Use `KB_ALLOWED_ORIGINS` to specify exact allowed origins
- **No wildcard origins**: Default to localhost for development; requires explicit configuration
- **Restricted methods**: Only GET, POST, DELETE, OPTIONS allowed
- **Secure by default**: Prevents unauthorized cross-origin access

```bash
# Configure allowed origins
KB_ALLOWED_ORIGINS=https://app.example.com,https://api.example.com
```

#### 2. Security Headers
- **X-Content-Type-Options**: Prevents MIME sniffing attacks
- **X-Frame-Options**: Prevents clickjacking (DENY)
- **X-XSS-Protection**: Browser XSS protection enabled
- **Content-Security-Policy**: Restricts resource loading to prevent XSS
- **Strict-Transport-Security**: Forces HTTPS when enabled (1 year, includeSubDomains, preload)
- **Referrer-Policy**: Controls referrer information leakage
- **Permissions-Policy**: Restricts browser features (geolocation, microphone, camera)

#### 3. Request Size Limits
- **Body size limit**: Default 10MB, configurable via `KB_MAX_REQUEST_SIZE`
- **Query string limit**: Default 10k characters, configurable via `KB_MAX_QUERY_LENGTH`
- **DoS protection**: Returns 413 for oversized requests

```bash
# Configure request limits
KB_MAX_REQUEST_SIZE=10485760  # 10MB
KB_MAX_QUERY_LENGTH=10000     # 10k chars
```

#### 4. Secure Caching
- **JSON-only cache**: Removed pickle deserialization (RCE risk eliminated)
- **Automatic migration**: Legacy pickle caches automatically rebuilt as JSON
- **No remote code execution**: All cache operations use safe JSON format

#### 5. Rate Limiting
- **Configurable limits**: Default 100 requests/minute
- **Per-IP tracking**: Prevents abuse from single sources
- **Customizable storage**: Memory or Redis backend

See [Security Configuration Guide](docs/deployment/security.md) for detailed configuration.

## Security Best Practices

### For Users

#### 1. Authentication

KnowledgeBeast does not include built-in authentication. For production:

```python
# Add authentication middleware
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != "your-secret-key":
        raise HTTPException(status_code=403, detail="Invalid API key")
```

#### 2. HTTPS/TLS

Always use HTTPS in production:

```bash
# Use reverse proxy with TLS
# Example with nginx
server {
    listen 443 ssl;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
    }
}
```

#### 3. Input Validation

KnowledgeBeast validates inputs, but additional validation is recommended:

```python
# Example: Sanitize file paths
from pathlib import Path

def safe_path(user_input: str) -> Path:
    path = Path(user_input).resolve()
    # Validate path is within allowed directory
    if not path.is_relative_to("/allowed/directory"):
        raise ValueError("Invalid path")
    return path
```

#### 4. Rate Limiting

Rate limiting is enabled by default (30 queries/minute). Adjust for your needs:

```python
# Custom rate limits
@limiter.limit("100/minute")
async def query_endpoint():
    ...
```

#### 5. CORS Configuration (Critical)

**CORS is now configured via environment variable** - do not modify code:

```bash
# Development (default if not set)
# Uses localhost:3000, localhost:8000, etc.

# Production (REQUIRED)
KB_ALLOWED_ORIGINS=https://yourdomain.com,https://api.yourdomain.com

# ❌ NEVER use wildcard in production
# KB_ALLOWED_ORIGINS=*  # INSECURE - DO NOT USE
```

The application automatically restricts CORS to configured origins and only allows necessary methods (GET, POST, DELETE).

#### 6. Secrets Management

Never hardcode secrets:

```python
import os

# Use environment variables
API_KEY = os.getenv("KB_API_KEY")
if not API_KEY:
    raise ValueError("KB_API_KEY not set")
```

#### 7. File Upload Security

If accepting file uploads:

- Validate file types
- Scan for malware
- Limit file sizes
- Use separate storage

#### 8. Data Privacy

KnowledgeBeast stores data locally. For sensitive data:

- Encrypt data at rest
- Use access controls
- Implement audit logging
- Follow data retention policies

### For Developers

#### 1. Dependencies

- Keep dependencies updated
- Review security advisories
- Use `pip-audit` to check for vulnerabilities

```bash
pip install pip-audit
pip-audit
```

#### 2. Code Review

- All PRs require review
- Security-focused code review
- Automated security scanning

#### 3. Testing

- Security-focused tests
- Input validation tests
- Authentication/authorization tests

#### 4. Secrets in Code

- Never commit secrets
- Use `.gitignore` for sensitive files
- Use environment variables or secret managers

## Security Hardening Checklist

Use this checklist to ensure your deployment is secure:

### Critical (Must Do)

- [ ] **Configure CORS origins** - Set `KB_ALLOWED_ORIGINS` to your specific domains
- [ ] **Enable HTTPS** - Use TLS/SSL certificates (via reverse proxy or direct)
- [ ] **Set request limits** - Configure `KB_MAX_REQUEST_SIZE` and `KB_MAX_QUERY_LENGTH`
- [ ] **Review security headers** - All security headers are enabled by default
- [ ] **Verify cache format** - Ensure using JSON cache (not pickle)

### Recommended

- [ ] **Add authentication** - Implement API key or OAuth2
- [ ] **Enable rate limiting** - Configure `KB_RATE_LIMIT_PER_MINUTE`
- [ ] **Set up monitoring** - Track 413, CORS, and rate limit errors
- [ ] **Run security scans** - Use `bandit -r knowledgebeast/`
- [ ] **Review dependencies** - Run `pip-audit` regularly
- [ ] **Implement logging** - Monitor security events
- [ ] **Backup data** - Regular backups of knowledge base

### Production Checklist

```bash
# 1. Set allowed origins (CRITICAL)
export KB_ALLOWED_ORIGINS=https://yourdomain.com

# 2. Configure request limits
export KB_MAX_REQUEST_SIZE=5242880  # 5MB for API
export KB_MAX_QUERY_LENGTH=5000

# 3. Enable rate limiting
export KB_RATE_LIMIT_PER_MINUTE=60

# 4. Run security scan
bandit -r knowledgebeast/

# 5. Run security tests
pytest tests/security/ -v

# 6. Verify no pickle usage
grep -r "pickle" knowledgebeast/core/engine.py  # Should only show comments
```

See [Security Configuration Guide](docs/deployment/security.md) for complete documentation.

## Known Security Considerations

### 1. Local File Access

KnowledgeBeast requires local file access for ingestion. Ensure:
- Proper file permissions
- Validated file paths
- Restricted directory access

### 2. No Built-in Authentication

Production deployments should add:
- API key authentication
- JWT tokens
- OAuth2

See [Security Configuration Guide](docs/deployment/security.md).

### 3. Embeddings Model

The default embedding model downloads from Hugging Face:
- First run requires internet connection
- Models are cached locally
- Consider using local models for air-gapped deployments

### 4. Vector Database

ChromaDB stores data locally:
- Ensure proper file permissions
- Consider encryption at rest
- Backup regularly

## Recent Security Improvements (v0.1.x)

### October 2025 - Comprehensive Security Hardening

- ✅ **CORS hardening**: Environment-based configuration, no wildcard
- ✅ **Pickle removal**: Eliminated RCE risk, JSON-only cache
- ✅ **Security headers**: CSP, HSTS, X-Frame-Options, etc.
- ✅ **Request limits**: DoS protection via size limits
- ✅ **15+ security tests**: Comprehensive test coverage

## Security Updates

Security updates will be:
- Released as patch versions (0.1.x)
- Announced in GitHub Releases
- Documented in CHANGELOG.md
- Highlighted in security advisories

## Compliance

KnowledgeBeast is designed to be compliant with:
- GDPR (when configured appropriately)
- SOC 2 (with proper deployment)
- ISO 27001 (with proper controls)

Compliance depends on your deployment and configuration.

## Contact

For security concerns: [security@example.com](mailto:security@example.com)

For general questions: [GitHub Issues](https://github.com/yourusername/knowledgebeast/issues)

---

Last updated: 2025-10-05
