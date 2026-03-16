# Squad Workflow Manual Editing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let users edit a published squad's workflow graph from the squad sheet and publish those changes back to the current Convex spec.

**Architecture:** Keep squad creation and squad editing as separate paths. The frontend edits a full local draft graph inside `SquadDetailSheet`, while a new Convex mutation updates the current `squadSpecs` and `workflowSpecs` in place so future workflow launches use the edited graph without changing existing task runs.

**Tech Stack:** Next.js, React, TypeScript, Convex, vitest, Testing Library, shadcn/ui

---

### Task 1: Add the failing backend mutation tests

**Files:**
- Modify: `dashboard/convex/squadSpecs.test.ts`
- Reference: `dashboard/convex/squadSpecs.ts`
- Reference: `dashboard/convex/lib/squadGraphPublisher.ts`

**Step 1: Write the failing test**

Add tests that assert:
- a new `updatePublishedGraph` mutation patches the current squad metadata
- existing workflow docs are updated in place
- removed workflows are cleaned up
- invalid step references reject the publish

**Step 2: Run test to verify it fails**

Run: `npm test -- convex/squadSpecs.test.ts`
Expected: FAIL because `updatePublishedGraph` does not exist yet.

**Step 3: Write minimal implementation**

Implement the new mutation contract and the minimal update logic needed for the tests.

**Step 4: Run test to verify it passes**

Run: `npm test -- convex/squadSpecs.test.ts`
Expected: PASS

### Task 2: Implement in-place squad/workflow publishing

**Files:**
- Modify: `dashboard/convex/squadSpecs.ts`
- Create or Modify: `dashboard/convex/lib/squadGraphUpdater.ts`
- Modify: `dashboard/convex/schema.ts` only if validation types need extension
- Test: `dashboard/convex/squadSpecs.test.ts`

**Step 1: Write the next failing test**

Add coverage for:
- default workflow id remains valid after publish
- workflow step `reviewSpecId`, `onReject`, and `dependsOn` values are persisted

**Step 2: Run test to verify it fails**

Run: `npm test -- convex/squadSpecs.test.ts`
Expected: FAIL on missing persistence/validation behavior.

**Step 3: Write minimal implementation**

Add a helper that:
- patches the current squad doc
- matches existing workflows by id/key
- updates existing workflow docs in place
- removes stale squad-owned workflows
- updates `defaultWorkflowSpecId`

**Step 4: Run test to verify it passes**

Run: `npm test -- convex/squadSpecs.test.ts`
Expected: PASS

### Task 3: Add the failing squad sheet editor tests

**Files:**
- Modify: `dashboard/features/agents/components/SquadDetailSheet.test.tsx`
- Reference: `dashboard/features/agents/components/SquadDetailSheet.tsx`
- Reference: `dashboard/features/agents/hooks/useSquadDetailData.ts`

**Step 1: Write the failing test**

Add tests that assert:
- edit mode can be entered from the squad sheet
- a user can change workflow step content locally
- `Publicar` is shown instead of a generic save action
- publish calls the new mutation with the edited graph

**Step 2: Run test to verify it fails**

Run: `npm test -- features/agents/components/SquadDetailSheet.test.tsx`
Expected: FAIL because the sheet is read-only today.

**Step 3: Write minimal implementation**

Add local draft state, edit mode, and publish wiring.

**Step 4: Run test to verify it passes**

Run: `npm test -- features/agents/components/SquadDetailSheet.test.tsx`
Expected: PASS

### Task 4: Build manual step editing in the squad sheet

**Files:**
- Modify: `dashboard/features/agents/components/SquadDetailSheet.tsx`
- Create: `dashboard/features/agents/components/SquadWorkflowEditor.tsx`
- Create: `dashboard/features/agents/components/SquadWorkflowStepEditor.tsx`
- Modify: `dashboard/features/agents/components/SquadDetailSheet.test.tsx`

**Step 1: Write the next failing test**

Add coverage for:
- adding a new step
- removing a step
- reordering steps
- editing `reviewSpecId`, `onReject`, `dependsOn`, and agent assignment
- rendering checkpoint steps in edit mode

**Step 2: Run test to verify it fails**

Run: `npm test -- features/agents/components/SquadDetailSheet.test.tsx`
Expected: FAIL on missing workflow editor interactions.

**Step 3: Write minimal implementation**

Introduce focused editor components and keep the state shape aligned with the publish payload.

**Step 4: Run test to verify it passes**

Run: `npm test -- features/agents/components/SquadDetailSheet.test.tsx`
Expected: PASS

### Task 5: Add agent navigation regression tests

**Files:**
- Modify: `dashboard/features/agents/components/SquadDetailSheet.test.tsx`
- Modify: `dashboard/features/agents/components/AgentSidebar.test.tsx`
- Modify: `dashboard/features/agents/components/SquadDetailSheet.tsx`
- Modify: `dashboard/features/agents/components/AgentSidebar.tsx` only if navigation plumbing changes

**Step 1: Write the failing test**

Add tests that assert:
- clicking an agent in the squad roster opens the corresponding agent panel/view
- clicking an assigned agent in a workflow step switches to the same agent context

**Step 2: Run test to verify it fails**

Run: `npm test -- features/agents/components/SquadDetailSheet.test.tsx features/agents/components/AgentSidebar.test.tsx`
Expected: FAIL until the navigation behavior is explicit.

**Step 3: Write minimal implementation**

Make squad-agent navigation deterministic and reuse the existing agent detail UI where possible.

**Step 4: Run test to verify it passes**

Run: `npm test -- features/agents/components/SquadDetailSheet.test.tsx features/agents/components/AgentSidebar.test.tsx`
Expected: PASS

### Task 6: Verify formatting, lint, and architecture guardrails

**Files:**
- Modify: touched dashboard files only
- Test: `dashboard/tests/architecture.test.ts`

**Step 1: Run file-scoped format check**

Run: `npm run format:file:check -- <touched-dashboard-paths>`
Expected: PASS

**Step 2: Run file-scoped lint**

Run: `npm run lint:file -- <touched-dashboard-paths>`
Expected: PASS

**Step 3: Run architecture guardrail**

Run: `npm run test:architecture`
Expected: PASS

**Step 4: Run targeted feature tests**

Run: `npm test -- features/agents/components/SquadDetailSheet.test.tsx features/agents/components/AgentSidebar.test.tsx convex/squadSpecs.test.ts`
Expected: PASS

Plan complete and saved to `docs/plans/2026-03-16-squad-workflow-manual-editing-implementation-plan.md`. Execution will continue in this session using the approved Codex worktree path.
