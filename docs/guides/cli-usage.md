# CLI Usage Guide

Complete guide to using the KnowledgeBeast command-line interface.

## Installation

```bash
pip install knowledgebeast
```

## Global Options

```bash
knowledgebeast --help          # Show help
knowledgebeast --version       # Show version
knowledgebeast -v <command>    # Verbose mode
```

## Commands

### init - Initialize Knowledge Base

```bash
# Initialize in current directory
knowledgebeast init

# Initialize in custom directory
knowledgebeast init /path/to/data

# With custom name
knowledgebeast init --name "My Knowledge Base"
```

### ingest - Add Single Document

```bash
# Ingest a document
knowledgebeast ingest document.pdf

# Custom data directory
knowledgebeast ingest document.pdf --data-dir ./my-data

# Supported formats
knowledgebeast ingest paper.pdf
knowledgebeast ingest README.md
knowledgebeast ingest notes.txt
knowledgebeast ingest report.docx
```

### add - Add Multiple Documents

```bash
# Add single file
knowledgebeast add document.pdf

# Add all markdown files in directory
knowledgebeast add ./docs/

# Recursive add
knowledgebeast add ./docs/ --recursive

# With custom data directory
knowledgebeast add ./docs/ -r --data-dir ./my-data
```

### query - Search Knowledge Base

```bash
# Basic query
knowledgebeast query "machine learning"

# Get more results
knowledgebeast query "neural networks" -n 20

# Disable cache
knowledgebeast query "deep learning" --no-cache

# Custom data directory
knowledgebeast query "AI" --data-dir ./my-data

# Save results to file
knowledgebeast query "ML" > results.txt
```

### stats - View Statistics

```bash
# Basic statistics
knowledgebeast stats

# Detailed statistics
knowledgebeast stats --detailed

# Custom data directory
knowledgebeast stats --data-dir ./my-data
```

### clear - Clear All Documents

```bash
# Clear knowledge base (with confirmation)
knowledgebeast clear

# Skip confirmation
knowledgebeast clear --yes

# Custom data directory
knowledgebeast clear --data-dir ./my-data
```

### clear-cache - Clear Query Cache

```bash
# Clear cache (with confirmation)
knowledgebeast clear-cache

# Skip confirmation
knowledgebeast clear-cache -y

# Custom data directory
knowledgebeast clear-cache --data-dir ./my-data
```

### warm - Warm Cache

```bash
# Warm cache with default queries
knowledgebeast warm

# Custom data directory
knowledgebeast warm --data-dir ./my-data
```

### health - Health Check

```bash
# Run health check
knowledgebeast health

# Custom data directory
knowledgebeast health --data-dir ./my-data
```

**Output Example:**
```
┌──────────────────────────────────────────────┐
│         Health Check Results                 │
├────────────────┬────────┬────────────────────┤
│ Check          │ Status │ Details            │
├────────────────┼────────┼────────────────────┤
│ Configuration  │ ✓ PASS │ Config loaded      │
│ Knowledge Base │ ✓ PASS │ 42 documents       │
│ Data Directory │ ✓ PASS │ ./data             │
└────────────────┴────────┴────────────────────┘
```

### heartbeat - Manage Background Monitoring

```bash
# Start heartbeat
knowledgebeast heartbeat start

# Custom interval (seconds)
knowledgebeast heartbeat start --interval 300

# Check status
knowledgebeast heartbeat status

# Stop heartbeat
knowledgebeast heartbeat stop
```

### serve - Start API Server

```bash
# Start on default port (8000)
knowledgebeast serve

# Custom host and port
knowledgebeast serve --host 0.0.0.0 --port 8080

# With auto-reload (development)
knowledgebeast serve --reload
```

### version - Show Version Info

```bash
knowledgebeast version
```

## Common Workflows

### Initial Setup

```bash
# 1. Initialize
knowledgebeast init ./my-kb

# 2. Add documents
knowledgebeast add ./documents/ --recursive --data-dir ./my-kb

# 3. Check stats
knowledgebeast stats --data-dir ./my-kb

# 4. Test query
knowledgebeast query "test query" --data-dir ./my-kb
```

### Research Workflow

```bash
# Initialize research KB
knowledgebeast init ./research

# Add papers
knowledgebeast add ./papers/ -r --data-dir ./research

# Search for topics
knowledgebeast query "neural architecture search" -n 10 --data-dir ./research

# View stats
knowledgebeast stats --data-dir ./research
```

### Documentation Search

```bash
# Initialize docs KB
knowledgebeast init ./docs-kb

# Add markdown files
knowledgebeast add ./docs/ -r --data-dir ./docs-kb

# Search docs
knowledgebeast query "API authentication" --data-dir ./docs-kb
```

### Production Deployment

