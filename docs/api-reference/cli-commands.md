# CLI Commands Reference

Complete reference for all KnowledgeBeast CLI commands.

## Global Options

- `--help`: Show help
- `--version`: Show version
- `-v, --verbose`: Verbose output

## Commands

### init

Initialize knowledge base.

```bash
knowledgebeast init [PATH] [--name NAME]
```

### ingest

Ingest single document.

```bash
knowledgebeast ingest FILE_PATH [--data-dir DIR]
```

### add

Add multiple documents.

```bash
knowledgebeast add PATH [-r] [--data-dir DIR]
```

### query

Query knowledge base.

```bash
knowledgebeast query QUERY [-n N] [--no-cache] [--data-dir DIR]
```

### stats

Show statistics.

```bash
knowledgebeast stats [--detailed] [--data-dir DIR]
```

### clear

Clear knowledge base.

```bash
knowledgebeast clear [--yes] [--data-dir DIR]
```

### clear-cache

Clear query cache.

```bash
knowledgebeast clear-cache [-y] [--data-dir DIR]
```

### warm

Warm cache.

```bash
knowledgebeast warm [--data-dir DIR]
```

### health

Health check.

```bash
knowledgebeast health [--data-dir DIR]
```

### heartbeat

Manage heartbeat.

```bash
knowledgebeast heartbeat {start|stop|status} [-i INTERVAL] [--data-dir DIR]
```

### serve

Start API server.

```bash
knowledgebeast serve [--host HOST] [--port PORT] [--reload]
```

### version

Show version info.

```bash
knowledgebeast version
```

For detailed usage, see [CLI Guide](../guides/cli-usage.md).
