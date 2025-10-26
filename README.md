# KnowledgeBeast - Vector RAG Knowledge Management System

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-278%20passing-brightgreen)](./tests)

A production-ready **Vector RAG (Retrieval-Augmented Generation)** knowledge management system combining semantic vector search with traditional keyword matching. Built for speed, reliability, and multi-tenant scalability.

## What's New in v3.0 🎉

### Backend Abstraction Layer

KnowledgeBeast v3.0 introduces a **pluggable backend architecture**:

- **ChromaDBBackend**: Legacy backend (default, backward compatible)
- **PostgresBackend**: Production-ready with pgvector + PostgreSQL full-text search ✨

```python
from knowledgebeast import HybridQueryEngine, DocumentRepository
from knowledgebeast.backends import ChromaDBBackend, PostgresBackend

# ChromaDB backend (default)
backend = ChromaDBBackend(persist_directory="./chroma_db")
repo = DocumentRepository()
engine = HybridQueryEngine(repo, backend=backend)

# PostgreSQL backend (production-ready, requires asyncpg + pgvector)
async with PostgresBackend(
    connection_string="postgresql://user:pass@localhost/kb",
    collection_name="my_kb"
) as postgres_backend:
    engine = HybridQueryEngine(repo, backend=postgres_backend)
    results = await engine.query("search query")

# Or use legacy mode (no backend, in-memory cache)
engine = HybridQueryEngine(repo)  # Still works!
```

**PostgresBackend Requirements:**
- PostgreSQL 15+ with `pgvector` extension
- `asyncpg` Python package: `pip install asyncpg`

See [docs/BACKENDS.md](docs/BACKENDS.md) for detailed backend documentation.

## Features

### Core Capabilities
- **Vector Embeddings**: Semantic search using sentence-transformers (384/768-dimensional embeddings)
- **ChromaDB Integration**: Persistent vector storage with HNSW indexing for fast similarity search
- **Hybrid Search**: Configurable blend of vector similarity (semantic) and keyword matching (exact)
- **Multi-Project Isolation**: Complete tenant isolation with per-project ChromaDB collections and caches
- **Query Optimization**: MMR (Maximal Marginal Relevance) and diversity sampling for varied results

### Performance & Scalability
- **High Performance**: P99 query latency < 100ms, 500+ concurrent queries/sec
- **Intelligent Caching**: Thread-safe LRU caches for embeddings and query results
- **Thread Safety**: Fully thread-safe operations with optimized lock contention (80% reduction)
- **Scalability**: Tested with 10k+ documents, 100+ concurrent users, 100+ projects

### Production Ready
- **Web UI**: Beautiful, responsive interface at `/ui` with real-time search
- **REST API**: FastAPI-powered API with authentication and rate limiting
- **CLI**: Powerful command-line interface
- **Docker**: Production-ready containerization
- **Comprehensive Testing**: 278 tests covering integration, quality (NDCG@10 > 0.85), and performance

## Quick Start

### Installation

```bash
pip install knowledgebeast
```

Or install from source:

```bash
git clone https://github.com/PerformanceSuite/KnowledgeBeast
cd knowledgebeast
pip install -e .
```

### Basic Usage

```python
from knowledgebeast.core.embeddings import EmbeddingEngine
from knowledgebeast.core.vector_store import VectorStore
from knowledgebeast.core.query_engine import HybridQueryEngine
from knowledgebeast.core.repository import DocumentRepository

# Initialize embedding engine
embedding_engine = EmbeddingEngine(model_name="all-MiniLM-L6-v2", cache_size=1000)

# Create vector store
vector_store = VectorStore(
    persist_directory="./chroma_db",
    collection_name="my_knowledge_base"
)

# Ingest documents
documents = [
    "Python is a versatile programming language for data science and web development.",
    "Machine learning enables computers to learn from data without explicit programming.",
    "Natural language processing helps computers understand human language."
]

for i, doc in enumerate(documents):
    embedding = embedding_engine.embed(doc)
    vector_store.add(
        ids=f"doc_{i}",
        embeddings=embedding,
        documents=doc,
        metadatas={'source': 'docs', 'index': i}
    )

# Query with vector search
query = "How do computers learn from data?"
query_embedding = embedding_engine.embed(query)
results = vector_store.query(query_embeddings=query_embedding, n_results=3)

print(f"Top results for: '{query}'")
for doc_id, document, distance in zip(results['ids'][0], results['documents'][0], results['distances'][0]):
    print(f"  [{doc_id}] (distance: {distance:.3f}): {document[:100]}...")
```

