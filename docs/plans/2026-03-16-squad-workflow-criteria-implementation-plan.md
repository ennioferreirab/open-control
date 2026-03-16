# Squad Workflow Criteria Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a workflow criteria tab for `exitCriteria` and expose squad-level `reviewPolicy` in the squad header area, with both values persisted on publish.

**Architecture:** Keep workflow-specific data inside `EditableWorkflow` and squad-wide data inside `EditableSquadDraft`. Extend the existing publish path instead of inventing a second persistence flow. Update tests first, then implement the smallest UI and Convex changes needed to satisfy them.

**Tech Stack:** Next.js, React, Vitest, Testing Library, Convex mutations/schema

---

### Task 1: Add failing UI tests

**Files:**
- Modify: `dashboard/features/agents/components/SquadWorkflowCanvas.test.tsx`
- Modify: `dashboard/features/agents/components/SquadDetailSheet.test.tsx`

**Step 1: Write the failing test**

- Add a test that expects a `Criteria` tab and a `Validation Criteria` field in the workflow editor.
- Add a test that expects `Review Policy` to render in the squad sheet and be included in the publish payload.

**Step 2: Run test to verify it fails**

Run: `npm test -- features/agents/components/SquadWorkflowCanvas.test.tsx features/agents/components/SquadDetailSheet.test.tsx`

Expected: FAIL because the new tab and field do not exist yet.

**Step 3: Write minimal implementation**

- Add the new tab and field.
- Add the squad-level review policy panel and wire it to draft state.

**Step 4: Run test to verify it passes**

Run: `npm test -- features/agents/components/SquadWorkflowCanvas.test.tsx features/agents/components/SquadDetailSheet.test.tsx`

Expected: PASS

### Task 2: Add failing persistence tests

**Files:**
- Modify: `dashboard/features/agents/hooks/useUpdatePublishedSquad.test.tsx`
- Modify: `dashboard/convex/squadSpecs.test.ts`
- Modify: `dashboard/convex/lib/squadGraphPublisher.test.ts`

**Step 1: Write the failing test**

- Expect `reviewPolicy` to pass through the hook payload.
- Expect publish/update handlers to persist `reviewPolicy`.

**Step 2: Run test to verify it fails**

Run: `npm test -- features/agents/hooks/useUpdatePublishedSquad.test.tsx convex/squadSpecs.test.ts convex/lib/squadGraphPublisher.test.ts`

Expected: FAIL until implementation is wired through.

**Step 3: Write minimal implementation**

- Persist `reviewPolicy` on squad insert/update.
- Accept it in the update mutation validator and hook types.

**Step 4: Run test to verify it passes**

Run: `npm test -- features/agents/hooks/useUpdatePublishedSquad.test.tsx convex/squadSpecs.test.ts convex/lib/squadGraphPublisher.test.ts`

Expected: PASS

### Task 3: Verify touched areas

**Files:**
- Modify: `dashboard/features/agents/components/SquadWorkflowCanvas.tsx`
- Modify: `dashboard/features/agents/components/SquadDetailSheet.tsx`
- Modify: `dashboard/features/agents/hooks/useUpdatePublishedSquad.ts`
- Modify: `dashboard/convex/schema.ts`
- Modify: `dashboard/convex/lib/squadGraphPublisher.ts`
- Modify: `dashboard/convex/lib/squadGraphUpdater.ts`
- Modify: `dashboard/convex/squadSpecs.ts`

**Step 1: Run targeted tests**

Run: `npm test -- features/agents/components/SquadWorkflowCanvas.test.tsx features/agents/components/SquadDetailSheet.test.tsx features/agents/hooks/useUpdatePublishedSquad.test.tsx convex/squadSpecs.test.ts convex/lib/squadGraphPublisher.test.ts`

**Step 2: Run file-level formatting and lint**

Run: `npm run format:file:check -- dashboard/features/agents/components/SquadWorkflowCanvas.tsx dashboard/features/agents/components/SquadDetailSheet.tsx dashboard/features/agents/hooks/useUpdatePublishedSquad.ts dashboard/convex/schema.ts dashboard/convex/lib/squadGraphPublisher.ts dashboard/convex/lib/squadGraphUpdater.ts dashboard/convex/squadSpecs.ts dashboard/features/agents/components/SquadWorkflowCanvas.test.tsx dashboard/features/agents/components/SquadDetailSheet.test.tsx dashboard/features/agents/hooks/useUpdatePublishedSquad.test.tsx dashboard/convex/squadSpecs.test.ts dashboard/convex/lib/squadGraphPublisher.test.ts`

**Step 3: Run guardrail**

Run: `npm run test:architecture`
