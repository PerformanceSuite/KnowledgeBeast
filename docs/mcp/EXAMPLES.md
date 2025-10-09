# KnowledgeBeast MCP - Usage Examples

This guide provides practical examples and workflows for using KnowledgeBeast through Claude Code via the MCP server.

## Table of Contents

- [Basic Workflows](#basic-workflows)
- [Project Management](#project-management)
- [Document Ingestion](#document-ingestion)
- [Search Operations](#search-operations)
- [Advanced Patterns](#advanced-patterns)
- [Best Practices](#best-practices)

## Basic Workflows

### Creating Your First Knowledge Base

**User:** "Create a knowledge base project called 'technical-docs' for storing technical documentation"

**Claude Response:**
```
I'll create that project for you using the kb_create_project tool.

Project created successfully:
- Project ID: proj_abc123def456
- Name: technical-docs
- Description: For storing technical documentation
- Embedding Model: all-MiniLM-L6-v2
- Created: 2025-10-09T10:30:00Z
```

### Adding Your First Document

**User:** "Add this document to technical-docs: 'FastAPI is a modern, fast (high-performance) web framework for building APIs with Python 3.7+ based on standard Python type hints.'"

**Claude Response:**
```
I'll ingest that document into the technical-docs project.

Document added successfully:
- Document ID: doc_1728472200000
- Project: technical-docs
- Content length: 142 characters
- Status: Indexed and ready for search
```

### Searching Your Knowledge Base

**User:** "Search technical-docs for 'Python web frameworks'"

**Claude Response:**
```
I found 1 relevant document:

1. Document doc_1728472200000 (Score: 0.87)
   Content: "FastAPI is a modern, fast (high-performance) web framework for building APIs with Python 3.7+ based on standard Python type hints."

The search used hybrid mode combining semantic and keyword matching.
```

## Project Management

### Listing All Projects

**User:** "What knowledge base projects do I have?"

**Claude Response:**
```
You have 3 knowledge base projects:

1. technical-docs
   - ID: proj_abc123def456
   - Description: For storing technical documentation
   - Model: all-MiniLM-L6-v2
   - Created: 2025-10-09

2. research-papers
   - ID: proj_def456ghi789
   - Description: Academic research papers collection
   - Model: all-mpnet-base-v2
   - Created: 2025-10-08

3. meeting-notes
   - ID: proj_ghi789jkl012
   - Description: Team meeting notes and decisions
   - Model: all-MiniLM-L6-v2
   - Created: 2025-10-07
```

### Getting Project Details

**User:** "Show me detailed information about the technical-docs project"

**Claude Response:**
```
Here's the detailed information for technical-docs:

Project Information:
- ID: proj_abc123def456
- Name: technical-docs
- Description: For storing technical documentation
- Embedding Model: all-MiniLM-L6-v2
- Collection Name: kb_proj_abc123def456
- Created: 2025-10-09T10:30:00Z
- Last Updated: 2025-10-09T14:20:00Z

Statistics:
- Total Documents: 47
- Cache Hit Rate: 85%
- Cache Size: 12/100

Metadata:
- Owner: user@example.com
- Tags: technical, documentation, api
```

### Creating Projects with Custom Models

**User:** "Create a project called 'multilingual-docs' using the paraphrase-multilingual-MiniLM-L12-v2 model"

**Claude Response:**
```
I'll create a project with the multilingual embedding model.

Project created:
- Project ID: proj_mno345pqr678
- Name: multilingual-docs
- Embedding Model: paraphrase-multilingual-MiniLM-L12-v2
- Description: (empty)
- Created: 2025-10-09T14:45:00Z

This model supports over 50 languages and is optimized for multilingual semantic search.
```

### Deleting a Project

**User:** "Delete the 'test-project' knowledge base"

**Claude Response:**
```
Are you sure you want to delete the test-project? This will remove:
- All documents in the project
- All embeddings and indexes
- All project metadata

This action cannot be undone.

[After confirmation]

Project deleted successfully:
- Project: test-project (proj_xyz789)
- Documents removed: 23
- Status: All data cleaned up
```

## Document Ingestion

### Ingesting from Files

**User:** "Ingest the file /Users/me/docs/api-guide.md into technical-docs"

**Claude Response:**
```
I'll ingest that file into the technical-docs project.

File ingested successfully:
- Document ID: doc_1728472300000
- File: api-guide.md
- Path: /Users/me/docs/api-guide.md
- Size: 4,532 characters
- Project: technical-docs
- Status: Indexed and searchable
```

### Batch Document Ingestion

**User:** "Ingest all markdown files in /Users/me/docs/tutorials/ into technical-docs"

**Claude Response:**
```
I'll batch ingest the files from that directory.

Batch ingestion started:
- Source: /Users/me/docs/tutorials/
- Pattern: *.md
- Found: 15 files
- Target project: technical-docs

Progress:
✓ 01-getting-started.md (doc_1728472400000)
✓ 02-authentication.md (doc_1728472401000)
✓ 03-database-setup.md (doc_1728472402000)
... [12 more files]

Batch ingestion completed:
- Successfully ingested: 15 documents
- Failed: 0
- Total time: 2.3 seconds
- Average: 153ms per document
```

### Ingesting with Custom Metadata

**User:** "Add this document to technical-docs with metadata author='John Doe' and category='tutorial': 'This tutorial covers advanced query optimization techniques...'"

**Claude Response:**
```
I'll ingest the document with the specified metadata.

Document ingested:
- Document ID: doc_1728472500000
- Project: technical-docs
- Content length: 187 characters
- Metadata:
  - author: John Doe
  - category: tutorial
  - source: direct
  - ingested_at: 2025-10-09T15:00:00Z
```

### Listing Project Documents

**User:** "List all documents in technical-docs"

**Claude Response:**
```
The technical-docs project contains 47 documents:

Recent documents (showing 10):

1. doc_1728472500000
   - Source: direct
   - Metadata: author=John Doe, category=tutorial
   - Ingested: 2025-10-09 15:00

2. doc_1728472300000
   - Source: file
   - File: api-guide.md
   - Path: /Users/me/docs/api-guide.md
   - Ingested: 2025-10-09 14:50

3. doc_1728472200000
   - Source: direct
   - Ingested: 2025-10-09 14:45

... [7 more documents]

Use 'Show me more documents' to see the next page.
Total: 47 documents
```

### Deleting Documents

**User:** "Delete document doc_1728472200000 from technical-docs"

**Claude Response:**
```
Document deleted successfully:
- Document ID: doc_1728472200000
- Project: technical-docs
- Status: Removed from index and vector store
- Remaining documents: 46
```

## Search Operations

### Vector Search (Semantic)

**User:** "Search technical-docs using vector search for 'how to optimize database queries'"

**Claude Response:**
```
Vector search results (semantic matching):

1. Document doc_1728472500000 (Score: 0.92)
   Content: "This tutorial covers advanced query optimization techniques including index usage, query planning, and performance monitoring..."
   Metadata: author=John Doe, category=tutorial

2. Document doc_1728471000000 (Score: 0.78)
   Content: "Database performance tuning involves several strategies: proper indexing, query rewriting, connection pooling, and caching..."
   Metadata: category=guide

3. Document doc_1728470500000 (Score: 0.71)
   Content: "PostgreSQL offers various optimization techniques through EXPLAIN ANALYZE, index strategies, and vacuuming procedures..."
   Metadata: database=postgresql

Vector search found 3 relevant documents based on semantic similarity.
```

### Keyword Search (Exact Matching)

**User:** "Search technical-docs using keyword search for 'FastAPI authentication'"

**Claude Response:**
```
Keyword search results (exact matching):

1. Document doc_1728472401000 (Score: 1.00)
   Content: "FastAPI Authentication Guide: This document covers OAuth2, JWT tokens, API keys, and session-based authentication in FastAPI..."
   File: 02-authentication.md

2. Document doc_1728469000000 (Score: 0.65)
   Content: "... When using FastAPI for API development, implementing proper authentication is crucial. The framework supports OAuth2..."

Keyword search found 2 documents with exact term matches.
```

### Hybrid Search (Combined)

**User:** "Search technical-docs for 'REST API best practices' using hybrid search with alpha 0.8"

**Claude Response:**
```
Hybrid search results (80% semantic, 20% keyword):

1. Document doc_1728472300000 (Score: 0.88)
   Content: "API Design Best Practices: RESTful API design principles, versioning strategies, error handling, and documentation standards..."
   File: api-guide.md

2. Document doc_1728471500000 (Score: 0.81)
   Content: "REST API Guidelines: Use meaningful resource names, implement proper HTTP status codes, version your APIs, and provide..."

3. Document doc_1728470000000 (Score: 0.76)
   Content: "Best practices for building scalable APIs include rate limiting, caching, pagination, and comprehensive error messages..."

Hybrid search combines semantic understanding (vector) with exact keyword matching for optimal results.
```

### Search with Result Limits

**User:** "Search technical-docs for 'Python' and show me the top 3 results"

**Claude Response:**
```
Top 3 results for "Python":

1. Document doc_1728472200000 (Score: 0.95)
   Content: "FastAPI is a modern, fast (high-performance) web framework for building APIs with Python 3.7+ based on standard Python type hints."

2. Document doc_1728471800000 (Score: 0.89)
   Content: "Python async programming with asyncio enables concurrent execution, improving performance for I/O-bound operations..."

3. Document doc_1728471200000 (Score: 0.84)
   Content: "Type hints in Python 3.9+ provide better IDE support, catch errors early, and improve code documentation..."

Showing top 3 of 12 total matches.
```

## Advanced Patterns

### Project Export and Backup

**User:** "Export the technical-docs project to a backup file"

**Claude Response:**
```
I'll export the technical-docs project.

Export started:
- Project: technical-docs (proj_abc123def456)
- Documents: 47
- Include embeddings: Yes

Export completed:
- File: technical-docs_export_20251009.json
- Size: 2.4 MB
- Documents exported: 47
- Metadata included: Yes
- Embeddings included: Yes

The export file can be imported into another KnowledgeBeast instance or used as a backup.
```

### Project Import and Restore

**User:** "Import the project from technical-docs_export_20251009.json"

**Claude Response:**
```
I'll import the project from that export file.

Import started:
- File: technical-docs_export_20251009.json
- Size: 2.4 MB

Analyzing export:
- Project name: technical-docs
- Documents: 47
- Embedding model: all-MiniLM-L6-v2

Import options:
1. Create new project (with new ID)
2. Restore to existing project (overwrite)
3. Merge with existing project

[After selection: Create new]

Import completed:
- New project ID: proj_stu901vwx234
- Project name: technical-docs
- Documents imported: 47
- Embeddings restored: 47
- Status: Ready for use
```

### Creating Project Templates

**User:** "Create a template from technical-docs that I can reuse"

**Claude Response:**
```
I'll create a template from technical-docs.

Template created:
- Template name: technical-docs-template
- Based on project: technical-docs
- Includes:
  - Project configuration
  - Embedding model: all-MiniLM-L6-v2
  - Metadata schema
  - (Documents NOT included - template is for structure only)

To create a new project from this template:
"Create a project called 'api-docs' using the technical-docs-template"
```

### Multi-Project Search

**User:** "Search across all my projects for 'machine learning'"

**Claude Response:**
```
Searching across 3 projects for "machine learning":

From technical-docs (2 results):
1. Document doc_1728460000000 (Score: 0.88)
   Content: "Implementing machine learning models in production requires careful consideration of serving infrastructure..."

From research-papers (5 results):
1. Document doc_1728350000000 (Score: 0.95)
   Content: "Deep Learning Architectures: A comprehensive survey of neural network architectures for machine learning tasks..."

2. Document doc_1728340000000 (Score: 0.92)
   Content: "Machine learning optimization algorithms including SGD, Adam, and RMSprop..."

From meeting-notes (0 results):
- No matches found

Total: 7 results across 2 projects
```

### Project Health Check

**User:** "Check the health and status of all my projects"

**Claude Response:**
```
Checking health of 3 projects:

1. technical-docs (proj_abc123def456)
   Status: Healthy ✓
   - Documents: 47
   - Cache hit rate: 85%
   - Last updated: 2 hours ago
   - No issues detected

2. research-papers (proj_def456ghi789)
   Status: Healthy ✓
   - Documents: 234
   - Cache hit rate: 92%
   - Last updated: 1 day ago
   - No issues detected

3. meeting-notes (proj_ghi789jkl012)
   Status: Warning ⚠
   - Documents: 0
   - Cache hit rate: N/A
   - Last updated: 2 days ago
   - Issue: Empty project (no documents)

Overall system health: Good
```

## Best Practices

### 1. Project Organization

**DO:**
- Create separate projects for different knowledge domains
- Use descriptive project names and descriptions
- Add metadata to documents for better organization

```
Create project "customer-support-docs" for customer support documentation
Create project "engineering-specs" for technical specifications
Create project "marketing-content" for marketing materials
```

**DON'T:**
- Mix unrelated documents in a single project
- Create too many small projects (adds overhead)
- Use generic names like "project1" or "docs"

### 2. Search Strategy Selection

**Vector Search:** Best for semantic/conceptual queries
```
Search "research-papers" using vector search for "neural network architectures"
```

**Keyword Search:** Best for exact term matching
```
Search "technical-docs" using keyword search for "PostgreSQL 14.5"
```

**Hybrid Search (Default):** Best for balanced results
```
Search "customer-support-docs" for "how to reset password"
```

### 3. Document Metadata

Add meaningful metadata to documents:

```
Ingest document with metadata:
- author: "Jane Smith"
- department: "Engineering"
- version: "2.1"
- tags: ["api", "authentication", "oauth"]
- last_reviewed: "2025-10-01"
```

### 4. Batch Operations

For multiple files, use batch ingestion:

```
Batch ingest all files from /docs/tutorials/ into technical-docs
```

Instead of:
```
Ingest /docs/tutorials/file1.md
Ingest /docs/tutorials/file2.md
... [repeated for each file]
```

### 5. Regular Backups

Export important projects regularly:

```
Export technical-docs project every week
Export research-papers project monthly
```

### 6. Model Selection

Choose embedding models based on your use case:

- **all-MiniLM-L6-v2**: Fast, good for English, 384 dimensions (default)
- **all-mpnet-base-v2**: More accurate, slower, 768 dimensions
- **paraphrase-multilingual-MiniLM-L12-v2**: Multilingual support, 50+ languages

```
Create project "german-docs" using paraphrase-multilingual-MiniLM-L12-v2 model
```

### 7. Cache Optimization

Monitor cache performance:

```
Show me project info for technical-docs
```

Look for:
- Cache hit rate > 80% is good
- Low cache hit rate → increase cache capacity or review query patterns

### 8. Document Cleanup

Regularly review and remove outdated documents:

```
List all documents in technical-docs
Delete document doc_OLD_VERSION from technical-docs
```

### 9. Search Result Limits

Use appropriate result limits:

```
Search "research-papers" for "transformers" limit 20
```

- Small limit (5-10): Quick answers, focused results
- Medium limit (20-50): Comprehensive search
- Large limit (100+): Data analysis, bulk operations

### 10. Monitoring and Maintenance

Regular health checks:

```
Show project info for all my projects
Check which projects haven't been updated recently
List projects with 0 documents
```

## Common Patterns

### Documentation Management

```
# Setup
Create project "company-docs" for internal documentation

# Bulk import
Batch ingest all markdown files from /docs/internal/

# Regular updates
Ingest /docs/internal/new-policy.md into company-docs

# Search
Search "company-docs" for "vacation policy"

# Backup
Export company-docs project weekly
```

### Research Paper Organization

```
# Setup with better model
Create project "ml-papers" using all-mpnet-base-v2 model

# Add papers with metadata
Ingest paper.pdf into ml-papers with metadata:
- authors: "Smith et al."
- year: "2025"
- conference: "NeurIPS"

# Semantic search
Search "ml-papers" using vector search for "attention mechanisms in transformers"

# Export for sharing
Export ml-papers project to share with team
```

### Customer Support Knowledge Base

```
# Setup
Create project "support-kb" for customer support knowledge base

# Organize with metadata
Ingest FAQ with metadata category="billing"
Ingest guide with metadata category="technical", difficulty="beginner"

# Hybrid search (best for support queries)
Search "support-kb" for "how to cancel subscription"

# Monitor usage
Show project info for support-kb
```

### Meeting Notes Archive

```
# Setup
Create project "meeting-notes" for team meeting notes

# Add notes with metadata
Ingest meeting notes with metadata:
- date: "2025-10-09"
- attendees: ["Alice", "Bob", "Charlie"]
- topics: ["Q4 planning", "budget review"]

# Time-based search
Search "meeting-notes" for "Q4 planning decisions from October"

# Regular cleanup
List documents in meeting-notes older than 2 years
Delete old meeting notes documents
```

## Integration Patterns

### CI/CD Documentation

```bash
# In your CI/CD pipeline
knowledgebeast mcp-server &

# Wait for server
sleep 2

# Use Claude to:
# 1. Create project for this build
# 2. Ingest code documentation
# 3. Generate changelog from docs
# 4. Search for related issues

# Cleanup
pkill -f "knowledgebeast mcp-server"
```

### Development Workflow

1. **Code Documentation**: Ingest READMEs, API docs into project
2. **Issue Tracking**: Search docs before creating issues
3. **Code Review**: Search for similar patterns
4. **Onboarding**: New devs search knowledge base

### Content Management

1. **Draft Creation**: Ingest notes and outlines
2. **Research**: Search for related content
3. **Review**: Find similar drafts for consistency
4. **Publishing**: Export final content

## Next Steps

- Review [CLAUDE_CODE_SETUP.md](./CLAUDE_CODE_SETUP.md) for configuration
- Check [API Reference](../api-reference/) for detailed tool documentation
- Join the community to share patterns and workflows

---

**Version:** 2.3.0
**Last Updated:** October 9, 2025
**Maintained by:** KnowledgeBeast Team
