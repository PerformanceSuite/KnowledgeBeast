# Security Configuration Guide

This document describes the security features and configuration options in KnowledgeBeast.

## Table of Contents

- [Overview](#overview)
- [CORS Configuration](#cors-configuration)
- [Security Headers](#security-headers)
- [Request Size Limits](#request-size-limits)
- [Cache Security](#cache-security)
- [Best Practices](#best-practices)
- [Environment Variables](#environment-variables)

## Overview

KnowledgeBeast implements multiple layers of security to protect against common web application vulnerabilities:

- **CORS Restrictions**: Configurable origin allowlist to prevent unauthorized cross-origin access
- **Security Headers**: Comprehensive HTTP security headers (CSP, HSTS, X-Frame-Options, etc.)
- **Request Size Limits**: Protection against DoS attacks via oversized requests
- **Secure Caching**: JSON-only cache format (no pickle deserialization)
- **Rate Limiting**: Configurable request rate limits

## CORS Configuration

### Environment Variable

Configure allowed origins via the `KB_ALLOWED_ORIGINS` environment variable:

```bash
# Single origin
KB_ALLOWED_ORIGINS=https://app.example.com

# Multiple origins (comma-separated)
KB_ALLOWED_ORIGINS=https://app.example.com,https://api.example.com,https://admin.example.com
```

### Default Behavior

If `KB_ALLOWED_ORIGINS` is not set, KnowledgeBeast defaults to localhost origins for development:

- `http://localhost:3000`
- `http://localhost:8000`
- `http://localhost:8080`
- `http://127.0.0.1:3000`
- `http://127.0.0.1:8000`
- `http://127.0.0.1:8080`

### Allowed Methods

CORS is restricted to only necessary HTTP methods:

- `GET` - Reading data
- `POST` - Creating/querying
- `DELETE` - Removing data
- `OPTIONS` - CORS preflight

Methods like `PUT`, `PATCH`, and `HEAD` are **not** allowed by default.

### Production Configuration

**Never use wildcard (`*`) origins in production.** Always specify exact origins:

```bash
# ❌ INSECURE - Do not use in production
KB_ALLOWED_ORIGINS=*

# ✅ SECURE - Specify exact origins
KB_ALLOWED_ORIGINS=https://app.example.com,https://api.example.com
```

## Security Headers

KnowledgeBeast automatically adds comprehensive security headers to all HTTP responses.

### Headers Applied

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME type sniffing |
| `X-Frame-Options` | `DENY` | Prevent clickjacking attacks |
| `X-XSS-Protection` | `1; mode=block` | Enable browser XSS protection |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Control referrer information leakage |
| `Content-Security-Policy` | (see below) | Restrict resource loading |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` | Force HTTPS (when enabled) |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=()` | Restrict browser features |

### Content Security Policy (CSP)

The CSP header restricts where resources can be loaded from:

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

### HSTS (HTTP Strict Transport Security)

HSTS is automatically enabled for HTTPS connections (detected via `X-Forwarded-Proto` header):

- **Max Age**: 1 year (31,536,000 seconds)
- **Include Subdomains**: Yes
- **Preload**: Enabled

## Request Size Limits

Protect against DoS attacks by limiting request sizes.

### Configuration

```bash
# Maximum request body size in bytes (default: 10MB)
KB_MAX_REQUEST_SIZE=10485760

# Maximum query string length in characters (default: 10k)
KB_MAX_QUERY_LENGTH=10000
```

### Behavior

Requests exceeding these limits receive a `413 Request Entity Too Large` response:

```json
{
  "error": "RequestEntityTooLarge",
  "message": "Request body too large",
  "detail": "Maximum request size is 10485760 bytes (10MB)",
  "status_code": 413
}
```

### Recommended Limits

| Environment | Body Size | Query Length |
|-------------|-----------|--------------|
| Development | 10MB | 10,000 chars |
| Production (API) | 5MB | 5,000 chars |
| Production (File Upload) | 50MB | 10,000 chars |

## Cache Security

KnowledgeBeast uses **JSON-only** caching for security.

### Pickle Removal

Previous versions used Python's `pickle` module for caching, which poses a **Remote Code Execution (RCE)** risk if cache files are tampered with.

**Current behavior:**

- All cache files are stored in secure JSON format
- Pickle deserialization has been **completely removed**
- Legacy pickle caches are detected and automatically rebuilt as JSON

### Cache Migration

If a legacy pickle cache is detected, you'll see:

```
⚠️  Legacy pickle cache detected - rebuilding in secure JSON format...
```

The system will automatically:
1. Detect the pickle cache
2. Rebuild the index from source markdown files
3. Save the new cache in JSON format

**No manual intervention required.**

## Best Practices

### Production Deployment

1. **CORS Configuration**
   ```bash
   # Specify exact allowed origins
   KB_ALLOWED_ORIGINS=https://yourdomain.com,https://api.yourdomain.com
   ```

2. **HTTPS Only**
   ```bash
   # Enable HTTPS enforcement
   KB_HTTPS_ONLY=true
   ```

3. **Request Limits**
   ```bash
   # Adjust based on your use case
   KB_MAX_REQUEST_SIZE=5242880  # 5MB for API-only
   KB_MAX_QUERY_LENGTH=5000
   ```

4. **Rate Limiting**
   ```bash
   # Prevent abuse
   KB_RATE_LIMIT_PER_MINUTE=60
   ```

### Reverse Proxy Configuration

When running behind a reverse proxy (nginx, Apache, Cloudflare):

1. **Ensure X-Forwarded-Proto is set** for proper HSTS detection
   ```nginx
   proxy_set_header X-Forwarded-Proto $scheme;
   ```

2. **Add additional security headers** at the proxy level (defense in depth)
   ```nginx
   add_header X-Content-Type-Options "nosniff" always;
   add_header X-Frame-Options "DENY" always;
   ```

3. **Configure TLS properly**
   ```nginx
   ssl_protocols TLSv1.2 TLSv1.3;
   ssl_prefer_server_ciphers on;
   ssl_ciphers "EECDH+AESGCM:EDH+AESGCM";
   ```

### Regular Security Audits

Run security scans regularly:

```bash
# Bandit - Python security scanner
bandit -r knowledgebeast/

# Safety - Check dependencies for vulnerabilities
safety check

# Run security tests
pytest tests/security/ -v
```

### Monitoring

Monitor for security events:

- Failed CORS requests (unauthorized origins)
- 413 errors (potential DoS attempts)
- Rate limit violations
- Unusual request patterns

## Environment Variables

Complete list of security-related environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `KB_ALLOWED_ORIGINS` | localhost origins | Comma-separated list of allowed CORS origins |
| `KB_MAX_REQUEST_SIZE` | `10485760` (10MB) | Maximum request body size in bytes |
| `KB_MAX_QUERY_LENGTH` | `10000` | Maximum query string length in characters |
| `KB_RATE_LIMIT_PER_MINUTE` | `100` | Requests allowed per minute per IP |
| `KB_HTTPS_ONLY` | `false` | Enforce HTTPS-only access |

## Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Content Security Policy Reference](https://content-security-policy.com/)
- [HSTS Preload List](https://hstspreload.org/)
- [CORS Best Practices](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)

## Support

For security issues or questions:

- Review the [SECURITY.md](../../SECURITY.md) file
- Open a security advisory on GitHub (for vulnerabilities)
- Contact the maintainers for security-related questions

---

**Last Updated**: 2025-10-05
**Security Review Status**: ✅ Comprehensive security hardening implemented
