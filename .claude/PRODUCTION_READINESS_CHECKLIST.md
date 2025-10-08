# Production Readiness Checklist

**Purpose**: This checklist MUST be completed before tagging any production release.

**Lesson Learned**: We tagged v2.0.0 with excellent unit test coverage (1036+ tests, 96% passing) but discovered the API endpoints didn't exist when we ran end-to-end tests. Unit tests ≠ working system.

---

## Phase 1: Component Testing ✅

- [ ] **Unit Tests**: All component-level tests passing
  - Core components (embeddings, vector store, query engine)
  - Repository patterns
  - Cache mechanisms
  - Migration scripts

- [ ] **Integration Tests**: Cross-component tests passing
  - Component integration
  - Data flow between components
  - Thread safety under load

- [ ] **Performance Benchmarks**: Synthetic load tests passing
  - NDCG@10 targets met
  - Latency targets met (P99 < target)
  - Throughput targets met

**Status**: ✅ v2.0.0-beta.1 passes this phase

---

## Phase 2: End-to-End Testing ⚠️ **MANDATORY**

### 2.1 API Server Testing

- [ ] **Server Startup**
  ```bash
  python3 -m uvicorn knowledgebeast.api.app:app --host 0.0.0.0 --port 8000
  ```
  - Server starts without errors
  - Logs show proper initialization
  - Health endpoint responds

- [ ] **API Route Verification**
  ```bash
  curl http://localhost:8000/openapi.json | python3 -m json.tool > api_routes.json
  ```
  - All documented endpoints present
  - No 404s for claimed endpoints
  - Routes match OpenAPI spec

- [ ] **API Contract Testing**
  - Create requests succeed (201 Created)
  - Read requests succeed (200 OK)
  - Update requests succeed (200 OK)
  - Delete requests succeed (200 OK/204 No Content)
  - Validation errors return 422
  - Auth errors return 401/403

### 2.2 Full Workflow Testing

- [ ] **Project Lifecycle**
  ```bash
  # Create project
  curl -X POST http://localhost:8000/api/v2/projects \
    -H "X-API-Key: test-key" \
    -d '{"name": "test", "description": "Test project"}'

  # Verify project exists
  curl http://localhost:8000/api/v2/projects \
    -H "X-API-Key: test-key"

  # Delete project
  curl -X DELETE http://localhost:8000/api/v2/projects/{id} \
    -H "X-API-Key: test-key"
  ```

- [ ] **Document Ingestion**
  ```bash
  # Ingest real PDF
  curl -X POST http://localhost:8000/api/v2/projects/{id}/ingest \
    -H "X-API-Key: test-key" \
    -F "file=@test.pdf"

  # Ingest real DOCX
  curl -X POST http://localhost:8000/api/v2/projects/{id}/ingest \
    -H "X-API-Key: test-key" \
    -F "file=@test.docx"

  # Ingest markdown
  curl -X POST http://localhost:8000/api/v2/projects/{id}/ingest \
    -H "X-API-Key: test-key" \
    -F "file=@README.md"
  ```

- [ ] **Search Functionality**
  ```bash
  # Vector search
  curl -X POST http://localhost:8000/api/v2/projects/{id}/query \
    -H "X-API-Key: test-key" \
    -d '{"query": "test query", "mode": "vector", "top_k": 10}'

  # Hybrid search
  curl -X POST http://localhost:8000/api/v2/projects/{id}/query \
    -H "X-API-Key: test-key" \
    -d '{"query": "test query", "mode": "hybrid", "top_k": 10}'

  # Keyword search
  curl -X POST http://localhost:8000/api/v2/projects/{id}/query \
    -H "X-API-Key: test-key" \
    -d '{"query": "test query", "mode": "keyword", "top_k": 10}'
  ```

- [ ] **Search Quality Validation**
  - Results are relevant to query
  - Ranking makes sense (top results most relevant)
  - All three modes return results
  - Hybrid mode ≥ quality of vector-only

### 2.3 CLI Testing

- [ ] **CLI Commands Work**
  ```bash
  knowledgebeast --version
  knowledgebeast --help
  knowledgebeast init
  knowledgebeast ingest docs/
  knowledgebeast query "test query"
  knowledgebeast serve
  ```

