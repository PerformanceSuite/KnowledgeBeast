#!/bin/bash
# KnowledgeBeast Production Entrypoint Script
# Handles initialization, migrations, and graceful shutdown

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Trap signals for graceful shutdown
trap 'log_info "Received SIGTERM, shutting down gracefully..."; exit 0' SIGTERM
trap 'log_info "Received SIGINT, shutting down gracefully..."; exit 0' SIGINT

# Wait for dependencies to be ready
wait_for_service() {
    local host=$1
    local port=$2
    local service_name=$3
    local max_attempts=30
    local attempt=0

    log_info "Waiting for $service_name at $host:$port..."

    while [ $attempt -lt $max_attempts ]; do
        if nc -z "$host" "$port" 2>/dev/null; then
            log_info "$service_name is ready!"
            return 0
        fi
        attempt=$((attempt + 1))
        log_warn "Attempt $attempt/$max_attempts: $service_name not ready yet..."
        sleep 2
    done

    log_error "$service_name failed to become ready after $max_attempts attempts"
    return 1
}

# Check required environment variables
check_env_vars() {
    log_info "Checking required environment variables..."

    local required_vars=(
        "APP_ENV"
        "LOG_LEVEL"
    )

    local missing_vars=()

    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing_vars+=("$var")
        fi
    done

    if [ ${#missing_vars[@]} -gt 0 ]; then
        log_error "Missing required environment variables: ${missing_vars[*]}"
        return 1
    fi

    log_info "All required environment variables are set"
}

# Initialize data directories
init_directories() {
    log_info "Initializing data directories..."

    mkdir -p /app/data/chroma
    mkdir -p /app/data/embeddings
    mkdir -p /app/logs
    mkdir -p /app/cache

    log_info "Data directories initialized"
}

# Run database migrations (if applicable)
run_migrations() {
    log_info "Running database migrations..."

    # Add migration logic here when needed
    # Example: python -m knowledgebeast.migrations.run

    log_info "Migrations completed"
}

# Validate configuration
validate_config() {
    log_info "Validating configuration..."

    # Check if config files exist
    if [ ! -f "/app/config/app.yaml" ] && [ "$APP_ENV" = "production" ]; then
        log_warn "Production config file not found, using defaults"
    fi

    log_info "Configuration validated"
}

# Pre-flight checks
preflight_checks() {
    log_info "Running pre-flight checks..."

    # Check Python version
    python_version=$(python --version 2>&1 | awk '{print $2}')
    log_info "Python version: $python_version"

    # Check disk space
    disk_usage=$(df -h /app | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ "$disk_usage" -gt 90 ]; then
        log_warn "Disk usage is high: ${disk_usage}%"
    else
        log_info "Disk usage: ${disk_usage}%"
    fi

    # Check memory
    if [ -f /proc/meminfo ]; then
        total_mem=$(grep MemTotal /proc/meminfo | awk '{print $2}')
        log_info "Total memory: $((total_mem / 1024)) MB"
    fi

    log_info "Pre-flight checks completed"
}

# Main initialization
main() {
    log_info "==================================================================="
    log_info "Starting KnowledgeBeast v2.3.0 - Production Mode"
    log_info "==================================================================="

    # Run initialization steps
    check_env_vars || exit 1
    init_directories
    validate_config

    # Wait for dependencies if configured
    if [ -n "$CHROMA_HOST" ] && [ -n "$CHROMA_PORT" ]; then
        wait_for_service "$CHROMA_HOST" "$CHROMA_PORT" "ChromaDB" || log_warn "ChromaDB not available, continuing anyway..."
    fi

    if [ -n "$REDIS_HOST" ] && [ -n "$REDIS_PORT" ]; then
        wait_for_service "$REDIS_HOST" "$REDIS_PORT" "Redis" || log_warn "Redis not available, continuing anyway..."
    fi

    # Run migrations
    run_migrations

    # Pre-flight checks
    preflight_checks

    log_info "Initialization complete, starting application..."
    log_info "Environment: $APP_ENV"
    log_info "Log Level: $LOG_LEVEL"
    log_info "Workers: ${WORKERS:-4}"
    log_info "==================================================================="

    # Execute the main command
    exec "$@"
}

# Run main initialization
main "$@"
