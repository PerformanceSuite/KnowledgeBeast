# Testing Guide

Guide for writing and running tests.

## Test Structure

```
tests/
├── __init__.py
├── test_cli.py          # CLI tests
├── test_engine.py       # Core engine tests
├── test_api.py          # API tests
└── conftest.py          # Pytest fixtures
```

## Running Tests

```bash
# All tests
make test

# Specific file
pytest tests/test_cli.py

# Specific test
pytest tests/test_cli.py::test_query

# With coverage
pytest --cov=knowledgebeast --cov-report=html
```

## Writing Tests

### Example Test

```python
import pytest
from knowledgebeast import KnowledgeBeast

def test_query():
    kb = KnowledgeBeast()
    results = kb.query("test")
    assert isinstance(results, list)
    kb.shutdown()

def test_query_with_fixture(kb):
    results = kb.query("test")
    assert len(results) >= 0
```

### Using Fixtures

```python
# conftest.py
import pytest
from knowledgebeast import KnowledgeBeast

@pytest.fixture
def kb():
    kb = KnowledgeBeast()
    yield kb
    kb.shutdown()
```

## Test Coverage

Aim for 80%+ coverage:

```bash
# Run with coverage
pytest --cov=knowledgebeast --cov-report=term-missing

# Generate HTML report
pytest --cov=knowledgebeast --cov-report=html
open htmlcov/index.html
```

## Continuous Integration

Tests run automatically on:
- Pull requests
- Commits to main
- Release tags

See `.github/workflows/` for CI configuration.
