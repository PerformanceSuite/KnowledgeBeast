#!/bin/bash
# KnowledgeBeast v2.3.1 - Autonomous Agent Launcher (FINAL - Reduced Scope)
# Launches 2 agents in parallel with realistic, achievable goals

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_ROOT="/Users/danielconnolly/Projects/KnowledgeBeast"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}KnowledgeBeast v2.3.1 Agent Launcher${NC}"
echo -e "${BLUE}(REDUCED SCOPE - Option 2)${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Verify project root
if [ ! -f "$PROJECT_ROOT/pyproject.toml" ]; then
    echo -e "${RED}Error: Not in KnowledgeBeast project root${NC}"
    exit 1
fi

cd "$PROJECT_ROOT"

# Check if branches exist
if ! git show-ref --verify --quiet refs/heads/feature/production-hardening; then
    echo -e "${RED}Error: Branch 'feature/production-hardening' not found${NC}"
    exit 1
fi

if ! git show-ref --verify --quiet refs/heads/feature/security-observability; then
    echo -e "${RED}Error: Branch 'feature/security-observability' not found${NC}"
    exit 1
fi

echo -e "${YELLOW}Checking existing worktrees...${NC}"

# Check if worktrees already exist
AGENT1_EXISTS=$(git worktree list | grep -c "production-hardening" || true)
AGENT2_EXISTS=$(git worktree list | grep -c "security-observability" || true)

if [ "$AGENT1_EXISTS" -gt 0 ]; then
    echo -e "${GREEN}✓ Agent 1 worktree already exists (reusing)${NC}"
    AGENT1_PATH=$(git worktree list | grep "production-hardening" | awk '{print $1}')
else
    echo -e "${YELLOW}Creating Agent 1 worktree...${NC}"
    git worktree add "$PROJECT_ROOT/.worktrees/production-hardening" feature/production-hardening
    AGENT1_PATH="$PROJECT_ROOT/.worktrees/production-hardening"
    echo -e "${GREEN}✓ Agent 1 worktree created${NC}"
fi

if [ "$AGENT2_EXISTS" -gt 0 ]; then
    echo -e "${GREEN}✓ Agent 2 worktree already exists (reusing)${NC}"
    AGENT2_PATH=$(git worktree list | grep "security-observability" | awk '{print $1}')
else
    echo -e "${YELLOW}Creating Agent 2 worktree...${NC}"
    git worktree add "$PROJECT_ROOT/.worktrees/security-observability" feature/security-observability
    AGENT2_PATH="$PROJECT_ROOT/.worktrees/security-observability"
    echo -e "${GREEN}✓ Agent 2 worktree created${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Worktrees Ready!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Display agent information
echo -e "${BLUE}Agent 1: Production Hardening (8h)${NC}"
echo "  Branch: feature/production-hardening"
echo "  Path: $AGENT1_PATH"
echo "  Current: 22/46 tests passing (48%)"
echo "  Target: 46/46 tests passing (100%)"
echo "  Tasks:"
echo "    1. Fix test isolation (2h)"
echo "    2. Fix API endpoint bugs (6h) - CRITICAL"
echo ""

