# KnowledgeBeast Migration Guide: v1 → v2

## Overview

This guide walks you through migrating your KnowledgeBeast installation from the term-based index (v1) to vector embeddings with ChromaDB (v2).

**Migration Benefits:**
- **Better semantic search**: Vector embeddings understand meaning, not just keywords
- **Improved relevance**: Results ranked by semantic similarity
- **Hybrid search**: Combine keyword and vector search for best results
- **Modern architecture**: Built on ChromaDB for scalability

**Migration Time:**
- Small knowledge base (< 100 documents): ~1-2 minutes
- Medium knowledge base (100-1000 documents): ~5-10 minutes
- Large knowledge base (1000+ documents): ~15-30 minutes

## Prerequisites

Before migrating, ensure you have:

1. **KnowledgeBeast v2+ installed**
   ```bash
   pip install knowledgebeast>=2.0.0
   ```

2. **Required dependencies**
   ```bash
   pip install chromadb sentence-transformers
   ```

3. **Backup your data** (optional, but recommended)
   ```bash
   cp -r ./data ./data.backup
   ```

## Quick Start: One-Command Migration

The simplest way to migrate is using the CLI:

```bash
knowledgebeast migrate --from term --to vector
```

This command will:
1. ✅ Create automatic backup of your term-based index
2. ✅ Load all existing documents
3. ✅ Generate vector embeddings for each document
4. ✅ Store embeddings in ChromaDB
5. ✅ Provide rollback option if needed

**Example Output:**
```
🚀 KnowledgeBeast Migration Tool
Migrating from term to vector
Data directory: ./data
Embedding model: all-MiniLM-L6-v2

Proceed with migration? [y/N]: y

Step 1/3: Creating backup...
✓ Backup created at ./data/backups/backup_20250107_143022

Step 2/3: Loading documents from term-based index...
✓ Loaded 156 documents

Step 3/3: Migrating to vector embeddings (model: all-MiniLM-L6-v2)...
Migrated 156/156 documents ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100%

╭─ Migration Complete ─────────────────────────────────────────╮
│ Migration successful!                                         │
│                                                              │
│ Documents migrated: 156                                      │
│ Errors: 0                                                    │
│ Duration: 42.3s                                              │
│ Backup: ./data/backups/backup_20250107_143022               │
│                                                              │
│ Your knowledge base is now using vector embeddings!          │
│ Run 'knowledgebeast migrate --rollback' to restore.         │
╰──────────────────────────────────────────────────────────────╯
```

## Advanced Migration Options

### Custom Embedding Model

Choose a different embedding model for your use case:

```bash
# Fast, lightweight (384 dimensions) - DEFAULT
knowledgebeast migrate --embedding-model all-MiniLM-L6-v2

# Balanced speed/quality (768 dimensions)
knowledgebeast migrate --embedding-model all-mpnet-base-v2

# Multilingual support (768 dimensions)
knowledgebeast migrate --embedding-model paraphrase-multilingual-mpnet-base-v2
```

**Model Comparison:**

| Model | Dimensions | Speed | Quality | Use Case |
|-------|-----------|-------|---------|----------|
| all-MiniLM-L6-v2 | 384 | Fast | Good | General purpose, fast queries |
| all-mpnet-base-v2 | 768 | Medium | Excellent | High-quality search |
| paraphrase-multilingual | 768 | Medium | Excellent | Multi-language content |

### Custom Data Directory

Migrate a knowledge base in a different location:

```bash
knowledgebeast migrate --data-dir /path/to/custom/data
```

### Skip Backup (Not Recommended)

For testing or if you have external backups:

```bash
knowledgebeast migrate --skip-backup
```

⚠️ **Warning**: This is not recommended for production use!

## Python API Migration

For programmatic migration or custom workflows:

```python
from scripts.migrate_to_vector import VectorMigrationTool
from pathlib import Path

# Initialize migration tool
migration_tool = VectorMigrationTool(
    data_dir=Path("./data")
)

# Execute migration
result = migration_tool.migrate(
    embedding_model="all-MiniLM-L6-v2",
    skip_backup=False
)

# Check results
if result["status"] == "success":
    print(f"Migrated {result['migration_result']['migrated_count']} documents")
    print(f"Duration: {result['duration_seconds']:.2f}s")
    print(f"Backup: {result['backup_path']}")
else:
    print(f"Migration failed or no documents to migrate")
```

## Rollback to v1

