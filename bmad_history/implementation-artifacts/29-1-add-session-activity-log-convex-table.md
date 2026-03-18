# Story 29.1: Add Session Activity Log Convex Table

Status: ready-for-dev

## Story

As a Mission Control platform maintainer,
I want a Convex table that persists structured supervision events per session,
so that the dashboard can show a real-time activity feed of what agents are doing.

## Acceptance Criteria

1. A `sessionActivityLog` table exists in the Convex schema with fields:
   sessionId, seq, kind, ts, toolName, toolInput, filePath, summary, error,
   turnId, itemId, stepId, agentName, provider, requiresAction
2. An `append` mutation exists that auto-increments `seq` per session using
   the `by_session_seq` index within a single transaction (OCC-safe)
3. A `listForSession` query exists that returns events ordered by seq,
   limited to the last 500 events
4. Truncation: `toolInput` capped at 2000 chars, `summary` at 1000, `error` at 2000
5. Indexes: `by_session` and `by_session_seq` exist
6. Focused tests validate the schema, append seq monotonicity, and query ordering

## Tasks / Subtasks

- [ ] Task 1: Add the table schema to `dashboard/convex/schema.ts`
- [ ] Task 2: Create `dashboard/convex/sessionActivityLog.ts` with `append`
      mutation and `listForSession` query
- [ ] Task 3: Add focused tests

## Dev Notes

- The `append` mutation must read max seq via `by_session_seq` index descending
  in the same transaction before inserting. Convex OCC makes this safe.
- The `listForSession` query uses `by_session_seq` index for guaranteed ordering.
- Keep truncation in the mutation, not in the caller.
- No cleanup job in this story — deferred to a follow-up.

### References

- [Source: docs/plans/2026-03-14-agent-activity-feed-design.md]