### Hybrid Search (Vector + Keyword)

```python
from knowledgebeast.core.repository import DocumentRepository
from knowledgebeast.core.query_engine import HybridQueryEngine

# Create repository and hybrid engine
repo = DocumentRepository()
hybrid_engine = HybridQueryEngine(
    repo,
    model_name="all-MiniLM-L6-v2",
    alpha=0.7  # 70% vector, 30% keyword
)

# Add documents
docs = {
    'python_guide': {
        'name': 'Python Programming Guide',
        'content': 'Python is excellent for data science, machine learning, and automation tasks.',
        'path': 'guides/python.md'
    },
    'ml_basics': {
        'name': 'Machine Learning Basics',
        'content': 'Machine learning algorithms learn patterns from data to make predictions.',
        'path': 'guides/ml.md'
    }
}

for doc_id, doc_data in docs.items():
    repo.add_document(doc_id, doc_data)
    # Index for keyword search
    for term in set(doc_data['content'].lower().split()):
        repo.index_term(term, doc_id)

# Hybrid search (combines semantic + keyword)
results = hybrid_engine.search_hybrid("python machine learning", top_k=5)

for doc_id, doc_data, score in results:
    print(f"{doc_data['name']}: {score:.3f}")

# Pure vector search (semantic only)
vector_results = hybrid_engine.search_vector("artificial intelligence", top_k=5)

# Pure keyword search (exact matching)
keyword_results = hybrid_engine.search_keyword("python")

# MMR for diverse results
mmr_results = hybrid_engine.search_with_mmr(
    "machine learning",
    lambda_param=0.5,  # Balance relevance vs diversity
    top_k=5,
    mode='hybrid'
)
```

### Multi-Project (Multi-Tenant) Usage

```python
from knowledgebeast.core.project_manager import ProjectManager
from knowledgebeast.core.vector_store import VectorStore
from knowledgebeast.core.embeddings import EmbeddingEngine

# Initialize project manager
manager = ProjectManager(
    storage_path="./projects.db",
    chroma_path="./chroma_db",
    cache_capacity=100
)

# Create isolated projects
audio_project = manager.create_project(
    name="Audio Processing",
    description="Audio ML and DSP knowledge base",
    embedding_model="all-MiniLM-L6-v2",
    metadata={'team': 'audio-ml', 'version': '1.0'}
)

nlp_project = manager.create_project(
    name="NLP Research",
    description="Natural language processing knowledge base",
    embedding_model="all-mpnet-base-v2",  # Different model per project
    metadata={'team': 'nlp', 'version': '1.0'}
)

# Each project has isolated vector store
embedding_engine = EmbeddingEngine()

audio_store = VectorStore(
    persist_directory="./chroma_db",
    collection_name=audio_project.collection_name
)

nlp_store = VectorStore(
    persist_directory="./chroma_db",
    collection_name=nlp_project.collection_name
)

# Add documents to audio project
audio_doc = "FFT and spectrograms are essential for audio signal processing."
audio_emb = embedding_engine.embed(audio_doc)
audio_store.add(ids="audio_1", embeddings=audio_emb, documents=audio_doc)

# Add documents to NLP project (completely isolated)
nlp_doc = "Transformers revolutionized natural language processing with attention mechanisms."
nlp_emb = embedding_engine.embed(nlp_doc)
nlp_store.add(ids="nlp_1", embeddings=nlp_emb, documents=nlp_doc)

# Query within project boundaries
audio_results = audio_store.query(
    query_embeddings=embedding_engine.embed("audio processing"),
    n_results=5
)

nlp_results = nlp_store.query(
    query_embeddings=embedding_engine.embed("language models"),
    n_results=5
)

# Projects are completely isolated - no data leakage
print(f"Audio project has {audio_store.count()} documents")
print(f"NLP project has {nlp_store.count()} documents")

# Per-project query caches are also isolated
audio_cache = manager.get_project_cache(audio_project.project_id)
nlp_cache = manager.get_project_cache(nlp_project.project_id)

# Cleanup
manager.delete_project(audio_project.project_id)
manager.delete_project(nlp_project.project_id)
```

