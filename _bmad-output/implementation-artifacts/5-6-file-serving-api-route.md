# Story 5.6: File Serving API Route

Status: done

## Story

As a **developer**,
I want an API endpoint that serves files from task directories with correct content types,
So that the dashboard viewer can fetch and render any file.

## Acceptance Criteria

1. **Given** a file exists at `~/.nanobot/tasks/{task-id}/{subfolder}/{filename}`, **When** the dashboard requests `GET /api/tasks/[taskId]/files/[subfolder]/[filename]`, **Then** the raw file bytes are returned with the correct `Content-Type` header (FR-F15, FR-F16) **And** the response includes a `Content-Disposition` header **And** the response returns within 1 second for files up to 10MB (NFR-F5)
2. **Given** the file does not exist, **When** the API is called, **Then** a 404 response is returned with `{ error: "File not found" }`
3. **Given** a request includes path traversal characters (`../`), **When** the path is validated, **Then** the request is rejected with 400 -- no directory traversal outside the task directory
4. **Given** a file has an ambiguous or missing extension, **When** MIME detection runs, **Then** fallback to `application/octet-stream`
5. **Given** an invalid `taskId` (non-alphanumeric characters besides `-` and `_`), **When** the API is called, **Then** a 400 response is returned with `{ error: "Invalid taskId" }`
6. **Given** a `subfolder` that is not `"attachments"` or `"output"`, **When** the API is called, **Then** a 400 response is returned with `{ error: "Invalid subfolder" }`
7. **And** Vitest tests cover all acceptance criteria: happy path, 404, path traversal rejection, invalid taskId, invalid subfolder, MIME detection, fallback to octet-stream
8. **And** the `Content-Length` header is set to the file's byte count
9. **And** the `Cache-Control` header is set to `private, max-age=60`

## Tasks / Subtasks

