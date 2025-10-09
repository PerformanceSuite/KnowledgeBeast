# MCP Server Implementation - 3 Parallel Agents

## Overview

Build a native MCP server for KnowledgeBeast using 3 parallel autonomous agents.

**Timeline:** 8 hours wall-clock (18h sequential)
**Strategy:** Git worktrees for parallel development
**Target:** Production-ready MCP server with full Claude Code integration

---

## Agent 1: MCP Server Core

**Branch:** `feature/mcp-server-core`
**Worktree:** `.worktrees/mcp-server-core`
**Effort:** 6-8 hours
**Focus:** Server infrastructure and protocol implementation

### Tasks

1. **Implement `knowledgebeast/mcp/server.py`**
   - MCP stdio protocol handler
   - Tool registration and dispatch
   - Server lifecycle (initialize, shutdown)
   - Error handling and logging
   - Use `mcp` package (https://github.com/modelcontextprotocol/python-sdk)

2. **Server Features**
   - List tools (12 tools total)
   - Execute tool calls
   - Handle concurrent requests
   - Graceful error recovery

3. **CLI Integration**
   - Add `knowledgebeast mcp-server` command to `knowledgebeast/cli.py`
   - Support `--projects-db`, `--chroma-path`, `--log-level` flags
   - Add to main CLI help

### Deliverables

- `knowledgebeast/mcp/server.py` (200-300 lines)
- Updated `knowledgebeast/cli.py` with `mcp-server` command
- MCP protocol compliance (stdio transport)
- 5 tests for server lifecycle

### Dependencies

- `mcp` package already in `pyproject.toml`
- Existing `KnowledgeBeastTools` class
- Existing `MCPConfig`

### Testing

```bash
# Manual test
knowledgebeast mcp-server

# Should respond to MCP initialize/list_tools/call_tool
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | knowledgebeast mcp-server
```

---

## Agent 2: Advanced Tools + Features

**Branch:** `feature/mcp-advanced-tools`
**Worktree:** `.worktrees/mcp-advanced-tools`
**Effort:** 5-7 hours
**Focus:** Additional tools and production features

### Tasks

1. **Add Advanced Tools to `knowledgebeast/mcp/tools.py`**
   - `kb_export_project` - Export project to ZIP
   - `kb_import_project` - Import project from ZIP
   - `kb_project_health` - Get project health status
   - `kb_batch_ingest` - Ingest multiple files
   - `kb_delete_document` - Remove document from project

2. **Error Handling Enhancement**
   - Validation for all tool inputs
   - Structured error responses
   - Timeout handling
   - Resource cleanup on errors

3. **Performance Optimization**
   - Connection pooling validation
   - Lazy loading for large projects
   - Memory-efficient streaming for large documents
   - Batch operation support

### Deliverables

- 5 new tools added to `tools.py`
- Comprehensive error handling
- Input validation on all tools
- 10 tests for advanced tools

### Dependencies

- Existing `ProjectManager` with export/import
- Existing health monitoring system
- ChromaDB connection pooling

### Testing

```python
# Test export/import
await tools.kb_export_project("proj_123", output_path="/tmp/backup.zip")
await tools.kb_import_project(zip_path="/tmp/backup.zip")

# Test health
await tools.kb_project_health("proj_123")  # Should return health status
```

---

## Agent 3: Testing + Integration

**Branch:** `feature/mcp-testing-docs`
**Worktree:** `.worktrees/mcp-testing-docs`
**Effort:** 4-6 hours
**Focus:** Testing, documentation, Claude Code integration

### Tasks

1. **Create Test Suite `tests/mcp/test_mcp_tools.py`**
   - Test all 12 MCP tools
   - Test error handling
   - Test concurrent requests
   - Mock ChromaDB for fast tests
   - 20+ tests (100% coverage)

2. **Create Integration Tests `tests/mcp/test_mcp_integration.py`**
   - Full workflow tests (create project → ingest → search)
   - Multi-project isolation
   - Large document handling
   - Performance benchmarks
   - 10+ integration tests

3. **Create Claude Code Integration Guide `docs/mcp/CLAUDE_CODE_SETUP.md`**
   - Installation instructions
   - Claude Code configuration (claude_desktop_config.json)
   - Example workflows
   - Troubleshooting guide

4. **Create Usage Examples `docs/mcp/EXAMPLES.md`**
   - Basic search examples
   - Document ingestion patterns
   - Multi-project workflows
   - Advanced features (export/import, health)

### Deliverables

- `tests/mcp/test_mcp_tools.py` (20+ tests)
- `tests/mcp/test_mcp_integration.py` (10+ tests)
- `docs/mcp/CLAUDE_CODE_SETUP.md` (comprehensive setup guide)
- `docs/mcp/EXAMPLES.md` (usage examples)
- `README.md` update with MCP section

### Dependencies

- Completed Agent 1 (server implementation)
- Completed Agent 2 (advanced tools)
- pytest, pytest-asyncio for testing

### Testing

```bash
# Run all MCP tests
pytest tests/mcp/ -v

# Should see 30+ tests passing (100%)
```

---

## Coordination & Merge Strategy

### File Ownership (No Conflicts)

**Agent 1 Files:**
- `knowledgebeast/mcp/server.py` (NEW)
- `knowledgebeast/cli.py` (MODIFY - add mcp-server command)
- `tests/mcp/test_server.py` (NEW)

**Agent 2 Files:**
- `knowledgebeast/mcp/tools.py` (MODIFY - add 5 new tools)
- `knowledgebeast/mcp/validation.py` (NEW)
- `tests/mcp/test_advanced_tools.py` (NEW)

**Agent 3 Files:**
- `tests/mcp/test_mcp_tools.py` (NEW)
- `tests/mcp/test_mcp_integration.py` (NEW)
- `docs/mcp/CLAUDE_CODE_SETUP.md` (NEW)
- `docs/mcp/EXAMPLES.md` (NEW)
- `README.md` (MODIFY - add MCP section)

**Potential Conflicts:**
- `knowledgebeast/mcp/tools.py` - Agent 2 adds new tools
  - Resolution: Merge sequentially (Agent 1 → Agent 2 → Agent 3)
- `knowledgebeast/cli.py` - Agent 1 modifies
  - Resolution: Agent 1 completes first, others rebase

### Merge Order

1. **Agent 1 (Core)** merges first → PR #53
2. **Agent 2 (Tools)** rebases on PR #53 → PR #54
3. **Agent 3 (Tests/Docs)** rebases on PR #54 → PR #55

---

## Success Criteria

### Agent 1 Success
- ✅ `knowledgebeast mcp-server` command works
- ✅ Responds to MCP protocol (initialize, list_tools, call_tool)
- ✅ All 12 tools registered and callable
- ✅ 5 server tests passing

### Agent 2 Success
- ✅ 5 new advanced tools implemented
- ✅ Input validation on all tools
- ✅ Error handling comprehensive
- ✅ 10 advanced tool tests passing

### Agent 3 Success
- ✅ 30+ tests passing (100% coverage)
- ✅ Claude Code setup guide complete
- ✅ Example workflows documented
- ✅ README.md updated with MCP section

### Overall Success
- ✅ All 3 PRs merged to main
- ✅ 40+ total tests passing
- ✅ MCP server production-ready
- ✅ Claude Code integration working
- ✅ Documentation complete

---

## MCP Tools Reference (12 Total)

### Knowledge Management (5 tools)
1. `kb_search` - Search knowledge base
2. `kb_ingest` - Add document
3. `kb_list_documents` - List project documents
4. `kb_batch_ingest` - Batch document ingestion (Agent 2)
5. `kb_delete_document` - Remove document (Agent 2)

### Project Management (5 tools)
6. `kb_list_projects` - List all projects
7. `kb_create_project` - Create new project
8. `kb_get_project_info` - Get project details
9. `kb_delete_project` - Delete project
10. `kb_project_health` - Health status (Agent 2)

### Advanced Operations (2 tools)
11. `kb_export_project` - Export to ZIP (Agent 2)
12. `kb_import_project` - Import from ZIP (Agent 2)

---

## Timeline

**Hour 0:** Launch all 3 agents in parallel
**Hour 1-6:** Agents working independently
**Hour 6:** Agent 3 likely completes (testing/docs)
**Hour 7:** Agent 2 likely completes (advanced tools)
**Hour 8:** Agent 1 completes (server core)
**Hour 9:** Sequential merging (Agent 1 → 2 → 3)
**Hour 10:** Final validation and release

**Total: ~10 hours wall-clock** (vs 18h sequential = 44% time savings)

---

## Launch Commands

```bash
# Create worktrees
git worktree add .worktrees/mcp-server-core -b feature/mcp-server-core
git worktree add .worktrees/mcp-advanced-tools -b feature/mcp-advanced-tools
git worktree add .worktrees/mcp-testing-docs -b feature/mcp-testing-docs

# Launch Agent 1
cd .worktrees/mcp-server-core
# [Agent 1 prompt]

# Launch Agent 2
cd .worktrees/mcp-advanced-tools
# [Agent 2 prompt]

# Launch Agent 3
cd .worktrees/mcp-testing-docs
# [Agent 3 prompt]
```

---

**Last Updated:** October 9, 2025
**Status:** Ready to launch
**Expected Completion:** October 9-10, 2025 (~10 hours)
