#!/bin/bash
# Phase 3 v2.3.0 Agent Launcher
# Creates git worktrees and launches 4 autonomous agents in parallel

set -e

echo "🚀 Phase 3: v2.3.0 Multi-Tenant Production Release"
echo "=================================================="
echo ""

# Create worktrees directory
echo "📁 Creating .worktrees directory..."
mkdir -p .worktrees

# Create git worktrees for all 4 agents
echo ""
echo "🌳 Creating git worktrees..."

echo "  → Agent 1: Multi-Project Backend (feature/multi-project-backend)"
git worktree add .worktrees/multi-project-backend -b feature/multi-project-backend

echo "  → Agent 2: Performance Infrastructure (feature/performance-infrastructure)"
git worktree add .worktrees/performance-infrastructure -b feature/performance-infrastructure

echo "  → Agent 3: Thread Safety Modernization (feature/thread-safety-v2)"
git worktree add .worktrees/thread-safety-v2 -b feature/thread-safety-v2

echo "  → Agent 4: Production Deployment (feature/production-deployment)"
git worktree add .worktrees/production-deployment -b feature/production-deployment

echo ""
echo "✅ Git worktrees created successfully!"
echo ""

# List worktrees
echo "📋 Active worktrees:"
git worktree list

echo ""
echo "🎯 Next Steps:"
echo "1. Launch 4 autonomous agents using Claude Code Task tool"
echo "2. Each agent will work in their isolated worktree"
echo "3. Agents will create PRs when ready"
echo "4. Coordinator will review and merge in correct order"
echo ""
echo "📝 Agent Tasks:"
echo "  - Agent 1: Implement multi-project backend (PR #44)"
echo "  - Agent 2: Fix performance test infrastructure (PR #45)"
echo "  - Agent 3: Modernize thread safety tests (PR #46)"
echo "  - Agent 4: Create production deployment guide (PR #47)"
echo ""
echo "🎉 Ready to launch agents!"
