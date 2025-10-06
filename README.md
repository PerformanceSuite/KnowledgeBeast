# KnowledgeBeast

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-ready knowledge management system with RAG (Retrieval-Augmented Generation) capabilities. Built for speed, reliability, and ease of use.

## Features

- **🎨 Web UI**: Beautiful, responsive web interface at `/ui`
- **Document Ingestion**: Support for multiple document formats via Docling
- **Vector Search**: Semantic search using sentence-transformers and ChromaDB
- **Intelligent Caching**: LRU cache for query results with configurable size
- **Background Heartbeat**: Continuous health monitoring and maintenance
- **FastAPI Integration**: Production-ready REST API
- **CLI**: Powerful command-line interface with Click
- **Type Safety**: Full type hints and mypy support
- **Production Ready**: Comprehensive error handling, logging, and testing

## Quick Start

### Installation

```bash
pip install knowledgebeast
```

Or install from source:

```bash
git clone https://github.com/yourusername/knowledgebeast
cd knowledgebeast
pip install -e .
```

### Initialize

```bash
knowledgebeast init
```

### Ingest Documents

```bash
knowledgebeast ingest path/to/document.pdf
```

### Query

```bash
knowledgebeast query "What is the main topic?"
```

## Usage

### Python API

```python
from knowledgebeast import KnowledgeBeast, KnowledgeBeastConfig

# Initialize with default config
kb = KnowledgeBeast()

# Ingest a document
chunks = kb.ingest_document("path/to/document.pdf")
print(f"Ingested {chunks} chunks")

# Query the knowledge base
results = kb.query("machine learning best practices", n_results=5)
for result in results:
    print(f"Text: {result['text']}")
    print(f"Source: {result['metadata']['source']}")
    print(f"Distance: {result['distance']}")

# Get statistics
stats = kb.get_stats()
print(stats)

# Cleanup
kb.shutdown()
```

### Using Context Manager

```python
from knowledgebeast import KnowledgeBeast

with KnowledgeBeast() as kb:
    results = kb.query("your question")
    # Automatic cleanup on exit
```

### Custom Configuration

```python
from pathlib import Path
from knowledgebeast import KnowledgeBeast, KnowledgeBeastConfig

config = KnowledgeBeastConfig(
    data_dir=Path("./my_data"),
    collection_name="my_collection",
    embedding_model="all-MiniLM-L6-v2",
    cache_size=200,
    heartbeat_interval=30.0
)

kb = KnowledgeBeast(config)
```

### CLI Commands

```bash
# Initialize a new knowledge base
knowledgebeast init --data-dir ./data

# Ingest a document
knowledgebeast ingest document.pdf --data-dir ./data

# Query the knowledge base
knowledgebeast query "your question" -n 10 --data-dir ./data

# Show statistics
knowledgebeast stats --data-dir ./data

# Clear all documents
knowledgebeast clear --data-dir ./data

# Start the API server
knowledgebeast serve --host 0.0.0.0 --port 8000
```

### Web UI

Start the server:

```bash
knowledgebeast serve
```

Then visit **http://localhost:8000/ui** for the beautiful web interface.

Features:
- 🔍 **Real-time Search**: Interactive semantic search with live results
- 📊 **Statistics Dashboard**: Live metrics and performance data
- 💚 **Health Monitoring**: Auto-refreshing system status
- ⚡ **Cache Management**: Warm KB and clear cache with one click
- 📱 **Responsive Design**: Works on desktop, tablet, and mobile

### REST API

Or with uvicorn directly:

```bash
uvicorn knowledgebeast.api.app:app --host 0.0.0.0 --port 8000
```

API endpoints:

- `GET /` - API information and links
- `GET /ui` - Web UI (static files)
- `GET /api/v1/health` - Health check
- `POST /api/v1/query` - Query the knowledge base
- `GET /api/v1/stats` - Get statistics
- `POST /api/v1/ingest` - Ingest a document
- `POST /api/v1/warm` - Warm knowledge base
- `POST /api/v1/cache/clear` - Clear query cache
- `GET /api/v1/stats` - Get statistics
- `DELETE /api/v1/clear` - Clear all documents

Example API usage:

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Query
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "machine learning", "n_results": 5}'

# Ingest document
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/path/to/document.pdf"}'
```

### Docker Deployment

```bash
# Build image
docker build -t knowledgebeast .

# Run with docker-compose
docker-compose up -d
```

Or run directly:

```bash
docker run -p 8000:8000 -v $(pwd)/data:/app/data knowledgebeast
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     KnowledgeBeast                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   CLI        │  │   API        │  │   Python     │     │
│  │   (Click)    │  │  (FastAPI)   │  │   SDK        │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                 │                 │              │
│         └─────────────────┼─────────────────┘              │
│                           │                                │
│                  ┌────────▼────────┐                       │
│                  │  Core Engine    │                       │
│                  ├─────────────────┤                       │
│                  │  - Ingestion    │                       │
│                  │  - Query        │                       │
│                  │  - Caching      │                       │
│                  │  - Heartbeat    │                       │
│                  └────────┬────────┘                       │
│                           │                                │
│         ┌─────────────────┼─────────────────┐             │
│         │                 │                 │             │
│    ┌────▼────┐      ┌────▼────┐      ┌────▼────┐        │
│    │ Docling │      │ ChromaDB│      │  Cache  │        │
│    │Converter│      │  Vector │      │  (LRU)  │        │
│    └─────────┘      │  Store  │      └─────────┘        │
│                     └─────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

## Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/yourusername/knowledgebeast
cd knowledgebeast

# Install development dependencies
make dev

# Or manually
pip install -e ".[dev]"
```

### Running Tests

```bash
make test
```

### Code Quality

```bash
# Format code
make format

# Run linters
make lint
```

### Available Make Commands

```bash
make help          # Show all available commands
make install       # Install production dependencies
make dev           # Install development dependencies
make test          # Run tests with coverage
make lint          # Run linters
make format        # Format code
make clean         # Clean build artifacts
make build         # Build distribution packages
make docker-build  # Build Docker image
make docker-run    # Run Docker container
make serve         # Start API server
```

## Configuration

KnowledgeBeast can be configured via:

1. **Python API**: Pass `KnowledgeBeastConfig` object
2. **CLI**: Use command-line options
3. **Environment Variables**: Prefix with `KB_`

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `data_dir` | `./data` | Directory for storing data and indexes |
| `collection_name` | `knowledge_base` | ChromaDB collection name |
| `embedding_model` | `all-MiniLM-L6-v2` | Sentence-transformers model |
| `chunk_size` | `1000` | Maximum chunk size in characters |
| `chunk_overlap` | `200` | Overlap between chunks |
| `cache_size` | `100` | Maximum LRU cache size |
| `heartbeat_interval` | `60.0` | Heartbeat interval in seconds |
| `log_level` | `INFO` | Logging level |

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [Docling](https://github.com/DS4SD/docling) for document conversion
- Powered by [ChromaDB](https://www.trychroma.com/) for vector storage
- Uses [sentence-transformers](https://www.sbert.net/) for embeddings
- FastAPI for the REST API
- Click for the CLI

## Support

- Documentation: [https://github.com/yourusername/knowledgebeast#readme](https://github.com/yourusername/knowledgebeast#readme)
- Issues: [https://github.com/yourusername/knowledgebeast/issues](https://github.com/yourusername/knowledgebeast/issues)

---

Made with ❤️ by Daniel Connolly