echo -e "${BLUE}Agent 2: Security & Observability (12h)${NC}"
echo "  Branch: feature/security-observability"
echo "  Path: $AGENT2_PATH"
echo "  Current: Core implemented, 0 tests"
echo "  Target: 20 essential tests, routes instrumented"
echo "  Tasks:"
echo "    1. Route instrumentation (3h) - 15 endpoints"
echo "    2. Write 20 essential tests (6h) - API keys + metrics"
echo "    3. API reference docs (3h) - Auto-generate"
echo ""

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}REDUCED SCOPE (v2.3.1)${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""
echo -e "${GREEN}Shipping Now:${NC}"
echo "  ✅ API endpoint bug fixes"
echo "  ✅ Project API key system"
echo "  ✅ Route metrics instrumentation"
echo "  ✅ 20 essential tests"
echo "  ✅ API reference documentation"
echo ""
echo -e "${YELLOW}Deferred to v2.3.2:${NC}"
echo "  ⏳ Per-project rate limiting"
echo "  ⏳ Project resource quotas"
echo "  ⏳ Distributed tracing context"
echo "  ⏳ Comprehensive documentation"
echo ""

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Next Steps${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""
echo "Launch agents using Claude Code Task tool with these prompts:"
echo ""

echo -e "${GREEN}=== AGENT 1 PROMPT ===${NC}"
cat << 'EOF'
You are Agent 1: Production Hardening (REDUCED SCOPE).
Working directory: [Agent 1 worktree path from above]

Mission: Fix 24 failing API tests in 8 hours.

Current State:
- 22/46 tests passing (48%)
- Target: 46/46 tests passing (100%)

Tasks (8 hours):
1. Fix test isolation (2h)
   - Run: pytest tests/api/test_project_endpoints.py::test_create_project_success -v --pdb
   - Check conftest.py fixtures
   - Verify ChromaDB cleanup
   - Goal: Tests run in any order

2. Fix API endpoint bugs (6h) - CRITICAL
   - Step 1: Diagnostic (1h)
     * Run failing test with --pdb
     * Identify root cause (likely ProjectManager initialization)
   - Step 2: Fix endpoints (4h)
     * GET /api/v2/projects/{id} - returns wrong data
     * UPDATE /api/v2/projects/{id} - not persisting
     * DELETE /api/v2/projects/{id} - not deleting
     * POST /api/v2/projects/{id}/query - not wired to ChromaDB
     * POST /api/v2/projects/{id}/ingest - not storing
   - Step 3: Verify (1h)
     * pytest tests/api/test_project_endpoints.py -v
     * Goal: 46/46 passing

DEFERRED TO v2.3.2:
- Rate limiting (do NOT implement)
- Quotas (do NOT implement)

Success Criteria:
- 46/46 tests passing (100%)
- All CRUD operations working
- Projects persist correctly
- PR ready for merge

Detailed plan: /Users/danielconnolly/Projects/KnowledgeBeast/.claude/v2.3.1_FINAL_PLAN.md (Agent 1 section)
EOF

echo ""
echo -e "${GREEN}=== AGENT 2 PROMPT ===${NC}"
cat << 'EOF'
You are Agent 2: Security & Observability (REDUCED SCOPE).
Working directory: [Agent 2 worktree path from above]

Mission: Instrument routes, write 20 essential tests, create API docs in 12 hours.

Current State:
- Core implemented: project_auth.py (498 lines), metrics.py (162 lines)
- 0/20 tests exist (must write from scratch)
- Routes not instrumented

Tasks (12 hours):
1. Route instrumentation (3h)
   - Add metrics to 15 endpoints in knowledgebeast/api/routes.py
   - Pattern:
     ```python
     from knowledgebeast.utils.metrics import measure_project_query

     @router_v2.post("/projects/{project_id}/query")
     async def query_project(...):
         try:
             with measure_project_query(project_id):
                 result = await project_manager.query(...)
             return result
         except Exception as e:
             record_project_error(project_id, "query", str(e))
             raise
     ```
   - Verify: curl http://localhost:8000/metrics

2. Write 20 essential tests (6h)
   - tests/api/test_project_api_keys.py (10 tests)
     * test_create_api_key
     * test_list_api_keys
     * test_revoke_api_key
     * test_api_key_scope_enforcement
     * test_api_key_expiration
     * test_api_key_validation
     * test_api_key_invalid_format
     * test_api_key_project_isolation
     * test_api_key_last_used_tracking
     * test_create_api_key_with_scopes

   - tests/observability/test_project_metrics.py (8 tests)
     * test_project_query_metrics_recorded
     * test_project_ingest_metrics_recorded
     * test_project_metrics_isolation
     * test_project_error_metrics
     * test_project_cache_hit_metrics
     * test_project_cache_miss_metrics
     * test_project_metrics_labels
     * test_metrics_endpoint_accessible

   - tests/api/test_project_security_integration.py (2 tests)
     * test_end_to_end_api_key_flow
     * test_metrics_recorded_during_operations

   - Goal: 20/20 passing

3. Create API reference documentation (3h)
   - Auto-generate from OpenAPI schema
   - File: docs/api/MULTI_PROJECT_API_REFERENCE.md
   - Include: All endpoints, request/response schemas, auth guide
   - Focus on API reference only (no examples, no troubleshooting)

DEFERRED TO v2.3.2:
- Distributed tracing context (do NOT implement)
- Comprehensive documentation with examples (do NOT write)
- 19 additional tests (write only 20, not 39)

Success Criteria:
- 15 endpoints instrumented
- 20/20 tests passing (100%)
- API reference complete (~800 lines)
- PR ready for merge

Detailed plan: /Users/danielconnolly/Projects/KnowledgeBeast/.claude/v2.3.1_FINAL_PLAN.md (Agent 2 section)
EOF

echo ""
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Timeline${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""
echo "Day 1-2 (Oct 9-10): Parallel execution (both agents work)"
echo "Day 3 (Oct 11): Complete implementation"
echo "Day 4 (Oct 12): Documentation & testing"
echo "Day 5 (Oct 13): Merge both PRs"
echo "Day 6 (Oct 14): Validation"
echo "Day 7 (Oct 15): Release v2.3.1"
echo ""

echo -e "${GREEN}Ready to launch autonomous agents!${NC}"
echo ""
echo "Merge order: Agent 2 first (simpler), then Agent 1 (rebase)"
echo ""
