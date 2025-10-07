#!/bin/bash
# KnowledgeBeast - Session Cleanup Script
# Auto-generated for Python project

set -e

echo "🧹 Cleaning up KnowledgeBeast project..."

# Python cache cleanup
echo "  → Removing Python cache files..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

# pytest cache
echo "  → Removing pytest cache..."
rm -rf .pytest_cache 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

# Coverage files
echo "  → Removing coverage files..."
rm -f .coverage 2>/dev/null || true
rm -rf htmlcov 2>/dev/null || true

# Temporary files
echo "  → Removing temporary files..."
find . -type f -name "*.tmp" -delete 2>/dev/null || true
find . -type f -name "*.log" -delete 2>/dev/null || true
find . -type f -name "*.swp" -delete 2>/dev/null || true
find . -type f -name "*.swo" -delete 2>/dev/null || true
find . -type f -name "*~" -delete 2>/dev/null || true

# macOS files
echo "  → Removing macOS files..."
find . -type f -name ".DS_Store" -delete 2>/dev/null || true

# Remove empty directories
echo "  → Removing empty directories..."
find . -type d -empty -delete 2>/dev/null || true

# Update timestamp in memory.md
if [ -f .claude/memory.md ]; then
    echo "  → Updating timestamp in memory.md..."
    sed -i.bak "s/\*\*Last Updated\*\*: .*/\*\*Last Updated\*\*: $(date '+%B %d, %Y')/" .claude/memory.md
    rm -f .claude/memory.md.bak
fi

echo "✅ Cleanup complete!"
