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

#### 5. CORS

Configure CORS appropriately:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Don't use "*" in production
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

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

See [Production Checklist](docs/deployment/production-checklist.md).

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
