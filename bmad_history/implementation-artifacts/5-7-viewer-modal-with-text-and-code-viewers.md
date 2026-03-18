# Story 5.7: Viewer Modal with Text and Code Viewers

Status: done

## Story

As a **user**,
I want to click a file and see it rendered in a viewer modal with support for text and code files,
So that I can read content and syntax-highlighted code without leaving the dashboard.

## Acceptance Criteria

1. **Given** the Files tab is open, **When** the user clicks a file entry, **Then** a `DocumentViewerModal` opens showing the file (FR-F7) **And** the modal header shows: file name, size, type badge **And** a "Download" button triggers browser download (FR-F14) **And** the modal closes with Escape or clicking outside
2. **Given** the user opens a plain text file (`.txt`, `.csv`, `.log`, `.json`, `.xml`, `.yaml`), **When** the viewer renders, **Then** content is displayed in monospace font with zoom controls (FR-F13) **And** renders within 2 seconds for files up to 10MB (NFR-F3)
3. **Given** the user opens a code file (`.py`, `.ts`, `.tsx`, `.js`, `.jsx`, etc.), **When** the viewer renders, **Then** content is displayed with syntax highlighting via `react-syntax-highlighter` and line numbers (FR-F9) **And** language is auto-detected from file extension
4. **Given** the user opens an unsupported file type, **When** the viewer cannot render it, **Then** a message shows: "Preview not available" with a Download button as fallback (NFR-F13)

## CRITICAL: This Feature Is Already Fully Implemented

**The `DocumentViewerModal` component and all supporting infrastructure already exist and are fully functional.** This was implemented during the old epic 9 (Thread Files Context) stories 9-6 through 9-10. The code is production-quality and covers ALL acceptance criteria above plus more (PDF, Markdown, HTML, Image viewers).

### Existing Files That Fulfill This Story

| File | Status | What It Does |
|------|--------|-------------|
| `dashboard/components/DocumentViewerModal.tsx` | COMPLETE | Full modal with text viewer, code viewer (syntax highlighting), zoom controls, download button, type badge, unsupported fallback |
| `dashboard/hooks/useDocumentFetch.ts` | COMPLETE | Fetches file content (text) or blob URL (binary) from the file serving API |
| `dashboard/app/api/tasks/[taskId]/files/[subfolder]/[filename]/route.ts` | COMPLETE | File serving API with MIME detection, path traversal protection, Content-Disposition header |
| `dashboard/components/TaskDetailSheet.tsx` | COMPLETE | Files tab with click-to-open wiring to DocumentViewerModal |
| `dashboard/components/viewers/PdfViewer.tsx` | COMPLETE | PDF viewer (Story 5.8 scope, but already built) |
| `dashboard/components/viewers/MarkdownViewer.tsx` | COMPLETE | Markdown viewer (Story 5.9 scope, but already built) |
| `dashboard/components/viewers/HtmlViewer.tsx` | COMPLETE | HTML viewer (Story 5.9 scope, but already built) |
| `dashboard/components/viewers/ImageViewer.tsx` | COMPLETE | Image viewer (Story 5.10 scope, but already built) |

### What the Dev Agent Must Do

This story requires **verification and testing only** -- no new component creation. The dev agent must:

1. Verify each acceptance criterion against the existing implementation
2. Write tests that prove compliance (no tests exist yet for DocumentViewerModal)
3. Fix any gaps found during verification (if any)

## Tasks / Subtasks

- [x] Task 1: Verify AC #1 -- Modal opens from Files tab click (AC: #1)
  - [x] 1.1: Confirm `TaskDetailSheet.tsx` wires file clicks to `setViewerFile(file)` on line 430 (attachments) and line 470 (outputs)
  - [x] 1.2: Confirm `DocumentViewerModal.tsx` opens when `file !== null` via `<Dialog open={file !== null}>` on line 144
  - [x] 1.3: Confirm modal header shows file name (`DialogTitle` line 148), type badge (`Badge` with extension, line 149), and size (`formatSize`, line 150)
  - [x] 1.4: Confirm Download button exists in header (line 153-155) and triggers browser download via anchor click (line 68-74)
  - [x] 1.5: Confirm modal closes with Escape/outside click via `onOpenChange` on line 144

