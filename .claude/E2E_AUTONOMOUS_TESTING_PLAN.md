# Autonomous E2E Testing Plan - KnowledgeBeast v2.0

## Overview

Fully autonomous end-to-end testing system using git worktrees for parallel execution and comprehensive system validation.

## Architecture

### 1. Git Worktree Strategy

```bash
# Main workspace
main/                       # Current development branch

# Test worktrees (isolated, parallel execution)
test-worktrees/
├── e2e-api-routes/        # API endpoint validation
├── e2e-document-flow/     # Document ingestion & retrieval
├── e2e-search-quality/    # Search quality & relevance
├── e2e-performance/       # Performance & load testing
├── e2e-migration/         # V1 → V2 migration testing
└── e2e-integration/       # Full system integration
```

**Benefits:**
- **Parallel Execution**: 6 test agents run simultaneously
- **Zero Conflicts**: Each agent has isolated workspace
- **Fast Cleanup**: Delete worktree when done
- **Resource Isolation**: Separate DBs, caches per worktree

### 2. Test Agents

#### Agent 1: API Routes Validator
**Workspace**: `test-worktrees/e2e-api-routes`
**Duration**: ~5 minutes

**Tests:**
1. ✅ **All v2 routes exist and respond**
   - POST `/api/v2/projects` → 201 Created
   - GET `/api/v2/projects` → 200 OK
   - GET `/api/v2/projects/{id}` → 200 OK
   - PUT `/api/v2/projects/{id}` → 200 OK
   - DELETE `/api/v2/projects/{id}` → 200 OK
   - POST `/api/v2/projects/{id}/ingest` → 201 Created
   - POST `/api/v2/projects/{id}/query` → 200 OK

2. ✅ **Authentication & Authorization**
   - Missing API key → 401
   - Invalid API key → 403
   - Valid API key → Success

3. ✅ **Input Validation**
   - Empty project name → 422
   - Invalid file format → 400
   - SQL injection attempts → Sanitized

**Exit Criteria**: All 21 endpoint tests pass

---

#### Agent 2: Document Flow Validator
**Workspace**: `test-worktrees/e2e-document-flow`
**Duration**: ~10 minutes

**Tests:**
1. ✅ **Multi-Format Ingestion**
   - PDF documents → Extracted correctly
   - DOCX documents → Extracted correctly
   - Markdown files → Parsed correctly
   - HTML files → Cleaned & indexed
   - Plain text → Ingested directly

2. ✅ **Document Lifecycle**
   - Create project → Success
   - Ingest 10 documents → All successful
   - Query documents → All retrievable
   - Update metadata → Changes persist
   - Delete project → All resources cleaned

3. ✅ **Error Handling**
   - Corrupt PDF → Graceful failure
   - Missing file → 404 error
   - Unsupported format → Clear error message

**Exit Criteria**: 15 document workflows complete successfully

---

#### Agent 3: Search Quality Validator
**Workspace**: `test-worktrees/e2e-search-quality`
**Duration**: ~15 minutes

**Tests:**
1. ✅ **Vector Search Quality**
   - Semantic similarity queries
   - NDCG@10 ≥ 0.85 (target: 0.93)
   - Mean Average Precision ≥ 0.60 (target: 0.74)
   - Embedding generation < 50ms per doc

2. ✅ **Hybrid Search Performance**
   - Keyword + Vector fusion
   - Ranking quality tests
   - Edge case handling (empty query, special chars)

3. ✅ **Multi-Project Isolation**
   - Project A docs NOT in Project B results
   - Cross-project query validation
   - Namespace isolation verification

**Exit Criteria**: Search quality metrics meet or exceed targets

---

#### Agent 4: Performance & Load Validator
**Workspace**: `test-worktrees/e2e-performance`
**Duration**: ~20 minutes

**Tests:**
1. ✅ **Latency Benchmarks**
   - P50 query latency < 50ms
   - P95 query latency < 100ms
   - P99 query latency < 150ms
   - Cached query < 10ms

