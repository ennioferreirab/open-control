# Story 22.4: Split Hotspots and Add Versioned Functional Regression

Status: ready-for-dev

## Story

As a **maintainer**,
I want the largest remaining architectural hotspots reduced and key UI flows covered by versioned browser regression,
so that the codebase becomes easier to evolve and structural refactors stop depending on manual smoke only.

## Acceptance Criteria

### AC1: Remaining Hotspots Are Reduced

**Given** several modules still concentrate too much behavior
**When** this story completes
**Then** the highest-value hotspots are split into more cohesive modules
**And** responsibilities are documented by the resulting file boundaries.

### AC2: Refactor Targets Follow Clear Selection Criteria

**Given** not every large file should be split in the same story
**When** this story completes
**Then** the chosen targets are the files with the highest combination of size, responsibility overlap, and architectural centrality
**And** the decomposition preserves current behavior.

### AC3: Versioned Functional Regression Exists

**Given** architecture changes currently rely heavily on manual or ad hoc smoke
**When** this story completes
**Then** a committed Playwright-based regression path exists for the main dashboard journey
**And** it can be rerun as part of future refactor validation.

### AC4: Cross-Layer Quality Gates Stay Green

**Given** hotspot decomposition can create subtle integration regressions
**When** this story completes
**Then** backend and frontend test suites relevant to the touched flows pass
**And** the Playwright regression and architecture guardrails pass.

### AC5: Story Exit Gate Is Green

**Given** this story is the cleanup capstone for the new epic
**When** the story closes
**Then** `/code-review` is run
**And** verification evidence is recorded for hotspot tests, architecture tests, and Playwright regression.

## Tasks / Subtasks

- [ ] **Task 1: Select and pin hotspot targets** (AC: #1, #2)
  - [ ] 1.1 Rank large modules by size, centrality, and mixed responsibility
  - [ ] 1.2 Choose the most valuable split targets for this story
  - [ ] 1.3 Add or update focused tests before refactor where needed

- [ ] **Task 2: Decompose the selected hotspots** (AC: #1, #2, #4)
  - [ ] 2.1 Extract cohesive helpers or submodules from the selected backend hotspot files
  - [ ] 2.2 Extract cohesive hooks or subcomponents from the selected dashboard hotspot files
  - [ ] 2.3 Keep behavior stable and update imports to the new internal seams

- [ ] **Task 3: Add versioned Playwright regression** (AC: #3, #4)
  - [ ] 3.1 Create committed Playwright coverage for board load, task open, thread, execution plan, settings, and activity flows
  - [ ] 3.2 Document how to run the regression locally
  - [ ] 3.3 Ensure the regression is stable enough for future architecture work

- [ ] **Task 4: Run the capstone verification gate** (AC: #4, #5)
  - [ ] 4.1 Run focused backend and frontend tests for all touched hotspots
  - [ ] 4.2 Run architecture guardrails for backend and dashboard
  - [ ] 4.3 Run the committed Playwright regression
  - [ ] 4.4 Run `/code-review`
  - [ ] 4.5 Record verification evidence and residual risks

## Dev Notes

### Architecture Patterns

- Split by responsibility boundary, not by arbitrary line count.
- Prefer internal seams that reveal ownership, not “utils” buckets with mixed behavior.
- Browser regression should be part of the repository, not a one-off operator ritual.

### Project Structure Notes

- Likely candidates include large backend orchestrators/executors and large dashboard task/Convex modules, but select targets based on current root reality before editing.
- Keep Playwright assets and docs in a conventional location that future refactors can reuse.

### References

- [Source: /Users/ennio/Documents/nanobot-ennio/docs/ARCHITECTURE.md]
- [Source: /Users/ennio/Documents/nanobot-ennio/tests/mc/test_architecture.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/tests/architecture.test.ts]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
