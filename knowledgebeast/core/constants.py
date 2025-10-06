"""Constants for KnowledgeBeast application.

Centralizes magic strings, numbers, and configuration defaults
for maintainability and consistency.
"""

# Cache and File I/O
DEFAULT_CACHE_FILE = ".kb_cache.json"
CACHE_TEMP_SUFFIX = ".tmp"
JSON_INDENT = 2

# Retry Configuration
MAX_RETRY_ATTEMPTS = 3
RETRY_MIN_WAIT_SECONDS = 1
RETRY_MAX_WAIT_SECONDS = 10
RETRY_MULTIPLIER = 1

# Performance Limits
DEFAULT_MAX_CACHE_SIZE = 1000
MIN_HEARTBEAT_INTERVAL = 10
DEFAULT_HEARTBEAT_INTERVAL = 300  # 5 minutes
HIGH_MEMORY_WARNING_MB = 1000

# Rate Limiting
DEFAULT_RATE_LIMIT_PER_MINUTE = 60
DEFAULT_RATE_LIMIT_STORAGE = "memory://"

# Health Check
HEALTH_STATUS_HEALTHY = "healthy"
HEALTH_STATUS_DEGRADED = "degraded"
HEALTH_STATUS_UNHEALTHY = "unhealthy"

# Warming Queries
DEFAULT_WARMING_QUERIES = [
    "audio processing",
    "juce framework",
    "librosa analysis",
    "supercollider patterns",
    "music theory",
    "real-time dsp",
    "knowledge base",
    "configuration settings"
]

# File Extensions
MARKDOWN_EXTENSION = ".md"

# Environment Variable Prefixes
ENV_PREFIX = "KB_"

# API Response Messages
MSG_CACHE_CLEARED = "Cache cleared"
MSG_HEARTBEAT_STARTED = "Heartbeat started successfully"
MSG_HEARTBEAT_STOPPED = "Heartbeat stopped successfully"
MSG_HEARTBEAT_ALREADY_RUNNING = "Heartbeat already running"
MSG_HEARTBEAT_NOT_RUNNING = "Heartbeat not running"
MSG_KB_WARMED = "Knowledge base warmed"
MSG_INGESTION_COMPLETE = "Ingestion completed"

# Error Messages
ERR_EMPTY_SEARCH_TERMS = "Search terms cannot be empty"
ERR_FILE_NOT_FOUND = "File not found"
ERR_NOT_A_FILE = "Path is not a file"
ERR_INTERVAL_TOO_SHORT = "Heartbeat interval must be at least 10 seconds"
ERR_COLLECTION_NOT_FOUND = "Collection not found"

# Logging Format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# HTTP Status Code Messages
HTTP_404_MESSAGE = "The requested resource was not found"
HTTP_500_MESSAGE = "An internal server error occurred"
HTTP_500_DETAIL = "Please contact support if this persists"
HTTP_422_MESSAGE = "Request validation failed"
