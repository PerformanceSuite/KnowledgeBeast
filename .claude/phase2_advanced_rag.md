# Phase 2: Advanced RAG Capabilities

**Target Version**: v2.2.0
**Estimated Timeline**: 4-6 weeks
**Success Criteria**: 150+ new tests, 25%+ quality improvement, production-ready

## 🎯 Overview

Phase 2 builds on the production excellence foundation from v2.1.0 by adding advanced Retrieval-Augmented Generation (RAG) capabilities that significantly improve search quality, relevance, and user experience.

## 🚀 Goals

1. **Improve Search Quality**: 25%+ improvement in relevance metrics
2. **Multi-Modal Support**: Handle PDFs, images, code with specialized processing
3. **Semantic Enhancements**: Re-ranking, query expansion, caching
4. **Production Ready**: Full test coverage, benchmarks, documentation

## 📋 Features

### 1. Re-Ranking with Cross-Encoders (Agent 1)

**Objective**: Improve result relevance by 30%+ using cross-encoder re-ranking

**Key Features**:
- **Cross-Encoder Integration**
  - Use `sentence-transformers/ms-marco-MiniLM-L-6-v2` for re-ranking
  - Configurable re-ranking depth (default: top 50 → top 10)
  - Batch processing for efficiency
  - GPU acceleration support

- **Hybrid Re-Ranking Pipeline**
  - Stage 1: Vector search retrieves top 50
  - Stage 2: Cross-encoder re-ranks to top 10
  - Stage 3: Optional diversity re-ranking (MMR)
  - Configurable pipeline stages

- **Performance Optimization**
  - Model caching and warmup
  - Batch size optimization (4-16)
  - Async re-ranking for API responsiveness
  - Fallback to vector scores on timeout

**Implementation Files**:
```
knowledgebeast/core/reranking.py          # Re-ranking engine
knowledgebeast/core/rerankers/
  ├── cross_encoder.py                    # Cross-encoder implementation
  ├── mmr.py                              # Maximal Marginal Relevance
  └── base.py                             # Base reranker interface
knowledgebeast/utils/model_cache.py      # Model caching utility
tests/reranking/
  ├── test_cross_encoder.py               # 12 tests
  ├── test_mmr.py                         # 8 tests
  ├── test_reranking_pipeline.py          # 15 tests
  └── test_reranking_performance.py       # 10 tests
```

**API Changes**:
```python
# New query parameters
POST /api/v1/projects/{project_id}/query
{
  "query": "search terms",
  "top_k": 10,
  "rerank": true,                    # NEW: Enable re-ranking
  "rerank_top_k": 50,                # NEW: Candidates for re-ranking
  "diversity": 0.5,                  # NEW: MMR diversity (0-1)
}

# Response includes re-ranking scores
{
  "results": [
    {
      "chunk_id": "doc1_chunk1",
      "text": "...",
      "vector_score": 0.87,          # Original vector similarity
      "rerank_score": 0.95,          # NEW: Re-ranking score
      "final_score": 0.95,           # NEW: Final combined score
      "rank": 1
    }
  ],
  "metadata": {
    "reranked": true,
    "rerank_model": "ms-marco-MiniLM-L-6-v2",
    "rerank_duration_ms": 45
  }
}
```

**Metrics**:
- `kb_reranking_duration_seconds` - Re-ranking latency histogram
- `kb_reranking_requests_total` - Re-ranking request counter
- `kb_reranking_model_loads_total` - Model load counter
- `kb_reranking_score_improvement` - Score delta histogram

**Test Coverage**: 45 tests
- Cross-encoder correctness
- MMR diversity validation
- Pipeline integration
- Performance benchmarks (P99 < 200ms for top 50)
- Fallback behavior
- Model caching efficiency

---

### 2. Advanced Chunking Strategies (Agent 2)

**Objective**: Improve chunk quality by 40% using semantic and structural chunking

**Key Features**:
- **Semantic Chunking**
  - Sentence-level embedding similarity
  - Dynamic chunk boundaries based on topic shifts
  - Configurable similarity threshold (0.5-0.9)
  - Preserves paragraph coherence

