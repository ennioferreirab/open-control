# Story 9-6: File Serving API Route

**Epic:** 9 — Thread Files Context: View Files in Dashboard
**Status:** ready-for-dev

## Story

As a **developer**,
I want an API endpoint that serves files from task directories with correct content types,
So that the dashboard viewer can fetch and render any file stored on the filesystem.

## Acceptance Criteria

**Given** a file exists at `~/.nanobot/tasks/{task-id}/{subfolder}/{filename}`
**When** the dashboard requests `GET /api/tasks/[taskId]/files/[subfolder]/[filename]`
**Then** the API route returns the raw file bytes with the correct `Content-Type` header based on file extension and MIME type detection (FR15, FR16)
**And** the response includes `Content-Disposition: inline; filename="{filename}"` header
**And** the response returns within 1 second for files up to 10MB (NFR5)

**Given** the requested file does not exist
**When** the API route is called
**Then** a 404 response is returned with a clear error message

**Given** a request includes path traversal characters (e.g., `../`)
**When** the API route validates the path
**Then** the request is rejected with a 400 response

**Given** a file has an ambiguous or missing extension
**When** MIME type detection runs
**Then** the system falls back to `application/octet-stream`

## Technical Notes

- Extend the existing `app/api/tasks/[taskId]/files/route.ts` with a `GET` handler
  - OR create a separate nested route: `app/api/tasks/[taskId]/files/[subfolder]/[filename]/route.ts`
  - Prefer the nested route for cleaner URL structure matching the spec: `/api/tasks/{taskId}/files/{subfolder}/{filename}`
- Validate `taskId`: `/^[a-zA-Z0-9_-]+$/` — 400 if invalid
- Validate `subfolder`: must be `"attachments"` or `"output"` only — 400 otherwise (prevents traversal)
- Validate `filename`: no path separators (`/`, `\`, `..`) — 400 if invalid
- File path: `~/.nanobot/tasks/{taskId}/{subfolder}/{filename}`
- Use `mime-types` npm package for MIME detection from extension — check if already in package.json; if not, use a simple extension-to-MIME map for the MVP types (pdf, md, html, txt, csv, png, jpg, jpeg, gif, svg, webp, json, yaml, py, ts, tsx, js, jsx, etc.)
- Return raw bytes with `Content-Type` and `Content-Disposition: inline; filename="{filename}"` headers
- Use `fs.readFile` or streaming via `fs.createReadStream` — streaming preferred for larger files
- 404 if file not found (`ENOENT`)
- After the route exists, update the `onClick` stub in `TaskDetailSheet.tsx` (the `console.log("open file", file.name)`) to instead open the viewer (stub for Story 9-7, for now just leave the console.log — the viewer integration happens in 9-7)

## NFRs Covered

- NFR5: File serving API returns file bytes within 1 second for files up to 10MB
