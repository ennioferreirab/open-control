# Story 19.1: Legacy Removal, Guardrails and Regression Hardening

Status: ready-for-dev

## Story

As a **maintainer**,
I want legacy paths removed and architecture rules enforced,
so that the codebase does not regress back to the current shape.

## Acceptance Criteria

### AC1: Legacy Code Removed

**Given** the refactoring waves 1-4 are complete
**When** this cleanup runs
**Then** all the following are removed:
- Duplicate helpers that were kept for backward compatibility
- Transitional adapters that bridged old and new code
- Dead code paths that are no longer reachable
- Compatibility shims in bridge, gateway, executor, and dispatcher
**And** no functional behavior changes

### AC2: Python Import Guardrails

**Given** the architectural rule: "services cannot import gateway"
**When** guardrails are in place
**Then** a test or lint rule enforces: no `mc.*` module imports from `mc.gateway` except `boot.py`
**And** this runs in CI and fails the build on violation
**And** the rule covers all modules in `mc/`

### AC3: Frontend Import Guardrails

**Given** feature components should not import Convex hooks directly
**When** guardrails are in place
**Then** a test or lint rule enforces: feature components in specific directories do not import `useQuery`/`useMutation` directly
**And** they must use feature hooks instead
**And** this runs in CI

### AC4: Architecture Documentation

**Given** the refactoring is complete
**When** documentation is updated
**Then** `docs/ARCHITECTURE.md` is created or updated with:
- Module boundary diagram (gateway → services → infrastructure)
- Data flow diagram (bridge repositories → engine → workers)
- Frontend architecture (read models → feature hooks → components)
**And** a short ADR (Architecture Decision Record) documents the refactoring rationale

### AC5: Full Regression Suite

**Given** all waves are complete
**When** the final regression runs
**Then** ALL tests pass:
- Python unit and integration tests
- TypeScript/Convex tests
- Frontend component tests
**And** the following sensitive scenarios are verified:
- Universal mentions
- Human task lifecycle
- Board operations
- File operations
- Plan editing
- Provider error handling
- Retry/crash recovery

## Tasks / Subtasks

- [ ] **Task 1: Identify and remove legacy code** (AC: #1)
  - [ ] 1.1 Grep for TODO/DEPRECATED/COMPAT markers added during refactoring
  - [ ] 1.2 Identify dead code paths with coverage analysis or manual review
  - [ ] 1.3 Remove duplicate helpers
  - [ ] 1.4 Remove transitional adapters
  - [ ] 1.5 Remove compatibility shims
  - [ ] 1.6 Run full test suite after each removal batch

- [ ] **Task 2: Add Python import guardrails** (AC: #2)
  - [ ] 2.1 Create test in `tests/mc/test_architecture.py` that scans for prohibited imports
  - [ ] 2.2 Rule: no `import mc.gateway` or `from mc.gateway` in any mc/ module except boot.py
  - [ ] 2.3 Rule: no direct executor↔dispatcher imports
  - [ ] 2.4 Verify test fails on violation and passes on clean code

- [ ] **Task 3: Add frontend import guardrails** (AC: #3)
  - [ ] 3.1 Create lint rule or test that checks feature components
  - [ ] 3.2 Rule: feature components must use hooks, not direct useQuery/useMutation
  - [ ] 3.3 Document exceptions (if any)

- [ ] **Task 4: Update architecture documentation** (AC: #4)
  - [ ] 4.1 Create or update `docs/ARCHITECTURE.md`
  - [ ] 4.2 Add module boundary diagram
  - [ ] 4.3 Add data flow diagram
  - [ ] 4.4 Write short ADR for the refactoring

- [ ] **Task 5: Full regression verification** (AC: #5)
  - [ ] 5.1 Run `uv run pytest tests/` -- full Python suite
  - [ ] 5.2 Run Convex/TypeScript test suite
  - [ ] 5.3 Run frontend tests
  - [ ] 5.4 Manually verify sensitive scenarios documented in test plan
  - [ ] 5.5 Document results

## Dev Notes

### Architecture Patterns

**This story only enters after 18.3 and 18.4 are green.** It is the final cleanup pass.

**Guardrail Tests:** Architecture tests that scan source code for prohibited patterns. These are cheap to run and catch regressions immediately.

```python
# Example architecture test
def test_no_gateway_imports_in_services():
    """Services must not import from mc.gateway."""
    for path in Path("mc").rglob("*.py"):
        if path.name == "gateway.py" or "test" in str(path):
            continue
        content = path.read_text()
        assert "from mc.gateway" not in content, f"{path} imports mc.gateway"
        assert "import mc.gateway" not in content, f"{path} imports mc.gateway"
```

**Key Files to Read First:**
- All modules modified in waves 1-4
- `boot.py` -- the only allowed gateway importer
- Existing test suite structure

### Project Structure Notes

**Files to CREATE:**
- `tests/mc/test_architecture.py`
- `docs/ARCHITECTURE.md`
- Frontend lint rule or test file

**Files to MODIFY/DELETE:**
- Various files across mc/ and dashboard/ -- removing legacy code

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log
