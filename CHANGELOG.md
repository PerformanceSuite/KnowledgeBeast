# Changelog

All notable changes to KnowledgeBeast will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive documentation suite
- Example scripts and integrations
- Production deployment guides

## [0.1.0] - 2025-10-05

### Added
- Initial release of KnowledgeBeast
- Core knowledge base engine with ChromaDB vector storage
- Document ingestion with Docling (PDF, Markdown, DOCX, HTML, TXT)
- Semantic search with sentence-transformers embeddings
- LRU query cache with configurable size
- Background heartbeat monitoring
- FastAPI REST API with 12 endpoints
- Beautiful CLI with Click and Rich
- Docker and Docker Compose support
- Python SDK with context manager support
- Rate limiting and error handling
- Comprehensive logging and monitoring
- Health check endpoints
- Cache warming capabilities
- Multi-directory knowledge base support
- Flexible configuration via Python API, CLI, and environment variables

### Core Features
- **Document Processing**: Support for multiple formats via Docling
- **Vector Search**: Semantic similarity search using ChromaDB
- **Intelligent Caching**: LRU cache with automatic warming
- **Background Tasks**: Heartbeat monitoring and maintenance
- **Production Ready**: Full error handling, logging, and testing
- **Type Safety**: Complete type hints and mypy support

### API Endpoints
- `GET /api/v1/health` - Health check
- `POST /api/v1/query` - Query knowledge base
- `POST /api/v1/ingest` - Ingest document
- `POST /api/v1/batch-ingest` - Batch ingest documents
- `GET /api/v1/stats` - Get statistics
- `DELETE /api/v1/clear` - Clear knowledge base
- `POST /api/v1/cache/clear` - Clear cache
- `POST /api/v1/warm` - Warm knowledge base
- `GET /api/v1/heartbeat/status` - Get heartbeat status
- `POST /api/v1/heartbeat/start` - Start heartbeat
- `POST /api/v1/heartbeat/stop` - Stop heartbeat
- `GET /api/v1/collections` - List collections

### CLI Commands
- `knowledgebeast init` - Initialize knowledge base
- `knowledgebeast ingest` - Ingest single document
- `knowledgebeast add` - Add multiple documents
- `knowledgebeast query` - Query knowledge base
- `knowledgebeast stats` - Show statistics
- `knowledgebeast clear` - Clear all documents
- `knowledgebeast clear-cache` - Clear query cache
- `knowledgebeast warm` - Warm cache
- `knowledgebeast health` - Run health check
- `knowledgebeast heartbeat` - Manage heartbeat
- `knowledgebeast serve` - Start API server
- `knowledgebeast version` - Show version info

### Dependencies
- `docling>=2.5.5` - Document conversion
- `fastapi>=0.109.0` - REST API framework
- `click>=8.1.0` - CLI framework
- `rich>=13.0.0` - Beautiful terminal output
- `chromadb>=0.4.0` - Vector database
- `sentence-transformers>=2.2.0` - Embeddings
- `pydantic>=2.0.0` - Data validation
- `uvicorn[standard]>=0.27.0` - ASGI server

### Technical Details
- Minimum Python version: 3.11
- Default embedding model: all-MiniLM-L6-v2
- Default cache size: 100 queries
- Default heartbeat interval: 60 seconds
- License: MIT

---

## Version History

- **0.1.0** (2025-10-05) - Initial release with core RAG functionality

[Unreleased]: https://github.com/yourusername/knowledgebeast/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/yourusername/knowledgebeast/releases/tag/v0.1.0
