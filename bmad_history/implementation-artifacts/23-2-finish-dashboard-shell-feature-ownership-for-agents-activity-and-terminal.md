# Story 23.2: Finish Dashboard Shell Feature Ownership for Agents, Activity, and Terminal

Status: done

## Story

As a **frontend maintainer**,
I want the dashboard shell to use feature-owned modules for agents, activity, and terminal flows,
so that `DashboardLayout` stops acting as an indirect owner of those behaviors and the root component layer becomes thinner.

## Acceptance Criteria

### AC1: Agents, Activity, and Terminal Use Feature-Owned Entry Points

**Given** the dashboard shell still mixes shared shell concerns with workflow-specific owners
**When** this story completes
**Then** agents, activity, and terminal flows are composed through `dashboard/features/*`
**And** root component aliases for those flows are removed or reduced to truly shared shells only.

### AC2: Feature Hooks Own Convex and View-Model State

**Given** shell-level components should not directly own workflow data access
**When** this story completes
**Then** agents, activity, and terminal state is sourced from feature hooks
**And** `DashboardLayout` only coordinates layout-level composition.

### AC3: Root Shell Surface Becomes More Explicit

**Given** the root `dashboard/components/*` layer should stay curated
**When** this story completes
**Then** remaining root modules in this area are clearly shared or shell-level
**And** workflow ownership lives under `dashboard/features/agents`, `dashboard/features/activity`, and `dashboard/features/terminal`.

### AC4: Architecture Tests Capture the New Ownership

**Given** this story continues the selective convergence work
**When** this story completes
**Then** dashboard architecture tests forbid reintroduction of root aliases for these flows
**And** shell imports point to canonical feature paths.

### AC5: Story Exit Gate Is Green

**Given** this story changes the main dashboard shell
**When** the story closes
**Then** `npm run typecheck`, focused dashboard tests, `npm run test:architecture`, and Playwright regression pass
**And** `/code-review` is run
**And** verification evidence is recorded.

## Tasks / Subtasks

- [ ] **Task 1: Move shell ownership to features** (AC: #1, #2, #3)
  - [ ] 1.1 Introduce or complete feature-owned entry points for agents, activity, and terminal shell surfaces
  - [ ] 1.2 Extract feature hooks for data/mutation ownership where still missing
  - [ ] 1.3 Keep root shell modules only where they are genuinely cross-feature

- [ ] **Task 2: Rewire DashboardLayout** (AC: #1, #2, #4)
  - [ ] 2.1 Rewrite shell imports to canonical feature entry points
  - [ ] 2.2 Remove direct workflow ownership from `DashboardLayout`
  - [ ] 2.3 Preserve existing shell behavior and responsive layout

- [ ] **Task 3: Tighten architecture guardrails** (AC: #3, #4, #5)
  - [ ] 3.1 Update dashboard architecture tests to lock the new feature-owned paths
  - [ ] 3.2 Update focused shell tests for agents, activity, and terminal flows
  - [ ] 3.3 Run `/code-review`

- [ ] **Task 4: Run the story exit gate** (AC: #5)
  - [ ] 4.1 Run `npm run typecheck`
  - [ ] 4.2 Run focused shell tests and `npm run test:architecture`
  - [ ] 4.3 Run `npm run test:e2e`
  - [ ] 4.4 Record verification evidence and residual risks

## Dev Notes

### Architecture Patterns

- `DashboardLayout` is a shell, not a workflow owner.
- Feature hooks may encapsulate `convex/react`; feature components should remain view-oriented.
- Prefer explicit feature ownership over root aliases.

### Project Structure Notes

- Primary shell file: `/Users/ennio/Documents/nanobot-ennio/dashboard/components/DashboardLayout.tsx`
- Target owners live under:
  - `dashboard/features/agents/*`
  - `dashboard/features/activity/*`
  - `dashboard/features/terminal/*`
- Preserve shared primitives under `components/ui` and shared viewers/widgets as appropriate.

### References

- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/components/DashboardLayout.tsx]
- [Source: /Users/ennio/Documents/nanobot-ennio/dashboard/tests/architecture.test.ts]
- [Source: /Users/ennio/Documents/nanobot-ennio/docs/ARCHITECTURE.md]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
