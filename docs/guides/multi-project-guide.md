# Multi-Project Guide

Complete guide to multi-tenant architecture and project isolation in KnowledgeBeast.

## Overview

KnowledgeBeast provides complete multi-tenant isolation allowing multiple independent projects to coexist without data leakage.

### Key Features

- **Per-project ChromaDB collections**: Complete vector data isolation
- **Per-project query caches**: Isolated LRU caches (configurable capacity)
- **Persistent metadata**: SQLite storage for project configuration
- **Scalability**: Tested with 100+ concurrent projects
- **Thread-safe**: Full concurrency support

## Quick Start

```python
from knowledgebeast.core.project_manager import ProjectManager

# Initialize manager
manager = ProjectManager(
    storage_path="./projects.db",
    chroma_path="./chroma_db",
    cache_capacity=100  # Per-project cache size
)

# Create project
project = manager.create_project(
    name="My Project",
    description="Project description",
    embedding_model="all-MiniLM-L6-v2",
    metadata={'team': 'ml', 'version': '1.0'}
)

print(f"Created project: {project.project_id}")
print(f"Collection name: {project.collection_name}")
```

## Project Lifecycle

### Create Project

```python
audio_project = manager.create_project(
    name="Audio ML",
    description="Audio processing knowledge base",
    embedding_model="all-MiniLM-L6-v2",
    metadata={
        'team': 'audio-ml',
        'environment': 'production',
        'version': '2.0'
    }
)
```

### Get Project

```python
# By ID
project = manager.get_project(project_id)

# List all projects
all_projects = manager.list_projects()
for p in all_projects:
    print(f"{p.name}: {p.project_id}")
```

### Update Project

```python
updated = manager.update_project(
    project_id,
    description="Updated description",
    metadata={'version': '2.1', 'status': 'active'}
)
```

### Delete Project

```python
# Cleans up all resources: collection, cache, metadata
success = manager.delete_project(project_id)
```

## Data Isolation

### Vector Store Isolation

Each project has its own ChromaDB collection:

```python
from knowledgebeast.core.vector_store import VectorStore
from knowledgebeast.core.embeddings import EmbeddingEngine

# Project 1
p1 = manager.create_project(name="Project1")
store1 = VectorStore(
    persist_directory="./chroma_db",
    collection_name=p1.collection_name
)

# Project 2
p2 = manager.create_project(name="Project2")
store2 = VectorStore(
    persist_directory="./chroma_db",
    collection_name=p2.collection_name
)

# Add to project 1
engine = EmbeddingEngine()
emb1 = engine.embed("Project 1 data")
store1.add(ids="doc1", embeddings=emb1, documents="Project 1 data")

# Add to project 2 (completely isolated)
emb2 = engine.embed("Project 2 data")
store2.add(ids="doc1", embeddings=emb2, documents="Project 2 data")

# Verify isolation
print(f"Project 1: {store1.count()} docs")  # 1
print(f"Project 2: {store2.count()} docs")  # 1

# No data leakage
data1 = store1.get(ids="doc1")
data2 = store2.get(ids="doc1")
assert data1['documents'][0] != data2['documents'][0]  # Different!
```

### Cache Isolation

Each project has its own query cache:

```python
# Get project caches
cache1 = manager.get_project_cache(p1.project_id)
cache2 = manager.get_project_cache(p2.project_id)

# Add to cache 1
cache1.put("query1", ["result1"])

# Check isolation
assert cache1.get("query1") == ["result1"]
assert cache2.get("query1") is None  # Isolated!
```

## Multi-Project Workflows

### Separate Teams/Use Cases

```python
# Team 1: Audio ML
audio_project = manager.create_project(
    name="Audio ML",
    description="Audio processing research",
    embedding_model="all-MiniLM-L6-v2",
    metadata={'team': 'audio', 'lead': 'alice@company.com'}
)

# Team 2: NLP
nlp_project = manager.create_project(
    name="NLP Research",
    description="Natural language processing",
    embedding_model="all-mpnet-base-v2",  # Different model!
    metadata={'team': 'nlp', 'lead': 'bob@company.com'}
)

# Team 3: Computer Vision
cv_project = manager.create_project(
    name="Computer Vision",
    description="Image recognition research",
    embedding_model="all-MiniLM-L6-v2",
    metadata={'team': 'cv', 'lead': 'charlie@company.com'}
)
```

### Per-Customer Isolation (SaaS)

```python
# Customer A
customer_a = manager.create_project(
    name=f"Customer A - {customer_a_id}",
    description="Customer A knowledge base",
    metadata={
        'customer_id': customer_a_id,
        'plan': 'enterprise',
        'max_docs': 10000
    }
)

# Customer B (completely isolated)
customer_b = manager.create_project(
    name=f"Customer B - {customer_b_id}",
    description="Customer B knowledge base",
    metadata={
        'customer_id': customer_b_id,
        'plan': 'pro',
        'max_docs': 5000
    }
)

# No data ever crosses customer boundaries
```

### Environment Separation

```python
# Development
dev_project = manager.create_project(
    name="Dev Environment",
    embedding_model="all-MiniLM-L6-v2",
    metadata={'environment': 'development'}
)

# Staging
staging_project = manager.create_project(
    name="Staging Environment",
    embedding_model="all-MiniLM-L6-v2",
    metadata={'environment': 'staging'}
)

# Production
prod_project = manager.create_project(
    name="Production Environment",
    embedding_model="all-mpnet-base-v2",  # Higher quality
    metadata={'environment': 'production'}
)
```

## Scalability

### 100+ Projects

