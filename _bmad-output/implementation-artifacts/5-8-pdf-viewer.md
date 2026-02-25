# Story 5.8: PDF Viewer

Status: review

## Story

As a **user**,
I want to view PDF files in the dashboard with page navigation and zoom,
So that I can read documents without opening an external app.

## Acceptance Criteria

1. **Given** the user opens a PDF file from the Files tab, **When** the DocumentViewerModal renders, **Then** the PDF is displayed using `react-pdf` with the first page visible (FR-F8)
2. **And** page navigation controls are present: previous page button, next page button, current-page / total-pages indicator
3. **And** zoom controls are present: zoom in, zoom out, fit-to-width
4. **And** the first page renders within 2 seconds (NFR-F3)
5. **Given** the user navigates pages, **When** next/previous is clicked, **Then** the target page renders within 500ms (NFR-F4)
6. **Given** a corrupted PDF, **When** rendering fails, **Then** an error message is shown with a Download fallback button (NFR-F13)

## Tasks / Subtasks

- [ ] Task 1: Add fit-to-width zoom mode to PdfViewer (AC: #3)
  - [ ] 1.1: Open `dashboard/components/viewers/PdfViewer.tsx`
  - [ ] 1.2: Add a `containerRef` using `useRef<HTMLDivElement>` on the scrollable PDF container div
  - [ ] 1.3: Add a `containerWidth` state variable, initialized to `null`
  - [ ] 1.4: Add a `useEffect` with a `ResizeObserver` on the container div to measure and track `containerWidth` (the inner width available for the PDF). Use `ref.current.clientWidth` minus padding (e.g., subtract 32px for py-4 padding on each side). Disconnect the observer on cleanup.
  - [ ] 1.5: Change `scale` state type from `number` to `number | "fit"` (default `"fit"`)
  - [ ] 1.6: Add a `Maximize2` icon import from lucide-react for the fit-to-width button
  - [ ] 1.7: Add a "Fit" button to the zoom controls bar (left side of zoom group) that sets `scale` to `"fit"`. Use `variant="secondary"` when active, `variant="ghost"` otherwise.
  - [ ] 1.8: When `scale === "fit"`, pass the `width={containerWidth}` prop to `<Page>` instead of the `scale` prop. When `scale` is a number, pass `scale={scale}` as before (no `width` prop).
  - [ ] 1.9: Update zoom in/out logic: when current scale is `"fit"`, zoom-in should switch to scale `1.0`; zoom-out when at `"fit"` should be disabled (already the minimum zoom level)
  - [ ] 1.10: Update the zoom percentage label: when `scale === "fit"`, display "Fit" instead of a percentage

- [ ] Task 2: Verify existing page navigation works correctly (AC: #2, #5)
  - [ ] 2.1: Confirm previous/next page buttons use `ChevronLeft`/`ChevronRight` icons and are disabled at boundaries (page 1 / last page)
  - [ ] 2.2: Confirm page indicator shows "Page X of Y" format
  - [ ] 2.3: Confirm `onDocumentLoadSuccess` callback sets `numPages` and resets `currentPage` to 1 -- already implemented

- [ ] Task 3: Verify existing error handling with download fallback (AC: #6)
  - [ ] 3.1: Confirm `onLoadError` callback sets `loadError` state to `true` -- already implemented
  - [ ] 3.2: Confirm error state renders "Unable to render this PDF." message with Download button fallback -- already implemented
  - [ ] 3.3: Verify the `onDownload` prop is called correctly from the error fallback button

- [ ] Task 4: Verify SSR skip and worker configuration (AC: #1, #4)
  - [ ] 4.1: Confirm `DocumentViewerModal.tsx` imports PdfViewer with `dynamic(() => import(...), { ssr: false })` -- already implemented
  - [ ] 4.2: Confirm worker is configured via `pdfjs.GlobalWorkerOptions.workerSrc` pointing to unpkg CDN at matching pdfjs version -- already implemented
  - [ ] 4.3: Confirm CSS imports for `react-pdf/dist/Page/AnnotationLayer.css` and `react-pdf/dist/Page/TextLayer.css` are present -- already implemented

- [ ] Task 5: Write unit tests for PdfViewer (AC: #1, #2, #3, #5, #6)
  - [ ] 5.1: Create `dashboard/components/viewers/PdfViewer.test.tsx`
  - [ ] 5.2: Mock `react-pdf` module: mock `Document` and `Page` components, mock `pdfjs` object
  - [ ] 5.3: Test: renders Document with file prop and Page with pageNumber=1 on initial load
  - [ ] 5.4: Test: calls onDocumentLoadSuccess and displays page count (simulate numPages callback)
  - [ ] 5.5: Test: previous button is disabled on page 1, next button is enabled when numPages > 1
  - [ ] 5.6: Test: clicking next increments page, clicking previous decrements page
  - [ ] 5.7: Test: next button is disabled on last page
  - [ ] 5.8: Test: zoom-in and zoom-out buttons cycle through scale steps
  - [ ] 5.9: Test: fit-to-width button sets scale to "fit" mode
  - [ ] 5.10: Test: on load error, shows error message and Download fallback button
  - [ ] 5.11: Test: Download fallback calls onDownload prop

## Dev Notes

### Critical: This Component Already Exists

The PdfViewer component is **already implemented** at `dashboard/components/viewers/PdfViewer.tsx`. The `react-pdf` package is already installed at `^10.4.0` (resolves to pdfjs-dist `5.4.296`). The `DocumentViewerModal.tsx` already dynamically imports and routes PDF files to this component.

**The primary work in this story is adding the fit-to-width zoom mode** -- the only AC not already satisfied by the existing implementation. All other features (page navigation, zoom in/out, error handling with download fallback, SSR skip, worker config) are already working.

### Existing Implementation Summary

The current `PdfViewer.tsx` (97 lines) has:
- `Document` + `Page` from `react-pdf` with annotation and text layer CSS
- Worker configured via unpkg CDN: `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`
- Page navigation: ChevronLeft/ChevronRight buttons, "Page X of Y" indicator, disabled at boundaries
- Zoom: Minus/Plus buttons cycling through `[0.5, 0.75, 1.0, 1.25, 1.5, 2.0]` scale steps
- Error handling: `loadError` state, "Unable to render this PDF." message with Download button
- Props: `{ blobUrl: string; onDownload: () => void }`

**What is missing:** fit-to-width mode. The AC specifies "zoom controls: zoom in, zoom out, fit-to-width" but the current implementation only has zoom in/out with fixed scale steps.

### Fit-to-Width Implementation Pattern

The `react-pdf` `Page` component accepts a `width` prop (pixels only, not percentage). To achieve fit-to-width:

1. Use a `useRef` on the PDF container div to measure its pixel width
2. Use `ResizeObserver` to track container width changes (responsive)
3. When in "fit" mode, pass `width={containerWidth}` to `<Page>` instead of `scale`
4. When in manual zoom mode, pass `scale={numericValue}` as before

This pattern is consistent with how `ImageViewer.tsx` handles its "fit" mode (using `"fit"` as a scale value vs numeric). Follow the same state pattern: `scale: number | "fit"` with default `"fit"`.

### Integration Point

`DocumentViewerModal.tsx` line 120 already calls:
```tsx
<PdfViewer blobUrl={blobUrl!} onDownload={handleDownload} />
```

The PdfViewer props interface does NOT need to change. The fit-to-width feature is entirely internal to PdfViewer.

### react-pdf v10 Technical Details

- **Package:** `react-pdf` ^10.4.0 (already in `dashboard/package.json`)
- **Peer dependency:** `pdfjs-dist` 5.4.296 (already resolved in package-lock.json)
- **Worker:** Configured via `pdfjs.GlobalWorkerOptions.workerSrc` -- uses unpkg CDN pointing to the exact version
- **SSR:** Must skip SSR in Next.js. Already done via `dynamic(() => import(...), { ssr: false })` in DocumentViewerModal.tsx
- **CSS imports:** `react-pdf/dist/Page/AnnotationLayer.css` and `react-pdf/dist/Page/TextLayer.css` -- already imported
- **Key components:**
  - `Document` -- wraps the PDF, accepts `file` (URL/blob), `onLoadSuccess({ numPages })`, `onLoadError`, `loading`
  - `Page` -- renders a single page, accepts `pageNumber`, `scale` (float multiplier), `width` (pixels), `renderAnnotationLayer`, `renderTextLayer`
  - `Page` `width` prop: accepts pixel value only (not percentage). When `width` is set, it overrides `scale` -- the page renders at exactly that width
- **Next.js 16 compatibility:** Next.js >= v15.0.0-canary.53 does not need special webpack config. This project uses Next.js ^16.1.5 so no extra config needed.

### File Locations

| File | Action | Purpose |
|------|--------|---------|
| `dashboard/components/viewers/PdfViewer.tsx` | MODIFY | Add fit-to-width zoom mode |
| `dashboard/components/viewers/PdfViewer.test.tsx` | CREATE | Unit tests for PdfViewer |
| `dashboard/components/DocumentViewerModal.tsx` | NO CHANGE | Already imports and uses PdfViewer |
| `dashboard/hooks/useDocumentFetch.ts` | NO CHANGE | Already handles PDF as binary blob |
| `dashboard/package.json` | NO CHANGE | react-pdf ^10.4.0 already present |

### Testing Approach

Use Vitest + React Testing Library (project standard). Mock `react-pdf` to avoid loading the actual PDF.js worker in tests:

```tsx
vi.mock("react-pdf", () => ({
  Document: ({ children, onLoadSuccess, onLoadError, ...props }: any) => {
    // Expose callbacks for test control
    return <div data-testid="pdf-document" {...props}>{children}</div>;
  },
  Page: (props: any) => <div data-testid="pdf-page" data-page={props.pageNumber} data-scale={props.scale} data-width={props.width} />,
  pdfjs: { GlobalWorkerOptions: { workerSrc: "" }, version: "5.4.296" },
}));
```

Simulate `onDocumentLoadSuccess` by finding the Document mock and calling the callback prop. Simulate `onLoadError` similarly.

### Project Structure Notes

- Viewer components live in `dashboard/components/viewers/` subdirectory (PdfViewer, MarkdownViewer, HtmlViewer, ImageViewer)
- This follows the existing pattern established by story 9-7 (now 5-7) where the viewers directory was created
- Test files should be co-located: `dashboard/components/viewers/PdfViewer.test.tsx`
- No Convex or Python changes needed -- this is a pure frontend component story

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.8: PDF Viewer] -- AC definition
- [Source: _bmad-output/planning-artifacts/epics.md#Epic 5] -- Epic context and FR/NFR coverage
- [Source: _bmad-output/planning-artifacts/architecture.md#File Viewing] -- Architecture notes on DocumentViewerModal
- [Source: _bmad-output/planning-artifacts/architecture.md#Library Decisions] -- react-pdf ^10.4.0
- [Source: _bmad-output/planning-artifacts/prd.md#FR-F8] -- PDF viewer with pages, zoom, pagination
- [Source: _bmad-output/planning-artifacts/prd.md#NFR-F3] -- Viewer renders first page within 2 seconds
- [Source: _bmad-output/planning-artifacts/prd.md#NFR-F4] -- PDF page navigation within 500ms
- [Source: _bmad-output/planning-artifacts/prd.md#NFR-F13] -- Unsupported/error fallback to download
- [Source: dashboard/components/viewers/PdfViewer.tsx] -- Existing implementation to modify
- [Source: dashboard/components/DocumentViewerModal.tsx] -- Integration point (no changes needed)
- [Source: dashboard/hooks/useDocumentFetch.ts] -- Blob URL provider (no changes needed)
- [Source: dashboard/components/viewers/ImageViewer.tsx] -- Pattern reference for fit mode state

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### Change Log
- 2026-02-25: Story created with exhaustive context analysis. Identified existing PdfViewer implementation -- primary work is adding fit-to-width zoom mode and unit tests.

### File List
