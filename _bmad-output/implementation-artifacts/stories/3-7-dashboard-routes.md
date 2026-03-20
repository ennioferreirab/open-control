# Story 3-7: Migrate remaining dashboard routes to getRuntimePath

## Story
As a developer, I need the remaining dashboard API routes (cron, skills) to use `getRuntimePath()` so the TypeScript side is fully consistent with the Python runtime home resolution.

## Status: ready

## Acceptance Criteria
- [ ] All 4 files below use `getRuntimePath()` instead of `join(homedir(), ".nanobot", ...)`
- [ ] No remaining `homedir(), ".nanobot"` in dashboard source (excluding node_modules/, tests/)
- [ ] `make validate` passes

## Tasks
- [ ] `dashboard/app/api/cron/route.ts:62` — `join(homedir(), ".nanobot", "cron", "jobs.json")` → `getRuntimePath("cron", "jobs.json")`; add import
- [ ] `dashboard/app/api/cron/[jobId]/route.ts` — lines 11, 45: same replacement (appears twice); add import
- [ ] `dashboard/app/api/skills/[skillName]/files/route.ts:18` — `join(homedir(), ".nanobot", "workspace", "skills")` → `getRuntimePath("workspace", "skills")`; add import
- [ ] `dashboard/app/api/skills/[skillName]/files/[...filePath]/route.ts:9` — same pattern; add import

## File List
- `dashboard/app/api/cron/route.ts`
- `dashboard/app/api/cron/[jobId]/route.ts`
- `dashboard/app/api/skills/[skillName]/files/route.ts`
- `dashboard/app/api/skills/[skillName]/files/[...filePath]/route.ts`

## Dev Notes
- Import: `import { getRuntimePath } from "@/lib/runtimeHome";`
- Remove the `import { homedir } from "os";` and `import { join } from "path";` imports ONLY if no other code in the file uses them
- The cron route files may have multiple occurrences of the path — replace all of them
