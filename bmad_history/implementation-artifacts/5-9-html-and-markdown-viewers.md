# Story 5.9: HTML and Markdown Viewers

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to view HTML and Markdown files in rendered mode with a raw source toggle,
So that I can read agent-produced reports and inspect the source when needed.

## Acceptance Criteria

1. **Given** the user opens an HTML file (`.html`, `.htm`) from the Files tab, **When** the DocumentViewerModal renders, **Then** the HTML is displayed in a sandboxed iframe using `srcDoc` with `sandbox="allow-same-origin"` (FR-F10)
2. **And** a "Raw / Rendered" toggle toolbar is visible above the content area, defaulting to "Rendered"
3. **And** clicking "Raw" shows the HTML source with full syntax highlighting via `react-syntax-highlighter` (language `html`) with line numbers
4. **And** scripts embedded in the HTML do NOT execute because the sandbox attribute blocks `allow-scripts`
5. **Given** the user opens a Markdown file (`.md`, `.markdown`) from the Files tab, **When** the DocumentViewerModal renders, **Then** the Markdown is rendered as formatted HTML using `react-markdown` with `remark-gfm` (FR-F11)
6. **And** the rendered Markdown supports: headings (h1-h6), paragraphs, ordered/unordered lists, tables, fenced code blocks with syntax highlighting, bold, italic, links (open in new tab), blockquotes, horizontal rules, and inline code
7. **And** a "Raw / Rendered" toggle toolbar is visible above the content area, defaulting to "Rendered"
8. **And** clicking "Raw" shows the raw Markdown source in monospace font (`whitespace-pre-wrap`)
9. **And** both viewers open and render content within 2 seconds for files up to 10 MB (NFR-F3)
10. **And** the toggle state is local per viewer instance (not persisted across modal opens)

## Tasks / Subtasks