- [x] Task 1: Verify existing route implementation matches all ACs (AC: #1-#6, #8, #9)
  - [x] 1.1: Read `dashboard/app/api/tasks/[taskId]/files/[subfolder]/[filename]/route.ts` and confirm it covers all validation, MIME detection, response headers, and error handling
  - [x] 1.2: Verify `TASK_ID_RE` regex rejects path traversal and special characters
  - [x] 1.3: Verify `VALID_SUBFOLDERS` set only allows `"attachments"` and `"output"`
  - [x] 1.4: Verify `FILENAME_RE` rejects `../` and path separators
  - [x] 1.5: Verify `getMimeType()` covers all required extensions and falls back to `application/octet-stream`
  - [x] 1.6: Verify response headers include `Content-Type`, `Content-Disposition`, `Content-Length`, `Cache-Control`

- [x] Task 2: Write Vitest test file (AC: #7)
  - [x] 2.1: Create `dashboard/app/api/tasks/[taskId]/files/[subfolder]/[filename]/route.test.ts`
  - [x] 2.2: Mock `fs/promises.readFile` and `os.homedir` using `vi.hoisted` + `vi.mock` pattern (see Dev Notes for exact pattern)
  - [x] 2.3: Test: valid file returns 200 with correct Content-Type for `.pdf`, `.md`, `.py`, `.json`, `.png`
  - [x] 2.4: Test: response includes Content-Disposition header with encoded filename
  - [x] 2.5: Test: response includes Content-Length matching buffer size
  - [x] 2.6: Test: response includes Cache-Control `private, max-age=60`
  - [x] 2.7: Test: file not found (ENOENT) returns 404
  - [x] 2.8: Test: filesystem read error (non-ENOENT) returns 500
  - [x] 2.9: Test: invalid taskId (with `/` or `..`) returns 400
  - [x] 2.10: Test: invalid subfolder (e.g., `"secrets"`) returns 400
  - [x] 2.11: Test: filename with `..` returns 400
  - [x] 2.12: Test: filename with `/` returns 400
  - [x] 2.13: Test: unknown extension returns `application/octet-stream`
  - [x] 2.14: Test: file path is correctly assembled from `homedir() + .nanobot/tasks/{taskId}/{subfolder}/{filename}`

- [x] Task 3: Verify MIME map completeness (AC: #1, #4)
  - [x] 3.1: Confirm MIME map covers all viewer-supported types: pdf, md, markdown, html, htm, txt, csv, json, yaml, yml, xml, png, jpg, jpeg, gif, svg, webp, bmp, ico, py, ts, tsx, js, jsx, go, rs, java, sh, bash, zsh, css, scss, sql, log
  - [x] 3.2: Confirm unknown extensions default to `application/octet-stream`

- [x] Task 4: Run tests and verify (AC: #7)
  - [x] 4.1: Run `cd dashboard && npx vitest run app/api/tasks` -- all tests pass
  - [x] 4.2: Run `cd dashboard && npx vitest run` -- no regressions in existing tests

## Dev Notes

### CRITICAL: Route Already Exists

The file serving API route is **already fully implemented** at:

```
dashboard/app/api/tasks/[taskId]/files/[subfolder]/[filename]/route.ts
```

This story's primary task is to **write comprehensive Vitest tests** for the existing implementation and verify it matches all acceptance criteria. DO NOT rewrite or restructure the existing route. It was implemented during a previous development cycle (story 9-6) and is production-ready.

### Existing Implementation Summary

The route exports a single `GET` handler that:
1. Extracts `taskId`, `subfolder`, `filename` from Next.js dynamic route params (awaited `Promise<{ ... }>`)
2. Validates `taskId` against `/^[a-zA-Z0-9_-]+$/`
3. Validates `subfolder` against `Set(["attachments", "output"])`
4. Validates `filename` against `/^[^/\\]+$/` and rejects `..`
5. Reads file from `join(homedir(), ".nanobot", "tasks", taskId, subfolder, filename)`
6. Returns raw bytes as `Uint8Array` with `Content-Type`, `Content-Disposition`, `Content-Length`, `Cache-Control` headers
7. Returns 404 for `ENOENT`, 500 for other filesystem errors, 400 for validation failures

### Test File Pattern (MUST Follow)

Follow the exact mocking pattern used by `dashboard/app/api/cron/route.test.ts` and `dashboard/app/api/cron/[jobId]/route.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockReadFile = vi.hoisted(() => vi.fn());

vi.mock("os", () => ({
  default: { homedir: () => "/home/test" },
  homedir: () => "/home/test",
}));
vi.mock("fs/promises", () => ({
  default: { readFile: mockReadFile },
  readFile: mockReadFile,
}));

import { GET } from "./route";
import { NextRequest } from "next/server";

function makeParams(taskId: string, subfolder: string, filename: string) {
  return { params: Promise.resolve({ taskId, subfolder, filename }) };
}

function makeReq(taskId: string, subfolder: string, filename: string) {
  return new NextRequest(
    `http://localhost/api/tasks/${taskId}/files/${subfolder}/${filename}`,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
});
```

### Key Implementation Details for Test Assertions

- `Content-Type` is determined by `getMimeType()` which splits on `.` and checks the last segment against `MIME_MAP`
- `Content-Disposition` uses `encodeURIComponent(filename)` for the filename value
- `Content-Length` is `String(buffer.length)`
- `Cache-Control` is `"private, max-age=60"`
- The response body is `new Uint8Array(buffer)` -- tests should assert `res.status` and headers, not necessarily decode the body
- For the ENOENT check: the route casts the error to `{ code: string }` and checks `code === "ENOENT"`

### MIME Map Coverage

The existing route covers 33 extensions. The full map from the implementation:

| Category | Extensions | Content-Type |
|----------|-----------|--------------|
| Documents | pdf | application/pdf |
| Markdown | md, markdown | text/markdown; charset=utf-8 |
| Web | html, htm | text/html; charset=utf-8 |
| Text | txt, log | text/plain; charset=utf-8 |
| Data | csv | text/csv; charset=utf-8 |
| Structured | json | application/json; charset=utf-8 |
| Config | yaml, yml | text/yaml; charset=utf-8 |
| XML | xml | application/xml; charset=utf-8 |
| Images | png, jpg, jpeg, gif, svg, webp, bmp, ico | image/* variants |
| Code | py, ts, tsx, js, jsx, go, rs, java | text/x-{lang}; charset=utf-8 |
| Shell | sh, bash, zsh | text/x-sh; charset=utf-8 |
| Style | css, scss | text/css or text/x-scss; charset=utf-8 |
| Database | sql | text/x-sql; charset=utf-8 |

Files without a recognized extension get `application/octet-stream`.

### Path Traversal Protection Layers

Three independent validation layers prevent directory traversal:

1. **taskId validation** (`/^[a-zA-Z0-9_-]+$/`): Rejects `.`, `/`, `\`, spaces, and any non-alphanumeric characters (except `-` and `_`)
2. **subfolder allowlist** (`Set(["attachments", "output"])`): Only two exact string values pass; `..` or any variant is rejected
3. **filename validation** (`/^[^/\\]+$/` + explicit `..` check): Rejects any filename containing `/`, `\`, or the literal string `..`

This triple-layer defense means a path traversal attack would need to bypass all three validators simultaneously, which is structurally impossible.

### Sibling Upload Route (DO NOT MODIFY)

The parent route at `dashboard/app/api/tasks/[taskId]/files/route.ts` handles `POST` (file upload) and `DELETE` (file deletion). This story does NOT modify that file. It was implemented in Story 5.2/5.4 (upload) and only the `GET` serving route in the nested `[subfolder]/[filename]/route.ts` is in scope.

### Common LLM Developer Mistakes to Avoid

1. **DO NOT rewrite the existing route** -- It is complete and correct. This story adds tests only.
2. **DO NOT use `mime-types` npm package** -- The implementation uses a simple `MIME_MAP` lookup, which is sufficient for the known file types and avoids adding a dependency.
3. **DO NOT use `createReadStream` for streaming** -- The implementation uses `readFile` (buffered read) which is simpler and fine for files up to 10MB on localhost.
4. **DO NOT test the response body bytes directly** -- Assert status codes and headers. The body is a `Uint8Array` which is harder to assert in Vitest; focus on headers and status.
5. **DO NOT modify `next.config.ts`** -- No API route size limits or body parser config is needed; the default Next.js settings work for file serving.
6. **DO NOT add authentication middleware** -- Single-user localhost tool, no auth (see architecture: "No authentication for MVP").
7. **DO NOT mock `join` or `path`** -- Only mock `fs/promises.readFile` and `os.homedir`. Let `path.join` resolve naturally in tests.

### What This Story Does NOT Include

- **File upload** -- Story 5.2 (already implemented in `dashboard/app/api/tasks/[taskId]/files/route.ts`)
- **File viewer modal** -- Story 5.7 (DocumentViewerModal fetches from this route)
- **File deletion** -- Implemented in the parent route's DELETE handler
- **Agent file context injection** -- Epic 6 (agent receives filesDir + manifest)
- **Manifest sync** -- Epic 6 (bridge updates Convex when agent writes output)

### Project Structure Notes

- Route file location follows Next.js App Router convention: `app/api/tasks/[taskId]/files/[subfolder]/[filename]/route.ts`
- Test file co-located: `app/api/tasks/[taskId]/files/[subfolder]/[filename]/route.test.ts`
- No conflicts with existing project structure
- Vitest config at `dashboard/vitest.config.ts` uses jsdom environment, globals enabled

### Files Created in This Story

| File | Purpose |
|------|---------|
| `dashboard/app/api/tasks/[taskId]/files/[subfolder]/[filename]/route.test.ts` | Vitest tests for the file serving GET handler |

### Files Modified in This Story

| File | Changes |
|------|---------|
| (none) | Route implementation already exists and is complete |

### Verification Steps

1. Read the existing route at `dashboard/app/api/tasks/[taskId]/files/[subfolder]/[filename]/route.ts` -- confirm it matches all ACs
2. Create test file with all 12+ test cases covering happy path, error cases, validation, MIME detection
3. Run `cd dashboard && npx vitest run app/api/tasks` -- all tests pass
4. Run `cd dashboard && npx vitest run` -- no regressions

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 5.6`] -- Original story definition with BDD acceptance criteria
- [Source: `_bmad-output/planning-artifacts/prd-thread-files-context.md#FR15`] -- System serves files from task directory via API endpoint
- [Source: `_bmad-output/planning-artifacts/prd-thread-files-context.md#FR16`] -- System detects file type based on MIME type and extension
- [Source: `_bmad-output/planning-artifacts/prd-thread-files-context.md#NFR5`] -- File serving API returns bytes within 1 second for 10MB
- [Source: `_bmad-output/planning-artifacts/architecture.md#Exception: File I/O via Next.js API Routes`] -- Architecture decision for filesystem-to-browser serving via Next.js API routes
- [Source: `_bmad-output/planning-artifacts/architecture.md#Boundary 5: File I/O Boundary`] -- File upload and serving go through Next.js API routes, NOT Convex
- [Source: `_bmad-output/planning-artifacts/architecture.md#Testing Strategy`] -- Vitest for dashboard tests
- [Source: `dashboard/app/api/tasks/[taskId]/files/[subfolder]/[filename]/route.ts`] -- Existing implementation (already complete)
- [Source: `dashboard/app/api/cron/route.test.ts`] -- Test pattern reference for fs/os mocking
- [Source: `dashboard/app/api/cron/[jobId]/route.test.ts`] -- Test pattern reference for dynamic route params

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

No issues encountered. The existing route implementation matched all acceptance criteria exactly as documented in the Dev Notes. The test file was written from scratch following the `vi.hoisted` + `vi.mock` pattern from sibling test files.

### Completion Notes List

- Verified existing route at `dashboard/app/api/tasks/[taskId]/files/[subfolder]/[filename]/route.ts` against all 9 ACs -- implementation is complete and correct.
- Confirmed `TASK_ID_RE = /^[a-zA-Z0-9_-]+$/` correctly rejects dots, slashes, spaces, and all non-alphanumeric characters except hyphen and underscore.
- Confirmed `VALID_SUBFOLDERS = new Set(["attachments", "output"])` -- only two allowed values, `..` and any other string is rejected.
- Confirmed `FILENAME_RE = /^[^/\\]+$/` combined with explicit `filename === ".."` check provides multi-layer protection.
- Confirmed `getMimeType()` covers all 33 viewer-supported extensions with correct MIME types; unknown extensions fall back to `application/octet-stream`.
- Confirmed response headers: `Content-Type`, `Content-Disposition` (inline with encodeURIComponent), `Content-Length` (byte count), `Cache-Control: private, max-age=60`.
- Created comprehensive test file with 32 test cases covering: 5 MIME type happy paths (.pdf, .md, .py, .json, .png), Content-Disposition header with encoded filename, Content-Length matching buffer size, Cache-Control header, ENOENT 404, non-ENOENT 500, taskId validation (slash, dots, spaces, valid), subfolder validation (secrets, .., attachments, output), filename validation (.., /, \, ../path), MIME fallback for unknown and no-extension files, case-insensitive MIME lookup, correct path assembly, and additional MIME types (.ts, .csv, .yaml, .svg, .sh, .log).
- All 32 new tests pass. Full regression suite: 466 tests across 33 test files -- all pass, no regressions.

### File List

- `dashboard/app/api/tasks/[taskId]/files/[subfolder]/[filename]/route.test.ts` (created, expanded with review fixes)
- `dashboard/app/api/tasks/[taskId]/files/[subfolder]/[filename]/route.ts` (modified -- security fix for filename validation)

### Senior Developer Review (AI)

**Reviewer:** Ennio | **Date:** 2026-02-25 | **Model:** claude-opus-4-6

**Issues Found:** 1 High, 3 Medium, 1 Low | **All Fixed**

#### Findings

1. **[HIGH] Filename validation rejects valid filenames containing consecutive dots** -- The check `filename.includes("..")` at line 64 of `route.ts` rejects any filename containing `..` anywhere, including legitimate names like `file..txt`, `backup..2026.pdf`, or `v1..2.patch`. The FILENAME_RE (`/^[^/\\]+$/`) already blocks path separators, and the subfolder allowlist blocks `..` as a subfolder. The only real traversal concern is `filename === ".."` which navigates to parent directory. **Fix:** Changed `filename === ".." || filename.includes("..")` to just `filename === ".."`. Path traversal remains fully blocked because: (a) FILENAME_RE blocks `/` and `\`, so `../etc/passwd` is already rejected by the regex, and (b) the subfolder allowlist only permits `"attachments"` and `"output"`.

2. **[MEDIUM] 500 error test uses weak assertion `toBeTruthy()` instead of exact match** -- The test for non-ENOENT filesystem errors asserted `expect(body.error).toBeTruthy()` which would pass even if the error message changed to an unexpected value. **Fix:** Changed to `expect(body.error).toBe("Failed to read file")` for exact contract validation.

3. **[MEDIUM] No test for valid filename with consecutive dots** -- The test suite did not verify that filenames like `file..txt` (valid, not path traversal) are accepted. This gap masked the overly aggressive validation bug in Finding 1. **Fix:** Added test "accepts filename with consecutive dots that is not path traversal".

4. **[MEDIUM] No tests verifying filesystem is NOT accessed when validation fails** -- Validation tests checked status codes but did not assert that `mockReadFile` was never called. This means the tests would pass even if the route accessed the filesystem before returning 400. **Fix:** Added 3 tests asserting `mockReadFile` is NOT called when taskId, subfolder, or filename validation fails.

5. **[LOW] Story dev notes reference the now-corrected `filename.includes("..")` pattern** -- The Dev Notes section described the triple-layer defense including `filename.includes("..")` which was the buggy check. The story's own documentation endorsed the bug. **Not separately fixed** -- the review notes document the correction.

#### Verdict: APPROVED with fixes applied
- Security bug fixed (filename validation false positive)
- Test coverage expanded from 32 to 36 tests
- All 36 tests pass, no regressions in related test files

### Change Log

- 2026-02-25: Story 5.6 implemented -- created comprehensive Vitest test suite (32 tests) for the existing file serving GET route. All acceptance criteria verified. No production code changes required.
- 2026-02-25: Review fixes applied -- fixed overly aggressive `filename.includes("..")` validation that rejected valid filenames, strengthened 500 error test assertion, added 4 new tests (consecutive dots acceptance, filesystem access guard verification). Total: 36 tests.