```bash
# Initialize production KB
knowledgebeast init /var/lib/knowledgebeast

# Add documents
knowledgebeast add /data/documents/ -r --data-dir /var/lib/knowledgebeast

# Start heartbeat
knowledgebeast heartbeat start --interval 300 --data-dir /var/lib/knowledgebeast

# Start API server
knowledgebeast serve --host 0.0.0.0 --port 8000
```

## Shell Scripting

### Batch Ingestion Script

```bash
#!/bin/bash
# ingest-all.sh

DATA_DIR="./kb"
DOCS_DIR="./documents"

echo "Initializing knowledge base..."
knowledgebeast init "$DATA_DIR"

echo "Ingesting documents..."
for file in "$DOCS_DIR"/*.pdf; do
    echo "Processing: $file"
    knowledgebeast ingest "$file" --data-dir "$DATA_DIR"
done

echo "Warming cache..."
knowledgebeast warm --data-dir "$DATA_DIR"

echo "Statistics:"
knowledgebeast stats --data-dir "$DATA_DIR"
```

### Query Script

```bash
#!/bin/bash
# search.sh

QUERY="$1"
DATA_DIR="${2:-./data}"
N_RESULTS="${3:-5}"

if [ -z "$QUERY" ]; then
    echo "Usage: $0 <query> [data-dir] [n-results]"
    exit 1
fi

knowledgebeast query "$QUERY" -n "$N_RESULTS" --data-dir "$DATA_DIR"
```

Usage:
```bash
./search.sh "machine learning" ./my-kb 10
```

### Health Check Script

```bash
#!/bin/bash
# health-check.sh

DATA_DIR="${1:-./data}"

echo "Running health check..."
if knowledgebeast health --data-dir "$DATA_DIR"; then
    echo "Health check passed"
    exit 0
else
    echo "Health check failed"
    exit 1
fi
```

## Output Formatting

KnowledgeBeast uses [Rich](https://rich.readthedocs.io/) for beautiful CLI output:

- **Spinners** during long operations
- **Progress bars** for batch operations
- **Tables** for statistics
- **Panels** for results
- **Syntax highlighting** for code

## Tips & Tricks

### 1. Use Aliases

```bash
# Add to ~/.bashrc or ~/.zshrc
alias kb='knowledgebeast'
alias kbq='knowledgebeast query'
alias kba='knowledgebeast add'
alias kbs='knowledgebeast stats'
```

Usage:
```bash
kb query "machine learning"
kbq "neural networks" -n 10
kbs
```

### 2. Default Data Directory

```bash
# Set default data directory
export KB_DATA_DIR=./my-kb

# Now you can omit --data-dir
knowledgebeast query "test"
```

### 3. Pipe Results

```bash
# Save results
knowledgebeast query "ML" > results.txt

# Count results
knowledgebeast query "AI" | grep "Result" | wc -l

# Filter results
knowledgebeast query "deep learning" | grep "paper"
```

### 4. Background Server

```bash
# Start server in background
knowledgebeast serve --host 0.0.0.0 --port 8000 &

# Save PID
echo $! > kb-server.pid

# Stop server later
kill $(cat kb-server.pid)
```

### 5. Systemd Service

```ini
# /etc/systemd/system/knowledgebeast.service
[Unit]
Description=KnowledgeBeast API Server
After=network.target

[Service]
Type=simple
User=knowledgebeast
WorkingDirectory=/var/lib/knowledgebeast
ExecStart=/usr/local/bin/knowledgebeast serve --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl enable knowledgebeast
sudo systemctl start knowledgebeast
sudo systemctl status knowledgebeast
```

## Environment Variables

```bash
# Knowledge directories
export KB_KNOWLEDGE_DIRS="./docs,./papers"

# Cache settings
export KB_CACHE_FILE="./.cache/kb.pkl"
export KB_MAX_CACHE_SIZE=200

# Heartbeat interval
export KB_HEARTBEAT_INTERVAL=300

# Auto-warm
export KB_AUTO_WARM=true
```

## Troubleshooting

### Command not found

```bash
# Check installation
pip show knowledgebeast

# Reinstall
pip install --force-reinstall knowledgebeast

# Check PATH
which knowledgebeast
```

### Permission denied

```bash
# Make sure data directory is writable
chmod -R u+w ./data

# Or run with appropriate permissions
sudo knowledgebeast init /var/lib/knowledgebeast
```

### Slow queries

```bash
# Warm cache
knowledgebeast warm

# Reduce n_results
knowledgebeast query "test" -n 3

# Check stats
knowledgebeast stats
```

## Next Steps

- [Python API Guide](python-api.md)
- [REST API Guide](rest-api.md)
- [Configuration Guide](../getting-started/configuration.md)
