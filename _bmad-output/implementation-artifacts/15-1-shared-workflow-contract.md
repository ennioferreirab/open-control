# Story 15.1: Shared Workflow Contract

Status: ready-for-dev

## Story

As a **platform maintainer**,
I want one versioned workflow spec for Python and TypeScript,
so that task and step behavior cannot drift.

## Acceptance Criteria

### AC1: Canonical Workflow Spec JSON

**Given** the need for a single source of truth for workflow behavior
**When** a new `shared/workflow/workflow_spec.json` file is created
**Then** it defines:
- All task statuses: `inbox`, `assigned`, `in_progress`, `review`, `done`, `retrying`, `crashed`, `waiting_human`
- All step statuses with their valid transitions
- Universal transitions (pause/resume)
- Event mappings (what events trigger which transitions)
- Thread message types
- Action flags (mention-safe states, etc.)
**And** the schema is self-documenting with clear field names

### AC2: Python Adapter

**Given** the canonical spec exists at `shared/workflow/workflow_spec.json`
**When** Python code needs to validate transitions or check statuses
**Then** an adapter in `mc/domain/workflow_contract.py` loads and exposes the spec
**And** it provides helper functions: `is_valid_transition(from_status, to_status)`, `get_allowed_transitions(status)`, `is_mention_safe(status)`, `get_universal_transitions()`
**And** it replaces any hardcoded transition maps currently in `mc/state_machine.py`

### AC3: TypeScript/Convex Adapter

**Given** the canonical spec exists at `shared/workflow/workflow_spec.json`
**When** Convex code needs to validate transitions or check statuses
**Then** an adapter in `dashboard/convex/lib/workflowContract.ts` loads and exposes the spec
**And** it provides equivalent helper functions to the Python adapter
**And** `dashboard/tsconfig.json` supports `resolveJsonModule` for importing the JSON spec
**And** Convex's `tsconfig.json` is aligned to also support the JSON import

### AC4: Parity Tests

**Given** both adapters exist
**When** parity tests are run
**Then** they verify Python and TypeScript adapters produce identical results for:
- All status transitions (inbox, assigned, in_progress, review, done, retrying, crashed, waiting_human)
- Universal transitions (pause/resume)
- Mention-safe state checks
- Event-to-transition mappings
**And** no hardcoded transition maps remain in `mc/state_machine.py` or Convex mutation files

### AC5: No Behavior Change

**Given** this is a structural refactor only
**When** all adapters and tests are in place
**Then** no visible behavior changes for end users
**And** existing mutations continue to work identically
**And** only validation helpers are migrated in this story (mutations stay intact)

## Tasks / Subtasks

- [ ] **Task 1: Create canonical workflow spec** (AC: #1)
  - [ ] 1.1 Create `shared/workflow/` directory structure
  - [ ] 1.2 Analyze current `mc/state_machine.py` to extract all task statuses, step statuses, valid transitions, universal transitions
  - [ ] 1.3 Analyze Convex files (`dashboard/convex/tasks.ts`, `dashboard/convex/steps.ts`) to extract their hardcoded transition maps
  - [ ] 1.4 Reconcile any differences between Python and Convex transition maps
  - [ ] 1.5 Create `shared/workflow/workflow_spec.json` with complete spec

- [ ] **Task 2: Create Python adapter** (AC: #2)
  - [ ] 2.1 Create `mc/domain/` package with `__init__.py`
  - [ ] 2.2 Create `mc/domain/workflow_contract.py` that loads JSON spec
  - [ ] 2.3 Implement helper functions: `is_valid_transition()`, `get_allowed_transitions()`, `is_mention_safe()`, `get_universal_transitions()`
  - [ ] 2.4 Write unit tests for all helpers in `tests/mc/domain/test_workflow_contract.py`
  - [ ] 2.5 Migrate `mc/state_machine.py` validation logic to use the new contract (keep state_machine.py as a thin wrapper for backward compat)

- [ ] **Task 3: Create TypeScript/Convex adapter** (AC: #3)
  - [ ] 3.1 Verify/update `dashboard/tsconfig.json` for `resolveJsonModule`
  - [ ] 3.2 Verify/update `dashboard/convex/tsconfig.json` for `resolveJsonModule`
  - [ ] 3.3 Create `dashboard/convex/lib/workflowContract.ts` that imports and exposes the spec
  - [ ] 3.4 Implement equivalent helper functions: `isValidTransition()`, `getAllowedTransitions()`, `isMentionSafe()`, `getUniversalTransitions()`
  - [ ] 3.5 Write tests for the TypeScript adapter

- [ ] **Task 4: Parity tests and migration** (AC: #4, #5)
  - [ ] 4.1 Create Python parity tests that verify spec completeness against known states
  - [ ] 4.2 Create TypeScript parity tests that verify spec completeness
  - [ ] 4.3 Verify no hardcoded transition maps remain in `mc/state_machine.py` (only delegations to contract)
  - [ ] 4.4 Verify Convex validation helpers can be consumed (but don't change mutations yet)
  - [ ] 4.5 Run full test suite to confirm no regressions

## Dev Notes

### Architecture Patterns

**Shared Contract Pattern:**
The `shared/workflow/workflow_spec.json` is the single source of truth. Both Python and TypeScript adapters are thin loaders that expose typed helpers. No business logic lives in the JSON -- it's pure data describing valid states and transitions.

**Migration Strategy:**
This story ONLY migrates validation helpers. The actual mutations in `tasks.ts`, `steps.ts`, and the Python executor/dispatcher remain untouched. They will consume the new contract in later stories (16.x, 17.x).

**Key Files to Read First:**
- `mc/state_machine.py` -- current Python state machine with hardcoded transitions
- `dashboard/convex/tasks.ts` -- Convex task mutations with status validation
- `dashboard/convex/steps.ts` -- Convex step mutations with status validation
- `mc/types.py` -- type definitions that may reference statuses

**Important: `shared/` directory is NEW.** This is the first file in the shared contract layer between Python and TypeScript. It must be accessible from both `mc/` (Python) and `dashboard/convex/` (TypeScript).

**Bridge Key Convention:**
Convex uses camelCase, Python uses snake_case. The JSON spec should use camelCase (as the canonical form) and the Python adapter should convert to snake_case internally.

### Project Structure Notes

**Files to CREATE:**
- `shared/workflow/workflow_spec.json`
- `mc/domain/__init__.py`
- `mc/domain/workflow_contract.py`
- `dashboard/convex/lib/workflowContract.ts`
- `tests/mc/domain/__init__.py`
- `tests/mc/domain/test_workflow_contract.py`

**Files to MODIFY:**
- `mc/state_machine.py` -- migrate to use contract
- `dashboard/tsconfig.json` -- ensure resolveJsonModule
- `dashboard/convex/tsconfig.json` -- ensure resolveJsonModule

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log