2. ✅ **Throughput Tests**
   - 10 concurrent workers → > 500 q/s
   - 50 concurrent workers → > 300 q/s
   - 100 concurrent workers → Graceful degradation

3. ✅ **Resource Usage**
   - Memory usage < 500MB baseline
   - CPU usage < 80% under load
   - Disk I/O reasonable
   - No memory leaks (24h soak test optional)

**Exit Criteria**: All performance targets met

---

#### Agent 5: Migration Validator
**Workspace**: `test-worktrees/e2e-migration`
**Duration**: ~15 minutes

**Tests:**
1. ✅ **V1 → V2 Migration**
   - Create V1 knowledge base (term-based)
   - Run migration script
   - Verify V2 vector embeddings created
   - Validate search still works
   - Compare search quality (V2 should be better)

2. ✅ **Backward Compatibility**
   - V1 API endpoints still work
   - V1 CLI commands functional
   - Existing integrations unaffected

3. ✅ **Data Integrity**
   - All documents migrated
   - No data loss
   - Metadata preserved
   - Cache invalidated correctly

**Exit Criteria**: Clean migration with zero data loss

---

#### Agent 6: Full Integration Validator
**Workspace**: `test-worktrees/e2e-integration`
**Duration**: ~30 minutes

**Tests:**
1. ✅ **Complete User Workflows**
   - New user onboarding flow
   - Multi-project setup
   - Document ingestion pipeline
   - Search & retrieval workflows
   - Project management (CRUD)

2. ✅ **Real-World Scenarios**
   - Ingest 1000+ documents
   - Multiple concurrent users
   - Mixed query patterns
   - Resource cleanup validation

3. ✅ **Failure Recovery**
   - API server restart → State persists
   - Database connection loss → Reconnects
   - ChromaDB failure → Graceful degradation

**Exit Criteria**: End-to-end workflows succeed

---

## Execution Plan

### Phase 1: Setup (1 minute)
```bash
# Create test worktrees
git worktree add test-worktrees/e2e-api-routes main
git worktree add test-worktrees/e2e-document-flow main
git worktree add test-worktrees/e2e-search-quality main
git worktree add test-worktrees/e2e-performance main
git worktrees/e2e-migration main
git worktree add test-worktrees/e2e-integration main
```

### Phase 2: Parallel Agent Launch (simultaneous)
```bash
# Launch all 6 agents in parallel
claude-agent --worktree test-worktrees/e2e-api-routes \
  --task "Run API routes validation tests" &

claude-agent --worktree test-worktrees/e2e-document-flow \
  --task "Run document flow validation tests" &

claude-agent --worktree test-worktrees/e2e-search-quality \
  --task "Run search quality validation tests" &

claude-agent --worktree test-worktrees/e2e-performance \
  --task "Run performance & load tests" &

claude-agent --worktree test-worktrees/e2e-migration \
  --task "Run V1→V2 migration tests" &

claude-agent --worktree test-worktrees/e2e-integration \
  --task "Run full integration tests" &

# Wait for all agents to complete
wait
```

### Phase 3: Results Aggregation (2 minutes)
```bash
# Collect results from all worktrees
python3 scripts/aggregate_e2e_results.py \
  --worktrees test-worktrees/* \
  --output .claude/e2e-test-results.json
```

### Phase 4: Cleanup (1 minute)
```bash
# Remove test worktrees
rm -rf test-worktrees/
git worktree prune
```

**Total Execution Time**: ~35 minutes (with parallel execution)
**Sequential Equivalent**: ~95 minutes
**Time Savings**: 63%

---

## Success Criteria

### Critical (Must Pass)
- ✅ All API routes return correct status codes
- ✅ Document ingestion works for all formats
- ✅ Search quality meets performance targets
- ✅ Zero data corruption or loss
- ✅ Migration completes successfully

