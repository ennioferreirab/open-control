# Story 5.4: Live File Read API and Dashboard Consumer Migration

Status: ready-for-dev

## Story

As an operator,
I want the dashboard to read Live transcripts from files instead of Convex,
so that opening Live does not re-subscribe to large transcript payloads.

## Acceptance Criteria

1. The dashboard exposes `GET /api/live/sessions/[sessionId]/meta`.
2. The dashboard exposes `GET /api/live/sessions/[sessionId]/events?afterSeq=<n>`.
3. `useProviderSession` reads transcript data from the file-backed API.
4. `useAgentActivity` also reads transcript data from the file-backed API.
5. Missing transcripts render as "No records" without crashing.

## Tasks / Subtasks

- [ ] Task 1: Add file-backed API routes
  - [ ] 1.1 Create `dashboard/app/api/live/sessions/[sessionId]/meta/route.ts`
  - [ ] 1.2 Create `dashboard/app/api/live/sessions/[sessionId]/events/route.ts`
  - [ ] 1.3 Add route tests

- [ ] Task 2: Add shared helpers
  - [ ] 2.1 Create `dashboard/lib/liveSessionFiles.ts`

- [ ] Task 3: Migrate consumers
  - [ ] 3.1 Update `dashboard/features/interactive/hooks/useProviderSession.ts`
  - [ ] 3.2 Update `dashboard/features/interactive/hooks/useAgentActivity.ts`
  - [ ] 3.3 Update hook/component tests

## Expected Files

| File | Change |
|------|--------|
| `dashboard/app/api/live/sessions/[sessionId]/meta/route.ts` | New route |
| `dashboard/app/api/live/sessions/[sessionId]/events/route.ts` | New route |
| `dashboard/lib/liveSessionFiles.ts` | New helper |
| `dashboard/features/interactive/hooks/useProviderSession.ts` | File-backed reads |
| `dashboard/features/interactive/hooks/useAgentActivity.ts` | File-backed reads |
| `dashboard/features/interactive/hooks/useProviderSession.test.ts` | Update tests |
