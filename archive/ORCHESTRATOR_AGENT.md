# Orchestrator Agent - Week 1 Critical Fixes Coordination

## Mission
Coordinate 8 parallel agents working on critical security and performance fixes. Review all PRs, enforce merge order, and ensure zero conflicts.

## Agent Assignments & Dependencies

### Merge Order Priority (Based on Dependencies)

**Priority 1 - Independent (Can merge in any order):**
1. **Agent 1**: API Authentication - `feature/api-authentication`
2. **Agent 2**: CORS Configuration - `feature/fix-cors`
3. **Agent 3**: Remove Pickle - `feature/remove-pickle`
4. **Agent 7**: Remove Duplicate Class - `feature/remove-duplicate-kb`

**Priority 2 - Depends on Priority 1:**
5. **Agent 4**: LRU Cache Thread Safety - `feature/lru-thread-safety`
6. **Agent 5**: Query Lock Contention - `feature/fix-lock-contention`
   - Depends on: Agent 4 (LRU cache must be thread-safe first)

**Priority 3 - Depends on Priority 2:**
7. **Agent 6**: Async/Sync Blocking - `feature/fix-async-blocking`
   - Depends on: Agent 5 (query optimization must be complete)

**Priority 4 - Depends on All Above:**
8. **Agent 8**: Security Tests - `feature/security-tests`
   - Depends on: All fixes complete (tests validate all changes)

## Agent Task Specifications

### Agent 1: API Authentication
- **Branch**: `feature/api-authentication`
- **Files**: `knowledgebeast/api/routes.py`, `knowledgebeast/api/middleware.py`, `.env.example`
- **Tasks**:
  1. Add `fastapi.security.APIKeyHeader` dependency
  2. Create `verify_api_key()` dependency function
  3. Add `dependencies=[Depends(verify_api_key)]` to all 12 routes
  4. Add `KB_API_KEY` to environment config
  5. Update `.env.example` with API key documentation
  6. Update API documentation with authentication requirements
- **Tests Required**: Test protected endpoints, test invalid keys, test missing keys
- **Conflicts**: None (independent)

### Agent 2: CORS Configuration
- **Branch**: `feature/fix-cors`
- **Files**: `knowledgebeast/api/app.py`, `.env.example`
- **Tasks**:
  1. Change `allow_origins=["*"]` to environment-based list
  2. Add `KB_ALLOWED_ORIGINS` environment variable
  3. Restrict `allow_methods` to `["GET", "POST"]`
  4. Update security documentation
- **Tests Required**: Test CORS headers, test origin validation
- **Conflicts**: None (independent)

### Agent 3: Remove Pickle Deserialization
- **Branch**: `feature/remove-pickle`
- **Files**: `knowledgebeast/core/engine.py` (line 240)
- **Tasks**:
  1. Remove pickle fallback in `_load_cache()`
  2. Remove `import pickle` statement
  3. Update cache format documentation
  4. Add migration notes for existing pickle caches
- **Tests Required**: Test JSON cache loading, test graceful failure for missing cache
- **Conflicts**: None (independent)

### Agent 4: LRU Cache Thread Safety
- **Branch**: `feature/lru-thread-safety`
- **Files**: `knowledgebeast/core/cache.py`
- **Tasks**:
  1. Add `import threading` to cache.py
  2. Add `self._lock = threading.Lock()` to `__init__`
  3. Wrap all `get()`, `put()`, `clear()`, `stats()` methods with `with self._lock:`
  4. Update docstrings to document thread safety
  5. Update CLAUDE.md with thread safety patterns
- **Tests Required**: 100 concurrent cache operations, race condition tests, capacity invariant tests
- **Conflicts**: None (independent)

### Agent 5: Query Lock Contention Fix
- **Branch**: `feature/fix-lock-contention`
- **Files**: `knowledgebeast/core/engine.py` (query method, lines 480-524)
- **Tasks**:
  1. Implement snapshot pattern for index access
  2. Minimize lock scope (4 separate small locks instead of 1 long lock)
  3. Move query processing outside lock
  4. Return deep copies of documents
  5. Update performance documentation
- **Tests Required**: Concurrent query throughput test, data consistency test, performance benchmark
- **Conflicts**: **DEPENDS ON Agent 4** (cache must be thread-safe first)

