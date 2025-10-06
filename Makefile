.PHONY: help install dev test lint format clean build docker-build docker-run

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

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

docker-build: ## Build Docker image
	docker build -t knowledgebeast:latest .

docker-run: ## Run Docker container
	docker-compose up -d

docker-stop: ## Stop Docker container
	docker-compose down

serve: ## Start the API server
	uvicorn knowledgebeast.api.app:app --reload --host 0.0.0.0 --port 8000

cli-help: ## Show CLI help
	knowledgebeast --help
