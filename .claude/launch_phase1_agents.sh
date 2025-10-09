#!/bin/bash
# Phase 1: Production Excellence - Agent Launcher
# Launches 4 parallel agents using git worktrees

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKTREE_BASE="${REPO_ROOT}/../knowledgebeast-phase1"

echo "🚀 Phase 1: Production Excellence - Launching Agents"
echo "=================================================="
echo ""

# Create worktree base directory
mkdir -p "${WORKTREE_BASE}"

# Agent 1: Observability Stack
echo "🤖 Agent 1: Observability Stack"
echo "  Branch: feature/observability-stack"
echo "  Duration: ~8 hours"
echo "  Tests: 35"
echo ""

git worktree add "${WORKTREE_BASE}/observability" -b feature/observability-stack 2>/dev/null || true

# Agent 2: Reliability Engineering
echo "🤖 Agent 2: Reliability Engineering"
echo "  Branch: feature/reliability-engineering"
echo "  Duration: ~10 hours"
echo "  Tests: 60"
echo ""

git worktree add "${WORKTREE_BASE}/reliability" -b feature/reliability-engineering 2>/dev/null || true

# Agent 3: Grafana Dashboards
echo "🤖 Agent 3: Grafana Dashboards"
echo "  Branch: feature/grafana-dashboards"
echo "  Duration: ~6 hours"
echo "  Tests: 18"
echo ""

git worktree add "${WORKTREE_BASE}/dashboards" -b feature/grafana-dashboards 2>/dev/null || true

# Agent 4: Production Documentation
echo "🤖 Agent 4: Production Documentation"
echo "  Branch: feature/production-docs"
echo "  Duration: ~6 hours"
echo "  Tests: 20"
echo ""

git worktree add "${WORKTREE_BASE}/docs" -b feature/production-docs 2>/dev/null || true

echo "=================================================="
echo "✅ All 4 worktrees created successfully!"
echo ""
echo "📂 Worktree locations:"
echo "  1. ${WORKTREE_BASE}/observability"
echo "  2. ${WORKTREE_BASE}/reliability"
echo "  3. ${WORKTREE_BASE}/dashboards"
echo "  4. ${WORKTREE_BASE}/docs"
echo ""
echo "🎯 Agent Tasks:"
echo "  Agent 1: OpenTelemetry, Prometheus, Structured Logging"
echo "  Agent 2: Circuit Breakers, Graceful Degradation, Retry Logic"
echo "  Agent 3: Grafana Dashboards, Prometheus Config, Alerting"
echo "  Agent 4: Runbook, SLA/SLO, DR Plan, Monitoring Guide"
echo ""
echo "⏱️  Estimated completion: ~10 hours (wall-clock)"
echo "📊 New tests: 133 (35+60+18+20)"
echo ""
echo "🚀 Ready to launch agents!"
echo ""
echo "Next steps:"
echo "  1. Review Phase 1 plan: cat .claude/phase1_production_excellence.md"
echo "  2. Launch agents with Claude Code Task tool"
echo "  3. Monitor progress: tail -f ${WORKTREE_BASE}/*/agent.log"
echo "  4. Verify PRs: gh pr list --label 'phase-1'"
echo ""
