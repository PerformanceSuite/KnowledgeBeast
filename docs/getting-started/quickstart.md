# Quick Start Guide

Get up and running with KnowledgeBeast in under 30 seconds!

## 30-Second Quick Start

```bash
# 1. Install
pip install knowledgebeast

# 2. Initialize
knowledgebeast init

# 3. Ingest a document
knowledgebeast ingest path/to/document.pdf

# 4. Query
knowledgebeast query "What is machine learning?"
```

## Step-by-Step Tutorial

### 1. Create a Knowledge Base

```bash
# Initialize a new knowledge base
knowledgebeast init --data-dir ./my-knowledge

# This creates:
# ./my-knowledge/
#   └── chroma_db/  (vector database)
```

### 2. Add Documents

```bash
# Ingest a single document
knowledgebeast ingest document.pdf --data-dir ./my-knowledge

# Ingest multiple documents from a directory
knowledgebeast add ./documents/ --recursive --data-dir ./my-knowledge
```

**Supported Formats:**
- PDF (.pdf)
- Markdown (.md)
- Text (.txt)
- Word (.docx)
- HTML (.html)

### 3. Query Your Knowledge Base

```bash
# Basic query
knowledgebeast query "machine learning best practices" --data-dir ./my-knowledge

# Get more results
knowledgebeast query "deep learning" -n 10 --data-dir ./my-knowledge

# Disable cache for fresh results
knowledgebeast query "neural networks" --no-cache --data-dir ./my-knowledge
```

### 4. View Statistics

```bash
# Basic stats
knowledgebeast stats --data-dir ./my-knowledge

# Detailed stats
knowledgebeast stats --detailed --data-dir ./my-knowledge
```

## Using the Python API

```python
from knowledgebeast import KnowledgeBeast, KnowledgeBeastConfig

# Initialize with default configuration
kb = KnowledgeBeast()

# Ingest a document
chunks = kb.ingest_document("document.pdf")
print(f"Ingested {chunks} chunks")

# Query the knowledge base
results = kb.query("machine learning", n_results=5)

for result in results:
    print(f"Source: {result['metadata']['source']}")
    print(f"Text: {result['text']}")
    print(f"Distance: {result['distance']}")
    print()

# Get statistics
stats = kb.get_stats()
print(f"Total documents: {stats['total_documents']}")

# Cleanup
kb.shutdown()
```

## Using Context Manager (Recommended)

```python
from knowledgebeast import KnowledgeBeast

# Automatic cleanup with context manager
with KnowledgeBeast() as kb:
    # Ingest
    kb.ingest_document("document.pdf")

    # Query
    results = kb.query("your question")

    # Process results
    for result in results:
        print(result['text'])
# Automatically cleaned up on exit
```

## Starting the API Server

```bash
# Start server on default port (8000)
knowledgebeast serve

# Custom host and port
knowledgebeast serve --host 0.0.0.0 --port 8080

# With auto-reload for development
knowledgebeast serve --reload
```

Test the API:

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Query
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "machine learning", "n_results": 5}'
```

## Docker Quick Start

```bash
# Using docker-compose
docker-compose up -d

# Or run directly
docker run -p 8000:8000 -v $(pwd)/data:/app/data knowledgebeast
```

## Common Workflows

### Academic Research

```bash
# Initialize research knowledge base
knowledgebeast init --data-dir ./research-kb

# Add research papers
knowledgebeast add ./papers/ --recursive --data-dir ./research-kb

# Query for specific topics
knowledgebeast query "neural network architectures" -n 20 --data-dir ./research-kb
```

### Documentation Search

```bash
# Initialize docs knowledge base
knowledgebeast init --data-dir ./docs-kb

# Add markdown documentation
knowledgebeast add ./docs/ --recursive --data-dir ./docs-kb

# Search documentation
knowledgebeast query "API authentication" --data-dir ./docs-kb
```

### Code Knowledge Base

```bash
# Initialize code knowledge base
knowledgebeast init --data-dir ./code-kb

# Add code documentation
knowledgebeast add ./README.md --data-dir ./code-kb
knowledgebeast add ./ARCHITECTURE.md --data-dir ./code-kb

# Query code concepts
knowledgebeast query "caching implementation" --data-dir ./code-kb
```

## Next Steps

- [Configuration Guide](configuration.md) - Customize your knowledge base
- [Python API Guide](../guides/python-api.md) - Deep dive into the Python SDK
- [CLI Usage Guide](../guides/cli-usage.md) - Master the command-line interface
- [REST API Guide](../guides/rest-api.md) - Build integrations
- [Architecture Overview](../architecture/overview.md) - Understand how it works

## Getting Help

```bash
# Show all available commands
knowledgebeast --help

# Show help for a specific command
knowledgebeast query --help
```

## Troubleshooting

### No results found

- Ensure documents are properly ingested: `knowledgebeast stats`
- Try a broader query
- Increase n_results: `-n 20`

### Slow queries

- Enable caching (enabled by default)
- Warm the cache: `knowledgebeast warm`
- Check system resources

### Out of memory

- Reduce cache size in configuration
- Process documents in smaller batches
- Increase system RAM
