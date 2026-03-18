# Live Tab Visualization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a durable, provider-agnostic Live tab that supports historical session navigation and chronological grouped rendering for related provider events.

**Architecture:** Enrich `sessionActivityLog` with canonical Live metadata at write time, normalize those records through a shared frontend translation layer, and expose a selector-driven `Live` tab that can switch between active and historical sessions without changing the underlying task/thread model.

**Tech Stack:** Python 3.12, Convex, TypeScript, Next.js 15, React 19, Vitest

---

### Task 1: Canonical Live Contract and Persistence

**Files:**
- Modify: `mc/contexts/provider_cli/providers/claude_code.py`
- Modify: `mc/application/execution/strategies/provider_cli.py`
- Modify: `dashboard/convex/schema.ts`
- Modify: `dashboard/convex/sessionActivityLog.ts`
- Test: `dashboard/convex/sessionActivityLog.test.ts`
- Test: `dashboard/features/interactive/lib/providerLiveEvents.test.ts`
- Docs: `agent_docs/database_schema.md`
- Docs: `agent_docs/service_communication_patterns.md`

**Step 1: Write the failing tests**

- Add Convex tests that assert `sessionActivityLog.append` stores `sourceType`, `sourceSubtype`, `groupKey`, `rawText`, and `rawJson` when provided.
- Add providerLiveEvents tests that assert canonical `sourceType` values bypass the old heuristic path.

**Step 2: Run the tests to verify they fail**

Run: `cd dashboard && npx vitest run convex/sessionActivityLog.test.ts features/interactive/lib/providerLiveEvents.test.ts`

Expected: failing assertions because the schema and append mutation do not support the new metadata yet.

**Step 3: Write the minimal implementation**

- Extend the Convex validator/table shape for the new Live metadata fields.
- Update `sessionActivityLog.append` to persist them.
- Teach the Claude Code parser / provider CLI activity logger to populate canonical metadata wherever the raw chunk already exposes it.
- Keep existing fields (`summary`, `toolInput`, `error`, `kind`) for backward compatibility.

**Step 4: Run the tests to verify they pass**

Run: `cd dashboard && npx vitest run convex/sessionActivityLog.test.ts features/interactive/lib/providerLiveEvents.test.ts`

Expected: PASS.

**Step 5: Update contract docs**

- Document the new fields in `agent_docs/database_schema.md`.
- Document the provider-to-Live translation behavior in `agent_docs/service_communication_patterns.md`.

**Step 6: Commit**

```bash
git add mc/contexts/provider_cli/providers/claude_code.py mc/application/execution/strategies/provider_cli.py dashboard/convex/schema.ts dashboard/convex/sessionActivityLog.ts dashboard/convex/sessionActivityLog.test.ts dashboard/features/interactive/lib/providerLiveEvents.test.ts agent_docs/database_schema.md agent_docs/service_communication_patterns.md
git commit -m "feat: add canonical live event metadata"
```

### Task 2: Live Session / Step Navigation

**Files:**
- Modify: `dashboard/features/interactive/hooks/useTaskInteractiveSession.ts`
- Test: `dashboard/features/interactive/hooks/useTaskInteractiveSession.test.ts`
- Modify: `dashboard/features/tasks/components/TaskDetailSheet.tsx`
- Test: `dashboard/components/TaskDetailSheet.test.tsx`

**Step 1: Write the failing tests**

- Add hook tests for a selector model that returns the active choice plus historical step/task Live choices.
- Add component tests that assert the `Live` tab shows a selector and can switch from a running step to a completed historical step.

**Step 2: Run the tests to verify they fail**

Run: `cd dashboard && npx vitest run features/interactive/hooks/useTaskInteractiveSession.test.ts components/TaskDetailSheet.test.tsx`

Expected: FAIL because the hook only returns `liveStepIds` and the sheet has no selector UI.

**Step 3: Write the minimal implementation**

- Extend `useTaskInteractiveSession` to return navigable Live choices with labels/status ordering.
- Wire `TaskDetailSheet` to render a selector in the `Live` tab and to switch `selectedLiveStepId` or task-level selection explicitly.
- Preserve the current default behavior for active running/review steps.

**Step 4: Run the tests to verify they pass**

Run: `cd dashboard && npx vitest run features/interactive/hooks/useTaskInteractiveSession.test.ts components/TaskDetailSheet.test.tsx`

Expected: PASS.

**Step 5: Commit**