- [ ] Task 1: Verify HtmlViewer component exists and meets acceptance criteria (AC: #1, #2, #3, #4)
  - [ ] 1.1: Open `dashboard/components/viewers/HtmlViewer.tsx` and confirm it already exists
  - [ ] 1.2: Verify it uses `<iframe srcDoc={content} sandbox="allow-same-origin">` for rendered mode
  - [ ] 1.3: Verify the sandbox attribute does NOT include `allow-scripts` -- scripts must not execute
  - [ ] 1.4: Verify the "Raw / Rendered" toggle uses `react-syntax-highlighter` with language `html`, `vscDarkPlus` theme, and `showLineNumbers`
  - [ ] 1.5: Verify the toggle defaults to "rendered" mode via `useState<"rendered" | "raw">("rendered")`
  - [ ] 1.6: Confirm the iframe has `title="HTML preview"` for accessibility
  - [ ] 1.7: If any of the above are missing or incorrect, fix them

- [ ] Task 2: Verify MarkdownViewer component exists and meets acceptance criteria (AC: #5, #6, #7, #8)
  - [ ] 2.1: Open `dashboard/components/viewers/MarkdownViewer.tsx` and confirm it already exists
  - [ ] 2.2: Verify it uses `react-markdown` with `remarkPlugins={[remarkGfm]}` for rendered mode
  - [ ] 2.3: Verify the code block rendering uses `react-syntax-highlighter` with `vscDarkPlus` for fenced code blocks (language-detected via `className` regex)
  - [ ] 2.4: Verify inline code does NOT get syntax highlighting (only fenced code blocks with a language class)
  - [ ] 2.5: Verify "Raw" mode shows raw Markdown in `<pre className="font-mono text-sm whitespace-pre-wrap break-all">`
  - [ ] 2.6: Verify the rendered Markdown supports ALL required elements: headings, lists, tables, code blocks, bold/italic, links, blockquotes, horizontal rules
  - [ ] 2.7: If tables do not render (remark-gfm missing or misconfigured), fix the plugin chain
  - [ ] 2.8: If any of the above are missing or incorrect, fix them

- [ ] Task 3: Verify DocumentViewerModal wiring is correct (AC: #1, #5, #9)
  - [ ] 3.1: Open `dashboard/components/DocumentViewerModal.tsx`
  - [ ] 3.2: Confirm `getViewerType()` returns `"markdown"` for `.md` and `.markdown` extensions
  - [ ] 3.3: Confirm `getViewerType()` returns `"html"` for `.html` and `.htm` extensions
  - [ ] 3.4: Confirm the render switch case routes `viewerType === "markdown"` to `<MarkdownViewer content={content ?? ""} />`
  - [ ] 3.5: Confirm the render switch case routes `viewerType === "html"` to `<HtmlViewer content={content ?? ""} />`
  - [ ] 3.6: Confirm that `useDocumentFetch` fetches HTML and Markdown files as text (not binary) -- verify they are NOT in the `BINARY_EXTS` set in `hooks/useDocumentFetch.ts`

- [ ] Task 4: Write Vitest unit tests for HtmlViewer (AC: #1, #2, #3, #4)
  - [ ] 4.1: Create `dashboard/components/viewers/HtmlViewer.test.tsx`
  - [ ] 4.2: Test: renders with "Rendered" mode active by default (button has `variant="secondary"`)
  - [ ] 4.3: Test: renders an iframe with `sandbox="allow-same-origin"` and `srcDoc` set to the content prop
  - [ ] 4.4: Test: sandbox attribute does NOT contain `allow-scripts`
  - [ ] 4.5: Test: clicking "Raw" button switches to raw mode showing SyntaxHighlighter with language `html`
  - [ ] 4.6: Test: clicking "Rendered" button switches back to iframe mode
  - [ ] 4.7: Test: iframe has `title="HTML preview"` attribute

- [ ] Task 5: Write Vitest unit tests for MarkdownViewer (AC: #5, #6, #7, #8)
  - [ ] 5.1: Create `dashboard/components/viewers/MarkdownViewer.test.tsx`
  - [ ] 5.2: Test: renders with "Rendered" mode active by default
  - [ ] 5.3: Test: renders Markdown content (verify ReactMarkdown is in the DOM)
  - [ ] 5.4: Test: clicking "Raw" button shows raw Markdown in a `<pre>` element with monospace font
  - [ ] 5.5: Test: clicking "Rendered" button switches back to rendered mode
  - [ ] 5.6: Test: raw mode displays exact source text (not rendered HTML)

- [ ] Task 6: Manual verification of Markdown element support (AC: #6)
  - [ ] 6.1: Create or use a test Markdown file containing ALL supported elements: `# Heading`, `**bold**`, `*italic*`, `- list item`, `1. ordered`, `| table |`, `` ```code``` ``, `> blockquote`, `---`, `[link](url)`, `` `inline code` ``
  - [ ] 6.2: Open the file in the DocumentViewerModal and verify each element renders correctly
  - [ ] 6.3: Verify tables render with proper borders/styling (remark-gfm must be active)
  - [ ] 6.4: Verify fenced code blocks have syntax highlighting with the correct language
  - [ ] 6.5: Verify links open in a new tab (if `target="_blank"` is configured in component overrides)

## Dev Notes

### Critical: Both Viewer Components Already Exist

**This story is primarily a VERIFICATION and TESTING story.** The `HtmlViewer.tsx` and `MarkdownViewer.tsx` components were already created as part of the old Epic 9 implementation cycle. They are already wired into `DocumentViewerModal.tsx`. The key work here is:

1. **Verify** the existing implementations match ALL acceptance criteria
2. **Fix** any gaps (especially around Markdown element support and security)
3. **Write unit tests** that did not exist before (no test files exist for any viewer components currently)

### Existing Component Inventory

| Component | Path | Status |
|-----------|------|--------|
| `HtmlViewer` | `dashboard/components/viewers/HtmlViewer.tsx` | EXISTS -- 34 lines, uses sandboxed iframe + SyntaxHighlighter raw toggle |
| `MarkdownViewer` | `dashboard/components/viewers/MarkdownViewer.tsx` | EXISTS -- 47 lines, uses react-markdown + remarkGfm + SyntaxHighlighter for code blocks |
| `DocumentViewerModal` | `dashboard/components/DocumentViewerModal.tsx` | EXISTS -- 167 lines, already routes to both viewers |
| `useDocumentFetch` | `dashboard/hooks/useDocumentFetch.ts` | EXISTS -- fetches text content for non-binary files |

### Existing HtmlViewer Implementation (Current State)

```tsx
// dashboard/components/viewers/HtmlViewer.tsx
"use client";
import { useState } from "react";
import SyntaxHighlighter from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Button } from "@/components/ui/button";

export function HtmlViewer({ content }: { content: string }) {
  const [mode, setMode] = useState<"rendered" | "raw">("rendered");

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-4 py-2 border-b shrink-0">
        <Button variant={mode === "rendered" ? "secondary" : "ghost"} size="sm" onClick={() => setMode("rendered")}>Rendered</Button>
        <Button variant={mode === "raw" ? "secondary" : "ghost"} size="sm" onClick={() => setMode("raw")}>Raw</Button>
      </div>
      <div className="flex-1 overflow-hidden">
        {mode === "rendered" ? (
          <iframe
            srcDoc={content}
            sandbox="allow-same-origin"
            className="w-full h-full border-0"
            title="HTML preview"
          />
        ) : (
          <div className="h-full overflow-auto">
            <SyntaxHighlighter language="html" style={vscDarkPlus} showLineNumbers customStyle={{ margin: 0, height: "100%", borderRadius: 0 }}>
              {content}
            </SyntaxHighlighter>
          </div>
        )}
      </div>
    </div>
  );
}
```

**Verdict:** Meets all AC. Sandbox is `"allow-same-origin"` only (no `allow-scripts`). Raw mode uses SyntaxHighlighter with language `html` and line numbers. Has `title="HTML preview"`.

### Existing MarkdownViewer Implementation (Current State)

```tsx
// dashboard/components/viewers/MarkdownViewer.tsx
"use client";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import SyntaxHighlighter from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Button } from "@/components/ui/button";

export function MarkdownViewer({ content }: { content: string }) {
  const [mode, setMode] = useState<"rendered" | "raw">("rendered");

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-4 py-2 border-b shrink-0">
        <Button variant={mode === "rendered" ? "secondary" : "ghost"} size="sm" onClick={() => setMode("rendered")}>Rendered</Button>
        <Button variant={mode === "raw" ? "secondary" : "ghost"} size="sm" onClick={() => setMode("raw")}>Raw</Button>
      </div>
      <div className="flex-1 overflow-auto p-6">
        {mode === "rendered" ? (
          <div className="text-sm leading-relaxed">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code(props) {
                  const { className, children } = props;
                  const match = /language-(\w+)/.exec(className ?? "");
                  if (match) {
                    return (
                      <SyntaxHighlighter language={match[1]} style={vscDarkPlus} PreTag="div">
                        {String(children).replace(/\n$/, "")}
                      </SyntaxHighlighter>
                    );
                  }
                  return <code className={className}>{children}</code>;
                },
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
        ) : (
          <pre className="font-mono text-sm whitespace-pre-wrap break-all">{content}</pre>
        )}
      </div>
    </div>
  );
}
```

**Verdict:** Mostly meets AC. Uses `react-markdown` v10.1.0 with `remark-gfm` v4.0.1. Code blocks get syntax highlighting. However:
- Missing explicit component overrides for links (`target="_blank"`), tables (styled borders), headings, blockquotes, etc.
- The existing `MarkdownRenderer.tsx` (used in thread view) has comprehensive component overrides -- the MarkdownViewer should ideally have similar coverage.
- **POTENTIAL GAP:** Links may not open in new tab without explicit `a` component override. Tables may render unstyled without explicit `table`/`th`/`td` overrides.

### Potential Gap: MarkdownViewer Styling vs MarkdownRenderer

The project has TWO Markdown rendering components:

1. **`MarkdownRenderer.tsx`** (at `dashboard/components/MarkdownRenderer.tsx`) -- Used in thread messages. Has comprehensive component overrides for: `code`, `pre`, `p`, `ul`, `ol`, `li`, `h1`, `h2`, `h3`, `blockquote`, `a` (with `target="_blank"`), `strong`, `em`, `hr`, `table`, `thead`, `th`, `td`.

2. **`MarkdownViewer.tsx`** (at `dashboard/components/viewers/MarkdownViewer.tsx`) -- Used in the file viewer. Only overrides `code`. Missing overrides for links, tables, headings, etc.

**The developer SHOULD enhance MarkdownViewer to include the same component overrides as MarkdownRenderer**, or at minimum add overrides for:
- `a` -- to set `target="_blank" rel="noopener noreferrer"` (links must open in new tab, not navigate away from the dashboard)
- `table`/`thead`/`th`/`td` -- to ensure tables render with visible borders and proper alignment
- `h1`/`h2`/`h3` -- for proper heading sizing

**DO NOT replace MarkdownViewer with MarkdownRenderer** -- they serve different contexts (viewer modal vs. inline thread message) and may need different styling.

### Installed Dependencies (Already Present)

All required packages are already installed in `dashboard/package.json`:

| Package | Version | Purpose |
|---------|---------|---------|
| `react-markdown` | ^10.1.0 | Markdown-to-React rendering |
| `remark-gfm` | ^4.0.1 | GitHub Flavored Markdown (tables, strikethrough, task lists, autolinks) |
| `react-syntax-highlighter` | ^16.1.0 | Code syntax highlighting for both raw HTML and Markdown code blocks |

**DO NOT run `npm install` for any of these packages.** They are already present.

### DocumentViewerModal Routing (Already Wired)

The `DocumentViewerModal.tsx` already includes the correct routing logic:

```tsx
const MD_EXTS = new Set(["md", "markdown"]);
const HTML_EXTS = new Set(["html", "htm"]);

function getViewerType(name: string): "text" | "code" | "markdown" | "html" | "image" | "pdf" | "unsupported" {
  const ext = getExt(name);
  // ...
  if (MD_EXTS.has(ext)) return "markdown";
  if (HTML_EXTS.has(ext)) return "html";
  // ...
}

// In renderContent():
if (viewerType === "markdown") {
  return <MarkdownViewer content={content ?? ""} />;
}
if (viewerType === "html") {
  return <HtmlViewer content={content ?? ""} />;
}
```

**This is already correct.** No changes needed to DocumentViewerModal routing.

### useDocumentFetch -- HTML and MD are text files

The `useDocumentFetch` hook in `dashboard/hooks/useDocumentFetch.ts` classifies files as binary or text based on `BINARY_EXTS`:

```tsx
const BINARY_EXTS = new Set(["pdf", "png", "jpg", "jpeg", "gif", "webp", "bmp", "ico", "svg"]);
```

HTML and Markdown extensions (`.html`, `.htm`, `.md`, `.markdown`) are NOT in this set, so they are fetched as text via `res.text()` and available as `content`. **This is correct -- no changes needed.**

### Security: Sandboxed Iframe Best Practices

The `sandbox="allow-same-origin"` attribute on the iframe is the correct security posture for this use case:

- **`allow-same-origin`** -- Required so the iframe can access `srcDoc` content properly and CSS renders correctly.
- **`allow-scripts` is NOT included** -- This prevents any `<script>` tags in the HTML from executing, which is critical since agents may produce HTML with embedded scripts.
- **`allow-forms` is NOT included** -- Prevents form submissions from the iframe.
- **`allow-popups` is NOT included** -- Prevents the iframe from opening new windows.

**CRITICAL: NEVER add `allow-scripts` to the sandbox attribute.** If both `allow-scripts` and `allow-same-origin` are present, the embedded content could remove the sandbox entirely, defeating all security.

Reference: [MDN iframe sandbox documentation](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/iframe), [Iframe Security Best Practices 2026](https://qrvey.com/blog/iframe-security/).

### Test Strategy

No viewer component tests currently exist in the project. The test files to create:

| Test File | Testing |
|-----------|---------|
| `dashboard/components/viewers/HtmlViewer.test.tsx` | Toggle behavior, iframe sandbox attributes, SyntaxHighlighter in raw mode |
| `dashboard/components/viewers/MarkdownViewer.test.tsx` | Toggle behavior, ReactMarkdown rendered output, raw mode pre element |

Use Vitest + React Testing Library (`@testing-library/react`), following existing patterns in the project (e.g., `dashboard/components/StepCard.test.tsx`, `dashboard/components/CronJobsModal.test.tsx`).

**Mocking strategy:**
- Mock `react-syntax-highlighter` -- it does not render meaningfully in jsdom. Verify it receives the correct `language` prop.
- Mock `react-markdown` -- or let it render and check for output elements (headings, lists, etc.).
- Use `fireEvent.click()` to test toggle behavior.

### Project Structure Notes

- All viewer components live in `dashboard/components/viewers/` -- follow this convention.
- Test files live next to their source files (e.g., `HtmlViewer.test.tsx` in the same `viewers/` directory).
- Run tests with: `cd dashboard && npx vitest run`
- Run TypeScript type check with: `cd dashboard && npx tsc --noEmit`

### Common LLM Developer Mistakes to Avoid

1. **DO NOT install `react-markdown`, `remark-gfm`, or `react-syntax-highlighter`** -- they are already installed. Running `npm install` will modify `package-lock.json` unnecessarily.

2. **DO NOT install `@tailwindcss/typography`** -- the project does not use Tailwind typography plugin. The MarkdownViewer uses custom component overrides instead of `prose` classes.

3. **DO NOT replace MarkdownViewer with MarkdownRenderer** -- they serve different contexts. MarkdownViewer is for the file viewer modal; MarkdownRenderer is for inline thread messages.

4. **DO NOT add `allow-scripts` to the iframe sandbox** -- this would create a critical security vulnerability when combined with `allow-same-origin`.

5. **DO NOT create a new `useDocumentFetch` hook or modify the existing one** -- it already handles HTML and Markdown files as text correctly.

6. **DO NOT modify `DocumentViewerModal.tsx` routing** -- the viewer type detection and component routing are already correct.

7. **DO NOT use `dangerouslySetInnerHTML` for HTML rendering** -- use the sandboxed iframe with `srcDoc`. The iframe provides proper isolation.

8. **DO NOT forget to add `target="_blank" rel="noopener noreferrer"` to the `a` component override** in MarkdownViewer if adding link support -- otherwise clicking a link in a rendered Markdown file will navigate away from the dashboard.

9. **DO NOT create test files in `dashboard/__tests__/` or `dashboard/tests/`** -- test files go next to their source in `dashboard/components/viewers/`.

### What This Story Does NOT Include

- **PDF viewing** -- That is Story 5.8 (already implemented as `PdfViewer.tsx`)
- **Image viewing** -- That is Story 5.10 (already implemented as `ImageViewer.tsx`)
- **Text/Code viewing** -- That is Story 5.7 (already implemented in `DocumentViewerModal.tsx` inline)
- **File upload or file serving** -- Those are earlier stories in Epic 5
- **New dependencies** -- All required packages are already installed

### Verification Steps

1. Open an `.html` file from the Files tab -- verify it renders in a sandboxed iframe
2. Toggle to "Raw" -- verify HTML source is shown with syntax highlighting and line numbers
3. Toggle back to "Rendered" -- verify iframe shows again
4. Inspect the iframe element in browser DevTools -- confirm `sandbox="allow-same-origin"` (no `allow-scripts`)
5. Open an `.md` file from the Files tab -- verify it renders as formatted Markdown
6. Verify headings, bold, italic, lists, tables, code blocks, links, blockquotes all render correctly
7. Toggle to "Raw" -- verify raw Markdown source in monospace font
8. Toggle back to "Rendered" -- verify formatted view returns
9. Click a link in rendered Markdown -- verify it opens in a new tab (not navigating away)
10. Run `cd dashboard && npx vitest run` -- all tests pass
11. Run `cd dashboard && npx tsc --noEmit` -- no new type errors

### Files Created in This Story

| File | Purpose |
|------|---------|
| `dashboard/components/viewers/HtmlViewer.test.tsx` | Unit tests for HtmlViewer toggle, sandbox, raw mode |
| `dashboard/components/viewers/MarkdownViewer.test.tsx` | Unit tests for MarkdownViewer toggle, rendering, raw mode |

### Files Modified in This Story

| File | Changes |
|------|---------|
| `dashboard/components/viewers/MarkdownViewer.tsx` | Add component overrides for `a` (target blank), `table`/`th`/`td` (styled borders), `h1`/`h2`/`h3` (heading sizes), `blockquote`, `hr`, `ul`/`ol` if missing |

### Files NOT Modified (Already Correct)

| File | Reason |
|------|--------|
| `dashboard/components/viewers/HtmlViewer.tsx` | Already meets all AC -- sandboxed iframe, raw/rendered toggle, syntax highlighting |
| `dashboard/components/DocumentViewerModal.tsx` | Already routes `markdown` and `html` viewer types correctly |
| `dashboard/hooks/useDocumentFetch.ts` | Already fetches HTML/MD as text content |
| `dashboard/package.json` | All dependencies already installed |

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 5.9`] -- Original story definition with BDD acceptance criteria
- [Source: `_bmad-output/planning-artifacts/epics.md#Epic 5 FR/NFR`] -- FR-F10 (HTML viewer), FR-F11 (Markdown viewer), NFR-F3 (viewer < 2s)
- [Source: `_bmad-output/planning-artifacts/architecture.md#Technology Decisions`] -- react-markdown ^10.1.0, react-syntax-highlighter ^16.1.0, remark-gfm ^4.0.1
- [Source: `_bmad-output/planning-artifacts/architecture.md#Component Mapping`] -- DocumentViewerModal.tsx listed as "Already complete -- reused as-is"
- [Source: `dashboard/components/viewers/HtmlViewer.tsx`] -- Existing HTML viewer implementation (34 lines)
- [Source: `dashboard/components/viewers/MarkdownViewer.tsx`] -- Existing Markdown viewer implementation (47 lines)
- [Source: `dashboard/components/MarkdownRenderer.tsx`] -- Reference for comprehensive component overrides (191 lines)
- [Source: `dashboard/components/DocumentViewerModal.tsx`] -- Existing viewer routing (167 lines)
- [Source: `dashboard/hooks/useDocumentFetch.ts`] -- Existing fetch hook (67 lines)
- [Source: `_bmad-output/implementation-artifacts/9-9-html-and-markdown-viewers-with-raw-toggle.md`] -- Previous story version from old epic numbering
- [Source: `_bmad-output/implementation-artifacts/9-7-viewer-modal-shell-with-text-and-code-viewers.md`] -- Predecessor story (viewer modal shell)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Enhanced `MarkdownViewer.tsx` with component overrides for `a` (target="_blank" rel="noopener noreferrer"), `h1`/`h2`/`h3` (proper sizing), `table`/`thead`/`th`/`td` (border styling), and `blockquote`
- Created `HtmlViewer.test.tsx` with 9 tests covering toggle behavior, iframe sandbox attribute, accessibility title, and SyntaxHighlighter invocation
- Created `MarkdownViewer.test.tsx` with 15 tests covering toggle behavior, heading rendering, link target="_blank", table border styling, code block highlighting, raw mode pre element, and blockquote rendering
- All 64 tests in `components/viewers/` pass

### File List

- `dashboard/components/viewers/MarkdownViewer.tsx` (modified)
- `dashboard/components/viewers/HtmlViewer.test.tsx` (created)
- `dashboard/components/viewers/MarkdownViewer.test.tsx` (created)