### 2.4 Python SDK Testing

- [ ] **SDK Workflow**
  ```python
  from knowledgebeast import KnowledgeBase
  from knowledgebeast.core.project_manager import ProjectManager

  # Create knowledge base
  kb = KnowledgeBase()
  kb.ingest_directory("docs/")
  results = kb.query("test query", mode="hybrid")

  # Multi-project
  manager = ProjectManager()
  project = manager.create_project(name="test", description="Test project")
  # ... test full workflow
  ```

**Status**: ❌ v2.0.0-beta.1 FAILS this phase (API routes missing)

---

## Phase 3: Real-World Validation

- [ ] **Real Documents**
  - Ingest actual PDFs from project
  - Ingest actual DOCX files
  - Ingest actual markdown docs
  - Verify all formats parse correctly
  - Verify embeddings computed

- [ ] **Real Queries**
  - Test queries users would actually run
  - Verify results are relevant
  - Compare quality across modes
  - Measure actual latencies

- [ ] **Performance Under Load**
  - Run 100+ sequential queries
  - Measure P50, P95, P99 latencies
  - Verify throughput targets
  - Check for memory leaks
  - Verify cache effectiveness

**Status**: ⏳ Not tested for v2.0.0-beta.1

---

## Phase 4: Migration Testing

- [ ] **Migration from v1.x**
  - Create v1 knowledge base with real data
  - Run migration script
  - Verify all documents migrated
  - Verify search still works
  - Verify performance acceptable

**Status**: ⚠️ Partially tested (unit tests only)

---

## Phase 5: Documentation Verification

- [ ] **README Accuracy**
  - Installation instructions work
  - Quick start example works
  - All code examples run successfully
  - Links are not broken

- [ ] **API Documentation**
  - All endpoints documented
  - Examples include real curl commands
  - Response schemas accurate
  - Error codes documented

- [ ] **User Guides**
  - Step-by-step tutorials work
  - Code examples run
  - Screenshots current (if any)

**Status**: ⚠️ Documentation written but not validated

---

## Phase 6: Security Review

- [ ] **Authentication**
  - API key required on protected endpoints
  - Unauthenticated requests rejected
  - Invalid keys rejected

- [ ] **Input Validation**
  - SQL injection attempts blocked
  - Path traversal attempts blocked
  - Oversized requests rejected
  - Invalid formats rejected

- [ ] **Security Headers**
  - CORS configured correctly
  - Security headers present
  - No sensitive data in logs

**Status**: ✅ Partially complete (unit tests pass)

---

## Phase 7: Release Artifacts

- [ ] **Version Bump**
  - `__version__` updated
  - CHANGELOG.md updated
  - Git tag matches version

- [ ] **Release Notes**
  - What's new clearly stated
  - Breaking changes highlighted
  - Migration guide included
  - Known limitations documented

- [ ] **Distribution**
  - Package builds successfully
  - Dependencies locked
  - Installation instructions tested

**Status**: ❌ v2.0.0 retracted, v2.0.0-beta.1 tagged

---

## Final Checklist Before Tagging

**Before running `git tag -a vX.Y.Z`:**

1. [ ] ✅ Phase 1 complete (unit/integration tests passing)
2. [ ] ⚠️ Phase 2 complete (E2E tests passing) - **CRITICAL**
3. [ ] Phase 3 complete (real-world validation)
4. [ ] Phase 4 complete (migration tested)
5. [ ] Phase 5 complete (docs validated)
6. [ ] Phase 6 complete (security reviewed)
7. [ ] Phase 7 complete (release artifacts ready)

**Only tag production release when ALL phases complete.**

**For beta releases:**
- Document which phases are incomplete
- Mark limitations in release notes
- Use `-beta.N` suffix

---

## Automation

**Future**: Create automated E2E test suite that:
- Starts API server
- Runs full workflow tests
- Validates all endpoints
- Tests with real documents
- Measures performance
- Blocks tag creation if tests fail

**File**: `tests/e2e/test_production_readiness.py` (created)

---

**Last Updated**: October 8, 2025
**Status**: v2.0.0-beta.1 is Phase 1 complete only
