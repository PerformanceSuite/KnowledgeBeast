# Installation Guide

## Requirements

- Python 3.11 or higher
- pip (Python package manager)
- 2GB+ RAM recommended
- 1GB+ disk space for embeddings and data

## Installation Methods

### Option 1: Install from PyPI (Recommended)

```bash
pip install knowledgebeast
```

### Option 2: Install from Source

```bash
# Clone the repository
git clone https://github.com/yourusername/knowledgebeast
cd knowledgebeast

# Install in development mode
pip install -e .
```

### Option 3: Install with Development Dependencies

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Or using make
make dev
```

## Verify Installation

```bash
# Check version
knowledgebeast version

# Run health check
knowledgebeast health
```

Expected output:
```
KnowledgeBeast v0.1.0
High-performance RAG knowledge base with intelligent caching and warming

System Information:
  Python: 3.11.x
  Platform: Darwin/Linux/Windows
  Architecture: x86_64/arm64

Built with Click and Rich
```

## System Dependencies

### macOS

```bash
# Install Python 3.11+ via Homebrew
brew install python@3.11
```

### Ubuntu/Debian

```bash
# Install Python 3.11+
sudo apt update
sudo apt install python3.11 python3.11-pip python3.11-venv
```

### Windows

Download Python 3.11+ from [python.org](https://www.python.org/downloads/)

## Optional Dependencies

### For API Development

```bash
pip install uvicorn[standard]
```

### For Development

```bash
pip install pytest pytest-cov black mypy ruff pre-commit
```

## Docker Installation

```bash
# Pull from Docker Hub (when available)
docker pull knowledgebeast/knowledgebeast:latest

# Or build from source
docker build -t knowledgebeast .
```

## Troubleshooting

### Issue: "No module named 'knowledgebeast'"

**Solution**: Ensure you're in the correct virtual environment and have installed the package:

```bash
pip install -e .
```

### Issue: "chromadb" installation fails

**Solution**: Upgrade pip and try again:

```bash
pip install --upgrade pip
pip install chromadb
```

### Issue: "sentence-transformers" requires specific PyTorch version

**Solution**: Install PyTorch first:

```bash
# CPU-only version
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Then install knowledgebeast
pip install knowledgebeast
```

## Next Steps

- [Quick Start Guide](quickstart.md)
- [Configuration](configuration.md)
- [Python API Guide](../guides/python-api.md)