- **Recursive Character Splitting**
  - Respects markdown structure (headers, code blocks, lists)
  - Configurable chunk size (256-1024 tokens)
  - Chunk overlap for context preservation (50-200 tokens)
  - Code-aware splitting (respects function boundaries)

- **Metadata-Rich Chunks**
  - Document structure metadata (section, subsection)
  - Source file and line numbers
  - Chunk type (text, code, table, list)
  - Parent-child relationships
  - Temporal metadata (creation date, version)

- **Multi-Level Indexing**
  - Document-level embeddings (summaries)
  - Chunk-level embeddings (content)
  - Hierarchical retrieval (doc → chunk)

**Implementation Files**:
```
knowledgebeast/core/chunking/
  ├── __init__.py
  ├── base.py                             # Base chunker interface
  ├── semantic.py                         # Semantic chunker
  ├── recursive.py                        # Recursive character splitter
  ├── markdown.py                         # Markdown-aware chunker
  └── code.py                             # Code-aware chunker
knowledgebeast/core/chunk_processor.py   # Chunk pipeline orchestrator
tests/chunking/
  ├── test_semantic_chunker.py            # 15 tests
  ├── test_recursive_chunker.py           # 12 tests
  ├── test_markdown_chunker.py            # 10 tests
  ├── test_code_chunker.py                # 8 tests
  └── test_chunking_pipeline.py           # 15 tests
```

**Configuration**:
```python
# New chunking config in project settings
{
  "chunking": {
    "strategy": "semantic",              # semantic | recursive | markdown | code
    "chunk_size": 512,                   # Max tokens per chunk
    "chunk_overlap": 128,                # Overlap in tokens
    "semantic_similarity_threshold": 0.7,
    "respect_markdown_structure": true,
    "preserve_code_blocks": true,
    "metadata_fields": [
      "section", "file_path", "line_start", "line_end", "chunk_type"
    ]
  }
}
```

**Metrics**:
- `kb_chunking_duration_seconds` - Chunking latency
- `kb_chunks_created_total` - Total chunks created
- `kb_chunk_size_bytes` - Chunk size distribution
- `kb_chunk_overlap_ratio` - Overlap ratio histogram

**Test Coverage**: 60 tests
- Semantic boundary detection
- Markdown structure preservation
- Code block handling
- Metadata extraction
- Hierarchical indexing
- Chunk quality metrics

---

### 3. Multi-Modal Document Support (Agent 3)

**Objective**: Support PDF, images, and code files with specialized extractors

**Key Features**:
- **PDF Processing**
  - Text extraction with PyPDF2/pdfplumber
  - Layout-aware extraction (columns, tables)
  - Image extraction from PDFs
  - OCR for scanned PDFs (Tesseract)
  - Metadata extraction (author, date, title)

- **Image Processing**
  - CLIP-based image embeddings (OpenAI ViT-L/14)
  - Caption generation with BLIP
  - OCR for text in images
  - Image similarity search
  - Thumbnail generation

- **Code File Processing**
  - Syntax-aware parsing (tree-sitter)
  - Function/class extraction
  - Docstring extraction
  - Import/dependency tracking
  - Language-specific tokenization (20+ languages)

- **Unified Multi-Modal Search**
  - Text queries find images via CLIP
  - Image queries find similar images
  - Code queries find similar functions
  - Cross-modal retrieval

**Implementation Files**:
```
knowledgebeast/converters/
  ├── pdf_converter.py                    # PDF extraction
  ├── image_converter.py                  # Image processing
  ├── code_converter.py                   # Code parsing
  └── multimodal_converter.py             # Unified converter
knowledgebeast/core/multimodal/
  ├── clip_embeddings.py                  # CLIP image embeddings
  ├── blip_captions.py                    # Image captioning
  └── ocr_engine.py                       # OCR processing
tests/multimodal/
  ├── test_pdf_converter.py               # 15 tests
  ├── test_image_converter.py             # 12 tests
  ├── test_code_converter.py              # 10 tests
  ├── test_clip_embeddings.py             # 8 tests
  └── test_multimodal_search.py           # 15 tests
```