If you need to revert to the term-based index:

### Using CLI

```bash
# Rollback to latest backup
knowledgebeast migrate --rollback

# Rollback to specific backup
knowledgebeast migrate --rollback --backup-path ./data/backups/backup_20250107_143022
```

**Example Output:**
```
⚠ ROLLBACK MODE

Are you sure you want to rollback to term-based index? [y/N]: y

Rolling back from: ./data/backups/backup_20250107_143022
✓ Rollback complete: 2 files restored

╭─ Rollback Complete ──────────────────────────────────────────╮
│ Rollback successful!                                         │
│                                                              │
│ Term-based index has been restored from backup.              │
╰──────────────────────────────────────────────────────────────╯
```

### Using Python API

```python
from scripts.migrate_to_vector import VectorMigrationTool

migration_tool = VectorMigrationTool(data_dir=Path("./data"))

# Rollback to latest backup
success = migration_tool.rollback()

# Rollback to specific backup
success = migration_tool.rollback(
    backup_path=Path("./data/backups/backup_20250107_143022")
)
```

## Configuration Changes

After migration, update your configuration to use vector search:

### Environment Variables

```bash
# Enable vector search (default: true)
export KB_USE_VECTOR_SEARCH=true

# Set search mode (vector, keyword, hybrid)
export KB_VECTOR_SEARCH_MODE=hybrid

# Configure embedding model
export KB_EMBEDDING_MODEL=all-MiniLM-L6-v2

# Set ChromaDB path
export KB_CHROMADB_PATH=./data/chromadb

# Configure chunking
export KB_CHUNK_SIZE=1000
export KB_CHUNK_OVERLAP=200
```

### Python Configuration

```python
from knowledgebeast.core.config import KnowledgeBeastConfig
from pathlib import Path

config = KnowledgeBeastConfig(
    # Vector RAG settings
    use_vector_search=True,
    vector_search_mode="hybrid",  # vector, keyword, or hybrid
    embedding_model="all-MiniLM-L6-v2",
    chromadb_path=Path("./data/chromadb"),
    chunk_size=1000,
    chunk_overlap=200,

    # Existing settings
    knowledge_dirs=[Path("./knowledge-base")],
    max_cache_size=100,
    auto_warm=True
)
```

### Configuration Options

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `use_vector_search` | `true`, `false` | `true` | Enable/disable vector search |
| `vector_search_mode` | `vector`, `keyword`, `hybrid` | `hybrid` | Search mode |
| `embedding_model` | See models above | `all-MiniLM-L6-v2` | Embedding model |
| `chunk_size` | Integer > 0 | `1000` | Document chunk size |
| `chunk_overlap` | Integer ≥ 0, < chunk_size | `200` | Chunk overlap |
| `chromadb_path` | Path | `./data/chromadb` | ChromaDB storage path |

## Search Mode Comparison

### Vector Mode
- **Best for**: Semantic similarity, concept search
- **Use when**: Looking for meaning, not exact keywords
- **Example**: "machine learning algorithms" finds "neural networks", "deep learning"

```python
config = KnowledgeBeastConfig(vector_search_mode="vector")
```

### Keyword Mode
- **Best for**: Exact term matching, backward compatibility
- **Use when**: Need precise keyword matches
- **Example**: "def process()" finds exact function names

```python
config = KnowledgeBeastConfig(vector_search_mode="keyword")
```

### Hybrid Mode (Recommended)
- **Best for**: Balanced results, general use
- **Use when**: Want both semantic and keyword matching
- **Example**: Combines both approaches for comprehensive results

```python
config = KnowledgeBeastConfig(vector_search_mode="hybrid")
```

## Verifying Migration

After migration, verify everything works:

### 1. Check Knowledge Base Stats

```bash
knowledgebeast stats --detailed
```

**Expected Output:**
```
Knowledge Base Statistics
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
┃ Metric                      ┃ Value                ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
│ Total documents             │ 156                  │
│ Collection                  │ knowledgebeast_v2    │
│ Embedding model             │ all-MiniLM-L6-v2     │
│ Heartbeat running           │ No                   │
└─────────────────────────────┴──────────────────────┘
```

### 2. Test Query

```bash
knowledgebeast query "machine learning algorithms" -n 5
```

### 3. Run Health Check

```bash
knowledgebeast health
```

## Troubleshooting

### Migration Fails

**Problem**: Migration fails with import error