- [x] Task 2: Verify AC #2 -- Text viewer with zoom controls (AC: #2)
  - [x] 2.1: Confirm `TEXT_EXTS` set on line 30 contains `txt`, `csv`, `log`, `json`, `xml`, `yaml`, `yml`
  - [x] 2.2: Confirm text viewer renders `<pre>` with `font-mono` class (line 91)
  - [x] 2.3: Confirm zoom controls exist: Minus button (line 87), font size display (line 88), Plus button (line 89)
  - [x] 2.4: Confirm zoom range is 10-24px via `Math.max(10, s - 2)` and `Math.min(24, s + 2)`

- [x] Task 3: Verify AC #3 -- Code viewer with syntax highlighting (AC: #3)
  - [x] 3.1: Confirm `CODE_EXTS` set on line 31 contains `py`, `ts`, `tsx`, `js`, `jsx`, `java`, `go`, `rs`, `rb`, `php`, `c`, `cpp`, `h`, `css`, `scss`, `sql`, `sh`, `bash`, `zsh`, `swift`, `kt`
  - [x] 3.2: Confirm code viewer uses `SyntaxHighlighter` from `react-syntax-highlighter` with `vscDarkPlus` theme (lines 105-113)
  - [x] 3.3: Confirm `showLineNumbers` prop is set (line 108)
  - [x] 3.4: Confirm language auto-detection from `LANG_MAP` record (lines 36-41) using file extension
  - [x] 3.5: Confirm zoom controls exist for code viewer (lines 100-103), same pattern as text viewer

- [x] Task 4: Verify AC #4 -- Unsupported file fallback (AC: #4)
  - [x] 4.1: Confirm `getViewerType()` returns `"unsupported"` for unknown extensions (line 61)
  - [x] 4.2: Confirm unsupported fallback renders "Preview not available for this file type." message (line 137) with Download button (line 138)

