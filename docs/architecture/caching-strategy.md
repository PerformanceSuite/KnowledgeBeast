# Caching Strategy

KnowledgeBeast uses multi-level caching for optimal performance.

## Cache Levels

### 1. Query Result Cache (LRU)
- **Type**: In-memory LRU cache
- **Key**: Query text hash
- **Value**: Search results
- **Size**: Configurable (default 100)
- **Hit Rate**: Typically 60-80%

### 2. Embedding Cache
- **Type**: sentence-transformers internal cache
- **Key**: Input text
- **Value**: Embedding vector
- **Automatic**: Managed by sentence-transformers

## Cache Warming

Automatically warm cache on initialization:

```python
config = KnowledgeBeastConfig(auto_warm=True)
```

Manual warming:

```python
kb.warm_cache()
```

## Cache Invalidation

- Clear on document changes
- Manual clearing supported
- TTL not implemented (future feature)

## Performance Impact

- **Cache Hit**: <10ms response
- **Cache Miss**: 100-500ms response
- **Memory**: ~1MB per 100 cached queries

See `knowledgebeast/core/cache.py` for implementation.
