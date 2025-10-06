# Code Style Guide

Coding standards for KnowledgeBeast.

## Python Style

Follow PEP 8 with these tools:

### Black (Code Formatting)

```bash
black knowledgebeast tests
```

Settings in `pyproject.toml`:
- Line length: 100
- Target version: Python 3.11

### Ruff (Linting)

```bash
ruff check knowledgebeast
```

### MyPy (Type Checking)

```bash
mypy knowledgebeast
```

## Type Hints

Always use type hints:

```python
from typing import List, Dict, Any

def query(text: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """Query with type hints."""
    ...
```

## Docstrings

Use Google-style docstrings:

```python
def query(text: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """Query the knowledge base.

    Args:
        text: Query text
        n_results: Number of results

    Returns:
        List of results with metadata

    Raises:
        ValueError: If query is empty
    """
    ...
```

## Naming Conventions

- Classes: `PascalCase`
- Functions: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private: `_leading_underscore`

## Import Order

1. Standard library
2. Third-party packages
3. Local imports

```python
import os
from pathlib import Path

import click
from fastapi import FastAPI

from knowledgebeast import KnowledgeBeast
```

## Pre-commit Hooks

Install pre-commit hooks:

```bash
pre-commit install
```

This runs black, ruff, and mypy before each commit.
