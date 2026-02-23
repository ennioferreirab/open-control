# Story 8.8: View Cron Jobs Modal

Status: done

## Story

As a **user**,
I want to open a modal from the Mission Control header that lists all scheduled cron jobs,
so that I can see what is scheduled, when it last ran, when it will run next, and what channel/recipient it delivers to.

## Acceptance Criteria

**Given** the Mission Control dashboard is open
**When** the user clicks the Clock icon in the header
**Then** a `CronJobsModal` dialog opens

**Given** the modal is open
**When** the GET `/api/cron` route reads `~/.nanobot/cron/jobs.json`
**Then** it returns the full list of jobs (both enabled and disabled)
**And** the modal renders a table/list with one row per job showing:
  - Job name
  - Schedule (human-readable: "every X min", "cron: 0 9 * * *", or "at: ISO datetime")
  - Timezone (if `schedule.tz` is set, shown next to schedule)
  - Enabled/disabled badge
  - Delivery: `payload.channel` + `payload.to` (shown as "channel → to", or "—" if not set)
  - Last run: `state.lastRunAtMs` formatted as relative time (e.g., "3 hours ago") or "—" if never run
  - Next run: `state.nextRunAtMs` formatted as relative time (e.g., "in 2 hours") or "—" if disabled/expired
  - Last status: `state.lastStatus` as a colored badge ("ok" = green, "error" = red, "skipped" = muted, or "—")
  - Last error: if `state.lastError` is set, show a tooltip or inline expandable with the error text

**Given** the cron store file does not exist or is empty
**When** the modal loads
**Then** a muted placeholder displays: "No scheduled jobs. Agents can create cron jobs using the `cron` tool."

**Given** the GET `/api/cron` request fails (e.g., filesystem error)
**When** the modal renders
**Then** an error state is shown: "Failed to load cron jobs."

**Given** the modal is open
**When** the user clicks the X button or presses Escape
**Then** the modal closes

## Tasks / Subtasks

