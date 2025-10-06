.PHONY: help install dev test lint format clean build docker-build docker-run docker-stop docker-clean docker-test docker-push docker-dev serve cli-help

# ============================================================================
# General Help
# ============================================================================

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ============================================================================
# Local Development
# ============================================================================

install: ## Install production dependencies
	pip install -e .

dev: ## Install development dependencies
	pip install -e ".[dev]"

test: ## Run tests with coverage
	pytest

lint: ## Run linters (ruff and mypy)
	ruff check knowledgebeast/
	mypy knowledgebeast/

format: ## Format code with black and ruff
	black knowledgebeast/
	ruff check --fix knowledgebeast/

clean: ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

build: clean ## Build distribution packages
	python -m build

serve: ## Start the API server locally
	uvicorn knowledgebeast.api.app:app --reload --host 0.0.0.0 --port 8000

cli-help: ## Show CLI help
	knowledgebeast --help

# ============================================================================
# Docker - Production
# ============================================================================

docker-build: ## Build production Docker image
	@echo "Building production Docker image..."
	docker build -t knowledgebeast:latest -t knowledgebeast:0.1.0 .
	@echo "Build complete: knowledgebeast:latest"

docker-run: ## Run Docker container with docker-compose
	@echo "Starting KnowledgeBeast with docker-compose..."
	docker-compose up -d
	@echo "Service started. Logs: make docker-logs"

docker-stop: ## Stop Docker containers
	@echo "Stopping KnowledgeBeast containers..."
	docker-compose down
	@echo "Containers stopped"

docker-restart: docker-stop docker-run ## Restart Docker containers

docker-logs: ## Show Docker container logs
	docker-compose logs -f

docker-logs-api: ## Show API container logs only
	docker-compose logs -f knowledgebeast

docker-logs-redis: ## Show Redis container logs only
	docker-compose logs -f redis

docker-ps: ## Show running Docker containers
	docker-compose ps

docker-stats: ## Show Docker container stats
	docker stats knowledgebeast knowledgebeast-redis

# ============================================================================
# Docker - Development
# ============================================================================

docker-dev-build: ## Build development Docker image
	@echo "Building development Docker image..."
	docker build -f Dockerfile.dev -t knowledgebeast:dev .
	@echo "Build complete: knowledgebeast:dev"

docker-dev: ## Run development environment with hot reload
	@echo "Starting development environment..."
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
	@echo "Development environment stopped"

docker-dev-daemon: ## Run development environment in background
	@echo "Starting development environment in background..."
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
	@echo "Development environment started. Logs: make docker-dev-logs"

docker-dev-logs: ## Show development container logs
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml logs -f

docker-dev-stop: ## Stop development environment
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml down

# ============================================================================
# Docker - Testing
# ============================================================================

docker-test: ## Run tests in Docker container
	@echo "Running tests in Docker container..."
	docker run --rm \
		-v $(PWD)/tests:/app/tests \
		-v $(PWD)/knowledgebeast:/app/knowledgebeast \
		knowledgebeast:latest \
		pytest -v

docker-test-coverage: ## Run tests with coverage in Docker
	@echo "Running tests with coverage in Docker container..."
	docker run --rm \
		-v $(PWD)/tests:/app/tests \
		-v $(PWD)/knowledgebeast:/app/knowledgebeast \
		knowledgebeast:latest \
		pytest -v --cov=knowledgebeast --cov-report=html

# ============================================================================
# Docker - Maintenance
# ============================================================================

docker-clean: ## Clean Docker images and containers
	@echo "Cleaning Docker resources..."
	docker-compose down -v --remove-orphans
	docker rmi knowledgebeast:latest knowledgebeast:dev 2>/dev/null || true
	docker system prune -f
	@echo "Docker cleanup complete"

docker-clean-all: ## Clean all Docker resources (including volumes)
	@echo "WARNING: This will remove ALL volumes (including data)!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose down -v --remove-orphans; \
		docker rmi knowledgebeast:latest knowledgebeast:dev 2>/dev/null || true; \
		docker system prune -af --volumes; \
		echo "All Docker resources cleaned"; \
	else \
		echo "Cancelled"; \
	fi

docker-shell: ## Open shell in running container
	docker exec -it knowledgebeast /bin/bash

docker-shell-redis: ## Open Redis CLI in running container
	docker exec -it knowledgebeast-redis redis-cli

# ============================================================================
# Docker - Registry Operations
# ============================================================================

REGISTRY ?= docker.io
IMAGE_NAME ?= knowledgebeast
VERSION ?= 0.1.0

docker-tag: ## Tag image for registry
	docker tag knowledgebeast:latest $(REGISTRY)/$(IMAGE_NAME):$(VERSION)
	docker tag knowledgebeast:latest $(REGISTRY)/$(IMAGE_NAME):latest

docker-push: docker-tag ## Push image to registry
	@echo "Pushing to $(REGISTRY)/$(IMAGE_NAME):$(VERSION)..."
	docker push $(REGISTRY)/$(IMAGE_NAME):$(VERSION)
	docker push $(REGISTRY)/$(IMAGE_NAME):latest
	@echo "Push complete"

docker-pull: ## Pull image from registry
	docker pull $(REGISTRY)/$(IMAGE_NAME):$(VERSION)
	docker pull $(REGISTRY)/$(IMAGE_NAME):latest

# ============================================================================
# Docker - Health & Monitoring
# ============================================================================

docker-health: ## Check container health status
	@echo "Container health status:"
	@docker inspect --format='{{json .State.Health}}' knowledgebeast 2>/dev/null | jq '.' || echo "Container not running or no health check configured"

docker-inspect: ## Inspect container details
	docker inspect knowledgebeast | jq '.'

docker-size: ## Show image and container sizes
	@echo "Image sizes:"
	@docker images | grep knowledgebeast
	@echo ""
	@echo "Container sizes:"
	@docker ps -a --filter name=knowledgebeast --format "table {{.Names}}\t{{.Size}}"

# ============================================================================
# Docker - Utilities
# ============================================================================

docker-env: ## Show environment variables in container
	docker exec knowledgebeast env | grep KB_

docker-validate: ## Validate docker-compose configuration
	docker-compose config

docker-validate-dev: ## Validate development docker-compose configuration
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml config

# ============================================================================
# Quick Start Commands
# ============================================================================

up: docker-run ## Alias for docker-run

down: docker-stop ## Alias for docker-stop

rebuild: docker-clean docker-build docker-run ## Clean, rebuild, and run

quick-start: ## Quick start guide
	@echo "KnowledgeBeast Docker Quick Start"
	@echo "=================================="
	@echo ""
	@echo "1. Copy environment file:"
	@echo "   cp .env.example .env"
	@echo ""
	@echo "2. Build and run:"
	@echo "   make docker-build"
	@echo "   make docker-run"
	@echo ""
	@echo "3. Check status:"
	@echo "   make docker-ps"
	@echo ""
	@echo "4. View logs:"
	@echo "   make docker-logs"
	@echo ""
	@echo "5. Open in browser:"
	@echo "   http://localhost:8000/docs"
	@echo ""
	@echo "For development with hot reload:"
	@echo "   make docker-dev"
