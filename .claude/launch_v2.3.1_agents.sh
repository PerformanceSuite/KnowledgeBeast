#!/bin/bash
# KnowledgeBeast v2.3.1 - Autonomous Agent Launcher
# Launches 2 agents in parallel to complete remaining v2.3.0 improvements

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Project root
PROJECT_ROOT="/Users/danielconnolly/Projects/KnowledgeBeast"
PARENT_DIR="/Users/danielconnolly/Projects"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}KnowledgeBeast v2.3.1 Agent Launcher${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Verify we're in the right directory
if [ ! -f "$PROJECT_ROOT/pyproject.toml" ]; then
    echo -e "${RED}Error: Not in KnowledgeBeast project root${NC}"
    echo "Expected: $PROJECT_ROOT"
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

# Clean up existing worktrees if they exist
echo -e "${YELLOW}Cleaning up existing worktrees...${NC}"
if [ -d "$PARENT_DIR/KnowledgeBeast-agent1" ]; then
    cd "$PROJECT_ROOT"
    git worktree remove "$PARENT_DIR/KnowledgeBeast-agent1" --force 2>/dev/null || true
    rm -rf "$PARENT_DIR/KnowledgeBeast-agent1"
fi

if [ -d "$PARENT_DIR/KnowledgeBeast-agent2" ]; then
    cd "$PROJECT_ROOT"
    git worktree remove "$PARENT_DIR/KnowledgeBeast-agent2" --force 2>/dev/null || true
    rm -rf "$PARENT_DIR/KnowledgeBeast-agent2"
fi

echo -e "${GREEN}✓ Cleanup complete${NC}"
echo ""

# Create git worktrees
echo -e "${BLUE}Creating git worktrees...${NC}"

echo -e "${YELLOW}Agent 1: Production Hardening${NC}"
git worktree add "$PARENT_DIR/KnowledgeBeast-agent1" feature/production-hardening
echo -e "${GREEN}✓ Worktree created: $PARENT_DIR/KnowledgeBeast-agent1${NC}"

echo -e "${YELLOW}Agent 2: Security & Observability${NC}"
git worktree add "$PARENT_DIR/KnowledgeBeast-agent2" feature/security-observability
echo -e "${GREEN}✓ Worktree created: $PARENT_DIR/KnowledgeBeast-agent2${NC}"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Worktrees Created Successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Display agent information
echo -e "${BLUE}Agent 1: Production Hardening${NC}"
echo "  Branch: feature/production-hardening"
echo "  Path: $PARENT_DIR/KnowledgeBeast-agent1"
echo "  Status: 65% complete (7h remaining)"
echo "  Tasks:"
echo "    1. Fix test isolation (2h) - 12 flaky tests"
echo "    2. Per-project rate limiting (2h) - NEW"
echo "    3. Project resource quotas (3h) - NEW"
echo ""

echo -e "${BLUE}Agent 2: Security & Observability${NC}"
echo "  Branch: feature/security-observability"
echo "  Path: $PARENT_DIR/KnowledgeBeast-agent2"
echo "  Status: 65% complete (10h remaining)"
echo "  Tasks:"
echo "    1. Route instrumentation (2h) - Metrics + auth"
echo "    2. Distributed tracing (3h) - Project context"
echo "    3. Comprehensive tests (2h) - 39 tests"
echo "    4. API documentation (4h) - Multi-project guide"
echo ""

# Display instructions
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Next Steps${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""
echo "The git worktrees are ready for autonomous agent execution."
echo ""
echo "To launch agents using Claude Code Task tool, use these prompts:"
echo ""
echo -e "${GREEN}Agent 1 Prompt:${NC}"
cat << 'EOF'
You are Agent 1: Production Hardening. Your working directory is:
/Users/danielconnolly/Projects/KnowledgeBeast-agent1

Your mission: Complete the feature/production-hardening branch (7h work).

Tasks (in order):
1. Fix test isolation (2h)
   - Debug 12 failing tests in tests/api/test_project_endpoints.py
   - Fix database/ChromaDB cleanup in tests/api/conftest.py
   - Goal: 34/34 tests passing (currently 22/34)

2. Implement per-project rate limiting (2h)
   - Create knowledgebeast/api/rate_limiter.py
   - Implement composite key: {api_key}:{project_id}
   - Apply to query/ingest endpoints
   - Write 8 tests in tests/api/test_rate_limiting.py

3. Implement project resource quotas (3h)
   - Add quota tracking to knowledgebeast/core/project_manager.py
   - Enforce quotas in API routes (402 on exceeded)
   - Create quota endpoint: GET /api/v2/projects/{id}/quota
   - Write 10 tests in tests/api/test_quotas.py

Commit strategy:
- 1 commit per task (3 commits total)
- Use conventional commit messages

Success criteria:
- 52/52 tests passing (100%)
- All features working end-to-end
- Ready for PR merge

Detailed plan: /Users/danielconnolly/Projects/KnowledgeBeast/.claude/v2.3.1_completion_plan.md
EOF

echo ""
echo -e "${GREEN}Agent 2 Prompt:${NC}"
cat << 'EOF'
You are Agent 2: Security & Observability. Your working directory is:
/Users/danielconnolly/Projects/KnowledgeBeast-agent2

Your mission: Complete the feature/security-observability branch (10h work).

Tasks (in order):
1. Complete route instrumentation (2h)
   - Add metric recording to all project endpoints in knowledgebeast/api/routes.py
   - Register ProjectAuthMiddleware in knowledgebeast/api/app.py
   - Verify metrics at /metrics endpoint

2. Add distributed tracing context (3h)
   - Enhance knowledgebeast/utils/observability.py with project context
   - Add @trace_project_operation decorators to project_manager.py
   - Add baggage propagation in routes.py
   - Write 12 tests in tests/observability/test_project_tracing.py

3. Write comprehensive tests (2h)
   - tests/api/test_project_api_keys.py (15 tests)
   - tests/observability/test_project_metrics.py (12 tests)
   - Goal: 39/39 tests passing (100%)

4. Create API documentation (4h)
   - docs/api/MULTI_PROJECT_GUIDE.md (~1500 lines)
   - examples/multi_project_client.py
   - examples/multi_project_curl.sh

Commit strategy:
- 1 commit per task (4 commits total)
- Use conventional commit messages

Success criteria:
- 39/39 tests passing (100%)
- Documentation complete with examples
- Ready for PR merge

Detailed plan: /Users/danielconnolly/Projects/KnowledgeBeast/.claude/v2.3.1_completion_plan.md
EOF

echo ""
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Merge Strategy${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""
echo "1. Agent 2 merges FIRST (simpler, less conflicts)"
echo "2. Agent 1 rebases on updated main, resolves conflicts, merges"
echo "3. Both agents work independently until merge time"
echo ""

echo -e "${GREEN}Ready to launch autonomous agents!${NC}"
echo ""
