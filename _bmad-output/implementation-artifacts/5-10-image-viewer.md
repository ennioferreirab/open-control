# Story 5.10: Image Viewer

Status: review

## Story

As a **user**,
I want to view image files in the dashboard with zoom controls,
So that I can inspect screenshots and reference images without leaving the dashboard.

## Acceptance Criteria

1. **Given** the user opens an image file (`.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.webp`) from the Files tab, **When** the DocumentViewerModal renders, **Then** the image is displayed centered in the viewer area with zoom controls: zoom in, zoom out, fit-to-container, actual size (1:1) (FR-F12) **And** the image loads within 2 seconds (NFR-F3)
2. **Given** the user zooms in beyond the viewer area, **When** the image is larger than the container, **Then** scroll/pan is available to navigate the full image
3. **Given** a corrupted or unrecognized image, **When** rendering fails (img `onError`), **Then** a broken image placeholder is shown with a Download button as fallback (NFR-F13)
4. **And** the ImageViewer component has co-located unit tests covering zoom state transitions, error fallback rendering, and scroll/pan behavior
5. **And** all existing Vitest tests continue to pass after changes

## Tasks / Subtasks

- [ ] Task 1: Fix zoom behavior to use width/height sizing instead of CSS transform (AC: #1, #2)
  - [ ] 1.1: Open `dashboard/components/viewers/ImageViewer.tsx`
  - [ ] 1.2: Add `onLoad` handler to capture `naturalWidth` and `naturalHeight` from the `<img>` element
  - [ ] 1.3: Replace `transform: scale()` approach with explicit `width` and `height` style based on `scale * naturalWidth` / `scale * naturalHeight`
  - [ ] 1.4: Ensure the container `div` has `overflow-auto` so that when the computed width/height exceed the container, native scroll bars appear for pan/scroll
  - [ ] 1.5: Keep `"fit"` mode unchanged (uses `max-w-full max-h-full object-contain`)
  - [ ] 1.6: For numeric scale modes, render image inside the scrollable container with computed pixel dimensions

- [ ] Task 2: Refine zoom controls UX (AC: #1)
  - [ ] 2.1: Keep the existing control bar layout: Fit button, 1:1 button, zoom out (-), percentage label, zoom in (+)
  - [ ] 2.2: Ensure Fit and 1:1 buttons use `variant="secondary"` when active, `variant="ghost"` when inactive (already implemented)
  - [ ] 2.3: Verify zoom out is disabled when scale is `"fit"`, zoom in is disabled when scale is `2.0` (already implemented)
  - [ ] 2.4: Verify percentage label shows `Math.round(scale * 100)%` for numeric scales, hidden for "fit" (already implemented)

- [ ] Task 3: Verify error fallback for corrupted images (AC: #3)
  - [ ] 3.1: Confirm `onError={() => setError(true)}` is present on both `<img>` elements (fit and scaled) -- already implemented
  - [ ] 3.2: Confirm error state renders "Unable to display this image." message with Download button -- already implemented
  - [ ] 3.3: Verify the Download button calls `onDownload` prop

- [ ] Task 4: Write co-located unit tests (AC: #4, #5)
  - [ ] 4.1: Create `dashboard/components/viewers/ImageViewer.test.tsx`
  - [ ] 4.2: Test: renders image with blobUrl in fit mode by default
  - [ ] 4.3: Test: zoom in from fit mode sets scale to 1.0
  - [ ] 4.4: Test: zoom in increments through SCALES array (0.5 -> 0.75 -> 1.0 -> 1.25 -> 1.5 -> 2.0)
  - [ ] 4.5: Test: zoom out decrements through SCALES array, final zoom out returns to "fit"
  - [ ] 4.6: Test: Fit button sets scale to "fit"
  - [ ] 4.7: Test: 1:1 button sets scale to 1.0
  - [ ] 4.8: Test: zoom in disabled at maximum scale (2.0)
  - [ ] 4.9: Test: zoom out disabled in fit mode
  - [ ] 4.10: Test: error state renders fallback message and Download button
  - [ ] 4.11: Test: Download button in error state calls onDownload
  - [ ] 4.12: Test: scaled image container has overflow-auto for scroll/pan

- [ ] Task 5: Run full test suite and verify no regressions (AC: #5)
  - [ ] 5.1: Run `cd dashboard && npx vitest run` -- all tests pass
  - [ ] 5.2: Verify TypeScript type-check passes: `cd dashboard && npx tsc --noEmit`

## Dev Notes

### Critical: ImageViewer.tsx Already Exists

The `ImageViewer` component already exists at `dashboard/components/viewers/ImageViewer.tsx` and is already wired into `DocumentViewerModal.tsx`. This story is NOT about creating the component from scratch -- it is about fixing one specific behavior gap and adding test coverage.

**What already works (DO NOT recreate or rewrite):**
- Component file exists at `dashboard/components/viewers/ImageViewer.tsx`
- Import in `DocumentViewerModal.tsx` line 13: `import { ImageViewer } from "@/components/viewers/ImageViewer"`
- Invocation in `DocumentViewerModal.tsx` line 132: `<ImageViewer blobUrl={blobUrl!} filename={file!.name} onDownload={handleDownload} />`
- `useDocumentFetch` hook at `dashboard/hooks/useDocumentFetch.ts` handles binary fetch and blob URL creation for image extensions
- Type routing in `DocumentViewerModal.tsx` function `getViewerType()` correctly maps `IMAGE_EXTS` to `"image"` viewer type
- `IMAGE_EXTS` set includes: `png, jpg, jpeg, gif, svg, webp, bmp, ico`
- Zoom controls: Fit, 1:1, zoom in (+), zoom out (-) with percentage display
- Error handling: `onError` on both `<img>` elements sets error state, which renders "Unable to display this image." with Download button
- SCALES array: `[0.5, 0.75, 1.0, 1.25, 1.5, 2.0]`

**What needs fixing:**
The current implementation uses `transform: scale()` with `transformOrigin: "top center"` for zoomed images. This CSS transform scales the visual rendering but does NOT change the element's layout box size. The container has `overflow-auto` but since the `<img>` element's layout size doesn't change (only its visual scale), the scrollbars never appear. The user cannot scroll/pan a zoomed image.

**Fix approach:** Replace `transform: scale(${scale})` with explicit `width` and `height` computed from `scale * naturalWidth` / `scale * naturalHeight`. This makes the `<img>` element actually take up more space in the DOM, triggering native scrollbar overflow on the parent container.

### Current ImageViewer.tsx Code Reference

```tsx
// Current problematic section (lines 79-94):
<div className="flex-1 overflow-auto flex items-center justify-center bg-muted/20 p-4">
  {scale === "fit" ? (
    <img
      src={blobUrl}
      alt={filename}
      className="max-w-full max-h-full object-contain"
      onError={() => setError(true)}
    />
  ) : (
    <img
      src={blobUrl}
      alt={filename}
      style={{ transform: `scale(${scale})`, transformOrigin: "top center" }}
      className="block"
      onError={() => setError(true)}
    />
  )}
</div>
```

**Target fix:**

```tsx
// Add state for natural dimensions:
const [naturalSize, setNaturalSize] = useState<{ w: number; h: number } | null>(null);

const handleLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
  const img = e.currentTarget;
  setNaturalSize({ w: img.naturalWidth, h: img.naturalHeight });
};

// Replace the scaled img rendering:
<div className="flex-1 overflow-auto bg-muted/20 p-4">
  {scale === "fit" ? (
    <div className="flex items-center justify-center h-full">
      <img
        src={blobUrl}
        alt={filename}
        className="max-w-full max-h-full object-contain"
        onLoad={handleLoad}
        onError={() => setError(true)}
      />
    </div>
  ) : (
    <div className="min-h-full min-w-full inline-flex items-start justify-center">
      <img
        src={blobUrl}
        alt={filename}
        style={{
          width: naturalSize ? naturalSize.w * (scale as number) : undefined,
          height: naturalSize ? naturalSize.h * (scale as number) : undefined,
        }}
        className="block"
        onLoad={handleLoad}
        onError={() => setError(true)}
      />
    </div>
  )}
</div>
```

### Viewer Architecture Pattern

All viewers in `dashboard/components/viewers/` follow the same pattern:
- Exported as named function component: `export function XxxViewer({ ... }: Props) { ... }`
- Self-contained with own control bar (border-b, shrink-0)
- Content area fills remaining space (flex-1, overflow-auto)
- Error handling is internal to the viewer (not delegated to parent)
- Props received from `DocumentViewerModal.tsx` -- the modal handles header, download button, close button

Existing viewers for reference:
- `PdfViewer.tsx` -- `react-pdf` with page navigation and zoom (scale-based)
- `MarkdownViewer.tsx` -- `react-markdown` with rendered/raw toggle
- `HtmlViewer.tsx` -- sandboxed iframe with rendered/raw toggle

### Testing Pattern

Dashboard tests use Vitest + React Testing Library. Co-located with source: `ImageViewer.test.tsx` next to `ImageViewer.tsx`.

```tsx
// Test file structure pattern:
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { ImageViewer } from "./ImageViewer";

describe("ImageViewer", () => {
  afterEach(() => { cleanup(); });
  // ... tests
});
```

Note: To test `onError` behavior, fire an error event on the img element. To test zoom button interactions, use `fireEvent.click()`. To test that scale state changes, check button disabled states and displayed percentage text.

### Project Structure Notes

- Component location: `dashboard/components/viewers/ImageViewer.tsx` (existing -- DO NOT move)
- Test location: `dashboard/components/viewers/ImageViewer.test.tsx` (new -- co-located)
- No new files besides the test file
- No new dependencies needed -- uses only React state, native `<img>`, and ShadCN Button (already imported)
- No Convex changes, no Python changes, no API route changes

### Common LLM Developer Mistakes to Avoid

1. **DO NOT recreate ImageViewer.tsx from scratch.** The file already exists and is wired in. Only modify the zoom/scroll behavior as described.

2. **DO NOT change DocumentViewerModal.tsx.** The modal already imports and invokes ImageViewer correctly. No changes needed there.

3. **DO NOT change useDocumentFetch.ts.** The hook already handles image files as binary blobs correctly.

4. **DO NOT add new npm dependencies.** Native `<img>` element is sufficient for image viewing. No image manipulation library needed.

5. **DO NOT use CSS `transform: scale()` for zoom.** That is the current bug. Use explicit `width`/`height` computed from `naturalWidth`/`naturalHeight` instead, so the DOM layout changes and enables native scrollbar overflow.

6. **DO NOT remove `bmp` or `ico` from the IMAGE_EXTS set.** The epics AC only lists `.png, .jpg, .jpeg, .gif, .svg, .webp` but the existing implementation supports `.bmp` and `.ico` as well. Keep them -- they work with native `<img>`.

7. **DO NOT add mouse-drag panning or custom scroll logic.** Native browser scroll (overflow-auto) is sufficient for MVP. The container's scrollbars handle pan when the image is larger than the viewport.

8. **DO NOT forget `onLoad` on both img elements** (fit mode and scaled mode). The fit-mode img also needs `onLoad` to capture natural dimensions so that if the user switches from fit to a numeric scale, the dimensions are available immediately.

### What This Story Does NOT Include

- Drag-and-drop panning (post-MVP)
- Pinch-to-zoom gesture (post-MVP)
- Image rotation or flip controls (not in scope)
- Image metadata display (EXIF, dimensions -- not in scope)
- Thumbnail generation (post-MVP)
- SVG-specific rendering optimizations (native `<img>` is sufficient)

### Files Modified in This Story

| File | Changes |
|------|---------|
| `dashboard/components/viewers/ImageViewer.tsx` | Add `naturalSize` state + `onLoad` handler, replace `transform: scale()` with explicit width/height for scroll-enabled zoom |

### Files Created in This Story

| File | Purpose |
|------|---------|
| `dashboard/components/viewers/ImageViewer.test.tsx` | Co-located unit tests for zoom transitions, error fallback, and scroll behavior |

### Verification Steps

1. Open an image file from the Files tab -- verify it displays centered in fit mode
2. Click zoom in -- verify image scales up with computed width/height (not CSS transform)
3. Zoom in to 200% on a large image -- verify horizontal and vertical scrollbars appear on the container
4. Scroll the zoomed image -- verify pan works via native scrollbars
5. Click Fit -- verify image returns to fit-to-container mode, scrollbars disappear
6. Click 1:1 -- verify image displays at actual pixel dimensions
7. Open a corrupted image (rename a .txt to .png) -- verify "Unable to display this image." message with Download button
8. Click Download in error state -- verify browser download triggers
9. Run `cd dashboard && npx vitest run` -- all tests pass including new ImageViewer tests
10. Run `cd dashboard && npx tsc --noEmit` -- no type errors

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 5.10`] -- Original story definition with BDD acceptance criteria
- [Source: `_bmad-output/planning-artifacts/prd-thread-files-context.md#FR12`] -- Image files with zoom controls
- [Source: `_bmad-output/planning-artifacts/prd-thread-files-context.md#NFR3`] -- Viewer loads within 2 seconds
- [Source: `_bmad-output/planning-artifacts/prd-thread-files-context.md#NFR13`] -- Viewer fallback for unsupported/corrupted files
- [Source: `_bmad-output/planning-artifacts/architecture.md#File Viewing`] -- 9 FRs for multi-format viewer
- [Source: `_bmad-output/planning-artifacts/architecture.md#Project Structure`] -- viewers/ subfolder in components
- [Source: `dashboard/components/viewers/ImageViewer.tsx`] -- Existing component to modify
- [Source: `dashboard/components/DocumentViewerModal.tsx`] -- Parent modal (DO NOT modify)
- [Source: `dashboard/hooks/useDocumentFetch.ts`] -- Fetch hook (DO NOT modify)
- [Source: `dashboard/components/viewers/PdfViewer.tsx`] -- Sibling viewer for pattern reference
- [Source: `_bmad-output/implementation-artifacts/9-10-image-viewer.md`] -- Previous story version (old epic numbering)
- [Source: `_bmad-output/implementation-artifacts/9-7-viewer-modal-shell-with-text-and-code-viewers.md`] -- Viewer modal architecture

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
