# Story 5.1: Convex Bandwidth Audit and Operator Report

Status: ready-for-dev

## Story

As the platform operator,
I want a repeatable report that groups Convex read and write bytes by function and day,
so that I can identify the current bandwidth hotspots and measure improvements.

## Acceptance Criteria

1. The dashboard has a script that reads Convex JSONL logs and aggregates `database_read_bytes` and `database_write_bytes`.
2. The report groups totals by function and by day.
3. The output ranks hotspots by total bandwidth and clearly surfaces `boards.ts`, `taskDetailView.ts`, `sessionActivityLog.ts`, and `tasks.ts` when present.
4. The report works on one file, many files, a directory, or stdin.
5. The report docs explain how to run it.

## Tasks / Subtasks

- [ ] Task 1: Add report script
  - [ ] 1.1 Create `dashboard/scripts/convex-bandwidth-report.mjs`
  - [ ] 1.2 Read JSONL from files or stdin
  - [ ] 1.3 Aggregate by function and day
  - [ ] 1.4 Format a markdown report

- [ ] Task 2: Wire package script
  - [ ] 2.1 Add `npm run convex:bandwidth-report` in `dashboard/package.json`

- [ ] Task 3: Add operator docs
  - [ ] 3.1 Create `docs/operations/convex-bandwidth-report.md`

## Expected Files

| File | Change |
|------|--------|
| `dashboard/scripts/convex-bandwidth-report.mjs` | New report script |
| `dashboard/package.json` | Add package script |
| `docs/operations/convex-bandwidth-report.md` | Usage and output guide |

## Testing Guidance

- Run the report against a small JSONL fixture and verify the grouped output.
- Keep the parser tolerant of variant field names from Convex log exports.