### Important (Should Pass)
- ✅ Performance targets met (latency, throughput)
- ✅ Multi-project isolation verified
- ✅ Resource usage within limits
- ✅ Error handling graceful

### Nice-to-Have (May Pass)
- ✅ Load soak tests (24h)
- ✅ Chaos engineering tests
- ✅ Security penetration tests

---

## Output Format

### Per-Agent Report
```json
{
  "agent": "e2e-api-routes",
  "status": "PASSED" | "FAILED",
  "duration_seconds": 285,
  "tests_run": 21,
  "tests_passed": 21,
  "tests_failed": 0,
  "coverage": "100%",
  "critical_failures": [],
  "warnings": [],
  "recommendations": []
}
```

### Aggregate Report
```json
{
  "overall_status": "PASSED" | "FAILED",
  "total_duration_seconds": 1800,
  "agents": [/* per-agent reports */],
  "summary": {
    "total_tests": 127,
    "passed": 127,
    "failed": 0,
    "warnings": 3
  },
  "production_ready": true,
  "blocker_issues": [],
  "recommendations": [
    "Increase server timeout to 60s for model loading",
    "Add rate limiting for ingestion endpoints",
    "Consider caching embedding model"
  ]
}
```

---

## Integration with CI/CD

### GitHub Actions Workflow
```yaml
name: E2E Production Readiness Tests
on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 45

    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest requests

      - name: Run E2E Tests (Parallel)
        run: |
          python3 scripts/run_autonomous_e2e.py \
            --parallel --agents 6 \
            --output e2e-results.json

      - name: Upload Results
        uses: actions/upload-artifact@v3
        with:
          name: e2e-test-results
          path: e2e-results.json

      - name: Fail if Critical Issues
        run: |
          python3 scripts/check_e2e_blockers.py \
            --results e2e-results.json \
            --fail-on-critical
```

---

## Maintenance

### Weekly Health Checks
- Run full E2E suite on staging
- Review performance trends
- Update test data as needed

### Release Checklist
- [ ] Run E2E tests on release branch
- [ ] All agents report PASSED
- [ ] No critical failures
- [ ] Performance targets met
- [ ] Migration tested with real V1 data

---

## Lessons Learned

### What Went Wrong (v2.0.0)
1. ❌ **Unit tests passed but system broken** - Need E2E validation
2. ❌ **API routes claimed but not implemented** - Test actual HTTP requests
3. ❌ **No end-to-end workflow testing** - Must test full user journeys
4. ❌ **Tagged release without validation** - E2E must be mandatory gate

### What to Do Better
1. ✅ **Mandatory E2E before any release tag**
2. ✅ **Parallel execution for fast feedback** (35min vs 95min)
3. ✅ **Isolated worktrees prevent conflicts**
4. ✅ **Comprehensive agent coverage** (6 specialized agents)
5. ✅ **Automated result aggregation** (clear pass/fail)

---

## Next Steps

1. **Implement Agent Scripts**
   - Create `scripts/e2e_agents/api_routes.py`
   - Create `scripts/e2e_agents/document_flow.py`
   - Create `scripts/e2e_agents/search_quality.py`
   - Create `scripts/e2e_agents/performance.py`
   - Create `scripts/e2e_agents/migration.py`
   - Create `scripts/e2e_agents/integration.py`

2. **Build Orchestrator**
   - `scripts/run_autonomous_e2e.py` - Main entry point
   - `scripts/aggregate_e2e_results.py` - Results collector
   - `scripts/check_e2e_blockers.py` - Gate checker

3. **Integrate with CI/CD**
   - Add GitHub Actions workflow
   - Configure staging environment
   - Set up result dashboards

4. **Document for Team**
   - Add to README.md
   - Create contribution guide
   - Training for new developers

---

**Status**: Ready for Implementation
**Priority**: 🔥 **CRITICAL** - Must complete before v2.0.0 final release
**Estimated Effort**: 1-2 days
**ROI**: Prevent release disasters, save 63% testing time, ensure production quality