```python
# Create many projects
projects = []
for i in range(100):
    project = manager.create_project(
        name=f"Project {i}",
        description=f"Test project {i}",
        metadata={'index': i, 'batch': i // 10}
    )
    projects.append(project)

# All isolated
stats = manager.get_stats()
print(f"Total projects: {stats['total_projects']}")  # 100
print(f"Total cache entries: {stats['total_cache_entries']}")
```

### Concurrent Access

```python
import threading

def process_project(project_id):
    # Get project resources
    cache = manager.get_project_cache(project_id)

    # Perform operations (thread-safe)
    for i in range(100):
        key = f"query_{i}"
        cache.put(key, [f"result_{i}"])
        retrieved = cache.get(key)
        assert retrieved == [f"result_{i}"]

# Process 20 projects concurrently
threads = []
for project in projects[:20]:
    t = threading.Thread(target=process_project, args=(project.project_id,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

print("All concurrent operations completed successfully")
```

## Resource Management

### Per-Project Statistics

```python
# Global stats
stats = manager.get_stats()
print(f"Total projects: {stats['total_projects']}")
print(f"Total cache entries: {stats['total_cache_entries']}")
print(f"Cache capacity per project: {stats['cache_capacity_per_project']}")

# Per-project stats
cache = manager.get_project_cache(project_id)
cache_stats = cache.stats()
print(f"Project cache size: {cache_stats['size']}/{cache_stats['capacity']}")
print(f"Project cache utilization: {cache_stats['utilization']:.1%}")
```

### Cleanup

```python
# Clear project cache
manager.clear_project_cache(project_id)

# Delete project (cleans ALL resources)
manager.delete_project(project_id)

# Cleanup all projects (for testing)
with ProjectManager(...) as manager:
    # Create projects...
    pass
# Automatic cleanup on context exit
```

## Best Practices

### 1. Descriptive Project Names

```python
# Good
project = manager.create_project(
    name="Customer-Acme-Production",
    description="Acme Corp production knowledge base",
    metadata={'customer_id': 'acme-123', 'environment': 'prod'}
)

# Bad
project = manager.create_project(name="Project1")  # Not descriptive
```

### 2. Use Metadata for Organization

```python
project = manager.create_project(
    name="ML Research",
    metadata={
        'team': 'ml-research',
        'lead': 'researcher@company.com',
        'created_date': '2025-01-01',
        'tags': ['nlp', 'audio', 'computer-vision'],
        'priority': 'high',
        'budget_code': 'ML-2025-Q1'
    }
)

# Query by metadata
all_projects = manager.list_projects()
ml_projects = [p for p in all_projects if p.metadata.get('team') == 'ml-research']
```

### 3. Right-Size Cache Capacity

```python
# Small project (< 1000 docs, low query volume)
manager = ProjectManager(cache_capacity=50)

# Medium project (1000-10000 docs)
manager = ProjectManager(cache_capacity=100)

# Large project (> 10000 docs, high query volume)
manager = ProjectManager(cache_capacity=200)
```

### 4. Monitor Per-Project Usage

```python
def monitor_project(project_id):
    cache = manager.get_project_cache(project_id)
    stats = cache.stats()

    if stats['utilization'] > 0.9:
        print(f"WARNING: Project {project_id} cache nearly full")
        print("Consider increasing cache_capacity")

    collection = manager.get_project_collection(project_id)
    if collection:
        doc_count = collection.count()
        if doc_count > 50000:
            print(f"INFO: Project {project_id} has {doc_count} documents")
            print("Consider archiving old documents")
```

### 5. Implement Project Quotas

```python
class QuotaManager:
    def __init__(self, manager, max_docs_per_project=10000):
        self.manager = manager
        self.max_docs = max_docs_per_project

    def check_quota(self, project_id):
        collection = self.manager.get_project_collection(project_id)
        if collection:
            count = collection.count()
            if count >= self.max_docs:
                raise QuotaExceededError(
                    f"Project {project_id} has reached quota: {count}/{self.max_docs}"
                )
        return True
```

## Migration and Backup

### Export Project Metadata

```python
project = manager.get_project(project_id)
metadata_json = project.to_dict()

import json
with open(f'project_{project_id}_metadata.json', 'w') as f:
    json.dump(metadata_json, f, indent=2)
```

### Backup Vector Data

```python
# ChromaDB handles persistence automatically
# Backup the chroma_path directory:
import shutil
shutil.copytree(
    manager.chroma_path,
    f"./backups/chroma_{timestamp}",
    dirs_exist_ok=True
)
```

### Restore Project

```python
# Metadata persists in SQLite
# Collections persist in ChromaDB
# Simply reconnect to same paths:

manager = ProjectManager(
    storage_path="./projects.db",  # Same path
    chroma_path="./chroma_db"      # Same path
)

# Projects automatically reloaded
projects = manager.list_projects()
print(f"Restored {len(projects)} projects")
```

## Troubleshooting

### Duplicate Name Error

```python
try:
    manager.create_project(name="Existing Name")
except ValueError as e:
    print(f"Error: {e}")  # "Project with name 'Existing Name' already exists"
```

### Project Not Found

```python
project = manager.get_project("nonexistent-id")
if project is None:
    print("Project not found")
```

### Cache Performance Issues

```python
# Increase cache capacity
manager = ProjectManager(cache_capacity=200)  # Instead of default 100
```

## Further Reading

- [Vector RAG Guide](./vector-rag-guide.md)
- [Performance Tuning Guide](./vector-performance-tuning.md)
- [ChromaDB Collections](https://docs.trychroma.com/usage-guide#collections)