### Agent 6: Fix Async/Sync Blocking
- **Branch**: `feature/fix-async-blocking`
- **Files**: `knowledgebeast/api/routes.py`
- **Tasks**:
  1. Add `ThreadPoolExecutor` at module level
  2. Convert blocking calls to `await run_in_executor()`
  3. Update all async route handlers
  4. Add executor shutdown in app lifecycle
  5. Update API performance documentation
- **Tests Required**: API throughput test, latency test, executor cleanup test
- **Conflicts**: **DEPENDS ON Agent 5** (query optimization must be complete)

### Agent 7: Remove Duplicate KnowledgeBase Class
- **Branch**: `feature/remove-duplicate-kb`
- **Files**: `knowledgebeast/core/knowledge_base.py` (delete or rename)
- **Tasks**:
  1. Verify `knowledgebeast/core/engine.py` is the canonical implementation
  2. Delete `knowledgebeast/core/knowledge_base.py` stub
  3. Check for any imports referencing deleted file
  4. Update documentation references
- **Tests Required**: Import test, ensure no broken references
- **Conflicts**: None (independent)

### Agent 8: Security Tests
- **Branch**: `feature/security-tests`
- **Files**: `tests/security/test_injection.py`, `tests/security/test_validation.py`, `tests/security/test_headers.py`
- **Tasks**:
  1. Create `tests/security/` directory
  2. Add SQL injection tests
  3. Add XSS tests
  4. Add path traversal tests
  5. Add command injection tests
  6. Add security header validation tests
  7. Add CORS validation tests
  8. Add authentication tests
  9. Target: 50+ security tests
- **Tests Required**: All 50+ security tests must pass
- **Conflicts**: **DEPENDS ON Agents 1-7** (tests validate all fixes)

## Merge Strategy

### Phase 1: Independent Fixes (Parallel)
```bash
# These can be merged in any order
git merge feature/api-authentication
git merge feature/fix-cors
git merge feature/remove-pickle
git merge feature/remove-duplicate-kb
```

### Phase 2: Thread Safety (Sequential)
```bash
# Must merge in this order
git merge feature/lru-thread-safety      # First: Make cache thread-safe
git merge feature/fix-lock-contention    # Then: Optimize query locks
```

### Phase 3: Async Optimization
```bash
git merge feature/fix-async-blocking     # After all sync fixes
```

### Phase 4: Validation
```bash
git merge feature/security-tests         # Final: Validate everything
```

## Autonomous Workflow Protocol

```
PHASE 1 - Launch Independent Agents (Parallel):
  1. Launch Agent 1, 2, 3, 7 simultaneously
  2. Each agent creates PR when ready
  3. Each agent runs /review
  4. Orchestrator monitors PR status
  5. Merge PRs as they reach 10/10 score

PHASE 2 - Launch Thread Safety Agents (Sequential):
  WHEN Phase 1 complete:
    1. Launch Agent 4 (LRU cache)
    2. Agent 4 creates PR, runs /review
    3. WHEN Agent 4 merged:
       Launch Agent 5 (query locks)
    4. Agent 5 creates PR, runs /review

PHASE 3 - Launch Async Agent:
  WHEN Agent 5 merged:
    1. Launch Agent 6 (async/sync)
    2. Agent 6 creates PR, runs /review

PHASE 4 - Launch Test Agent:
  WHEN Agents 1-7 all merged:
    1. Launch Agent 8 (security tests)
    2. Agent 8 creates PR, runs /review
    3. Final validation

FOR EACH PR:
  WHILE review_score < 10:
    1. Run /review on PR
    2. If issues found, agent fixes automatically
    3. Re-run /review

  WHEN review_score == 10:
    1. Orchestrator presents to human for final approval
    2. Human executes merge
```

## Success Criteria

### After All Merges Complete:
- [ ] All 8 PRs merged to main
- [ ] Zero merge conflicts
- [ ] All existing tests pass
- [ ] 50+ new security tests pass
- [ ] Performance benchmarks show improvement
- [ ] No security vulnerabilities remaining

### Performance Targets:
- [ ] Query P99 latency < 100ms
- [ ] Concurrent throughput improved 5-10x
- [ ] Cache hit latency < 10ms
- [ ] Zero data corruption in stress tests

### Security Targets:
- [ ] 100% API endpoints authenticated
- [ ] CORS restricted to specific origins
- [ ] No pickle deserialization
- [ ] Security headers enabled
- [ ] 50+ security tests passing

---

**Orchestrator Status**: READY TO LAUNCH
**Mode**: Autonomous coordination with human final approval
**Next Action**: Create git worktrees and launch Phase 1 agents
**Last Updated**: 2025-10-06
