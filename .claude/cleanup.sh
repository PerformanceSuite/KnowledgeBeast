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
    echo "  Attempting to kill them..."
    ps aux | grep -E "python.*knowledgebeast|uvicorn.*knowledgebeast" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null || true
    echo "  ✅ Killed lingering processes"
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
rm -f .coverage.* 2>/dev/null || true
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

# Step 7: Clean test databases (but preserve schema/migrations)
echo ""
echo "Step 7: Cleaning test databases..."
# Remove test databases but keep production ones (if any)
rm -f test*.db 2>/dev/null || true
rm -f kb_projects.db 2>/dev/null || true  # Test DB created by E2E tests
rm -f projects.db 2>/dev/null || true     # Another test DB
# Clean ChromaDB test data (but preserve the directory structure)
if [ -d "chroma" ]; then
    rm -rf chroma/*.sqlite3 2>/dev/null || true
    rm -rf chroma/*.sqlite3-* 2>/dev/null || true
fi
if [ -d "chroma_db" ]; then
    rm -rf chroma_db/*.sqlite3 2>/dev/null || true
    rm -rf chroma_db/*.sqlite3-* 2>/dev/null || true
fi
echo "  ✅ Test databases cleaned"

# Step 8: Clean knowledge base cache files
echo ""
echo "Step 8: Cleaning knowledge base cache..."
rm -f .knowledge_cache.pkl 2>/dev/null || true
rm -f knowledge_cache.pkl 2>/dev/null || true
echo "  ✅ Knowledge base cache cleaned"

# Step 9: Remove empty directories
echo ""
echo "Step 9: Removing empty directories..."
find . -type d -empty -not -path "./.git/*" -delete 2>/dev/null || true
echo "  ✅ Empty directories removed"

# Step 10: Update timestamp in memory.md
echo ""
echo "Step 10: Updating timestamp in memory.md..."
if [ -f .claude/memory.md ]; then
    # Use a more portable sed approach (works on both macOS and Linux)
    TIMESTAMP=$(date '+%B %d, %Y')
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/\*\*Last Updated\*\*: .*/\*\*Last Updated\*\*: $TIMESTAMP/" .claude/memory.md
    else
        # Linux
        sed -i "s/\*\*Last Updated\*\*: .*/\*\*Last Updated\*\*: $TIMESTAMP/" .claude/memory.md
    fi
    echo "  ✅ Timestamp updated to: $TIMESTAMP"
else
    echo "  ⚠️  Warning: .claude/memory.md not found"
fi

# Step 11: Clean mypy cache
echo ""
echo "Step 11: Cleaning mypy cache..."
rm -rf .mypy_cache 2>/dev/null || true
find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
echo "  ✅ Mypy cache cleaned"

# Step 12: Clean ruff cache
echo ""
echo "Step 12: Cleaning ruff cache..."
rm -rf .ruff_cache 2>/dev/null || true
echo "  ✅ Ruff cache cleaned"

# Step 13: Check for uncommitted changes
echo ""
echo "Step 13: Checking git status..."
if [ -n "$(git status --porcelain)" ]; then
    echo "  ⚠️  You have uncommitted changes:"
    git status --short
    echo ""
    echo "  Remember to review and commit if needed!"
else
    echo "  ✅ Working tree is clean"
fi

# Step 14: Verify cleanup
echo ""
echo "Step 14: Verifying cleanup..."
REMAINING=$(find . -type f \( -name "*.pyc" -o -name "*.log" -o -name "*.tmp" -o -name ".DS_Store" \) 2>/dev/null | wc -l | xargs)
if [ "$REMAINING" -eq 0 ]; then
    echo "  ✅ All temporary files cleaned"
else
    echo "  ⚠️  Warning: $REMAINING temporary files remaining"
fi

echo ""
echo "=================================="
echo "✅ Cleanup complete!"
echo ""
echo "Summary:"
echo "  ✓ Background processes killed"
echo "  ✓ Python/pytest cache cleaned"
echo "  ✓ Test databases removed"
echo "  ✓ Temporary files cleaned"
echo "  ✓ Timestamp updated"
echo ""
echo "Next steps:"
echo "  1. Review any uncommitted changes above"
echo "  2. Run 'git status' to verify"
echo "  3. Push to origin: git push origin main"
echo "  4. Verify ports are free: lsof -ti:8000"