**API Changes**:
```python
# New upload endpoint for multi-modal files
POST /api/v1/projects/{project_id}/documents/upload
Content-Type: multipart/form-data

# Supports: .pdf, .png, .jpg, .py, .js, .java, .cpp, etc.

# Response
{
  "document_id": "doc123",
  "file_type": "pdf",
  "chunks_created": 15,
  "images_extracted": 3,
  "processing_time_ms": 1250
}

# Search supports modal filters
POST /api/v1/projects/{project_id}/query
{
  "query": "search terms",
  "modalities": ["text", "image", "code"],  # NEW: Filter by modality
  "code_language": "python"                 # NEW: Code-specific filter
}
```

**Dependencies**:
```
PyPDF2>=3.0.0
pdfplumber>=0.10.0
pytesseract>=0.3.10
pillow>=10.0.0
transformers>=4.30.0      # CLIP, BLIP models
torch>=2.0.0
tree-sitter>=0.20.0
tree-sitter-python>=0.20.0
tree-sitter-javascript>=0.20.0
```

**Metrics**:
- `kb_pdf_pages_processed_total` - PDF page counter
- `kb_images_processed_total` - Image counter
- `kb_ocr_operations_total` - OCR counter
- `kb_multimodal_search_duration_seconds` - Latency

**Test Coverage**: 60 tests
- PDF text extraction accuracy
- Image embedding quality
- Code parsing correctness
- Multi-modal search relevance
- OCR accuracy
- Format support coverage

---

### 4. Query Expansion & Semantic Caching (Agent 4)

**Objective**: Improve recall by 30% and reduce latency by 50% with caching

**Key Features**:
- **Query Expansion**
  - Synonym expansion using WordNet
  - Acronym expansion (ML → Machine Learning)
  - Multi-language query translation
  - Contextual expansion with LLM (optional)
  - User feedback loop for expansions

- **Semantic Query Caching**
  - Cache similar queries (cosine > 0.95)
  - Embedding-based cache key
  - TTL-based cache expiration (1 hour default)
  - Cache warming for common queries
  - Cache hit rate tracking

- **Query Reformulation**
  - Question → keyword transformation
  - Negation handling ("not about X")
  - Date range extraction
  - Entity recognition (NER)

- **Personalized Ranking**
  - User history tracking
  - Click-through rate modeling
  - Personalized re-ranking weights
  - A/B testing framework

**Implementation Files**:
```
knowledgebeast/core/query/
  ├── expander.py                         # Query expansion
  ├── reformulator.py                     # Query reformulation
  ├── semantic_cache.py                   # Semantic caching
  └── personalizer.py                     # Personalized ranking
knowledgebeast/utils/wordnet_utils.py    # WordNet integration
tests/query/
  ├── test_query_expansion.py             # 15 tests
  ├── test_semantic_cache.py              # 12 tests
  ├── test_query_reformulation.py         # 10 tests
  └── test_personalization.py             # 8 tests
```

**Configuration**:
```python
{
  "query_expansion": {
    "enabled": true,
    "synonyms": true,
    "acronyms": true,
    "max_expansions": 3,
    "llm_expansion": false  # Optional, requires API key
  },
  "semantic_cache": {
    "enabled": true,
    "similarity_threshold": 0.95,
    "ttl_seconds": 3600,
    "max_entries": 10000
  },
  "personalization": {
    "enabled": false,  # Opt-in
    "history_window_days": 30
  }
}
```

**API Changes**:
```python
# Query expansion details in response
POST /api/v1/projects/{project_id}/query
{
  "query": "ML best practices",
  "expand_query": true               # NEW: Enable expansion
}

# Response
{
  "results": [...],
  "metadata": {
    "original_query": "ML best practices",
    "expanded_query": "ML best practices OR machine learning best practices OR ML good practices",
    "expansion_terms": ["machine learning"],
    "cache_hit": false,
    "personalized": false
  }
}
```

**Metrics**:
- `kb_query_expansions_total` - Expansion counter
- `kb_semantic_cache_hits_total` - Semantic cache hits
- `kb_semantic_cache_misses_total` - Semantic cache misses
- `kb_query_expansion_duration_seconds` - Expansion latency

**Test Coverage**: 45 tests
- Synonym expansion accuracy
- Cache hit rate validation
- Query reformulation correctness
- Personalization effectiveness
- Cache eviction behavior

