# Merged Thread Sticky Header Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep merged source-thread collapses pinned to the top of the Thread tab while live messages continue scrolling normally underneath.

**Architecture:** This is a UI-only change in the task detail sheet. The merged source-thread sections stay inside the existing Radix `ScrollArea`, but move into a dedicated sticky container rendered before the live-message list. The existing bottom sentinel and auto-scroll logic remain attached to the live-message portion of the thread.

**Tech Stack:** React, TypeScript, Tailwind CSS, Radix ScrollArea, Vitest, Testing Library

---

### Task 1: Lock The Expected Sticky Layout In Tests

**Files:**
- Modify: `dashboard/components/TaskDetailSheet.test.tsx`

**Step 1: Write the failing test**

Add a test that renders a merged task with direct messages plus `mergeSourceThreads`, then asserts the merged-thread container appears before the live-message content and carries sticky styling.

**Step 2: Run test to verify it fails**

Run: `cd /Users/ennio/Documents/nanobot-ennio/dashboard && npx vitest run components/TaskDetailSheet.test.tsx`
Expected: FAIL because the merged-thread block is still rendered after the live messages and has no sticky container.

**Step 3: Write minimal implementation**

Recompose the Thread tab so merged source threads render inside a dedicated sticky container above the live-message list, with background, border, spacing, and stacking styles.

**Step 4: Run test to verify it passes**

Run: `cd /Users/ennio/Documents/nanobot-ennio/dashboard && npx vitest run components/TaskDetailSheet.test.tsx`
Expected: PASS

### Task 2: Regression Verification

**Files:**
- Test: `dashboard/components/TaskDetailSheet.test.tsx`

**Step 1: Run focused regression suite**

Run: `cd /Users/ennio/Documents/nanobot-ennio/dashboard && npx vitest run components/TaskDetailSheet.test.tsx`

**Step 2: Check formatting if needed**

Run: `cd /Users/ennio/Documents/nanobot-ennio/dashboard && npx prettier --check features/tasks/components/TaskDetailSheet.tsx components/TaskDetailSheet.test.tsx`