```bash
git add dashboard/features/interactive/hooks/useTaskInteractiveSession.ts dashboard/features/interactive/hooks/useTaskInteractiveSession.test.ts dashboard/features/tasks/components/TaskDetailSheet.tsx dashboard/components/TaskDetailSheet.test.tsx
git commit -m "feat: add live session navigation"
```

### Task 3: Chronological Grouped Live Rendering

**Files:**
- Modify: `dashboard/features/interactive/lib/providerLiveEvents.ts`
- Test: `dashboard/features/interactive/lib/providerLiveEvents.test.ts`
- Modify: `dashboard/features/interactive/hooks/useProviderSession.ts`
- Test: `dashboard/features/interactive/hooks/useProviderSession.test.ts`
- Modify: `dashboard/features/interactive/components/ProviderLiveChatPanel.tsx`
- Modify: `dashboard/features/interactive/components/ProviderLiveEventRow.tsx`
- Test: `dashboard/features/interactive/components/ProviderLiveChatPanel.test.tsx`
- Test: `dashboard/features/interactive/components/ProviderLiveEventRow.test.tsx`

**Step 1: Write the failing tests**

- Add unit tests for grouping consecutive events by `groupKey` while preserving chronological order.
- Add component tests for grouped blocks containing `system` + `assistant` + `result` in one visual cluster.
- Add fallback tests for rows without `groupKey` / `sourceType`.

**Step 2: Run the tests to verify they fail**

Run: `cd dashboard && npx vitest run features/interactive/lib/providerLiveEvents.test.ts features/interactive/hooks/useProviderSession.test.ts features/interactive/components/ProviderLiveChatPanel.test.tsx features/interactive/components/ProviderLiveEventRow.test.tsx`

Expected: FAIL because the panel still renders one card per event and the event model has no grouped timeline representation.

**Step 3: Write the minimal implementation**

- Expand `providerLiveEvents.ts` to build grouped chronological timeline nodes.
- Keep compatibility mapping from legacy rows into the new grouped model.
- Update `useProviderSession` and `ProviderLiveChatPanel` to consume the grouped model.
- Adjust row rendering to distinguish `system`, `assistant`, `tool`, `result`, and fallback/error states clearly.

**Step 4: Run the tests to verify they pass**

Run: `cd dashboard && npx vitest run features/interactive/lib/providerLiveEvents.test.ts features/interactive/hooks/useProviderSession.test.ts features/interactive/components/ProviderLiveChatPanel.test.tsx features/interactive/components/ProviderLiveEventRow.test.tsx`

Expected: PASS.

**Step 5: Commit**

```bash
git add dashboard/features/interactive/lib/providerLiveEvents.ts dashboard/features/interactive/lib/providerLiveEvents.test.ts dashboard/features/interactive/hooks/useProviderSession.ts dashboard/features/interactive/hooks/useProviderSession.test.ts dashboard/features/interactive/components/ProviderLiveChatPanel.tsx dashboard/features/interactive/components/ProviderLiveEventRow.tsx dashboard/features/interactive/components/ProviderLiveChatPanel.test.tsx dashboard/features/interactive/components/ProviderLiveEventRow.test.tsx
git commit -m "feat: group live output chronologically"
```

### Task 4: Integration Verification

**Files:**
- Verify only

**Step 1: Run affected dashboard tests**

Run:

```bash
cd dashboard && npx vitest run \
  convex/sessionActivityLog.test.ts \
  features/interactive/lib/providerLiveEvents.test.ts \
  features/interactive/hooks/useProviderSession.test.ts \
  features/interactive/hooks/useTaskInteractiveSession.test.ts \
  features/interactive/components/ProviderLiveChatPanel.test.tsx \
  features/interactive/components/ProviderLiveEventRow.test.tsx \
  components/TaskDetailSheet.test.tsx
```

Expected: PASS.

**Step 2: Run lint/typecheck for the affected layer**

Run:

```bash
cd dashboard && npx next lint
cd dashboard && npx tsc --noEmit
```

Expected: PASS.

**Step 3: Manual verification checklist**

- Open a task with an active Live step.
- Confirm the selector defaults to the active step.
- Switch to a completed historical step.
- Confirm grouped chronology preserves timestamp order and related events appear in one cluster.
- Confirm legacy rows without `groupKey` still render individually.

**Step 4: Final commit**

```bash
git add .
git commit -m "test: verify live tab visualization flow"
```
