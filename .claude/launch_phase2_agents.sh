#!/bin/bash
# Phase 2: Advanced RAG Capabilities - Agent Launcher
# This script creates git worktrees for parallel agent execution

set -e  # Exit on error

echo "🚀 Launching Phase 2: Advanced RAG Capabilities"
echo "================================================"

# Get repo root
REPO_ROOT=$(git rev-parse --show-toplevel)
WORKTREE_BASE="${REPO_ROOT}/../knowledgebeast-phase2"

# Ensure we're on main branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "⚠️  Warning: Not on main branch (currently on $CURRENT_BRANCH)"
    echo "   Continuing anyway..."
fi

# Create base directory
mkdir -p "$WORKTREE_BASE"

echo ""
echo "📁 Creating worktrees..."
echo "========================"

# Agent 1: Re-Ranking
if [ ! -d "${WORKTREE_BASE}/reranking" ]; then
    echo "  Creating worktree: reranking (feature/reranking)"
    git worktree add "${WORKTREE_BASE}/reranking" -b feature/reranking
    echo "  ✅ reranking worktree created"
else
    echo "  ⏭️  Skipping reranking (already exists)"
fi

# Agent 2: Advanced Chunking
if [ ! -d "${WORKTREE_BASE}/chunking" ]; then
    echo "  Creating worktree: chunking (feature/advanced-chunking)"
    git worktree add "${WORKTREE_BASE}/chunking" -b feature/advanced-chunking
    echo "  ✅ chunking worktree created"
else
    echo "  ⏭️  Skipping chunking (already exists)"
fi

# Agent 3: Multi-Modal Support
if [ ! -d "${WORKTREE_BASE}/multimodal" ]; then
    echo "  Creating worktree: multimodal (feature/multimodal-support)"
    git worktree add "${WORKTREE_BASE}/multimodal" -b feature/multimodal-support
    echo "  ✅ multimodal worktree created"
else
    echo "  ⏭️  Skipping multimodal (already exists)"
fi

# Agent 4: Query Expansion & Semantic Caching
if [ ! -d "${WORKTREE_BASE}/query-expansion" ]; then
    echo "  Creating worktree: query-expansion (feature/query-expansion)"
    git worktree add "${WORKTREE_BASE}/query-expansion" -b feature/query-expansion
    echo "  ✅ query-expansion worktree created"
else
    echo "  ⏭️  Skipping query-expansion (already exists)"
fi

echo ""
echo "📊 Worktree Summary"
echo "=================="
git worktree list

echo ""
echo "✅ Phase 2 worktrees ready!"
echo ""
echo "Next Steps:"
echo "1. Launch 4 agents in parallel using Claude Code Task tool"
echo "2. Each agent will work in isolation on their feature"
echo "3. Review and merge PRs when agents complete"
echo "4. Run integration tests and quality benchmarks"
echo "5. Tag v2.2.0 release"
echo ""
echo "Agent Tasks:"
echo "  - Agent 1 (reranking): Re-ranking with cross-encoders (45 tests)"
echo "  - Agent 2 (chunking): Advanced chunking strategies (60 tests)"
echo "  - Agent 3 (multimodal): Multi-modal support (60 tests)"
echo "  - Agent 4 (query-expansion): Query expansion & caching (45 tests)"
echo ""
echo "Total Expected Tests: 210 new tests"
echo "Expected Quality Improvement: 25%+"
echo "Expected Timeline: 4-6 weeks"
