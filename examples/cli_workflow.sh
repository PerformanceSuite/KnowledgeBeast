#!/bin/bash
# CLI workflow example for KnowledgeBeast
#
# This script demonstrates:
# - Initializing a knowledge base
# - Ingesting documents
# - Querying
# - Statistics
# - Cache management

set -e  # Exit on error

echo "KnowledgeBeast - CLI Workflow Example"
echo "====================================="
echo ""

# Configuration
DATA_DIR="./example-kb"
DOCS_DIR="./documents"

# 1. Initialize knowledge base
echo "1. Initializing knowledge base..."
knowledgebeast init "$DATA_DIR" --name "Example KB"
echo ""

# 2. Check health
echo "2. Running health check..."
knowledgebeast health --data-dir "$DATA_DIR"
echo ""

# 3. Ingest documents
echo "3. Ingesting documents..."
if [ -d "$DOCS_DIR" ]; then
    knowledgebeast add "$DOCS_DIR" --recursive --data-dir "$DATA_DIR"
else
    echo "   No documents directory found. Creating example..."
    mkdir -p "$DOCS_DIR"
    echo "# Example Document" > "$DOCS_DIR/example.md"
    echo "This is an example document for KnowledgeBeast." >> "$DOCS_DIR/example.md"
    knowledgebeast ingest "$DOCS_DIR/example.md" --data-dir "$DATA_DIR"
fi
echo ""

# 4. View statistics
echo "4. Viewing statistics..."
knowledgebeast stats --data-dir "$DATA_DIR"
echo ""

# 5. Query knowledge base
echo "5. Querying knowledge base..."
knowledgebeast query "example" -n 3 --data-dir "$DATA_DIR"
echo ""

# 6. Warm cache
echo "6. Warming cache..."
knowledgebeast warm --data-dir "$DATA_DIR"
echo ""

# 7. Clear cache
echo "7. Clearing cache..."
knowledgebeast clear-cache -y --data-dir "$DATA_DIR"
echo ""

# 8. Start heartbeat
echo "8. Starting heartbeat..."
knowledgebeast heartbeat start --interval 60 --data-dir "$DATA_DIR"
knowledgebeast heartbeat status --data-dir "$DATA_DIR"
knowledgebeast heartbeat stop --data-dir "$DATA_DIR"
echo ""

echo "✓ Workflow complete!"
echo ""
echo "Next steps:"
echo "  - knowledgebeast serve     # Start API server"
echo "  - knowledgebeast query 'your search'  # Search knowledge base"
echo "  - knowledgebeast --help    # View all commands"