- [x] Task 1: Create `/api/cron` Next.js API route (AC: #2, #4, #5)
  - [x] 1.1 Create `dashboard/app/api/cron/route.ts`
  - [x] 1.2 Route reads `~/.nanobot/cron/jobs.json` using Node.js `fs` and `os.homedir()`
  - [x] 1.3 Returns parsed JSON: `{ jobs: CronJob[] }` with camelCase fields matching the cron store schema
  - [x] 1.4 Returns `{ jobs: [] }` (200) if file does not exist
  - [x] 1.5 Returns 500 on unexpected filesystem errors

- [x] Task 2: Create `CronJobsModal` component (AC: #2, #3, #4, #5, #6)
  - [x] 2.1 Create `dashboard/components/CronJobsModal.tsx`
  - [x] 2.2 Use ShadCN `Dialog` (same pattern as `DocumentViewerModal.tsx`)
  - [x] 2.3 On open, `fetch("/api/cron")` — show loading skeleton while fetching
  - [x] 2.4 Render job list with all fields listed in AC #2
  - [x] 2.5 Human-readable schedule formatting:
    - `kind: "every"` → "every X min" / "every X sec" / "every X hr" (from `everyMs`)
    - `kind: "cron"` → `cron: {expr}` + optional `(tz)` suffix
    - `kind: "at"` → `at: {ISO datetime}` formatted as locale string
  - [x] 2.6 Relative timestamps using `Intl.RelativeTimeFormat` or a small inline helper (no new deps)
  - [x] 2.7 Empty state and error state (AC #4, #5)
  - [x] 2.8 Close on X click or Escape (AC #6)

- [x] Task 3: Add Clock button to DashboardLayout (AC: #1)
  - [x] 3.1 Import `Clock` from `lucide-react` and `CronJobsModal` in `DashboardLayout.tsx`
  - [x] 3.2 Add `cronOpen` state variable (similar to `settingsOpen`, `tagsOpen`)
  - [x] 3.3 Add Clock icon button in header (between Tags and Settings buttons)
  - [x] 3.4 Render `<CronJobsModal open={cronOpen} onClose={() => setCronOpen(false)} />`

## Dev Notes

### Architecture Patterns

- **No Convex**: Cron jobs live in `~/.nanobot/cron/jobs.json` (filesystem-only). The API route reads the file directly — same pattern as `dashboard/app/api/tasks/[taskId]/files/route.ts`.
- **No new dependencies**: Use `fs/promises`, `os`, `path` (Node.js built-ins). No npm packages needed.
- **Modal pattern**: Use ShadCN `Dialog` (same as `DocumentViewerModal.tsx` at `dashboard/components/DocumentViewerModal.tsx:4`).
- **Data fetch**: `fetch` in `useEffect` on modal open (client-side), not Convex query.

### Cron Store Location

```
~/.nanobot/cron/jobs.json
```

Resolved in Node.js as:
```ts
import { homedir } from "os";
import { join } from "path";
const storePath = join(homedir(), ".nanobot", "cron", "jobs.json");
```

### Cron Store JSON Schema

The file format (from `nanobot/cron/service.py`):
```json
{
  "version": 1,
  "jobs": [
    {
      "id": "abc12345",
      "name": "Check GitHub stars",
      "enabled": true,
      "schedule": {
        "kind": "every",
        "everyMs": 600000,
        "atMs": null,
        "expr": null,
        "tz": null
      },
      "payload": {
        "kind": "agent_turn",
        "message": "Check HKUDS/nanobot GitHub stars and report",
        "deliver": true,
        "channel": "whatsapp",
        "to": "+1234567890"
      },
      "state": {
        "nextRunAtMs": 1740000000000,
        "lastRunAtMs": 1739999400000,
        "lastStatus": "ok",
        "lastError": null
      },
      "createdAtMs": 1739999400000,
      "updatedAtMs": 1739999400000,
      "deleteAfterRun": false
    }
  ]
}
```

### TypeScript Types for API Route Response

Define inline in the component file:
```ts
interface CronSchedule {
  kind: "at" | "every" | "cron";
  atMs: number | null;
  everyMs: number | null;
  expr: string | null;
  tz: string | null;
}
interface CronPayload {
  kind: string;
  message: string;
  deliver: boolean;
  channel: string | null;
  to: string | null;
}
interface CronJobState {
  nextRunAtMs: number | null;
  lastRunAtMs: number | null;
  lastStatus: "ok" | "error" | "skipped" | null;
  lastError: string | null;
}
interface CronJob {
  id: string;
  name: string;
  enabled: boolean;
  schedule: CronSchedule;
  payload: CronPayload;
  state: CronJobState;
  createdAtMs: number;
  updatedAtMs: number;
  deleteAfterRun: boolean;
}
```

### DashboardLayout Header Pattern

Current header buttons in `dashboard/components/DashboardLayout.tsx:73-88`:
```tsx
<div className="flex items-center gap-1">
  <button aria-label="Open tags" onClick={() => setTagsOpen(true)} ...>
    <Tag className="h-5 w-5" />
  </button>
  <button aria-label="Open settings" onClick={() => setSettingsOpen(true)} ...>
    <Settings className="h-5 w-5" />
  </button>
</div>
```
Add `Clock` button with the same styling before the Tags button.

### Human-Readable Schedule Formatting

```ts
function formatSchedule(schedule: CronSchedule): string {
  if (schedule.kind === "every" && schedule.everyMs) {
    const s = schedule.everyMs / 1000;
    if (s < 60) return `every ${s}s`;
    if (s < 3600) return `every ${Math.round(s / 60)}min`;
    return `every ${Math.round(s / 3600)}hr`;
  }
  if (schedule.kind === "cron" && schedule.expr) {
    return `cron: ${schedule.expr}${schedule.tz ? ` (${schedule.tz})` : ""}`;
  }
  if (schedule.kind === "at" && schedule.atMs) {
    return `at: ${new Date(schedule.atMs).toLocaleString()}`;
  }
  return "—";
}
```

### Relative Timestamp Formatting

```ts
function formatRelative(ms: number | null): string {
  if (!ms) return "—";
  const diff = ms - Date.now();
  const abs = Math.abs(diff);
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  if (abs < 60_000) return rtf.format(Math.round(diff / 1000), "seconds");
  if (abs < 3_600_000) return rtf.format(Math.round(diff / 60_000), "minutes");
  if (abs < 86_400_000) return rtf.format(Math.round(diff / 3_600_000), "hours");
  return rtf.format(Math.round(diff / 86_400_000), "days");
}
```

### Module Size Constraint

Both files must stay under 500 lines (NFR21). The API route should be < 50 lines. The modal component should be < 300 lines.

### Project Structure Notes

Files to create:
- `dashboard/app/api/cron/route.ts` — new API route (< 50 lines)
- `dashboard/components/CronJobsModal.tsx` — new modal component (< 300 lines)

Files to modify:
- `dashboard/components/DashboardLayout.tsx` — add Clock button and modal state/render

No schema changes, no Convex changes, no Python changes needed.

### References

- Cron types: [Source: nanobot/cron/types.py]
- Cron service (store path, JSON schema): [Source: nanobot/cron/service.py#_load_store, _save_store]
- File serving API route pattern: [Source: dashboard/app/api/tasks/[taskId]/files/route.ts]
- Modal pattern (ShadCN Dialog): [Source: dashboard/components/DocumentViewerModal.tsx#1-30]
- DashboardLayout header: [Source: dashboard/components/DashboardLayout.tsx#69-88]
- Architecture NFR21 (500-line limit): [Source: _bmad-output/planning-artifacts/architecture.md]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Created `dashboard/app/api/cron/route.ts`: GET handler reads `~/.nanobot/cron/jobs.json` via `fs/promises`. Returns `{jobs:[]}` on ENOENT or empty file, 500 on other errors. storePath computed inside GET() for testability.
- Created `dashboard/components/CronJobsModal.tsx`: ShadCN Dialog modal with fetch-on-open pattern, cancel flag in useEffect cleanup, stale jobs reset on open, 3-row loading skeleton, job table with all AC fields, schedule tz shown for all kinds, `ms == null` guard in formatRelative, aria-label on close button.
- Modified `dashboard/components/DashboardLayout.tsx`: Added `Clock` icon import, `CronJobsModal` import, `cronOpen` state, Clock button between Tags and Settings in header, modal render.
- Created `dashboard/app/api/cron/route.test.ts`: 6 tests covering success, ENOENT, empty file, missing jobs field, EACCES error, malformed JSON.
- Created `dashboard/components/CronJobsModal.test.tsx`: 8 tests covering loading skeleton, job table render, empty state, fetch error (non-ok), fetch reject, close button, no-fetch-when-closed, cancel on close.
- TypeScript: `npx tsc --noEmit` passes with zero errors.
- Tests: 14/14 new tests pass. Pre-existing suite: 202/203 (1 pre-existing unrelated TaskCard failure unchanged).
- Code review fixed: M1 (empty file 500→{jobs:[]}), M2 (abort/cancel in useEffect), M3 (stale jobs cleared on open), M4 (tests added), L1 (ms==null), L2 (tz all kinds), L3 (STORE_PATH in handler), L4 (aria-label).

### File List

- dashboard/app/api/cron/route.ts (created)
- dashboard/app/api/cron/route.test.ts (created)
- dashboard/components/CronJobsModal.tsx (created)
- dashboard/components/CronJobsModal.test.tsx (created)
- dashboard/components/DashboardLayout.tsx (modified)

### Change Log

- 2026-02-23: Implemented Story 8.8 — View Cron Jobs Modal. Created GET /api/cron API route, CronJobsModal component, and wired Clock button in DashboardLayout header.
- 2026-02-23: Code review — fixed 4 MEDIUM (empty file edge case, missing abort on fetch, stale jobs on reopen, missing tests) and 4 LOW (ms==null, tz all schedule kinds, STORE_PATH location, aria-label). Added 14 tests (6 route + 8 component). Status: done.
