# Story 8.2: Cron Schedule Table

Status: ready-for-dev

## Story

As a **user**,
I want to see cron schedules as a structured table (Days / Hours / Minutes) instead of raw cron expressions,
so that I can quickly understand and compare job schedules.

## Context

The `CronJobsModal` currently displays cron schedules as raw monospace text (e.g., `cron: 0 9 * * 1-5 (America/New_York)`) in the Schedule column of the jobs table. Users need to mentally parse the 5-field cron expression to understand what it means. This story adds a human-readable 3-column breakdown (Days, Hours, Minutes) rendered below the raw cron expression for jobs with `schedule.kind === "cron"`.

A new utility function `parseCronToTable` is created in `dashboard/lib/cron-parser.ts` to parse 5-field cron expressions (`min hour dom month dow`) into English-readable strings. The raw cron expression is preserved above the table for power users who prefer the original notation.

**No schema changes. No new external dependencies.**

## Acceptance Criteria

1. **3-column table shown for cron jobs** -- Given a cron job with `schedule.kind === "cron"` and a valid 5-field cron expression, when the CronJobsModal is open, then a 3-column mini-table (Days, Hours, Minutes) is displayed below the raw cron expression in that job's Schedule cell.

2. **Raw cron expression preserved** -- Given a cron job with `schedule.kind === "cron"`, when the CronJobsModal is open, then the raw cron expression (e.g., `cron: 0 9 * * 1-5`) is still visible above the human-readable table.

3. **Only shown for cron-kind schedules** -- Given a cron job with `schedule.kind === "every"` or `schedule.kind === "at"`, when the CronJobsModal is open, then no human-readable table is shown -- only the existing formatted schedule text.

4. **English human-readable values** -- Given the cron expression `0 9 * * 1-5`, then the table shows Days: "Monday - Friday", Hours: "9 AM", Minutes: "At :00". Given `*/15 9-17 * * *`, then Days: "Every day", Hours: "9 AM - 5 PM", Minutes: "Every 15 min".

5. **Graceful fallback for unparseable expressions** -- Given a cron expression that cannot be parsed (e.g., malformed or using non-standard syntax), then the table is not shown and only the raw cron expression is displayed.

## Tasks / Subtasks

- [ ] **Task 1: Create `parseCronToTable` utility** (AC: 4, 5)
  - [ ] 1.1 Create new file `dashboard/lib/cron-parser.ts`.
  - [ ] 1.2 Export function `parseCronToTable(expr: string): { days: string; hours: string; minutes: string } | null`.
  - [ ] 1.3 Split the expression on whitespace; if the result does not have exactly 5 fields, return `null`.
  - [ ] 1.4 **Parse minutes field** (field[0]):
    - `*` -> "Every min"
    - `*/N` -> "Every N min"
    - Single number `N` -> "At :NN" (zero-padded, e.g., `0` -> "At :00", `30` -> "At :30")
    - Comma-separated list `N,M,...` -> "At :NN, :MM, ..."
    - Range `N-M` -> "Every min :NN - :MM"
    - Range with step `N-M/S` -> "Every S min :NN - :MM"
    - Anything else -> return `null` (fallback)
  - [ ] 1.5 **Parse hours field** (field[1]):
    - `*` -> "Every hour"
    - `*/N` -> "Every N hours"
    - Single number `H` -> format as `H AM/PM` (0->12 AM, 12->12 PM, 13->1 PM, etc.)
    - Comma-separated list -> join formatted hours with ", "
    - Range `H1-H2` -> "H1 AM/PM - H2 AM/PM"
    - Range with step `H1-H2/S` -> "Every S hours H1 AM/PM - H2 AM/PM"
    - Anything else -> return `null`
  - [ ] 1.6 **Parse day-of-week field** (field[4]):
    - `*` -> "Every day"
    - Single number -> day name (0/7->"Sunday", 1->"Monday", ..., 6->"Saturday")
    - Comma-separated list -> join day names with ", " (e.g., `1,3,5` -> "Monday, Wednesday, Friday")
    - Range `N-M` -> "DayN - DayM" (e.g., `1-5` -> "Monday - Friday")
    - Anything else -> return `null`
  - [ ] 1.7 **Ignore DOM and Month fields** (fields[2] and fields[3]): If either is not `*`, still parse the other fields but do not attempt to represent DOM/Month in the table. The raw cron expression above covers those cases. Return the parsed result normally.
  - [ ] 1.8 Add named day constants: `const DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]`.
  - [ ] 1.9 Add helper `formatHour(h: number): string` that converts 0-23 to "12 AM", "1 AM", ..., "12 PM", "1 PM", ..., "11 PM".

