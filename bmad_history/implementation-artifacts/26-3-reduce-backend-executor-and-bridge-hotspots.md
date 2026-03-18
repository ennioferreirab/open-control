# Story 26.3: Reduce Backend Executor and Bridge Hotspots

Status: ready-for-dev

## Story

As a **backend maintainer**,
I want the next cohesive seams extracted from `executor.py` and `bridge/__init__.py`,
so that orchestration and façade responsibilities are clearer and the biggest backend hotspots keep shrinking.

## Acceptance Criteria

### AC1: A Cohesive Seam Leaves `executor.py`

**Given** `mc/contexts/execution/executor.py` still concentrates too much orchestration logic
**When** this story completes
**Then** at least one cohesive responsibility cluster is extracted into an explicit owner module
**And** executor becomes thinner without changing behavior.

### AC2: A Cohesive Seam Leaves `bridge/__init__.py`

**Given** `mc/bridge/__init__.py` is still a large façade hotspot
**When** this story completes
**Then** at least one cohesive helper/facade cluster is extracted into a smaller internal owner
**And** the external bridge contract remains stable.

### AC3: Backend Guardrails and Tests Stay Green

**Given** these modules are core runtime infrastructure
**When** this story completes
**Then** backend architecture tests, focused executor/bridge tests, and full `tests/mc` verification pass.

## Tasks / Subtasks

- [ ] **Task 1: Lock the seams with tests first** (AC: #1, #2, #3)
  - [ ] 1.1 Add failing architecture assertions for the new extracted modules
  - [ ] 1.2 Confirm red before implementation

- [ ] **Task 2: Extract the next executor seam** (AC: #1)
  - [ ] 2.1 Move one cohesive executor cluster into an explicit owner module
  - [ ] 2.2 Preserve existing patch/test targets where useful during the transition

- [ ] **Task 3: Extract the next bridge seam** (AC: #2)
  - [ ] 3.1 Move one cohesive bridge helper/facade cluster into an explicit owner module
  - [ ] 3.2 Keep the public bridge contract stable

- [ ] **Task 4: Verify and review** (AC: #3)
  - [ ] 4.1 Run focused backend tests
  - [ ] 4.2 Run `uv run pytest tests/mc -q`
  - [ ] 4.3 Run `/code-review`

## Dev Notes

- Favor extractions that reduce cross-cutting responsibilities, not just file size.
- Preserve runtime behavior and existing public bridge usage.

## References

- [Source: /Users/ennio/Documents/nanobot-ennio/mc/contexts/execution/executor.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/mc/bridge/__init__.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/tests/mc/test_architecture.py]
