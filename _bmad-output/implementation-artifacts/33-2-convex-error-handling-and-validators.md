# Story 33.2: Convex Error Handling and Shared Validators

Status: ready-for-dev

## Story

As a developer,
I want Convex mutations to use `ConvexError` for user-facing errors and shared validators for status/ID fields,
so that error handling is consistent and type safety is enforced at function boundaries.

## Acceptance Criteria

1. All user-facing `throw new Error(...)` in Convex handlers converted to `throw new ConvexError(...)`
2. Shared validators exported from `schema.ts`: `taskStatusValidator`, `stepStatusValidator`, `agentStatusValidator`
3. All mutation args use `v.id("tableName")` instead of `v.string()` for document IDs
4. All inline status unions in mutation args replaced with shared validators
5. `ConvexError` used in `lib/` modules for validation errors; plain `Error` kept for programmer errors
6. Zero TypeScript errors in `dashboard/convex/`

## Tasks / Subtasks

- [ ] Task 1: Convert `throw new Error` to `ConvexError` in handler files (AC: #1)
  - [ ] `agents.ts` — 11 instances (lines 271, 313, 318, 348, 352, 389, 393, 418, 422, 515)
  - [ ] `boards.ts` — 4 instances (lines 56, 66, 104, 129, 132)
  - [ ] `squadSpecs.ts` — 6 instances (lines 42, 45, 65, 117, 118, 130, 131)
  - [ ] `agentSpecs.ts` — 2 instances (lines 60, 63)
  - [ ] `reviewSpecs.ts` — 2 instances (lines 51, 54)
  - [ ] `workflowSpecs.ts` — 4 instances (lines 21, 24, 27, 89, 92)
  - [ ] `boardSquadBindings.ts` — 1 instance (line 32)
  - [ ] Add `import { ConvexError } from "convex/values"` to each file if not present

- [ ] Task 2: Convert validation errors in `lib/` modules (AC: #5)
  - [ ] `lib/squadGraphValidator.ts` — 12 validation errors → ConvexError (lines 15, 21, 54, 71, 79, 88, 101, 117, 121, 126, 144, 155)
  - [ ] `lib/squadGraphUpdater.ts` — 7 validation errors → ConvexError (lines 33, 42, 45, 48, 51, 72, 125, 144)
  - [ ] `lib/squadGraphPublisher.ts` — 3 validation errors → ConvexError (lines 104, 107, 110)
  - [ ] `lib/squadMissionLaunch.ts` — 1 validation error → ConvexError (line 167)
  - [ ] `lib/workflowHelpers.ts` — 1 validation error → ConvexError (line 141)
  - [ ] Keep `Error` in `lib/taskLifecycle.ts:106` (programmer error: no mapping)
  - [ ] Keep `Error` in `lib/workflowExecutionCompiler.ts:159,162,165,191` (compiler invariants)

- [ ] Task 3: Extract shared validators in `schema.ts` (AC: #2)
  - [ ] Export `taskStatusValidator` from the existing inline union (lines 113-124)
  - [ ] Export `stepStatusValidator` from the existing inline union
  - [ ] Export `agentStatusValidator` from the existing inline union
  - [ ] Export `activityEventTypeValidator` from the existing inline union (lines 333-377)
  - [ ] Reference these validators in the table definitions instead of inline unions

- [ ] Task 4: Replace `v.string()` with `v.id()` for document IDs (AC: #3)
  - [ ] `agentSpecs.ts` — `specId` arg (lines 55, 77) → `v.id("agentSpecs")`
  - [ ] `reviewSpecs.ts` — `specId` arg (line 46) → `v.id("reviewSpecs")`
  - [ ] `workflowSpecs.ts` — `specId` arg (line 84) → `v.id("workflowSpecs")`
  - [ ] `squadSpecs.ts` — `specId` arg (line 37) → `v.id("squadSpecs")`
  - [ ] `boardSquadBindings.ts` — `bindingId` arg (line 26) → `v.id("boardSquadBindings")`
  - [ ] Remove corresponding `as Id<>` casts from handlers

- [ ] Task 5: Replace inline status unions with shared validators (AC: #4)
  - [ ] `tasks.ts:163-175` — use `taskStatusValidator`
  - [ ] `tasks.ts:577` — `status: v.string()` → `status: taskStatusValidator`
  - [ ] `tasks.ts:607,609` — `fromStatus`/`toStatus: v.string()` → `taskStatusValidator`
  - [ ] `steps.ts:152` — `status: v.optional(stepStatusValidator)`
  - [ ] `steps.ts:287` — `status: stepStatusValidator`
  - [ ] `steps.ts:338,340` — `fromStatus`/`toStatus` → `stepStatusValidator`
  - [ ] `agents.ts:202` — `status: v.string()` → `agentStatusValidator`
  - [ ] `workflowRuns.ts:58-63` — use shared workflow run status validator
  - [ ] `squadSpecs.ts:168-173,225-230` — use `workflowStepTypeValidator` from schema

- [ ] Task 6: Verify (AC: #6)
  - [ ] `cd dashboard && npx tsc --noEmit` — zero errors in `convex/`

## Dev Notes

- ConvexError accepts strings or structured objects. For simple "not found" errors, use string. For errors the frontend handles programmatically, use `{ code: "...", detail: "..." }`.
- When extracting shared validators, the schema table definitions should reference the exported validators rather than duplicating the union.
- The `v.id()` change may require updating Python callers if they pass plain strings — but the bridge already sends valid Convex ID strings, so this should be transparent.

### References

- [Source: agent_docs/code_conventions/convex.md#Error Handling] — ConvexError vs Error
- [Source: agent_docs/code_conventions/convex.md#Argument Validation] — v.id() convention
- [Source: dashboard/convex/schema.ts] — all table definitions and inline validators
- [Source: agent_docs/code_conventions/cross_service_naming.md] — canonical status values
