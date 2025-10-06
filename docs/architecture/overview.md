# Architecture Overview

KnowledgeBeast is a production-ready RAG (Retrieval-Augmented Generation) knowledge management system built with Python.

## System Architecture

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

## Core Components

### 1. Core Engine
- **Location**: `knowledgebeast/core/engine.py`
- **Purpose**: Main knowledge base engine
- **Features**: Document ingestion, semantic search, caching

### 2. Document Converter (Docling)
- **Purpose**: Convert documents to searchable text
- **Supported Formats**: PDF, Markdown, DOCX, HTML, TXT
- **Features**: Text extraction, metadata preservation

### 3. Vector Store (ChromaDB)
- **Purpose**: Store and search document embeddings
- **Features**: Semantic similarity search, persistence

### 4. Embedding Model (sentence-transformers)
- **Default**: all-MiniLM-L6-v2
- **Purpose**: Convert text to vector embeddings
- **Customizable**: Can use any sentence-transformers model

### 5. LRU Cache
- **Location**: `knowledgebeast/core/cache.py`
- **Purpose**: Cache query results
- **Features**: Configurable size, automatic eviction

### 6. Heartbeat Monitor
- **Location**: `knowledgebeast/core/heartbeat.py`
- **Purpose**: Background health monitoring
- **Features**: Periodic checks, cache warming

## Interfaces

### Python SDK
Direct programmatic access to the knowledge base.

```python
from knowledgebeast import KnowledgeBeast

kb = KnowledgeBeast()
results = kb.query("machine learning")
```

### CLI (Click + Rich)
Command-line interface with beautiful output.

```bash
knowledgebeast query "machine learning"
```

### REST API (FastAPI)
HTTP API for integrations.

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -d '{"query": "machine learning"}'
```

## Data Flow

### Ingestion Pipeline

```
Document → Docling → Text Chunks → Embeddings → ChromaDB
                                                      ↓
                                            Index + Metadata
```

### Query Pipeline

```
Query → Embedding → Vector Search → Top-K Results → Cache
                        ↓
                    ChromaDB
```

## Key Design Decisions

### 1. ChromaDB for Vector Storage
**Why**: Lightweight, embeddable, no external dependencies

**Alternatives Considered**:
- Pinecone (cloud-based, costs)
- Weaviate (heavier, more complex)
- FAISS (no metadata, manual persistence)

### 2. sentence-transformers for Embeddings
**Why**: Easy to use, many pre-trained models, offline support

**Alternatives Considered**:
- OpenAI embeddings (costs, API dependency)
- Custom trained models (training overhead)

### 3. LRU Cache for Query Results
**Why**: Simple, effective, memory-efficient

**Features**:
- Configurable size
- Automatic eviction
- Persistent across restarts

### 4. Docling for Document Conversion
**Why**: Excellent PDF support, preserves structure

**Alternatives Considered**:
- PyPDF2 (basic extraction only)
- Apache Tika (Java dependency)
- Unstructured.io (heavier)

## Performance Characteristics

### Ingestion
- **Speed**: ~1-5 seconds per document (depends on size)
- **Memory**: O(document_size)
- **Storage**: ~2-3x original document size (embeddings + metadata)

### Query
- **Cold Query**: ~100-500ms (embedding + search)
- **Cached Query**: <10ms (cache lookup)
- **Memory**: O(n_results)

### Scaling
- **Documents**: Tested up to 100K documents
- **Query Load**: ~30 queries/second (with caching)
- **Memory**: ~4GB for 10K documents

## Security Considerations

1. **No Authentication**: Currently no built-in auth
2. **Local File Access**: Ingestion requires local file access
3. **Data Privacy**: All data stored locally
4. **API Security**: Rate limiting enabled

See [Security Policy](../../SECURITY.md) for details.

## Next Steps

- [Core Engine](core-engine.md)
- [Caching Strategy](caching-strategy.md)
- [Performance Tuning](performance.md)
