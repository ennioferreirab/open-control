# Story 33.3: Convex Boundary Fix and Activity Event Alignment

Status: ready-for-dev

## Story

As a developer,
I want the Convex module to be self-contained with no external imports, and activity event types to be consistent across all layers,
so that the architectural boundary is clean and events are never rejected by validator drift.

## Acceptance Criteria

1. `settings.ts` no longer imports from outside `convex/`
2. `activities.ts` create mutation uses the shared `activityEventTypeValidator` from schema
3. All 4 missing event types added to the create mutation (or resolved by using shared validator)
4. `v.any()` usages documented or replaced with typed validators where feasible
5. Zero TypeScript errors in `dashboard/convex/`

## Tasks / Subtasks

- [ ] Task 1: Fix cross-boundary import in `settings.ts` (AC: #1)
  - [ ] Line 3: `import { isChatHandlerRuntime } from "../lib/chatSyncRuntime"`
  - [ ] Line 4: `import { isGatewaySleepRuntime } from "../lib/gatewaySleepRuntime"`
  - [ ] Move these pure type-guard functions into `convex/lib/runtimeGuards.ts`
  - [ ] Update `settings.ts` to import from `./lib/runtimeGuards`
  - [ ] Verify the original `dashboard/lib/` files still work (they may have other consumers)

- [ ] Task 2: Align activity eventType in `activities.ts` (AC: #2, #3)
  - [ ] Replace inline eventType union (lines 9-48) with `activityEventTypeValidator` from schema
  - [ ] This automatically includes the 4 missing values: `agent_deleted`, `agent_restored`, `manual_task_status_changed`, `task_merged`
  - [ ] Depends on Story 33.2 Task 3 (shared validators must be exported first)

- [ ] Task 3: Audit and document `v.any()` usages (AC: #4)
  - [ ] `schema.ts:132` — `executionPlan`: replace with `executionPlanSchema` (already exists in `convex/lib/`)
  - [ ] `schema.ts:159` — `routingDecision`: define `routingDecisionValidator` with `v.object()`
  - [ ] `schema.ts:275` — `metadata` (runtimeClaims): define `v.optional(v.record(v.string(), v.any()))` at minimum
  - [ ] `schema.ts:287` — `response` (runtimeReceipts): document why `v.any()` is needed (polymorphic receipt data)
  - [ ] `schema.ts:580` — `stepMapping` (workflowRuns): define proper validator
  - [ ] `schema.ts:612` — `payload` (executionInteractions): define discriminated union
  - [ ] `schema.ts:629` — `questions` (executionQuestions): define proper validator
  - [ ] `tasks.ts:206,494,513` — use `executionPlanSchema` from lib
  - [ ] `tasks.ts:817` — use `routingDecisionValidator`
  - [ ] For each `v.any()` that cannot be replaced, add a `// v.any(): <reason>` comment

- [ ] Task 4: Verify (AC: #5)
  - [ ] `cd dashboard && npx tsc --noEmit` — zero errors in `convex/`

## Dev Notes

- Task 1 is simple — the functions are pure boolean guards (`return runtime === "..."`) with no dependencies.
- Task 2 depends on Story 33.2 Task 3 — the shared validator must be exported before it can be referenced.
- Task 3 is the most exploratory. Some `v.any()` are genuinely polymorphic (receipt responses from different mutation types). Document those with comments; replace the rest.
- The `executionPlanSchema` validator already exists in `convex/lib/` but is not used consistently.

### References

- [Source: agent_docs/code_conventions/convex.md#Boundary] — self-contained module rule
- [Source: agent_docs/code_conventions/convex.md#Schema] — no v.any() convention
- [Source: agent_docs/code_conventions/cross_service_naming.md#ActivityEventType] — event catalog
- [Source: dashboard/convex/schema.ts] — all v.any() locations
- [Source: dashboard/convex/settings.ts:3-4] — cross-boundary imports
- [Source: dashboard/convex/activities.ts:9-48] — inline eventType union
