# Contributing to KnowledgeBeast

Thank you for your interest in contributing to KnowledgeBeast! This document provides guidelines and instructions for contributing.

## Code of Conduct

Be respectful, inclusive, and professional. We welcome contributions from everyone.

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [Issues](https://github.com/yourusername/knowledgebeast/issues)
2. If not, create a new issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (Python version, OS, etc.)
   - Code samples or error messages

### Suggesting Features

1. Check existing [Issues](https://github.com/yourusername/knowledgebeast/issues) and [Discussions](https://github.com/yourusername/knowledgebeast/discussions)
2. Create a new issue with:
   - Clear use case
   - Expected behavior
   - Why this would be useful
   - Possible implementation approach

### Pull Requests

1. **Fork the repository**
   ```bash
   git clone https://github.com/yourusername/knowledgebeast
   cd knowledgebeast
   ```

2. **Create a branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```

3. **Set up development environment**
   ```bash
   make dev
   ```

4. **Make your changes**
   - Write code following our [style guide](docs/contributing/code-style.md)
   - Add tests for new functionality
   - Update documentation as needed
   - Ensure all tests pass

5. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add amazing feature"
   ```

   Use [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` - New feature
   - `fix:` - Bug fix
   - `docs:` - Documentation changes
   - `test:` - Test changes
   - `refactor:` - Code refactoring
   - `chore:` - Build/tooling changes

6. **Push and create PR**
   ```bash
   git push origin feature/amazing-feature
   ```

   Then create a Pull Request on GitHub with:
   - Clear description of changes
   - Link to related issues
   - Screenshots/examples if applicable

## Development Setup

See [Development Setup Guide](docs/contributing/development-setup.md) for detailed instructions.

### Quick Start

```bash
# Clone and setup
git clone https://github.com/yourusername/knowledgebeast
cd knowledgebeast
make dev

# Run tests
make test

# Format code
make format

# Lint code
make lint
```

## Code Style

We use:
- **Black** for code formatting (line length: 100)
- **Ruff** for linting
- **MyPy** for type checking
- **Google-style** docstrings

See [Code Style Guide](docs/contributing/code-style.md) for details.

### Pre-commit Hooks

Install pre-commit hooks to automatically format and lint:

```bash
pre-commit install
```

## Testing

- Write tests for all new functionality
- Aim for 80%+ code coverage
- Run tests before submitting PR

```bash
make test
```

See [Testing Guide](docs/contributing/testing.md) for details.

## Documentation

- Update documentation for any user-facing changes
- Use clear, concise language
- Include code examples
- Add screenshots where helpful

Documentation is in `docs/` directory.

## Review Process

1. Maintainers will review your PR
2. Address any requested changes
3. Once approved, PR will be merged
4. Your changes will be included in the next release

## Release Process

Maintainers follow this process for releases:

1. Update version in `pyproject.toml` and `__init__.py`
2. Update CHANGELOG.md
3. Create release tag
4. Publish to PyPI
5. Create GitHub release

## Getting Help

- **Documentation**: Check [docs/](docs/)
- **Issues**: Search or create an [issue](https://github.com/yourusername/knowledgebeast/issues)
- **Discussions**: Start a [discussion](https://github.com/yourusername/knowledgebeast/discussions)

## Recognition

Contributors will be recognized in:
- CHANGELOG.md
- Release notes
- README.md (for significant contributions)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to KnowledgeBeast! 🚀
