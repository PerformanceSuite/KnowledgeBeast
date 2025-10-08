# end-session - Comprehensive Session Cleanup & Documentation

Ensures proper session closure with complete documentation and cleanup.

## Checklist (Execute in Order)

### 1. ✅ Session Documentation
- [ ] Update `.claude/memory.md` with session summary
  - What was accomplished
  - Critical findings/issues discovered
  - Current status (honest assessment)
  - Next steps required
- [ ] Include metrics and test results
- [ ] Document any breaking changes or issues

### 2. ✅ Kill Background Processes
**CRITICAL: Do this BEFORE committing to prevent port conflicts**
```bash
# Kill any background processes
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true

# Check for any running Python processes
ps aux | grep python | grep -v grep
```

### 3. ✅ Run Cleanup Script
```bash
# If cleanup.sh exists, run it
if [ -f cleanup.sh ]; then
  ./cleanup.sh
fi

# Or run manual cleanup
# - Update timestamps
# - Remove temp files
# - Format code if needed
```

### 4. ✅ Commit Documentation Changes
```bash
# Stage memory and documentation
git add .claude/memory.md
git add .claude/*.md

# Commit with proper format
git commit -m "docs: Update session memory and documentation

- Session summary: [brief description]
- [Key finding 1]
- [Key finding 2]

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### 5. ✅ Commit Code Changes (if any)
```bash
# Stage all changes
git add .

# Review changes
git status
git diff --cached

# Commit with descriptive message
git commit -m "[type]: [description]

[Detailed explanation]

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

**Commit Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `test`: Adding/fixing tests
- `refactor`: Code refactoring
- `chore`: Maintenance tasks
- `perf`: Performance improvements

### 6. ✅ Push Changes
```bash
# Push to origin (use --no-verify if hooks timeout)
git push origin main --no-verify

# Or if on feature branch
git push origin <branch-name> --no-verify
```

### 7. ✅ Create PR (if on feature branch)
```bash
# Only if NOT on main branch
git branch --show-current

# If on feature branch
gh pr create --title "[Title]" --body "$(cat <<'EOF'
## Summary
[What this PR does]

## Changes
- [Change 1]
- [Change 2]

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] E2E tests pass (if applicable)

## Checklist
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] No breaking changes (or documented)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

### 8. ✅ Final Verification
```bash
# Verify everything is pushed
git status

# Verify remote is up to date
git fetch origin
git log origin/main..HEAD  # Should be empty if pushed

# Check for uncommitted changes
git diff  # Should be empty

# Verify no background processes
lsof -ti:8000  # Should return nothing
```

## Pre-Flight Checks

**Before starting end-session:**

1. All background processes killed?
2. All changes committed?
3. Memory.md updated with accurate status?
4. Cleanup script run?
5. Ready to push?

## Post-Session Checklist

- [ ] Memory.md reflects current state
- [ ] All commits pushed to remote
- [ ] No uncommitted changes remain
- [ ] No background processes running
- [ ] PR created if on feature branch
- [ ] Session documented honestly and completely

## Common Issues

### Issue: "Cannot push - pre-push hook times out"
**Solution**: Use `git push --no-verify`

### Issue: "Port 8000 already in use"
**Solution**: Kill processes BEFORE committing
```bash
lsof -ti:8000 | xargs kill -9
```

### Issue: "Uncommitted changes after cleanup"
**Solution**: Commit cleanup changes separately
```bash
git add .
git commit -m "chore: Run cleanup script"
```

## Example Full Session Close

```bash
# 1. Kill background processes
lsof -ti:8000 | xargs kill -9 2>/dev/null

# 2. Run cleanup
./cleanup.sh

# 3. Stage and review
git add .
git status

# 4. Commit documentation
git commit -m "docs: Update memory with E2E testing findings

- Discovered API v2 routes missing
- Retracted v2.0.0, tagged v2.0.0-beta.1
- Created production readiness checklist
- Documented critical gaps

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# 5. Push
git push origin main --no-verify

# 6. Verify
git status
lsof -ti:8000
```

## Notes

- **Always update memory.md** - It's the project's source of truth
- **Be honest** - Document failures and gaps, not just successes
- **Kill processes first** - Prevents port conflicts
- **Use --no-verify carefully** - Only when hooks timeout
- **Verify before leaving** - Check git status and no background processes

---

**Remember**: Good documentation is more valuable than perfect code.
Document what you learned, what failed, and what's next.
