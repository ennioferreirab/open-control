# Story 9-10: Image Viewer

**Epic:** 9 — Thread Files Context: View Files in Dashboard
**Status:** ready-for-dev

## Story

As a **user**,
I want to view image files in the dashboard with zoom controls,
So that I can inspect screenshots, charts, and reference images without downloading them.

## Acceptance Criteria

**Given** the user opens an image file (`.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.webp`, `.bmp`, `.ico`)
**When** the DocumentViewerModal renders
**Then** the image is displayed centered in the viewer area (FR12)
**And** zoom controls are available: zoom in, zoom out, fit-to-container, actual size (1:1)
**And** the image loads within 2 seconds for files up to 10MB (NFR3)

**Given** the image file is corrupted
**When** the viewer attempts to render it
**Then** a broken image placeholder is shown with the Download button as fallback (NFR13)

## Technical Notes

- Create `components/viewers/ImageViewer.tsx`
- Props: `{ blobUrl: string; filename: string; onDownload: () => void }`
- Use a native `<img>` element with `src={blobUrl}`
- Zoom state: `scale` (default "fit") — values: "fit" | 0.5 | 1 | 1.5 | 2
- For "fit": `max-w-full max-h-full object-contain`
- For numeric scale: `width: scale * naturalWidth` (use `onLoad` to get naturalWidth/naturalHeight)
- Show zoom controls: Fit | 1:1 | + | - (or use percentage like 50%, 100%, 150%, 200%)
- On `img` `onError`: set error state → show "Unable to display image" + Download button
- Wire into `DocumentViewerModal.tsx`: replace the `image` stub with `<ImageViewer blobUrl={blobUrl!} filename={file.name} onDownload={handleDownload} />`
