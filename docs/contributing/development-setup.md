# Development Setup

Set up your development environment for contributing to KnowledgeBeast.

## Prerequisites

- Python 3.11+
- Git
- Make (optional, but recommended)

## Setup Steps

### 1. Fork and Clone

```bash
git clone https://github.com/yourusername/knowledgebeast
cd knowledgebeast
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Using make
make dev

# Or manually
pip install -e ".[dev]"
```

### 4. Install Pre-commit Hooks

```bash
pre-commit install
```

### 5. Verify Installation

```bash
# Run tests
make test

# Check code style
make lint

# Run CLI
knowledgebeast --version
```

## Development Workflow

### 1. Create Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes

Edit code, add tests, update docs.

### 3. Run Tests

```bash
make test
```

### 4. Format Code

```bash
make format
```

### 5. Lint Code

```bash
make lint
```

### 6. Commit Changes

```bash
git add .
git commit -m "feat: add amazing feature"
```

### 7. Push and Create PR

```bash
git push origin feature/your-feature-name
```

## Project Structure

```
knowledgebeast/
├── knowledgebeast/       # Source code
│   ├── core/            # Core engine
│   ├── api/             # REST API
│   ├── cli/             # CLI commands
│   └── utils/           # Utilities
├── tests/               # Tests
├── docs/                # Documentation
├── examples/            # Examples
├── Makefile            # Build commands
└── pyproject.toml      # Project config
```

## Running Locally

### CLI Development

```bash
# Run CLI commands
knowledgebeast init
knowledgebeast query "test"
```

### API Development

```bash
# Start server with auto-reload
knowledgebeast serve --reload

# Or with uvicorn
uvicorn knowledgebeast.api.app:app --reload
```

### Running Tests

```bash
# All tests
make test

# Specific test file
pytest tests/test_cli.py

# With coverage
pytest --cov=knowledgebeast
```

## Code Style

We use:
- **black** for code formatting
- **ruff** for linting
- **mypy** for type checking

```bash
# Format code
black knowledgebeast tests

# Lint
ruff check knowledgebeast

# Type check
mypy knowledgebeast
```

## Next Steps

- [Testing Guide](testing.md)
- [Code Style Guide](code-style.md)
- [Contributing Guide](../../CONTRIBUTING.md)
