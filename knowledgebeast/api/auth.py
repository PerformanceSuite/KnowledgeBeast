"""API Key Authentication for KnowledgeBeast API.

This module provides API key authentication using FastAPI's security utilities.
API keys are validated against environment variables and support rate limiting
per key.

Environment Variables:
    KB_API_KEY: Single API key or comma-separated list of API keys

Usage:
    from knowledgebeast.api.auth import get_api_key

    @router.get("/protected")
    async def protected_route(api_key: str = Depends(get_api_key)):
        return {"message": "Authenticated"}
"""

import logging
import os
import time
from collections import defaultdict
from typing import Dict, Optional, Set

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

# API Key header name
API_KEY_NAME = "X-API-Key"

# API Key header security scheme
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

# Rate limiting storage
# Format: {api_key: [(timestamp1, timestamp2, ...)]}
_rate_limit_storage: Dict[str, list] = defaultdict(list)

# Rate limit configuration (requests per window)
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW = 60  # seconds


def get_valid_api_keys() -> Set[str]:
    """Get set of valid API keys from environment variables.

    Reads KB_API_KEY environment variable which can contain:
    - Single API key: "secret_key_123"
    - Multiple keys (comma-separated): "key1,key2,key3"

    Returns:
        Set of valid API keys

    Raises:
        RuntimeError: If no API keys are configured
    """
    api_key_env = os.getenv("KB_API_KEY", "").strip()

    if not api_key_env:
        logger.warning("KB_API_KEY environment variable not set - API authentication disabled")
        # In production, this should raise an error
        # For development, we'll return an empty set
        return set()

    # Split by comma and strip whitespace
    keys = {key.strip() for key in api_key_env.split(",") if key.strip()}

    if not keys:
        logger.warning("KB_API_KEY is empty - API authentication disabled")
        return set()

    logger.info(f"Loaded {len(keys)} API key(s) from environment")
    return keys


def validate_api_key(api_key: str) -> bool:
    """Validate an API key against configured keys.

    Args:
        api_key: API key to validate

    Returns:
        True if valid, False otherwise
    """
    valid_keys = get_valid_api_keys()

    # If no keys configured, allow access (development mode)
    if not valid_keys:
        logger.warning("No API keys configured - allowing unauthenticated access")
        return True

    return api_key in valid_keys


def check_rate_limit(api_key: str) -> bool:
    """Check if API key has exceeded rate limit.

    Uses a sliding window algorithm to track requests per key.

    Args:
        api_key: API key to check

    Returns:
        True if within rate limit, False if exceeded
    """
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    # Get request history for this key
    request_times = _rate_limit_storage[api_key]

    # Remove old requests outside the window
    request_times[:] = [t for t in request_times if t > window_start]

    # Check if limit exceeded
    if len(request_times) >= RATE_LIMIT_REQUESTS:
        logger.warning(
            f"Rate limit exceeded for API key {api_key[:8]}... "
            f"({len(request_times)} requests in {RATE_LIMIT_WINDOW}s)"
        )
        return False

    # Add current request
    request_times.append(now)
    return True


def get_rate_limit_info(api_key: str) -> Dict[str, int]:
    """Get rate limit information for an API key.

    Args:
        api_key: API key to check

    Returns:
        Dictionary with rate limit info:
        - requests_made: Number of requests in current window
        - requests_remaining: Number of requests remaining
        - window_seconds: Rate limit window in seconds
    """
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    # Get request history for this key
    request_times = _rate_limit_storage[api_key]

    # Count requests in current window
    requests_in_window = sum(1 for t in request_times if t > window_start)

    return {
        "requests_made": requests_in_window,
        "requests_remaining": max(0, RATE_LIMIT_REQUESTS - requests_in_window),
        "window_seconds": RATE_LIMIT_WINDOW,
        "limit": RATE_LIMIT_REQUESTS,
    }


def reset_rate_limit(api_key: Optional[str] = None) -> None:
    """Reset rate limit counters.

    Args:
        api_key: Specific API key to reset, or None to reset all
    """
    if api_key:
        _rate_limit_storage.pop(api_key, None)
        logger.info(f"Reset rate limit for API key {api_key[:8]}...")
    else:
        _rate_limit_storage.clear()
        logger.info("Reset all rate limits")


async def get_api_key(api_key_header_value: str = Security(api_key_header)) -> str:
    """FastAPI dependency for API key authentication.

    Validates the API key from the X-API-Key header and enforces rate limiting.

    Args:
        api_key_header_value: API key from request header

    Returns:
        Validated API key

    Raises:
        HTTPException: If API key is invalid or rate limit exceeded
    """
    # Validate API key
    if not validate_api_key(api_key_header_value):
        logger.warning(f"Invalid API key attempted: {api_key_header_value[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Check rate limit
    if not check_rate_limit(api_key_header_value):
        rate_info = get_rate_limit_info(api_key_header_value)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Limit: {rate_info['limit']} requests per {rate_info['window_seconds']}s",
            headers={
                "X-RateLimit-Limit": str(rate_info["limit"]),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time() + RATE_LIMIT_WINDOW)),
            },
        )

    # Log successful authentication
    logger.debug(f"API key authenticated: {api_key_header_value[:8]}...")

    return api_key_header_value


async def get_api_key_optional(
    api_key_header_value: Optional[str] = Security(api_key_header),
) -> Optional[str]:
    """FastAPI dependency for optional API key authentication.

    Similar to get_api_key but doesn't raise error if key is missing.
    Useful for endpoints that support both authenticated and unauthenticated access.

    Args:
        api_key_header_value: API key from request header

    Returns:
        Validated API key or None

    Raises:
        HTTPException: If API key is provided but invalid
    """
    if not api_key_header_value:
        return None

    return await get_api_key(api_key_header_value)