---

## 📊 Metrics & Monitoring

### Quality Metrics
- **Relevance Improvement**: 25%+ vs baseline (v2.1.0)
- **MRR (Mean Reciprocal Rank)**: > 0.85
- **NDCG@10**: > 0.90
- **Precision@5**: > 0.80
- **Recall@10**: > 0.75

### Performance Targets
- **Re-Ranking Latency (P99)**: < 200ms
- **Multi-Modal Processing (PDF)**: < 2s per page
- **Semantic Cache Hit Ratio**: > 40%
- **Query Expansion Overhead**: < 50ms

### New Dashboards
- **RAG Quality Dashboard**
  - Relevance metrics over time
  - Re-ranking score improvements
  - Cache hit rates
  - Query expansion stats

- **Multi-Modal Processing Dashboard**
  - PDF processing throughput
  - Image embedding latency
  - OCR success rate
  - File type distribution

---

## 🧪 Testing Strategy

### Test Distribution
- **Agent 1 (Re-Ranking)**: 45 tests
- **Agent 2 (Chunking)**: 60 tests
- **Agent 3 (Multi-Modal)**: 60 tests
- **Agent 4 (Query Expansion)**: 45 tests
- **Total**: 210 new tests

### Test Categories
1. **Unit Tests**: Component-level correctness (60%)
2. **Integration Tests**: End-to-end workflows (25%)
3. **Performance Tests**: Latency and throughput benchmarks (10%)
4. **Quality Tests**: Relevance metrics and baselines (5%)

### Quality Benchmarks
- Create test dataset with 100 queries and relevance judgments
- Measure MRR, NDCG@10, Precision@5, Recall@10
- Compare v2.2.0 vs v2.1.0 baseline
- Target: 25%+ improvement across all metrics

---

## 🚀 Orchestration Strategy

### Parallel Agent Execution
```bash
# Create 4 git worktrees
WORKTREE_BASE="../knowledgebeast-phase2"

git worktree add "${WORKTREE_BASE}/reranking" -b feature/reranking
git worktree add "${WORKTREE_BASE}/chunking" -b feature/advanced-chunking
git worktree add "${WORKTREE_BASE}/multimodal" -b feature/multimodal-support
git worktree add "${WORKTREE_BASE}/query-expansion" -b feature/query-expansion

# Launch agents in parallel (Claude Code Task tool)
```

### Agent Dependencies
- **No blocking dependencies**: All 4 agents can work in parallel
- **Integration point**: All merge into `main` after PR reviews
- **Conflict resolution**: Semantic conflicts resolved during merge

### PR Review Criteria
- ✅ All tests passing (100% success rate)
- ✅ Code coverage > 90% for new code
- ✅ Performance benchmarks meet targets
- ✅ Documentation complete (docstrings, README updates)
- ✅ No breaking API changes
- ✅ Prometheus metrics added
- ✅ OpenTelemetry spans added

---

## 📚 Documentation Requirements

### New Documentation
1. **Advanced RAG Guide** (`docs/guides/advanced-rag.md`)
   - Re-ranking strategies
   - Chunking best practices
   - Multi-modal workflows
   - Query optimization tips

2. **Multi-Modal Setup** (`docs/setup/multimodal.md`)
   - PDF processing setup
   - CLIP/BLIP model installation
   - OCR dependencies (Tesseract)
   - GPU acceleration guide

3. **Performance Tuning** (`docs/operations/performance-tuning.md`)
   - Re-ranking optimization
   - Semantic cache tuning
   - Chunk size optimization
   - Model caching strategies

4. **API v2 Migration Guide** (`docs/migration/v2.1-to-v2.2.md`)
   - New query parameters
   - Response format changes
   - Configuration updates
   - Backward compatibility notes

---

## 🔄 Success Criteria

### Must Have (Release Blockers)
- ✅ 210+ new tests (all passing)
- ✅ 25%+ quality improvement on benchmark dataset
- ✅ All performance targets met
- ✅ Zero breaking changes
- ✅ Documentation complete
- ✅ Grafana dashboards updated

