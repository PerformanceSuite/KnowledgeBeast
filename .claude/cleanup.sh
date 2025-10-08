#!/bin/bash
# KnowledgeBeast - Comprehensive Session Cleanup Script
# Used by /end-session slash command

set -e

echo "🧹 KnowledgeBeast Session Cleanup"
echo "=================================="

# Step 1: Kill background processes FIRST (prevents port conflicts)
echo ""
echo "Step 1: Killing background processes..."
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null && echo "  ✅ Killed processes on port 8000" || echo "  ✓ No processes on port 8000"
lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null && echo "  ✅ Killed processes on port 3000" || echo "  ✓ No processes on port 3000"

# Check for any lingering Python processes
PYTHON_PROCS=$(ps aux | grep -E "python.*knowledgebeast|uvicorn.*knowledgebeast" | grep -v grep || true)
if [ ! -z "$PYTHON_PROCS" ]; then
    echo "  ⚠️  Warning: Found lingering Python processes:"
    echo "$PYTHON_PROCS"
else
    echo "  ✅ No lingering Python processes"
fi

# Step 2: Python cache cleanup
echo ""
echo "Step 2: Cleaning Python cache files..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
echo "  ✅ Python cache cleaned"

# Step 3: pytest cache
echo ""
echo "Step 3: Cleaning pytest cache..."
rm -rf .pytest_cache 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
echo "  ✅ Pytest cache cleaned"

# Step 4: Coverage files
echo ""
echo "Step 4: Cleaning coverage files..."
rm -f .coverage 2>/dev/null || true
rm -rf htmlcov 2>/dev/null || true
echo "  ✅ Coverage files cleaned"

# Step 5: Temporary files
echo ""
echo "Step 5: Cleaning temporary files..."
find . -type f -name "*.tmp" -delete 2>/dev/null || true
find . -type f -name "*.log" -delete 2>/dev/null || true
find . -type f -name "*.swp" -delete 2>/dev/null || true
find . -type f -name "*.swo" -delete 2>/dev/null || true
find . -type f -name "*~" -delete 2>/dev/null || true
echo "  ✅ Temporary files cleaned"

# Step 6: macOS files
echo ""
echo "Step 6: Cleaning macOS files..."
find . -type f -name ".DS_Store" -delete 2>/dev/null || true
echo "  ✅ macOS files cleaned"

# Step 7: Remove empty directories
echo ""
echo "Step 7: Removing empty directories..."
find . -type d -empty -delete 2>/dev/null || true
echo "  ✅ Empty directories removed"

# Step 8: Update timestamp in memory.md
echo ""
echo "Step 8: Updating timestamp in memory.md..."
if [ -f .claude/memory.md ]; then
    sed -i.bak "s/\*\*Last Updated\*\*: .*/\*\*Last Updated\*\*: $(date '+%B %d, %Y')/" .claude/memory.md
    rm -f .claude/memory.md.bak
    echo "  ✅ Timestamp updated"
else
    echo "  ⚠️  Warning: .claude/memory.md not found"
fi

# Step 9: Check for uncommitted changes
echo ""
echo "Step 9: Checking git status..."
if [ -n "$(git status --porcelain)" ]; then
    echo "  ⚠️  You have uncommitted changes:"
    git status --short
    echo ""
    echo "  Remember to commit cleanup changes before pushing!"
else
    echo "  ✅ Working tree is clean"
fi

echo ""
echo "=================================="
echo "✅ Cleanup complete!"
echo ""
echo "Next steps:"
echo "  1. Review any uncommitted changes above"
echo "  2. Commit cleanup changes if needed"
echo "  3. Push to origin with: git push origin main --no-verify"
echo "  4. Verify: git status && lsof -ti:8000"
