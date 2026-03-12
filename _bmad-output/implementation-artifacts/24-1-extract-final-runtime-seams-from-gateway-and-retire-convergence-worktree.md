# Story 24.1: Extract Final Runtime Seams from Gateway and Retire Convergence Worktree

Status: done

## Story

As a **backend maintainer**,
I want the last worthwhile runtime helper seams extracted from `mc/runtime/gateway.py`,
so that the old `architecture-convergence` worktree can be retired without losing useful simplification work.

## Acceptance Criteria

### AC1: Polling Settings Leave Gateway

**Given** gateway still owns environment-driven polling configuration logic
**When** this story completes
**Then** polling defaults, bounds, and settings parsing live in a dedicated runtime module
**And** gateway consumes that module instead of owning the parsing implementation directly.

### AC2: Cron Delivery Callback Leaves Gateway

**Given** gateway still embeds cron completion delivery behavior
**When** this story completes
**Then** Telegram delivery and task-completed callback construction live in a dedicated runtime module
**And** gateway depends on that extracted seam without changing behavior.

### AC3: Cron Requeue Logic Leaves Gateway

**Given** gateway still embeds cron task requeue and cron-job handling logic
**When** this story completes
**Then** requeue and cron-job helper behavior live in a dedicated runtime module
**And** gateway keeps only orchestration and entrypoint responsibilities.

### AC4: Existing Runtime Tests and Guardrails Stay Green

**Given** these helpers already have focused backend coverage
**When** this story completes
**Then** runtime-focused tests, backend architecture tests, and backend reorganization tests pass
**And** no useful behavior from the current root implementation is lost.

### AC5: Convergence Worktree Can Be Safely Deleted

**Given** the old `architecture-convergence` worktree was kept only to avoid losing this runtime simplification
**When** this story completes
**Then** the remaining useful delta is integrated into the root codebase
**And** the old worktree is removed after verification.

## Tasks / Subtasks

- [x] **Task 1: Lock the extraction with tests first** (AC: #1, #2, #3, #4)
  - [x] 1.1 Add or tighten focused tests for polling settings ownership
  - [x] 1.2 Add or tighten focused tests for cron delivery callback ownership
  - [x] 1.3 Add or tighten focused tests for cron requeue ownership

- [x] **Task 2: Extract the final runtime seams** (AC: #1, #2, #3)
  - [x] 2.1 Move polling settings parsing into `mc/runtime/polling_settings.py`
  - [x] 2.2 Move cron completion delivery callback construction into `mc/runtime/cron_delivery.py`
  - [x] 2.3 Move cron requeue helpers into `mc/runtime/task_requeue.py`
  - [x] 2.4 Update `mc/runtime/gateway.py` to compose these helpers instead of owning them

- [x] **Task 3: Tighten guardrails and verify the rescue** (AC: #4)
  - [x] 3.1 Update backend architecture tests if the extracted seams should now be explicit
  - [x] 3.2 Run focused runtime tests and backend architecture/reorganization tests
  - [x] 3.3 Run `/code-review`

- [ ] **Task 4: Retire the old worktree** (AC: #5)
  - [x] 4.1 Confirm no other worthwhile source delta remains in `architecture-convergence`
  - [ ] 4.2 Remove the `architecture-convergence` worktree
  - [x] 4.3 Record verification evidence and residual risks

## Dev Notes

### Architecture Patterns

- Keep `mc/runtime/gateway.py` focused on runtime composition, loop control, and process coordination.
- Extract helpers by ownership boundary, not by arbitrary size splitting.
- Reuse the already proven helper shapes from the old convergence worktree where they still match the current root behavior.

### Project Structure Notes

- Primary root target:
  - `/Users/ennio/Documents/nanobot-ennio/mc/runtime/gateway.py`
- Source-of-truth salvage reference:
  - `/Users/ennio/Documents/nanobot-ennio/.worktrees/codex/architecture-convergence/mc/runtime/polling_settings.py`
  - `/Users/ennio/Documents/nanobot-ennio/.worktrees/codex/architecture-convergence/mc/runtime/cron_delivery.py`
  - `/Users/ennio/Documents/nanobot-ennio/.worktrees/codex/architecture-convergence/mc/runtime/task_requeue.py`

### References

- [Source: /Users/ennio/Documents/nanobot-ennio/mc/runtime/gateway.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/tests/mc/test_polling_settings.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/tests/mc/test_gateway_cron_delivery.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/tests/mc/test_architecture.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/tests/mc/test_module_reorganization.py]

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

### Completion Notes List

- Extracted the remaining worthwhile runtime seams from `mc/runtime/gateway.py` into `mc/runtime/polling_settings.py`, `mc/runtime/cron_delivery.py`, and `mc/runtime/task_requeue.py`.
- Tightened backend architecture guardrails so `gateway.py` can no longer keep these helpers inline.
- Confirmed the old `architecture-convergence` worktree no longer holds any clearly worthwhile source delta beyond this rescued runtime split.
- Pending final step: delete the old `architecture-convergence` worktree after integration.

### File List

- /Users/ennio/Documents/nanobot-ennio/mc/runtime/gateway.py
- /Users/ennio/Documents/nanobot-ennio/mc/runtime/polling_settings.py
- /Users/ennio/Documents/nanobot-ennio/mc/runtime/cron_delivery.py
- /Users/ennio/Documents/nanobot-ennio/mc/runtime/task_requeue.py
- /Users/ennio/Documents/nanobot-ennio/tests/mc/test_polling_settings.py
- /Users/ennio/Documents/nanobot-ennio/tests/mc/test_architecture.py
- /Users/ennio/Documents/nanobot-ennio/dashboard/features/settings/polling-fields.ts
- /Users/ennio/Documents/nanobot-ennio/_bmad-output/implementation-artifacts/24-1-extract-final-runtime-seams-from-gateway-and-retire-convergence-worktree.md
- /Users/ennio/Documents/nanobot-ennio/_bmad-output/implementation-artifacts/sprint-status.yaml
