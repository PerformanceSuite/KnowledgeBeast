# KnowledgeBeast

A high-performance knowledge base system with intelligent caching, search, and a world-class CLI.

**Powered by battle-tested code from Performia's knowledge_rag_v2.py engine.**

## Features

- **Document Management**: Add and manage Markdown documents with Docling converter
- **Intelligent Search**: Fast word-index based search with LRU caching
- **Automatic Warming**: Pre-load and warm cache on startup for instant queries
- **Cache Warming**: Pre-load frequently accessed data with configurable queries
- **Heartbeat System**: Background maintenance, stale cache detection, and health monitoring
- **Multi-Directory Support**: Ingest from multiple knowledge base directories
- **Progress Callbacks**: Track long operations with custom callbacks
- **Environment Config**: Full configuration via environment variables
- **Production Ready**: Comprehensive error handling and thread-safe operation
- **Beautiful CLI**: Rich terminal output with progress bars, tables, and colors

## Installation

```bash
pip install -e .
```

## Quick Start

### 1. Initialize a Knowledge Base

```bash
knowledgebeast init ./my-knowledge-base
cd my-knowledge-base
```

### 2. Add Documents

```bash
# Add a single file
knowledgebeast add document.pdf

# Add all files in a directory
knowledgebeast add ./documents -r
```

### 3. Query Your Knowledge Base

```bash
knowledgebeast query "machine learning algorithms"
```

### 4. Start the API Server

```bash
knowledgebeast serve --port 5000
```

## CLI Commands

### `knowledgebeast init [PATH]`
Initialize a new knowledge base with directory structure and configuration.

**Options:**
- `--name TEXT` - Knowledge base name
- `--description TEXT` - Description

**Example:**
```bash
knowledgebeast init ./kb --name "My Knowledge Base"
```

---

### `knowledgebeast add <FILE_OR_DIR>`
Add documents to the knowledge base.

**Options:**
- `-r, --recursive` - Add directories recursively
- `--format [pdf|docx|md|txt|html|auto]` - Document format (auto-detect by default)

**Examples:**
```bash
knowledgebeast add document.pdf
knowledgebeast add ./documents -r
```

---

### `knowledgebeast query "search terms"`
Search the knowledge base.

**Options:**
- `--no-cache` - Disable cache for this query
- `-n, --limit INTEGER` - Maximum number of results (default: 10)
- `--min-score FLOAT` - Minimum relevance score 0-1 (default: 0.0)

**Examples:**
```bash
knowledgebeast query "python programming"
knowledgebeast query "search term" --limit 5 --min-score 0.5
```

---

### `knowledgebeast serve`
Start the REST API server.

**Options:**
- `-p, --port INTEGER` - Port to run server on (default: 5000)
- `-h, --host TEXT` - Host to bind to (default: localhost)
- `--debug` - Run in debug mode

**Example:**
```bash
knowledgebeast serve --port 8080 --host 0.0.0.0
```

**API Endpoints:**
- `GET /health` - Health check
- `POST /query` - Search knowledge base
- `GET /stats` - Statistics
- `POST /documents/add` - Add document

---

### `knowledgebeast warm`
Manually trigger cache warming.

**Options:**
- `-f, --force` - Skip cache warming optimization

**Example:**
```bash
knowledgebeast warm
```

---

### `knowledgebeast stats`
Show knowledge base statistics.

**Options:**
- `-d, --detailed` - Show detailed statistics

**Example:**
```bash
knowledgebeast stats --detailed
```

---

### `knowledgebeast heartbeat [start|stop|status]`
Manage background heartbeat process.

**Options:**
- `-i, --interval INTEGER` - Heartbeat interval in seconds (default: 300)

**Examples:**
```bash
knowledgebeast heartbeat start --interval 600
knowledgebeast heartbeat stop
knowledgebeast heartbeat status
```

---

### `knowledgebeast health`
Run health check on the knowledge base.

**Example:**
```bash
knowledgebeast health
```

---

### `knowledgebeast clear-cache`
Clear the query cache.

**Options:**
- `-y, --yes` - Skip confirmation prompt

**Example:**
```bash
knowledgebeast clear-cache --yes
```

---

### `knowledgebeast version`
Display version and system information.

**Example:**
```bash
knowledgebeast version
```

---

## Configuration

KnowledgeBeast uses a `.knowledgebeast.yml` configuration file:

```yaml
name: My Knowledge Base
description: Description of your knowledge base
version: '1.0'

paths:
  documents: ./documents
  cache: ./cache
  index: ./index

cache:
  enabled: true
  max_size: 1000
  ttl: 3600

search:
  max_results: 10
  min_relevance: 0.3

heartbeat:
  enabled: false
  interval: 300
```

## Environment Variables

All configuration can be overridden with environment variables using the `KB_` prefix:

- `KB_CONFIG` - Path to config file (default: `.knowledgebeast.yml`)
- `KB_KNOWLEDGE_DIRS` - Comma-separated list of knowledge directories
- `KB_CACHE_FILE` - Path to cache file
- `KB_MAX_CACHE_SIZE` - Maximum number of cached queries
- `KB_HEARTBEAT_INTERVAL` - Heartbeat interval in seconds
- `KB_AUTO_WARM` - Auto-warm on initialization (true/false)

## Development

### Install Development Dependencies

```bash
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest
```

### Format Code

```bash
black knowledgebeast/
ruff check knowledgebeast/
```

## License

MIT License - see LICENSE file for details.