### Nice to Have (Post-Release)
- 🎯 LLM-based query expansion (requires API key)
- 🎯 Personalized ranking (opt-in feature)
- 🎯 Multi-language support (beyond English)
- 🎯 Video processing support

---

## 📅 Timeline

### Week 1-2: Foundation
- Agent setup and worktree creation
- Dependency installation
- Base interfaces and abstractions
- Initial test scaffolding

### Week 3-4: Implementation
- Core feature development
- Integration with existing components
- Comprehensive testing
- Performance optimization

### Week 5: Integration & Testing
- PR reviews and merges
- End-to-end integration testing
- Quality benchmark validation
- Documentation finalization

### Week 6: Release
- Final testing and bug fixes
- Release notes preparation
- v2.2.0 tag and release
- Announcement and promotion

---

## 🔗 Dependencies

### New Python Dependencies
```
# Re-ranking
sentence-transformers>=2.2.0
torch>=2.0.0

# Multi-modal
PyPDF2>=3.0.0
pdfplumber>=0.10.0
pytesseract>=0.3.10
pillow>=10.0.0
transformers>=4.30.0
tree-sitter>=0.20.0
tree-sitter-python>=0.20.0
tree-sitter-javascript>=0.20.0

# Query expansion
nltk>=3.8.0          # WordNet
spacy>=3.5.0         # NER
```

### System Dependencies
```bash
# OCR support
brew install tesseract  # macOS
apt-get install tesseract-ocr  # Ubuntu

# GPU acceleration (optional)
# Requires CUDA 11.8+ and compatible GPU
```

---

## 📊 Risk Assessment

### High Risk
- **Multi-modal model size**: CLIP/BLIP models are 400MB+ each
  - Mitigation: Lazy loading, model quantization, optional feature

- **Re-ranking latency**: Cross-encoders are slower than bi-encoders
  - Mitigation: Batch processing, async execution, configurable depth

### Medium Risk
- **OCR accuracy**: Tesseract quality varies by document
  - Mitigation: Fallback to layout extraction, quality metrics

- **Chunking quality**: Semantic chunking may fail on unstructured text
  - Mitigation: Multiple strategies, fallback to recursive

### Low Risk
- **Query expansion**: May add noise for precise queries
  - Mitigation: Configurable, optional, user feedback loop

---

## 🎉 Expected Impact

### User Experience
- **30% more relevant results** via re-ranking
- **40% better context preservation** via semantic chunking
- **Support for 15+ file types** via multi-modal processing
- **50% lower latency** via semantic caching

### Engineering Excellence
- **210+ new tests** (total: 1,571 tests)
- **Production-ready monitoring** with new dashboards
- **Comprehensive documentation** for advanced features
- **Backward compatible** - zero breaking changes

### Business Value
- **Broader use cases**: PDF processing, image search, code search
- **Better search quality**: Measurable 25%+ improvement
- **Faster queries**: Semantic caching reduces compute costs
- **Competitive differentiation**: Advanced RAG vs basic vector search

---

## 🚀 Launch Plan

### Pre-Launch (Week 5)
- Beta testing with select users
- Performance load testing (1000+ concurrent queries)
- Documentation review
- Security audit

### Launch (Week 6)
- Tag v2.2.0 release
- Update main documentation
- Blog post: "KnowledgeBeast v2.2.0 - Advanced RAG"
- Social media announcement

### Post-Launch (Week 7+)
- Monitor metrics and user feedback
- Bug fixes and patches
- Plan Phase 3 (Enterprise Scale)

---

**Next Steps**: Ready to execute Phase 2? Use the launch script below:

```bash
# .claude/launch_phase2_agents.sh
#!/bin/bash
REPO_ROOT=$(git rev-parse --show-toplevel)
WORKTREE_BASE="${REPO_ROOT}/../knowledgebeast-phase2"

# Create worktrees
git worktree add "${WORKTREE_BASE}/reranking" -b feature/reranking
git worktree add "${WORKTREE_BASE}/chunking" -b feature/advanced-chunking
git worktree add "${WORKTREE_BASE}/multimodal" -b feature/multimodal-support
git worktree add "${WORKTREE_BASE}/query-expansion" -b feature/query-expansion

echo "✅ Phase 2 worktrees created. Ready to launch agents!"
```