**Solution**: Install required dependencies
```bash
pip install chromadb sentence-transformers
```

---

**Problem**: Out of memory during migration

**Solution**: Use a smaller embedding model
```bash
knowledgebeast migrate --embedding-model all-MiniLM-L6-v2
```

---

**Problem**: Migration takes too long

**Solution**: This is normal for large knowledge bases. Migration runs once and progress is shown.

### After Migration

**Problem**: Queries return no results

**Solution**: Verify vector search is enabled
```bash
export KB_USE_VECTOR_SEARCH=true
```

---

**Problem**: Results quality is poor

**Solution**: Try different search modes:
```bash
# Try hybrid mode
export KB_VECTOR_SEARCH_MODE=hybrid

# Or try vector-only mode
export KB_VECTOR_SEARCH_MODE=vector
```

---

**Problem**: Want to return to v1

**Solution**: Use rollback
```bash
knowledgebeast migrate --rollback
```

## Performance Considerations

### Disk Space

Vector embeddings require additional disk space:
- **Small model (384 dims)**: ~1.5KB per document
- **Large model (768 dims)**: ~3KB per document

**Example**: 1000 documents with all-MiniLM-L6-v2 ≈ 1.5MB

### Query Performance

After migration, expect:
- **First query**: Slower (model loading)
- **Subsequent queries**: Fast (model cached)
- **With caching**: < 10ms for cache hits
- **Without caching**: 50-100ms typical

### Memory Usage

Embedding models use RAM:
- **all-MiniLM-L6-v2**: ~100MB
- **all-mpnet-base-v2**: ~400MB
- **multilingual models**: ~400-500MB

## Migration Checklist

Before migration:
- [ ] Backup your data directory
- [ ] Install required dependencies
- [ ] Test migration on a copy first (recommended)
- [ ] Review configuration options

During migration:
- [ ] Monitor progress output
- [ ] Note backup location
- [ ] Watch for errors

After migration:
- [ ] Verify stats with `knowledgebeast stats`
- [ ] Test queries with `knowledgebeast query`
- [ ] Run health check with `knowledgebeast health`
- [ ] Update configuration if needed
- [ ] Test rollback procedure (optional)

## Getting Help

If you encounter issues:

1. **Check the logs**: Migration tool logs errors with details
2. **Review documentation**: See [FAQ.md](../FAQ.md) for common issues
3. **Try rollback**: You can always revert to v1
4. **File an issue**: [GitHub Issues](https://github.com/PerformanceSuite/KnowledgeBeast/issues)

## Migration Timeline

**Recommended Migration Path:**

1. **Week 1**: Test migration on development environment
2. **Week 2**: Validate results and performance
3. **Week 3**: Migrate staging environment
4. **Week 4**: Migrate production with rollback plan

## Backward Compatibility

KnowledgeBeast v2 maintains backward compatibility:

- ✅ All v1 APIs still work
- ✅ Existing code requires no changes
- ✅ Can disable vector search and use keyword mode
- ✅ Rollback available if needed

## What Gets Migrated

**Migrated:**
- ✅ All documents and content
- ✅ Document metadata
- ✅ Document IDs

**Not Migrated (Rebuilt):**
- 🔄 Term-based index (replaced by vector embeddings)
- 🔄 Query cache (cleared, will rebuild)
- 🔄 Statistics (reset to zero)

## Post-Migration Optimization

After migration, consider:

1. **Warm the cache**: Run common queries to populate cache
   ```bash
   knowledgebeast warm
   ```

2. **Tune chunk size**: Adjust based on document length
   ```bash
   export KB_CHUNK_SIZE=1500
   export KB_CHUNK_OVERLAP=300
   ```

3. **Monitor performance**: Use benchmarks to track improvements
   ```bash
   knowledgebeast benchmark --output report.html
   ```

## Summary

Migration from v1 to v2 is:
- ✅ **Safe**: Automatic backups with rollback support
- ✅ **Simple**: One-command migration
- ✅ **Fast**: Typical migration in minutes
- ✅ **Reversible**: Full rollback capability
- ✅ **Compatible**: Existing code continues to work

**Next Steps:**
1. Run `knowledgebeast migrate`
2. Verify with `knowledgebeast stats`
3. Test queries with `knowledgebeast query`
4. Enjoy better semantic search!

---

**Version**: 2.0.0
**Last Updated**: January 7, 2025
**Maintained by**: KnowledgeBeast Team