- [ ] **Task 2: Write unit tests for `parseCronToTable`** (AC: 4, 5)
  - [ ] 2.1 Create `dashboard/lib/cron-parser.test.ts`.
  - [ ] 2.2 Test: `"0 9 * * 1-5"` -> `{ days: "Monday - Friday", hours: "9 AM", minutes: "At :00" }`.
  - [ ] 2.3 Test: `"*/15 9-17 * * *"` -> `{ days: "Every day", hours: "9 AM - 5 PM", minutes: "Every 15 min" }`.
  - [ ] 2.4 Test: `"30 14 * * 0"` -> `{ days: "Sunday", hours: "2 PM", minutes: "At :30" }`.
  - [ ] 2.5 Test: `"0 0 * * *"` -> `{ days: "Every day", hours: "12 AM", minutes: "At :00" }`.
  - [ ] 2.6 Test: `"0 12 * * *"` -> `{ days: "Every day", hours: "12 PM", minutes: "At :00" }`.
  - [ ] 2.7 Test: `"0,30 8,17 * * 1-5"` -> `{ days: "Monday - Friday", hours: "8 AM, 5 PM", minutes: "At :00, :30" }`.
  - [ ] 2.8 Test: `"* * * * *"` -> `{ days: "Every day", hours: "Every hour", minutes: "Every min" }`.
  - [ ] 2.9 Test: malformed `"invalid"` -> `null`.
  - [ ] 2.10 Test: too few fields `"0 9 *"` -> `null`.
  - [ ] 2.11 Test: 6-field expression `"0 9 * * 1-5 2026"` -> `null` (only 5-field supported).
  - [ ] 2.12 Run tests with `npx vitest run dashboard/lib/cron-parser.test.ts`.

- [ ] **Task 3: Integrate human-readable table into CronJobsModal** (AC: 1, 2, 3)
  - [ ] 3.1 In `CronJobsModal.tsx`, add import: `import { parseCronToTable } from "@/lib/cron-parser";`.
  - [ ] 3.2 Locate the Schedule `<td>` cell (line 245-247):
    ```tsx
    <td className="py-2 pr-4 text-muted-foreground font-mono text-xs">
      {formatSchedule(job.schedule)}
    </td>
    ```
  - [ ] 3.3 Replace the cell contents with a richer layout. For `schedule.kind === "cron"` jobs, render:
    - The existing `formatSchedule(job.schedule)` text (raw cron, preserved as-is)
    - Below it, if `parseCronToTable(job.schedule.expr!)` returns non-null, render a compact 3-column mini-table
  - [ ] 3.4 For non-cron schedules (`kind === "every"` or `kind === "at"`), render only `formatSchedule(job.schedule)` (no table).
  - [ ] 3.5 Create a small inline component or JSX block for the cron breakdown table:
    ```tsx
    {job.schedule.kind === "cron" && job.schedule.expr && (() => {
      const parsed = parseCronToTable(job.schedule.expr);
      if (!parsed) return null;
      return (
        <div className="mt-1 grid grid-cols-3 gap-x-3 text-[11px] text-muted-foreground">
          <div>
            <span className="font-medium text-foreground/70">Days</span>
            <div>{parsed.days}</div>
          </div>
          <div>
            <span className="font-medium text-foreground/70">Hours</span>
            <div>{parsed.hours}</div>
          </div>
          <div>
            <span className="font-medium text-foreground/70">Minutes</span>
            <div>{parsed.minutes}</div>
          </div>
        </div>
      );
    })()}
    ```
  - [ ] 3.6 The `font-mono` class on the `<td>` should remain for the raw cron expression but the mini-table should use `font-sans` (or simply not inherit `font-mono`). Wrap the raw expression in a `<div className="font-mono">` and let the grid below use default font.

- [ ] **Task 4: Adjust Schedule column width** (AC: 1)
  - [ ] 4.1 The Schedule column may need to be slightly wider to accommodate the 3-column breakdown. Check if the existing `<th>` and `<td>` have width constraints. If the table overflows, add `min-w-[180px]` or similar to the Schedule `<th>` (line 222).
  - [ ] 4.2 Alternatively, if the modal is `max-w-4xl` (line 178) and the table already has room, no width adjustment may be needed -- verify visually.