## CLI Commands

```bash
# Query with vector search (default hybrid mode)
knowledgebeast query "machine learning algorithms" --mode hybrid --top-k 10

# Pure vector search
knowledgebeast query "natural language processing" --mode vector

# Pure keyword search
knowledgebeast query "python" --mode keyword

# Ingest documents
knowledgebeast ingest document.pdf --chunk-size 1000

# List all projects
knowledgebeast project list

# Create new project
knowledgebeast project create "My Project" --description "My knowledge base"

# Switch project
knowledgebeast project use <project-id>

# Get statistics
knowledgebeast stats

# Start API server
knowledgebeast serve --host 0.0.0.0 --port 8000

# Clear cache
knowledgebeast cache clear
```

## MCP Server (Claude Code Integration)

KnowledgeBeast provides a native **Model Context Protocol (MCP)** server that integrates seamlessly with Claude Desktop and Claude Code. This allows Claude to directly access your knowledge bases, search documents, and manage projects through natural language.

### Quick Setup

1. **Start the MCP Server:**

```bash
knowledgebeast mcp-server --projects-db ./kb_projects.db --chroma-path ./chroma_db
```

2. **Configure Claude Desktop:**

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "knowledgebeast": {
      "command": "knowledgebeast",
      "args": [
        "mcp-server",
        "--projects-db", "/absolute/path/to/kb_projects.db",
        "--chroma-path", "/absolute/path/to/chroma_db"
      ],
      "env": {
        "KB_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

3. **Restart Claude Desktop** and start using KnowledgeBeast through natural language:

```
"Create a knowledge base project called 'technical-docs'"
"Ingest this document into technical-docs: 'Machine learning is...'"
"Search technical-docs for 'API authentication best practices'"
```

### Available MCP Tools

Once connected, Claude has access to these KnowledgeBeast operations:

**Knowledge Management:**
- `kb_search` - Search documents (vector, keyword, hybrid modes)
- `kb_ingest` - Add documents from content or files
- `kb_list_documents` - List project documents
- `kb_batch_ingest` - Bulk document ingestion
- `kb_delete_document` - Remove documents

**Project Management:**
- `kb_list_projects` - List all projects
- `kb_create_project` - Create new projects
- `kb_get_project_info` - Get project details and statistics
- `kb_delete_project` - Delete projects

**Advanced Operations:**
- `kb_export_project` - Export project data to JSON
- `kb_import_project` - Import project from JSON
- `kb_create_template` - Create reusable project templates

### Documentation

- **[Setup Guide](./docs/mcp/CLAUDE_CODE_SETUP.md)**: Complete installation and configuration
- **[Examples](./docs/mcp/EXAMPLES.md)**: Common workflows and patterns
- **[Troubleshooting](./docs/mcp/CLAUDE_CODE_SETUP.md#troubleshooting)**: Common issues and solutions

### Example Workflows

**Creating a Knowledge Base:**
```
User: "Create a project called 'api-docs' for API documentation"
Claude: [Uses kb_create_project tool]
        Project created with ID: proj_abc123
```

**Ingesting Documents:**
```
User: "Add the file /docs/rest-api.md to api-docs"
Claude: [Uses kb_ingest tool]
        Document ingested successfully (doc_xyz789)
```

**Searching:**
```
User: "Search api-docs for 'authentication methods'"
Claude: [Uses kb_search tool with hybrid mode]
        Found 3 relevant documents:
        1. OAuth 2.0 Implementation Guide (score: 0.92)
        2. API Key Authentication (score: 0.85)
        3. JWT Token Best Practices (score: 0.78)
```

**Export/Import Projects:**
```
User: "Export my api-docs project to a backup file"
Claude: [Uses kb_export_project tool]
        Project exported successfully:
        - File: /backups/api-docs-2025-10-24.json
        - Documents: 15
        - Size: 2.4 MB

User: "Export as ZIP for easier transfer"
Claude: [Uses kb_export_project tool with format="zip"]
        Project exported as ZIP:
        - File: /backups/api-docs-2025-10-24.zip
        - Documents: 15
        - Compressed size: 428 KB (82% compression)

User: "Import that backup as a new project called 'api-docs-restored'"
Claude: [Uses kb_import_project tool]
        Project imported successfully:
        - New Project ID: proj_def456
        - Name: api-docs-restored
        - Documents restored: 15
        - All embeddings preserved
```

### Export/Import Features

- **Multiple Formats**: Export to JSON, YAML, or compressed ZIP
- **Complete Fidelity**: Preserves all documents, embeddings, and metadata
- **Project Transfer**: Move projects between KnowledgeBeast instances
- **Backup & Recovery**: Create snapshots for disaster recovery
- **Version Control**: Export to JSON for tracking changes
- **Compression**: ZIP format reduces file size by 70-90%

## Web UI

Start the server:

```bash
knowledgebeast serve
```

Then visit **http://localhost:8000/ui** for the beautiful web interface.

### Features:
- **Real-time Vector Search**: Semantic search with live results
- **Search Mode Toggle**: Switch between vector, keyword, and hybrid search
- **Statistics Dashboard**: Live metrics on embeddings, queries, and cache performance
- **Health Monitoring**: Auto-refreshing system status
- **Cache Management**: Warm cache and clear with one click
- **Responsive Design**: Works on desktop, tablet, and mobile

## REST API

### Authentication

All API endpoints require authentication via API key:

```bash
# Set API key
export KB_API_KEY="your_secret_api_key_here"

# Or use .env file
echo "KB_API_KEY=your_secret_api_key_here" > .env
```

### Core Endpoints

```bash
# Health check
curl http://localhost:8000/api/v1/health \
  -H "X-API-Key: your_secret_api_key_here"

# Vector search
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_secret_api_key_here" \
  -d '{
    "query": "machine learning algorithms",
    "mode": "hybrid",
    "top_k": 10,
    "alpha": 0.7
  }'

# Ingest document
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_secret_api_key_here" \
  -d '{
    "file_path": "/path/to/document.pdf",
    "chunk_size": 1000
  }'

# Get embedding statistics
curl http://localhost:8000/api/v1/stats/embeddings \
  -H "X-API-Key: your_secret_api_key_here"

# Get vector store statistics
curl http://localhost:8000/api/v1/stats/vectors \
  -H "X-API-Key: your_secret_api_key_here"

# List projects
curl http://localhost:8000/api/v1/projects \
  -H "X-API-Key: your_secret_api_key_here"

# Create project
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_secret_api_key_here" \
  -d '{
    "name": "My Project",
    "description": "Project description",
    "embedding_model": "all-MiniLM-L6-v2"
  }'
```

## Performance

KnowledgeBeast is optimized for production workloads with comprehensive benchmarking:

### Latency Benchmarks

| Metric | Target | Actual |
|--------|--------|--------|
| P50 Query Latency | < 50ms | ~35ms |
| P95 Query Latency | < 100ms | ~75ms |
| P99 Query Latency | < 150ms | ~120ms |
| P99 Cached Query | < 10ms | ~3ms |
| Embedding Latency (batch 32) | < 100ms | ~80ms |

### Throughput Benchmarks

| Metric | Target | Actual |
|--------|--------|--------|
| Concurrent Throughput (10 workers) | > 500 q/s | ~800 q/s |
| Concurrent Throughput (50 workers) | > 300 q/s | ~600 q/s |
| Embedding Throughput (batch) | > 50 emb/s | ~120 emb/s |

### Search Quality Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Vector Search NDCG@10 | > 0.85 | ~0.91 |
| Hybrid Search NDCG@10 | > 0.85 | ~0.93 |
| Keyword Search NDCG@10 | > 0.50 | ~0.67 |
| Mean Average Precision (MAP) | > 0.60 | ~0.74 |
| Cache Hit Ratio | > 90% | ~95% |

### Scalability

- **10k+ documents**: Tested and verified
- **100+ concurrent queries**: No degradation
- **100+ projects**: Full isolation maintained
- **Memory efficiency**: Cache-bounded, predictable

See [BENCHMARK_REPORT.md](./BENCHMARK_REPORT.md) for detailed results.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   KnowledgeBeast Vector RAG                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   CLI        │  │   Web UI     │  │   REST API   │     │
│  │   (Click)    │  │  (FastAPI)   │  │  (FastAPI)   │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                 │                 │              │
│         └─────────────────┼─────────────────┘              │
│                           │                                │
│         ┌─────────────────▼─────────────────┐             │
│         │    HybridQueryEngine              │             │
│         │  ┌────────────┬─────────────┐     │             │
│         │  │ Vector (α) │ Keyword (1-α)│    │             │
│         │  │  Search    │   Search     │    │             │
│         │  └────────────┴─────────────┘     │             │
│         │         MMR Re-ranking            │             │
│         └─────────┬─────────────┬──────────┘             │
│                   │             │                         │
│         ┌─────────▼───────┐  ┌──▼──────────┐             │
│         │ EmbeddingEngine │  │ Repository  │             │
│         │ ┌─────────────┐ │  │ (Keyword    │             │
│         │ │ LRU Cache   │ │  │  Index)     │             │
│         │ │ (1000 emb)  │ │  └─────────────┘             │
│         │ └─────────────┘ │                               │
│         │ SentenceTransf. │                               │
│         └────────┬─────────┘                              │
│                  │                                         │
│         ┌────────▼──────────┐   ┌─────────────────┐      │
│         │   VectorStore     │   │ ProjectManager  │      │
│         │   ┌───────────┐   │   │ ┌─────────────┐ │      │
│         │   │ ChromaDB  │   │   │ │  SQLite DB  │ │      │
│         │   │ HNSW Index│   │   │ │  (Metadata) │ │      │
│         │   │ Persistent│   │   │ └─────────────┘ │      │
│         │   └───────────┘   │   │ Per-Project:    │      │
│         │  384/768-dim vecs │   │ - Collections   │      │
│         └───────────────────┘   │ - Caches        │      │
│                                 └─────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

1. **EmbeddingEngine**: Generates 384 or 768-dimensional vectors using sentence-transformers
   - Thread-safe LRU cache (1000 embeddings)
   - Batch processing support
   - Multiple model support (MiniLM, MPNet, Multilingual)

2. **VectorStore**: ChromaDB-backed persistent vector storage
   - HNSW indexing for fast similarity search
   - Metadata filtering
   - Cosine similarity/L2 distance metrics

3. **HybridQueryEngine**: Combines vector and keyword search
   - Configurable alpha parameter (0=keyword only, 1=vector only)
   - MMR re-ranking for diversity
   - Thread-safe, lock-free query execution

4. **ProjectManager**: Multi-tenant isolation
   - Per-project ChromaDB collections
   - Per-project query caches
   - SQLite metadata storage

## Configuration

### Embedding Models

KnowledgeBeast supports multiple sentence-transformer models:

| Model | Dimensions | Speed | Quality | Use Case |
|-------|------------|-------|---------|----------|
| all-MiniLM-L6-v2 | 384 | Fast | Good | General purpose, low latency |
| all-mpnet-base-v2 | 768 | Medium | Best | High quality search |
| paraphrase-multilingual-mpnet-base-v2 | 768 | Medium | Best | Multilingual support |

```python
# Choose model
engine = EmbeddingEngine(
    model_name="all-mpnet-base-v2",  # Higher quality
    cache_size=1000
)
```

### Hybrid Search Alpha Parameter

The `alpha` parameter controls the blend of vector vs keyword search:

- **alpha = 0.0**: Pure keyword search (exact matching)
- **alpha = 0.3**: Keyword-heavy hybrid
- **alpha = 0.5**: Balanced hybrid
- **alpha = 0.7**: Vector-heavy hybrid (default)
- **alpha = 1.0**: Pure vector search (semantic only)

```python
# Experiment with different alpha values
for alpha in [0.0, 0.3, 0.5, 0.7, 1.0]:
    results = engine.search_hybrid("query", alpha=alpha, top_k=5)
    print(f"Alpha {alpha}: {len(results)} results")
```

### MMR Parameters

MMR (Maximal Marginal Relevance) balances relevance and diversity:

- **lambda_param = 0.0**: Maximum diversity (minimal relevance)
- **lambda_param = 0.5**: Balanced
- **lambda_param = 1.0**: Maximum relevance (minimal diversity)

```python
results = engine.search_with_mmr(
    "machine learning",
    lambda_param=0.5,  # Balance relevance/diversity
    top_k=10,
    mode='hybrid'
)
```

## Guides

- **[Vector RAG Guide](./docs/guides/vector-rag-guide.md)**: Deep dive into vector search and RAG
- **[Multi-Project Guide](./docs/guides/multi-project-guide.md)**: Multi-tenant architecture
- **[Performance Tuning](./docs/guides/vector-performance-tuning.md)**: Optimization tips

## Development

### Setup

```bash
git clone https://github.com/PerformanceSuite/KnowledgeBeast
cd knowledgebeast
make dev  # Install development dependencies
```

### Running Tests

```bash
# All tests (278 tests)
make test

# Integration tests
pytest tests/integration/ -v

# Quality tests (NDCG@10, MAP, etc.)
pytest tests/quality/ -v

# Performance benchmarks
pytest tests/performance/ -v

# Scalability tests (10k docs, 100 concurrent queries)
pytest tests/performance/test_scalability.py -v

# With coverage
pytest --cov=knowledgebeast --cov-report=html
```

### Code Quality

```bash
make format  # Format code with black
make lint    # Run linters (flake8, mypy)
```

## Docker Deployment

```bash
# Build image
docker build -t knowledgebeast .

# Run with docker-compose
docker-compose up -d

# Or run directly
docker run -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -e KB_API_KEY=your_key_here \
  knowledgebeast
```

## Migration from Term-Based to Vector RAG

If you're upgrading from the old term-based KnowledgeBeast:

### Key Changes

1. **Vector embeddings** replace simple term matching
2. **Hybrid search** combines semantic + keyword
3. **Multi-project support** for tenant isolation
4. **ChromaDB** replaces in-memory index

### Migration Steps

```python
# Old approach (term-based)
from knowledgebeast.core.engine import KnowledgeBase

kb = KnowledgeBase(config)
results = kb.query("search terms")

# New approach (vector RAG)
from knowledgebeast.core.embeddings import EmbeddingEngine
from knowledgebeast.core.vector_store import VectorStore
from knowledgebeast.core.query_engine import HybridQueryEngine
from knowledgebeast.core.repository import DocumentRepository

# 1. Create components
embedding_engine = EmbeddingEngine()
vector_store = VectorStore(persist_directory="./chroma_db")
repo = DocumentRepository()
hybrid_engine = HybridQueryEngine(repo)

# 2. Ingest documents
for doc_id, content in documents.items():
    embedding = embedding_engine.embed(content)
    vector_store.add(ids=doc_id, embeddings=embedding, documents=content)

# 3. Query with hybrid search
results = hybrid_engine.search_hybrid("search query", top_k=10)
```

See [Migration Guide](./docs/guides/migration-guide.md) for details.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](./CONTRIBUTING.md).

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - see [LICENSE](./LICENSE) for details.

## Acknowledgments

- **[ChromaDB](https://www.trychroma.com/)**: Vector database
- **[sentence-transformers](https://www.sbert.net/)**: Embedding models
- **[Docling](https://github.com/DS4SD/docling)**: Document conversion
- **[FastAPI](https://fastapi.tiangolo.com/)**: REST API framework
- **[Click](https://click.palletsprojects.com/)**: CLI framework

## Support

- **Documentation**: [https://github.com/PerformanceSuite/KnowledgeBeast](https://github.com/PerformanceSuite/KnowledgeBeast)
- **Issues**: [GitHub Issues](https://github.com/PerformanceSuite/KnowledgeBeast/issues)
- **Discussions**: [GitHub Discussions](https://github.com/PerformanceSuite/KnowledgeBeast/discussions)

---

**Built with ❤️ for AI-powered knowledge management**
