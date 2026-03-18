# Story 9-9: HTML and Markdown Viewers with Raw Toggle

**Epic:** 9 — Thread Files Context: View Files in Dashboard
**Status:** ready-for-dev

## Story

As a **user**,
I want to view HTML and Markdown files in rendered mode and toggle to raw source,
So that I can read agent-produced reports beautifully and inspect the source when needed.

## Acceptance Criteria

**Given** the user opens an HTML file
**When** the DocumentViewerModal renders
**Then** the HTML is displayed in a sandboxed iframe (`sandbox="allow-same-origin"`) (FR10)
**And** a "Raw / Rendered" toggle is visible
**And** "Raw" shows the HTML source with syntax highlighting
**And** the viewer opens within 2 seconds (NFR3)

**Given** the user opens a Markdown file
**When** the DocumentViewerModal renders
**Then** the content is rendered as formatted HTML (FR11)
**And** supports: headings, paragraphs, lists, tables, code blocks, bold/italic, links
**And** a "Raw / Rendered" toggle is visible
**And** "Raw" shows the raw Markdown in monospace font

**Given** the HTML file contains scripts
**When** the sandboxed iframe renders it
**Then** scripts do not execute (sandbox attribute blocks them)

## Technical Notes

### Install `react-markdown` and `remark-gfm`
`npm install react-markdown remark-gfm`

### Create `components/viewers/MarkdownViewer.tsx`
Props: `{ content: string }`

```tsx
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
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className ?? "");
                  const isBlock = !props.ref;  // inline vs block heuristic
                  if (match && isBlock) {
                    return (
                      <SyntaxHighlighter language={match[1]} style={vscDarkPlus} PreTag="div">
                        {String(children).replace(/\n$/, "")}
                      </SyntaxHighlighter>
                    );
                  }
                  return <code className={className} {...props}>{children}</code>;
                },
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
        ) : (
          <pre className="font-mono text-sm whitespace-pre-wrap break-all text-foreground">{content}</pre>
        )}
      </div>
    </div>
  );
}
```

Note: `prose` classes require `@tailwindcss/typography` — check if it's in tailwind.config. If not, use a simplified version without prose classes (just render ReactMarkdown with basic styling).

### Create `components/viewers/HtmlViewer.tsx`
Props: `{ content: string }`

```tsx
"use client";
import { useState } from "react";
import SyntaxHighlighter from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Button } from "@/components/ui/button";

export function HtmlViewer({ content }: { content: string }) {
  const [mode, setMode] = useState<"rendered" | "raw">("rendered");

  const srcDoc = content; // sandboxed iframe uses srcdoc

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-4 py-2 border-b shrink-0">
        <Button variant={mode === "rendered" ? "secondary" : "ghost"} size="sm" onClick={() => setMode("rendered")}>Rendered</Button>
        <Button variant={mode === "raw" ? "secondary" : "ghost"} size="sm" onClick={() => setMode("raw")}>Raw</Button>
      </div>
      <div className="flex-1 overflow-hidden">
        {mode === "rendered" ? (
          <iframe
            srcDoc={srcDoc}
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

### Wire into DocumentViewerModal
Replace the stubs for `markdown` and `html` with the new viewers. Pass `content` (already available from `useDocumentFetch`).

## NFRs Covered
- NFR3: Viewer opens within 2 seconds for files up to 10MB
