# Story 9-8: PDF Viewer

**Epic:** 9 — Thread Files Context: View Files in Dashboard
**Status:** ready-for-dev

## Story

As a **user**,
I want to view PDF files in the dashboard with page navigation and zoom,
So that I can read documents like financial reports and contracts without opening an external app.

## Acceptance Criteria

**Given** the user opens a PDF file from the Files tab
**When** the DocumentViewerModal renders
**Then** the PDF is displayed using react-pdf with the first page visible (FR8)
**And** page navigation controls: previous page, next page, current page / total pages
**And** zoom controls: zoom in, zoom out, fit-to-width
**And** first page renders within 2 seconds for files up to 10MB (NFR3)

**Given** the user clicks next/previous page
**When** navigation is triggered
**Then** the target page renders within 500ms (NFR4)

**Given** a PDF file is corrupted or cannot be parsed
**When** the viewer attempts to render it
**Then** an error message is shown with the Download button as fallback (NFR13)

## Technical Notes

- Install `react-pdf` and configure PDF.js worker for Next.js
  - `npm install react-pdf` (includes pdfjs-dist)
  - Worker config: in the PdfViewer component, set `pdfjs.GlobalWorkerOptions.workerSrc` to use the bundled worker
  - Use `pdfjs-dist/build/pdf.worker.min.mjs` path or CDN approach — check react-pdf docs for Next.js setup
- Create `components/viewers/PdfViewer.tsx` (keep viewers in a subdirectory)
- Props: `{ blobUrl: string }` — the blobUrl comes from `useDocumentFetch` (already created in 9-7)
- Use `react-pdf`'s `Document` and `Page` components
- State: `numPages`, `currentPage` (1-indexed), `scale` (default 1.0)
- Controls bar:
  - Previous / Next page buttons (ChevronLeft / ChevronRight from lucide)
  - Page indicator: "Page X of Y"
  - Zoom out / Zoom in buttons (ZoomOut / ZoomIn or Minus / Plus) — scale steps: 0.5, 0.75, 1.0, 1.25, 1.5, 2.0
- On load error: show error message + Download fallback
- Replace the "Full viewer coming soon" stub for `viewerType === "pdf"` in `DocumentViewerModal.tsx` with `<PdfViewer blobUrl={blobUrl!} />`

## NFRs Covered
- NFR3: First page renders within 2 seconds for files up to 10MB
- NFR4: PDF page navigation renders within 500ms