- [x] Task 5: Write Vitest tests for DocumentViewerModal (AC: #1-4)
  - [x] 5.1: Create `dashboard/components/DocumentViewerModal.test.tsx`
  - [x] 5.2: Test: modal renders when file prop is non-null, shows file name, size, and type badge
  - [x] 5.3: Test: modal does not render when file is null
  - [x] 5.4: Test: text file renders with monospace pre and zoom controls
  - [x] 5.5: Test: code file renders SyntaxHighlighter with correct language prop
  - [x] 5.6: Test: unsupported file type shows "Preview not available" with Download button
  - [x] 5.7: Test: Download button creates anchor with correct href and download attribute
  - [x] 5.8: Test: `getViewerType()` returns correct type for each extension category (verified via rendered output)
  - [x] 5.9: Test: zoom controls increment/decrement fontSize within bounds (10-24)

- [x] Task 6: Write Vitest tests for useDocumentFetch hook (AC: #2, #3)
  - [x] 6.1: Create `dashboard/hooks/useDocumentFetch.test.ts`
  - [x] 6.2: Test: returns `{ content: null, blobUrl: null, loading: false, error: null }` when file is null
  - [x] 6.3: Test: fetches text content for non-binary file extensions
  - [x] 6.4: Test: fetches blob URL for binary file extensions (pdf, png, jpg, etc.)
  - [x] 6.5: Test: sets error on fetch failure
  - [x] 6.6: Test: cleans up blob URL on file change

## Dev Notes

### Architecture: Everything Is Already Built

The entire DocumentViewerModal component tree was implemented during the old epic 9 (Thread Files Context) under stories 9-6 through 9-10. The architecture document at `_bmad-output/planning-artifacts/architecture.md` explicitly confirms this:

> `DocumentViewerModal.tsx` -- Already built -- multi-format viewer (line 788)

The component is fully wired into `TaskDetailSheet.tsx` (line 496-500), which passes the selected file and task ID. The `useDocumentFetch` hook handles fetching from the file serving API at `/api/tasks/[taskId]/files/[subfolder]/[filename]`.

### react-syntax-highlighter Version and Usage

- **Installed version:** `react-syntax-highlighter@16.1.0` (in `dashboard/package.json` line 49)
- **Types installed:** `@types/react-syntax-highlighter@15.5.13` (line 36)
- **Import pattern used in this project:** Default import from `react-syntax-highlighter` with Prism styles from `react-syntax-highlighter/dist/esm/styles/prism`
- **Theme:** `vscDarkPlus` in DocumentViewerModal, `oneDark` in ArtifactRenderer -- both are valid Prism themes
- **Known pattern:** The project uses two different import styles:
  - `DocumentViewerModal.tsx`: `import SyntaxHighlighter from "react-syntax-highlighter"` (default export)
  - `ArtifactRenderer.tsx`: `import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"` (named Prism export)
  - Both work. The default export also uses Prism under the hood when paired with Prism style imports.

### File Type Detection Logic

The `getViewerType()` function in `DocumentViewerModal.tsx` routes files to the correct viewer based on extension:

```
pdf       -> "pdf"       (PdfViewer, dynamic import with ssr: false)
image     -> "image"     (ImageViewer)
code      -> "code"      (SyntaxHighlighter with Prism)
markdown  -> "markdown"  (MarkdownViewer with react-markdown)
html      -> "html"      (HtmlViewer with sandboxed iframe)
text      -> "text"      (pre block with monospace font)
*         -> "unsupported" (fallback message + Download)
```

Priority order matters: PDF and images are checked before code to prevent `.svg` from matching as code.

### useDocumentFetch Hook Behavior

The hook at `dashboard/hooks/useDocumentFetch.ts`:
- Determines binary vs text based on `BINARY_EXTS` set (pdf, png, jpg, jpeg, gif, webp, bmp, ico, svg)
- For text files: `res.text()` -> sets `content`
- For binary files: `res.blob()` -> `URL.createObjectURL(blob)` -> sets `blobUrl`
- Cleans up blob URLs on unmount/file change via `useEffect` cleanup
- Dependency array: `[taskId, file?.name, file?.subfolder]`

### File Serving API Route

`dashboard/app/api/tasks/[taskId]/files/[subfolder]/[filename]/route.ts`:
- Validates taskId format (`/^[a-zA-Z0-9_-]+$/`), subfolder (`attachments` or `output`), filename (no path separators)
- Rejects path traversal (`..`)
- Reads from `~/.nanobot/tasks/{taskId}/{subfolder}/{filename}`
- Returns file with correct Content-Type from MIME map, fallback `application/octet-stream`
- Sets `Content-Disposition: inline` with encoded filename
- Caches privately for 60 seconds

### Download Implementation

```tsx
const handleDownload = () => {
  if (!file) return;
  const a = document.createElement("a");
  a.href = `/api/tasks/${taskId}/files/${file.subfolder}/${encodeURIComponent(file.name)}`;
  a.download = file.name;
  a.click();
};
```

This triggers a browser download by creating and clicking an anchor element. The `download` attribute forces download instead of navigation.

### Testing Strategy

**No tests exist yet** for `DocumentViewerModal` or `useDocumentFetch`. This story's primary value-add is creating comprehensive test coverage.

Testing framework: **Vitest** with `@testing-library/react` and `jsdom`.

Key mocking requirements for DocumentViewerModal tests:
- Mock `useDocumentFetch` to return controlled content/blobUrl/loading/error states
- Mock `react-syntax-highlighter` (heavy dependency, render check only)
- Mock `next/dynamic` for PdfViewer dynamic import
- Mock `URL.createObjectURL` and `URL.revokeObjectURL` for blob URL tests

For useDocumentFetch tests:
- Mock global `fetch` to return text or blob responses
- Mock `URL.createObjectURL` and `URL.revokeObjectURL`
- Use `renderHook` from `@testing-library/react`

### Existing Test Patterns in the Project

Examine these files for testing conventions:
- `dashboard/components/StepCard.test.tsx` -- Component testing pattern with mocked Convex queries
- `dashboard/components/TaskCard.test.tsx` -- Another component test example
- `dashboard/components/ArtifactRenderer.test.tsx` -- Tests for a component that also uses `react-syntax-highlighter`
- `dashboard/components/PreKickoffModal.test.tsx` -- Modal component testing pattern

### Common LLM Developer Mistakes to Avoid

1. **DO NOT create a new DocumentViewerModal component** -- It already exists at `dashboard/components/DocumentViewerModal.tsx` and is fully functional. Read it first.

2. **DO NOT install react-syntax-highlighter** -- It is already in `package.json` at version 16.1.0 with types at 15.5.13.

3. **DO NOT create new viewer components** -- `PdfViewer`, `MarkdownViewer`, `HtmlViewer`, and `ImageViewer` all exist in `dashboard/components/viewers/`.

4. **DO NOT wire DocumentViewerModal into TaskDetailSheet** -- It is already wired on line 496-500 of `TaskDetailSheet.tsx`.

5. **DO NOT create a useDocumentFetch hook** -- It exists at `dashboard/hooks/useDocumentFetch.ts`.

6. **DO NOT create the file serving API route** -- It exists at `dashboard/app/api/tasks/[taskId]/files/[subfolder]/[filename]/route.ts`.

7. **DO NOT modify any existing component code unless a specific gap is found** -- The purpose of this story is verification and test creation.

8. **DO NOT use `import { Prism as SyntaxHighlighter }` in the modal** -- The existing code uses the default import `import SyntaxHighlighter from "react-syntax-highlighter"`. Keep it consistent within the file.

9. **When writing tests, DO NOT forget to mock heavy dependencies** -- `react-syntax-highlighter`, `react-pdf`, and `next/dynamic` must be mocked or tests will fail or be extremely slow.

10. **DO NOT use `vi.mock` with incorrect module paths** -- The project uses `@/` path aliases. Mock `@/hooks/useDocumentFetch` not `../../hooks/useDocumentFetch`.

### What This Story Does NOT Include

- **PDF viewer** -- That is Story 5.8 (already built as `PdfViewer.tsx`)
- **HTML and Markdown viewers** -- That is Story 5.9 (already built as `HtmlViewer.tsx` and `MarkdownViewer.tsx`)
- **Image viewer** -- That is Story 5.10 (already built as `ImageViewer.tsx`)
- **File serving API** -- That is Story 5.6 (already built as the API route)
- **File upload** -- That is Story 5.2 and 5.4
- **Files tab** -- That is Story 5.3

### Project Structure Notes

All components follow the established project structure:
- Components in `dashboard/components/` (flat, no subdirectories except `ui/` and `viewers/`)
- Hooks in `dashboard/hooks/`
- API routes in `dashboard/app/api/`
- Tests co-located next to their source files (e.g., `Component.test.tsx` next to `Component.tsx`)
- Hook tests in `dashboard/hooks/` directory

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 5.7`] -- Original story definition with BDD acceptance criteria
- [Source: `_bmad-output/planning-artifacts/epics.md#FR-F7`] -- Open file in multi-format viewer modal
- [Source: `_bmad-output/planning-artifacts/epics.md#FR-F9`] -- Code viewer with syntax highlighting
- [Source: `_bmad-output/planning-artifacts/epics.md#FR-F13`] -- Text/CSV viewer with zoom
- [Source: `_bmad-output/planning-artifacts/epics.md#FR-F14`] -- Download file from viewer
- [Source: `_bmad-output/planning-artifacts/epics.md#NFR-F3`] -- Viewer opens within 2 seconds for files up to 10MB
- [Source: `_bmad-output/planning-artifacts/epics.md#NFR-F13`] -- Unsupported type fallback with download
- [Source: `_bmad-output/planning-artifacts/architecture.md#DocumentViewerModal.tsx`] -- Architecture confirms "Already built -- multi-format viewer"
- [Source: `_bmad-output/implementation-artifacts/9-7-viewer-modal-shell-with-text-and-code-viewers.md`] -- Original implementation story from epic 9
- [Source: `dashboard/components/DocumentViewerModal.tsx`] -- Existing implementation (167 lines)
- [Source: `dashboard/hooks/useDocumentFetch.ts`] -- Existing hook (66 lines)
- [Source: `dashboard/app/api/tasks/[taskId]/files/[subfolder]/[filename]/route.ts`] -- Existing API route (92 lines)
- [Source: `dashboard/components/TaskDetailSheet.tsx#L496-500`] -- Existing wiring of modal
- [Source: `dashboard/package.json#L49`] -- react-syntax-highlighter@16.1.0 already installed

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — implementation was straightforward verification and test creation.

### Completion Notes List

- Verified all 4 ACs against existing `DocumentViewerModal.tsx` and `useDocumentFetch.ts` — all ACs met by existing code with no gaps found.
- AC #1: Modal opens via `<Dialog open={file !== null}>`, header shows file name (DialogTitle), type badge (Badge with uppercase extension), size (formatSize), and Download button triggers anchor `.click()`.
- AC #2: `TEXT_EXTS` set covers txt/csv/log/json/xml/yaml/yml. Text viewer renders `<pre className="...font-mono">` with zoom controls (Minus/Plus buttons, 10–24px range).
- AC #3: `CODE_EXTS` covers py/ts/tsx/js/jsx/java/go/rs/rb/php/c/cpp/h/css/scss/sql/sh/bash/zsh/swift/kt. Code viewer uses `SyntaxHighlighter` from `react-syntax-highlighter` with `vscDarkPlus` theme, `showLineNumbers`, and language from `LANG_MAP`.
- AC #4: `getViewerType()` returns `"unsupported"` for unknown extensions and the fallback renders "Preview not available for this file type." with a Download button.
- Created `DocumentViewerModal.test.tsx` with 34 tests covering all 4 ACs.
- Created `useDocumentFetch.test.ts` with 12 tests covering null file, text fetch, binary fetch, URL construction, error handling, and blob URL cleanup.
- Pre-existing failures in `PlanStepCard.test.tsx` (10 tests) and `PlanEditor.test.tsx` (9 tests) are unrelated to this story and were failing before this work.

### File List

- `dashboard/components/DocumentViewerModal.test.tsx` — NEW — 34 Vitest tests for DocumentViewerModal component
- `dashboard/hooks/useDocumentFetch.test.ts` — NEW — 12 Vitest tests for useDocumentFetch hook
- `dashboard/components/DocumentViewerModal.tsx` — VERIFIED (no changes needed)
- `dashboard/hooks/useDocumentFetch.ts` — VERIFIED (no changes needed)

## Senior Developer Review (AI)

**Reviewer:** claude-sonnet-4-6
**Date:** 2026-02-25
**Result:** APPROVED WITH FIXES

### AC Verification

| AC | Status | Notes |
|----|--------|-------|
| AC #1 — Modal opens, header shows name/size/badge, Download button, Escape/outside close | IMPLEMENTED | `<Dialog open={file !== null}>`, DialogTitle, Badge, formatSize, handleDownload, onOpenChange |
| AC #2 — Text viewer with monospace pre and zoom controls (10-24px) | IMPLEMENTED | TEXT_EXTS set, `<pre className="...font-mono">`, Math.max/min clamp |
| AC #3 — Code viewer with syntax highlighting, line numbers, auto-detected language | IMPLEMENTED | CODE_EXTS set, SyntaxHighlighter with vscDarkPlus, showLineNumbers, LANG_MAP |
| AC #4 — Unsupported file type shows "Preview not available" with Download fallback | IMPLEMENTED | getViewerType() returns "unsupported", fallback renders message + Download button |

### Issues Found

#### MEDIUM-1: TypeScript compile error in test — null not assignable to file type (FIXED)

**File:** `dashboard/hooks/useDocumentFetch.test.ts:258`

**Error:** `TS2322: Type 'null' is not assignable to type '{ name: string; subfolder: string; }'`

The `renderHook` generic inferred `initialProps` type as `{ file: { name: string; subfolder: string } }` (non-nullable), so the later `rerender({ file: null })` was a TypeScript type error. The tests still ran because Vitest compiles with esbuild (no type checking), but `tsc --noEmit` flagged it.

**Fix:** Added explicit type annotation `as { name: string; subfolder: string } | null` to `initialProps` to widen the type and allow `null` on rerender.

```ts
// Before (triggers TS2322)
{ initialProps: { file: textFile } }

// After (explicit nullable type)
{ initialProps: { file: textFile as { name: string; subfolder: string } | null } }
```

#### MEDIUM-2: Download test does not verify encodeURIComponent is applied (FIXED)

**File:** `dashboard/components/DocumentViewerModal.test.tsx`

The existing download test used `baseFile` with `name: "readme.txt"` — a plain filename with no special characters. `encodeURIComponent("readme.txt") === "readme.txt"`, so the test would pass even if `encodeURIComponent` were removed from the component. This is a test quality failure: the assertion does not falsify against the defect it's meant to catch.

**Fix:** Added a new test `"Download button URL-encodes filename with special characters"` using `name: "my report (2).txt"` and asserting the href contains `my%20report%20(2).txt`.

#### MEDIUM-3: Missing test for SVG routing — SVG must go to image viewer, not code viewer (FIXED)

**File:** `dashboard/components/DocumentViewerModal.test.tsx`

`getViewerType()` checks `IMAGE_EXTS.has(ext)` before `CODE_EXTS.has(ext)`, which correctly routes `.svg` to the image viewer. However, no test exercised this path. If someone reordered the checks, SVG would fall through to `CODE_EXTS` (it is not in that set), then `TEXT_EXTS`, and finally `"unsupported"` — a silent regression.

**Fix:** Added test `"routes .svg to image viewer (not code viewer)"` that asserts `image-viewer` is rendered and `syntax-highlighter` is absent.

#### LOW-1: Missing tests for .htm and .yml extension aliases (FIXED)

**File:** `dashboard/components/DocumentViewerModal.test.tsx`

`HTML_EXTS` contains both `"html"` and `"htm"`. `TEXT_EXTS` contains both `"yaml"` and `"yml"`. Only `"html"` and `"yaml"` were tested, leaving the aliases untested. While these are low-risk paths, an adversarial edit removing `"htm"` or `"yml"` from the Sets would not be caught.

**Fix:** Added `"renders .htm as html viewer"` and `"renders .yml as text viewer (pre with font-mono)"` tests.

#### LOW-2: Async drain uses single Promise.resolve() — fragile for multi-tick chains (NOT FIXED — accepted)

**File:** `dashboard/hooks/useDocumentFetch.test.ts` (all async tests)

The pattern `await act(async () => { await Promise.resolve() })` flushes only one microtask tick. The `useDocumentFetch` fetch chain has multiple ticks: `fetch` resolves → `.then(async res => await res.text())` → setState → `.finally()`. Tests pass because `vi.fn().mockResolvedValue()` returns already-settled promises and testing-library's `act()` implementation flushes enough. However, this is environmental — a more robust drain would be `await act(async () => { await new Promise(r => setTimeout(r, 0)) })` or `await vi.waitFor(...)`.

**Decision:** Accepted as-is. All 50 tests pass consistently and the pattern is intentional. Upgrading to `waitFor` would require refactoring every async test and is out of scope for this story.

### Test Results After Fixes

```
Test Files  2 passed (2)
      Tests  50 passed (50)  [was 46 before review]
   Duration  2.87s
```

4 new tests added; 0 tests removed; 0 pre-existing failures introduced.
