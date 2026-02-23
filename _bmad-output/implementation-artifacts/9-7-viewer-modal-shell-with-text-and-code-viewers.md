# Story 9-7: Viewer Modal Shell with Text and Code Viewers

**Epic:** 9 — Thread Files Context: View Files in Dashboard
**Status:** ready-for-dev

## Story

As a **user**,
I want to click a file in the Files tab and see it rendered in a viewer modal with support for text and code files,
So that I can read plain text, CSV data, and syntax-highlighted code without leaving the dashboard.

## Acceptance Criteria

**Given** the Files tab is open on a task
**When** the user clicks a file entry in the file list
**Then** a `DocumentViewerModal` opens as a centered modal overlay (FR7)
**And** the modal header shows: file name, file type badge, file size
**And** the modal includes a "Download" button that triggers a browser download of the file (FR14)
**And** the modal can be closed with Escape key or clicking outside

**Given** the user opens a plain text file (`.txt`, `.csv`, `.log`, `.json`, `.xml`, `.yaml`, `.yml`)
**When** the viewer renders
**Then** the content is displayed as plain text in a monospace font with zoom controls (FR13)
**And** the viewer opens within 2 seconds for files up to 10MB (NFR3)

**Given** the user opens a code file (`.py`, `.ts`, `.tsx`, `.js`, `.jsx`, `.java`, `.go`, `.rs`, `.rb`, `.php`, `.c`, `.cpp`, `.h`, `.css`, `.scss`, `.sql`, `.sh`, `.bash`, `.zsh`, `.swift`, `.kt`)
**When** the viewer renders
**Then** the content is displayed with syntax highlighting and line numbers (FR9)
**And** the language is auto-detected from the file extension

**Given** the user opens an unsupported file type
**When** the viewer cannot render it
**Then** the modal shows "Preview not available for this file type" with a Download button (NFR13)

## Technical Notes

### Component: `components/DocumentViewerModal.tsx`
New component. Use ShadCN `Dialog` as the modal base.

```tsx
interface DocumentViewerModalProps {
  taskId: string;
  file: { name: string; type: string; size: number; subfolder: string } | null;
  onClose: () => void;
}
```

Structure:
- `Dialog` open when `file !== null`
- `DialogContent` — large, e.g. `max-w-4xl w-full h-[80vh]`
- Header: filename, type badge, human-readable size, Download button, close button
- Body: viewer area (flex-1, overflow-auto)

### Hook: `hooks/useDocumentFetch.ts`
Fetches file content from the serving API.

```ts
function useDocumentFetch(taskId: string, file: FileRef | null): {
  content: string | null;
  blobUrl: string | null;  // for binary files (PDF, images)
  loading: boolean;
  error: string | null;
}
```

- Fetch from `/api/tasks/${taskId}/files/${file.subfolder}/${file.name}`
- For text-based files (text/*, application/json, text/markdown, etc.): read as text → `content`
- For binary files (PDF, images): create `URL.createObjectURL(blob)` → `blobUrl`
- Clean up blob URLs on unmount/file change

### Type detection and viewer routing
Based on file extension (use same logic as the MIME map in route.ts):

```
TEXT_EXTS = txt, csv, log, json, xml, yaml, yml
CODE_EXTS = py, ts, tsx, js, jsx, java, go, rs, rb, php, c, cpp, h, css, scss, sql, sh, bash, zsh, swift, kt
MD_EXTS   = md, markdown  (stub for Story 9-9 — show "Markdown viewer coming soon" or render as text for now)
HTML_EXTS = html, htm     (stub for Story 9-9 — show raw text for now)
IMAGE_EXTS = png, jpg, jpeg, gif, svg, webp, bmp, ico  (stub for Story 9-10)
PDF_EXTS   = pdf           (stub for Story 9-8)
```

For stubs: render a placeholder div: `<p className="text-muted-foreground text-sm">Full viewer coming in next story.</p>`

### Text viewer
Monospace pre/code block, overflow-auto, with font-size zoom:
- State: `fontSize` (default 14)
- Buttons: A- / A+ (range 10–24px)

### Code viewer
Use `react-syntax-highlighter` with `Prism` (lighter than Highlight.js).
- Check if already in package.json — if not, add it: `npm install react-syntax-highlighter @types/react-syntax-highlighter`
- Use `PrismLight` for tree-shaking — register only needed languages, or use `Prism` for simplicity
- Language detection map from extension (py→python, ts→typescript, tsx→tsx, js→javascript, etc.)
- Show line numbers
- Theme: `vscDarkPlus` or `oneDark` — pick one that works with the dark ShadCN theme

### Download button
```tsx
const handleDownload = () => {
  const a = document.createElement("a");
  a.href = `/api/tasks/${taskId}/files/${file.subfolder}/${file.name}`;
  a.download = file.name;
  a.click();
};
```

### Wire into TaskDetailSheet
Replace the `console.log("open file", file.name)` stub in `TaskDetailSheet.tsx` with:
```tsx
const [viewerFile, setViewerFile] = useState<FileRef | null>(null);
// ...
onClick={() => setViewerFile(file)}
// ...
<DocumentViewerModal taskId={task._id} file={viewerFile} onClose={() => setViewerFile(null)} />
```

## NFRs Covered
- NFR3: Viewer opens within 2 seconds for files up to 10MB
- NFR13: Unsupported file types show download fallback
