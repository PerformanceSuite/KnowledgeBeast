# KnowledgeBeast MCP Server - Claude Code Setup Guide

## Overview

KnowledgeBeast provides a native Model Context Protocol (MCP) server that integrates seamlessly with Claude Desktop and Claude Code. This allows Claude to directly access your knowledge bases, search documents, manage projects, and perform advanced knowledge management operations.

## Prerequisites

- **Python 3.11+** installed and accessible in your PATH
- **KnowledgeBeast v2.3.0+** installed (`pip install knowledgebeast`)
- **Claude Desktop** app installed ([Download](https://claude.ai/download))
- Basic familiarity with command-line tools

## Quick Start

### 1. Install KnowledgeBeast

```bash
# Install via pip
pip install knowledgebeast

# Verify installation
knowledgebeast --version
```

### 2. Start the MCP Server

The MCP server can be started manually for testing:

```bash
# Start with default settings
knowledgebeast mcp-server

# Start with custom paths
knowledgebeast mcp-server \
  --projects-db ./my_projects.db \
  --chroma-path ./my_chroma_db \
  --cache-capacity 200
```

**MCP Server Options:**
- `--projects-db PATH`: Path to projects database (default: `./kb_projects.db`)
- `--chroma-path PATH`: Path to ChromaDB storage (default: `./chroma_db`)
- `--cache-capacity N`: LRU cache capacity (default: `100`)
- `--log-level LEVEL`: Logging level (default: `INFO`)

### 3. Configure Claude Desktop

Edit your Claude Desktop configuration file:

**macOS/Linux:**
```bash
nano ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

**Windows:**
```bash
notepad %APPDATA%\Claude\claude_desktop_config.json
```

Add the KnowledgeBeast MCP server configuration:

```json
{
  "mcpServers": {
    "knowledgebeast": {
      "command": "knowledgebeast",
      "args": [
        "mcp-server",
        "--projects-db", "/absolute/path/to/kb_projects.db",
        "--chroma-path", "/absolute/path/to/chroma_db",
        "--cache-capacity", "100"
      ],
      "env": {
        "KB_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

**Important Notes:**
- Use **absolute paths** for `--projects-db` and `--chroma-path`
- The command must be in your system PATH (test with `which knowledgebeast`)
- On Windows, use forward slashes (`/`) or escaped backslashes (`\\`) in paths

**Example Configuration (macOS):**

```json
{
  "mcpServers": {
    "knowledgebeast": {
      "command": "/usr/local/bin/knowledgebeast",
      "args": [
        "mcp-server",
        "--projects-db", "/Users/yourusername/Documents/kb_projects.db",
        "--chroma-path", "/Users/yourusername/Documents/chroma_db"
      ],
      "env": {
        "KB_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

### 4. Restart Claude Desktop

After saving the configuration:

1. **Quit Claude Desktop completely** (Cmd+Q on macOS, or File > Exit)
2. **Restart Claude Desktop**
3. Wait for the MCP server to initialize (usually 2-3 seconds)

### 5. Verify Connection

In a new Claude conversation, try one of these commands:

```
List my knowledge base projects
```

or

```
Create a new knowledge base project called "test-project"
```

If configured correctly, Claude will use the KnowledgeBeast MCP tools to respond.

## Available MCP Tools

Once connected, Claude has access to these KnowledgeBeast tools:

### Knowledge Management Tools

1. **kb_search** - Search documents in a project
   - Supports vector, keyword, and hybrid search modes
   - Returns ranked results with relevance scores

2. **kb_ingest** - Add documents to a project
   - Ingest from direct content or file paths
   - Automatic embedding generation

3. **kb_list_documents** - List all documents in a project
   - Paginated results with metadata
   - Document count statistics

4. **kb_batch_ingest** - Bulk document ingestion
   - Process multiple files efficiently
   - Progress tracking and error handling

5. **kb_delete_document** - Remove a document from a project
   - Safe deletion with confirmation
   - Automatic index cleanup

### Project Management Tools

6. **kb_list_projects** - List all knowledge base projects
   - Project metadata and statistics
   - Creation and update timestamps

7. **kb_create_project** - Create a new knowledge base project
   - Custom embedding models
   - Project-specific metadata

8. **kb_get_project_info** - Get detailed project information
   - Document counts
   - Cache statistics
   - Model information

9. **kb_delete_project** - Delete a knowledge base project
   - Removes all associated documents
   - Cleans up ChromaDB collections

### Advanced Tools

10. **kb_export_project** - Export project data to JSON
    - Full project backup
    - Documents and metadata
    - Importable format

11. **kb_import_project** - Import project from JSON
    - Restore from backup
    - Create from templates
    - Merge with existing projects

12. **kb_create_template** - Create project templates
    - Reusable project configurations
    - Shareable across teams

## Common Workflows

### Creating Your First Knowledge Base

```
Create a knowledge base project called "technical-docs" with description "Technical documentation and guides"
```

Claude will create the project and return the project ID.

### Ingesting Documents

```
Ingest the file /path/to/document.md into the "technical-docs" project
```

or for direct content:

```
Add this document to technical-docs: "Machine learning is a subset of artificial intelligence..."
```

### Searching Your Knowledge Base

```
Search "technical-docs" for "API authentication best practices"
```

or with specific search mode:

```
Search "technical-docs" using vector search for "database optimization"
```

### Managing Projects

```
List all my knowledge base projects
```

```
Show me detailed information about project "technical-docs"
```

```
Export the "technical-docs" project to a backup file
```

## Environment Variables

You can configure the MCP server using environment variables:

```bash
export KB_PROJECTS_DB="/path/to/projects.db"
export KB_CHROMA_PATH="/path/to/chroma"
export KB_DEFAULT_MODEL="all-MiniLM-L6-v2"
export KB_CACHE_CAPACITY="200"
export KB_LOG_LEVEL="DEBUG"
```

Then start with:

```json
{
  "mcpServers": {
    "knowledgebeast": {
      "command": "knowledgebeast",
      "args": ["mcp-server"]
    }
  }
}
```

The server will read configuration from environment variables.

## Troubleshooting

### MCP Server Not Connecting

**Symptom:** Claude doesn't show KnowledgeBeast tools available.

**Solutions:**

1. **Verify Installation:**
   ```bash
   which knowledgebeast
   knowledgebeast --version
   ```

2. **Check Configuration Path:**
   - Ensure `claude_desktop_config.json` is in the correct location
   - Use absolute paths for all arguments

3. **Verify JSON Syntax:**
   - Use a JSON validator (e.g., [jsonlint.com](https://jsonlint.com))
   - Check for trailing commas, missing quotes

4. **Check Logs:**
   - macOS: `~/Library/Logs/Claude/mcp*.log`
   - Windows: `%APPDATA%\Claude\logs\mcp*.log`

### Permission Errors

**Symptom:** "Permission denied" when accessing database or ChromaDB.

**Solutions:**

1. **Check Directory Permissions:**
   ```bash
   ls -la /path/to/kb_projects.db
   ls -la /path/to/chroma_db
   ```

2. **Create Directories:**
   ```bash
   mkdir -p /path/to/chroma_db
   touch /path/to/kb_projects.db
   ```

3. **Fix Permissions:**
   ```bash
   chmod 755 /path/to/chroma_db
   chmod 644 /path/to/kb_projects.db
   ```

### Command Not Found

**Symptom:** Claude logs show "command not found: knowledgebeast"

**Solutions:**

1. **Use Absolute Path:**
   ```bash
   which knowledgebeast
   # Returns: /usr/local/bin/knowledgebeast
   ```

   Then in config:
   ```json
   "command": "/usr/local/bin/knowledgebeast"
   ```

2. **Check Python Environment:**
   - If using virtual environments, use the full path to the venv's knowledgebeast
   - Example: `/Users/you/.venv/kb/bin/knowledgebeast`

3. **Reinstall KnowledgeBeast:**
   ```bash
   pip uninstall knowledgebeast
   pip install knowledgebeast
   ```

### Slow Search Performance

**Symptom:** Searches take a long time to return results.

**Solutions:**

1. **Increase Cache Capacity:**
   ```json
   "args": ["mcp-server", "--cache-capacity", "500"]
   ```

2. **Use Hybrid Search Wisely:**
   - Vector search is fastest for semantic queries
   - Keyword search is fastest for exact matches
   - Hybrid search combines both (slower but more comprehensive)

3. **Check Document Count:**
   - Large projects (10,000+ documents) may require optimization
   - Consider splitting into multiple projects by topic

### ChromaDB Errors

**Symptom:** "Failed to initialize ChromaDB" or similar errors.

**Solutions:**

1. **Clear ChromaDB Cache:**
   ```bash
   rm -rf /path/to/chroma_db/*
   ```
   Then recreate your projects.

2. **Check Disk Space:**
   ```bash
   df -h /path/to/chroma_db
   ```

3. **Update Dependencies:**
   ```bash
   pip install --upgrade chromadb sentence-transformers
   ```

## Advanced Configuration

### Custom Embedding Models

Specify a custom embedding model when creating projects:

```
Create a project called "legal-docs" using the "all-mpnet-base-v2" embedding model
```

Supported models:
- `all-MiniLM-L6-v2` (default, fast, 384 dimensions)
- `all-mpnet-base-v2` (slower, more accurate, 768 dimensions)
- `paraphrase-multilingual-MiniLM-L12-v2` (multilingual support)

### Multiple MCP Servers

You can run multiple KnowledgeBeast instances with different databases:

```json
{
  "mcpServers": {
    "knowledgebeast-personal": {
      "command": "knowledgebeast",
      "args": [
        "mcp-server",
        "--projects-db", "/Users/you/personal/kb_projects.db",
        "--chroma-path", "/Users/you/personal/chroma_db"
      ]
    },
    "knowledgebeast-work": {
      "command": "knowledgebeast",
      "args": [
        "mcp-server",
        "--projects-db", "/Users/you/work/kb_projects.db",
        "--chroma-path", "/Users/you/work/chroma_db"
      ]
    }
  }
}
```

Claude will show tools from both instances with different prefixes.

### Performance Tuning

For large-scale deployments:

```json
{
  "mcpServers": {
    "knowledgebeast": {
      "command": "knowledgebeast",
      "args": [
        "mcp-server",
        "--projects-db", "/data/kb_projects.db",
        "--chroma-path", "/data/chroma_db",
        "--cache-capacity", "1000"
      ],
      "env": {
        "KB_LOG_LEVEL": "WARNING",
        "TOKENIZERS_PARALLELISM": "true",
        "OMP_NUM_THREADS": "4"
      }
    }
  }
}
```

## Security Considerations

### File System Access

The MCP server has access to:
- Project database at specified path
- ChromaDB storage directory
- Files specified in ingestion operations

**Best Practices:**
- Use dedicated directories for KnowledgeBeast data
- Set appropriate file permissions (read/write only for your user)
- Avoid storing sensitive data in ChromaDB without encryption

### Network Isolation

The MCP server runs locally and does not:
- Open network ports
- Connect to external services (except for downloading embedding models)
- Share data with third parties

All communication is via local IPC (Inter-Process Communication) between Claude Desktop and the MCP server.

### Data Privacy

- Documents are stored locally in ChromaDB
- Embeddings are generated locally using sentence-transformers
- No data is sent to external APIs (unless you explicitly configure external embedding providers)

## Getting Help

### Documentation

- [Full MCP Documentation](../README.md)
- [API Reference](../api-reference/)
- [Examples and Workflows](./EXAMPLES.md)

### Community

- [GitHub Issues](https://github.com/yourusername/knowledgebeast/issues)
- [Discord Community](https://discord.gg/knowledgebeast)
- [Stack Overflow](https://stackoverflow.com/questions/tagged/knowledgebeast)

### Support

For bugs and feature requests:
1. Check existing [GitHub Issues](https://github.com/yourusername/knowledgebeast/issues)
2. Review the [FAQ](../FAQ.md)
3. Create a new issue with:
   - KnowledgeBeast version (`knowledgebeast --version`)
   - Python version (`python --version`)
   - Operating system
   - MCP configuration (with sensitive paths redacted)
   - Error logs

## Next Steps

1. Read [EXAMPLES.md](./EXAMPLES.md) for common usage patterns
2. Explore the [API Reference](../api-reference/) for detailed tool documentation
3. Join the community and share your knowledge base projects!

---

**Version:** 2.3.0
**Last Updated:** October 9, 2025
**Maintained by:** KnowledgeBeast Team