- [ ] **Task 5: Manual verification** (AC: 1, 2, 3, 4, 5)
  - [ ] 5.1 Open CronJobsModal with a mix of `cron`, `every`, and `at` scheduled jobs.
  - [ ] 5.2 Verify cron jobs show the raw expression AND the 3-column breakdown below it.
  - [ ] 5.3 Verify `every` and `at` jobs show only the existing format text (no table).
  - [ ] 5.4 Verify the table values are correct English (compare against crontab.guru or similar).
  - [ ] 5.5 Verify that if a cron expression is exotic/unparseable, only the raw expression is shown (graceful fallback).
  - [ ] 5.6 Verify the modal table does not overflow or look broken with the wider Schedule cells.

## Dev Notes

### Code Locations (CronJobsModal.tsx)

**Schedule display to extend (lines 245-247):**
```tsx
<td className="py-2 pr-4 text-muted-foreground font-mono text-xs">
  {formatSchedule(job.schedule)}
</td>
```

**`formatSchedule` function (lines 66-81):** Returns formatted string like `"cron: 0 9 * * 1-5 (America/New_York)"`. This stays as-is -- the new table is rendered *below* it.

**CronSchedule interface (lines 24-30):**
```tsx
interface CronSchedule {
  kind: "at" | "every" | "cron";
  atMs: number | null;
  everyMs: number | null;
  expr: string | null;    // <-- 5-field cron expression for kind="cron"
  tz: string | null;
}
```

### Architecture: Parser Design

Keep the parser pure and simple. No external cron-parsing libraries. The 5-field format is well-defined:

```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of week (0-6, 0=Sunday)
│ │ │ │ │
* * * * *
```

The parser should handle the common patterns: `*`, `*/N`, single value, comma list, range `N-M`, range with step `N-M/S`. Anything more complex (e.g., `L`, `W`, `#` non-standard extensions) returns `null` for graceful fallback.

### Mini-table Styling

Use a CSS grid (`grid grid-cols-3`) rather than a `<table>` element inside a `<td>`. Nesting `<table>` inside `<td>` is technically valid HTML but can cause layout quirks. A grid div is simpler and avoids table-in-table styling issues.

Use `text-[11px]` for the breakdown text to keep it visually subordinate to the raw cron expression above it. Use `text-muted-foreground` for values and slightly stronger `text-foreground/70` for the column headers ("Days", "Hours", "Minutes").

### Common LLM Developer Mistakes to Avoid

1. **DO NOT install a cron-parsing npm package** -- The parsing logic is simple enough to write inline. Adding a dependency for this is overkill and introduces a supply-chain risk for a UI-only feature.

2. **DO NOT modify `formatSchedule`** -- It is used for all schedule kinds and returns a well-formatted string. The new table is rendered *alongside* it, not as a replacement.

3. **DO NOT render the table for `kind !== "cron"`** -- Only `kind === "cron"` has an `expr` field. The `every` and `at` kinds use `everyMs` and `atMs` respectively, which are already human-readable via `formatSchedule`.

4. **DO NOT forget to handle `null` from `parseCronToTable`** -- The raw expression must always be visible. The table is an enhancement, not a replacement. If parsing fails, the raw expression alone is sufficient.

5. **DO NOT use 1-indexed days** -- Cron uses 0=Sunday, 1=Monday, ..., 6=Saturday. Some cron implementations accept 7=Sunday as well -- handle both 0 and 7 as Sunday.

6. **DO NOT forget edge cases for hour formatting** -- Hour 0 is "12 AM" (midnight), hour 12 is "12 PM" (noon). Do not render "0 AM" or "0 PM".

### Test Runner

Run parser unit tests with: `cd dashboard && npx vitest run lib/cron-parser.test.ts`

### Project Structure Notes

- New file: `dashboard/lib/cron-parser.ts` (pure utility, no React)
- New file: `dashboard/lib/cron-parser.test.ts` (vitest unit tests)
- Modified: `dashboard/components/CronJobsModal.tsx` (add import + table rendering)
- Existing test pattern: see `dashboard/lib/planUtils.test.ts` and `dashboard/lib/flowLayout.test.ts` for vitest test style

### References

- [Source: `dashboard/components/CronJobsModal.tsx`] -- Modal component to modify
- [Source: `dashboard/components/CronJobsModal.tsx#L24-30`] -- `CronSchedule` interface with `kind` and `expr` fields
- [Source: `dashboard/components/CronJobsModal.tsx#L66-81`] -- `formatSchedule` function (keep as-is)
- [Source: `dashboard/components/CronJobsModal.tsx#L245-247`] -- Schedule `<td>` cell to extend
- [Source: `dashboard/lib/planUtils.ts`] -- Example of existing lib utility pattern
- [Source: `dashboard/lib/planUtils.test.ts`] -- Example vitest test file in this project

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
