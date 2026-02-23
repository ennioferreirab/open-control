# Story 8.9: Agent Memory & History Viewer

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **dashboard user**,
I want to see an agent's memory and history directly in the agent config sheet with a button to open the full content in a large modal,
so that I can easily read what the agent has learned and review its interaction history without leaving the dashboard.

## Acceptance Criteria

### AC1 — Memory preview in agent config sheet

**Given** an agent has `~/.nanobot/agents/{agentName}/memory/MEMORY.md`
**When** I click on the agent in the sidebar and the config sheet opens
**Then** a "Memory" section is visible in the sheet (below the existing form fields, above footer)
**And** it shows a small scrollable preview of the MEMORY.md content (monospace, `text-xs`, max 4 lines visible, scroll-clipped)
**And** a "View" button is shown next to the section label

### AC2 — History preview in agent config sheet

**Given** an agent has `~/.nanobot/agents/{agentName}/memory/HISTORY.md`
**When** the config sheet opens for that agent
**Then** a "History" section is visible below the Memory section
**And** it shows a small scrollable preview of the HISTORY.md content (same styling as Memory)
**And** a "View" button is shown next to the section label

### AC3 — Empty / missing files handled gracefully

**Given** an agent has no `MEMORY.md` (e.g., new agent never ran)
**When** the config sheet opens
**Then** the Memory section shows a muted placeholder: *"No memory yet."*

**Given** an agent has no `HISTORY.md`
**When** the config sheet opens
**Then** the History section shows a muted placeholder: *"No history yet."*

### AC4 — Clicking "View" opens full-content modal for Memory

**Given** the Memory section is visible with content
**When** I click the "View" button next to "Memory"
**Then** a Dialog modal opens with title "Memory" and the **full** MEMORY.md content in a large scrollable monospace area
**And** a "Close" button closes the modal
**And** a "Copy" button copies the full content to clipboard

### AC5 — Clicking "View" opens full-content modal for History

**Given** the History section is visible with content
**When** I click the "View" button next to "History"
**Then** a Dialog modal opens with title "History" and the full HISTORY.md content in a large scrollable monospace area
**And** the same Close and Copy buttons are present

### AC6 — API route returns plain text for existing files

**Given** a file exists at `~/.nanobot/agents/{agentName}/memory/{MEMORY.md|HISTORY.md}`
**When** `GET /api/agents/[agentName]/memory/[filename]` is called
**Then** the response is `200 OK` with `Content-Type: text/plain; charset=utf-8` and the file content

### AC7 — API route returns 404 for missing files (no error UI crash)

**Given** the file does not exist
**When** the GET route is called
**Then** a `404` JSON `{ error: "File not found" }` is returned
**And** the dashboard shows the "No memory yet" / "No history yet" placeholder (no error thrown in UI)

### AC8 — API route rejects invalid agent names

**Given** the agentName contains path traversal characters (e.g., `../`, `/etc`)
**When** the GET route validates the name
**Then** a `400` JSON `{ error: "Invalid agentName" }` is returned

---

## Tasks / Subtasks

- [x] Task 1 — API route: serve agent memory/history files (AC: 6, 7, 8)
  - [x] 1.1 Create `dashboard/app/api/agents/[agentName]/memory/[filename]/route.ts`
  - [x] 1.2 Validate `agentName` with regex `/^[a-zA-Z0-9_-]+$/` (return 400 on fail)
  - [x] 1.3 Allow only `filename` values `MEMORY.md` or `HISTORY.md` (return 400 otherwise)
  - [x] 1.4 Resolve path: `path.join(homedir(), ".nanobot", "agents", agentName, "memory", filename)`
  - [x] 1.5 Return file content as `text/plain; charset=utf-8` (200), or `{ error: "File not found" }` (404)

- [x] Task 2 — Create `AgentTextViewerModal` component (AC: 4, 5)
  - [x] 2.1 Create `dashboard/components/AgentTextViewerModal.tsx`
  - [x] 2.2 Props: `{ open: boolean; onClose: () => void; title: string; content: string }`
  - [x] 2.3 Use `DialogContent` with `className="max-w-3xl w-full flex flex-col p-0 gap-0 [&>button]:hidden"` pattern (same as PromptEditModal)
  - [x] 2.4 Body: `ScrollArea` with `<pre>` content in `font-mono text-sm whitespace-pre-wrap break-words`
  - [x] 2.5 Footer: "Copy" button (copies `content` to clipboard via `navigator.clipboard.writeText`) + "Close" button

- [x] Task 3 — Update `AgentConfigSheet` to fetch and show memory/history (AC: 1, 2, 3, 4, 5)
  - [x] 3.1 Add state: `memory: string | null`, `history: string | null`, `memoryLoading: boolean`, `historyLoading: boolean`
  - [x] 3.2 Add state: `showMemoryModal: boolean`, `showHistoryModal: boolean`
  - [x] 3.3 `useEffect` on `agentName` change: fetch `/api/agents/${agentName}/memory/MEMORY.md` and `/api/agents/${agentName}/memory/HISTORY.md`, store results (null if 404)
  - [x] 3.4 Reset memory/history state to `null` when agentName changes (prevents stale content flash)
  - [x] 3.5 Render "Memory" section with label + "View" button + `4-line` preview or placeholder
  - [x] 3.6 Render "History" section with label + "View" button + `4-line` preview or placeholder
  - [x] 3.7 Mount `AgentTextViewerModal` twice (for memory and history) inside `{isLoaded && (...)}` block
  - [x] 3.8 Sections are read-only — they do NOT affect `isDirty` or `handleSave`
  - [x] 3.9 Import `AgentTextViewerModal` and add `vi.mock` stub in `AgentConfigSheet.test.tsx`

- [x] Task 4 — Add test mock stub in `AgentConfigSheet.test.tsx` (no new test cases needed) (AC: none — regression guard)
  - [x] 4.1 Add after existing `vi.mock("@/components/PromptEditModal", ...)` block:
    `vi.mock("@/components/AgentTextViewerModal", () => ({ AgentTextViewerModal: () => null }))`
  - [x] 4.2 Run existing test suite to confirm no regressions

---

## Dev Notes

### Architecture

- Memory and history files live on the **local filesystem** at `~/.nanobot/agents/{agentName}/memory/`. They are NOT in Convex.
- File serving follows the exact same pattern as `app/api/tasks/[taskId]/files/route.ts`: Next.js API route reads from `homedir()` path.
- Agent name validation regex: `/^[a-zA-Z0-9_-]+$/` — same pattern used in the tasks files route as `TASK_ID_RE`.
- `AgentTextViewerModal` is a **pure read-only variant** of the Dialog pattern. It does NOT extend `PromptEditModal` (which has variable detection logic). Create it as a simple, standalone component.
- The `ScrollArea` shadcn component is already used in the codebase — use it for the modal body.

### Fetch Strategy in AgentConfigSheet

Use plain `fetch` in a `useEffect` — no need for SWR or additional libraries. Pattern:

```tsx
useEffect(() => {
  if (!agentName) return;
  setMemory(null);
  setHistory(null);
  setMemoryLoading(true);
  setHistoryLoading(true);

  fetch(`/api/agents/${encodeURIComponent(agentName)}/memory/MEMORY.md`)
    .then((r) => r.ok ? r.text() : null)
    .then((text) => setMemory(text))
    .finally(() => setMemoryLoading(false));

  fetch(`/api/agents/${encodeURIComponent(agentName)}/memory/HISTORY.md`)
    .then((r) => r.ok ? r.text() : null)
    .then((text) => setHistory(text))
    .finally(() => setHistoryLoading(false));
}, [agentName]);
```

### Preview Rendering

Render a small clipped area. Example for the Memory section:

```tsx
<div className="space-y-1">
  <div className="flex items-center justify-between">
    <label className="text-sm font-medium">Memory</label>
    {memory && (
      <Button
        variant="ghost"
        size="sm"
        className="h-6 px-2 text-xs gap-1"
        onClick={() => setShowMemoryModal(true)}
      >
        <Eye className="h-3 w-3" />
        View
      </Button>
    )}
  </div>
  {memoryLoading ? (
    <p className="text-xs text-muted-foreground">Loading...</p>
  ) : memory ? (
    <div className="rounded-md border bg-muted/30 px-3 py-2 max-h-[80px] overflow-hidden">
      <pre className="text-xs font-mono text-muted-foreground whitespace-pre-wrap line-clamp-4">{memory}</pre>
    </div>
  ) : (
    <p className="text-xs text-muted-foreground italic">No memory yet.</p>
  )}
</div>
```

### `AgentTextViewerModal` Structure

```tsx
// dashboard/components/AgentTextViewerModal.tsx
"use client";
import { useCallback } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";

interface AgentTextViewerModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  content: string;
}

export function AgentTextViewerModal({ open, onClose, title, content }: AgentTextViewerModalProps) {
  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(content).catch(() => {});
  }, [content]);

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-3xl w-full flex flex-col p-0 gap-0 [&>button]:hidden">
        <DialogHeader className="px-6 pt-6 pb-4">
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <ScrollArea className="flex-1 px-6 pb-4 max-h-[60vh]">
          <pre className="text-sm font-mono whitespace-pre-wrap break-words">{content}</pre>
        </ScrollArea>
        <DialogFooter className="px-6 py-4 border-t gap-2">
          <Button variant="outline" onClick={handleCopy}>Copy</Button>
          <Button onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

### API Route Structure

```ts
// dashboard/app/api/agents/[agentName]/memory/[filename]/route.ts
import { NextRequest, NextResponse } from "next/server";
import { readFile } from "fs/promises";
import { join } from "path";
import { homedir } from "os";

const AGENT_NAME_RE = /^[a-zA-Z0-9_-]+$/;
const ALLOWED_FILENAMES = new Set(["MEMORY.md", "HISTORY.md"]);

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ agentName: string; filename: string }> },
) {
  const { agentName, filename } = await params;

  if (!AGENT_NAME_RE.test(agentName)) {
    return NextResponse.json({ error: "Invalid agentName" }, { status: 400 });
  }
  if (!ALLOWED_FILENAMES.has(filename)) {
    return NextResponse.json({ error: "Invalid filename" }, { status: 400 });
  }

  const filePath = join(homedir(), ".nanobot", "agents", agentName, "memory", filename);

  try {
    const content = await readFile(filePath, "utf-8");
    return new NextResponse(content, {
      status: 200,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  } catch {
    return NextResponse.json({ error: "File not found" }, { status: 404 });
  }
}
```

### Icons

- Use `Eye` from `lucide-react` for the "View" button (already installed).

### `ScrollArea` Import

```ts
import { ScrollArea } from "@/components/ui/scroll-area";
```

Check that `scroll-area` exists in `dashboard/components/ui/` — it is part of the shadcn codebase used throughout the project.

### Dirty State

The memory/history sections are **read-only** — they MUST NOT affect `isDirty`, `handleSave`, or any existing form logic. These are purely informational displays.

### Project Structure Notes

- Alignment with unified project structure:
  - New API route: `dashboard/app/api/agents/[agentName]/memory/[filename]/route.ts` (follows Next.js dynamic route pattern)
  - New component: `dashboard/components/AgentTextViewerModal.tsx` (PascalCase, same directory as `PromptEditModal.tsx`)
  - Modified: `dashboard/components/AgentConfigSheet.tsx` and `dashboard/components/AgentConfigSheet.test.tsx`
- The existing `app/api/agents/` directory already has `assist/` and `create/` subdirectories — the new `[agentName]/memory/[filename]/` route is a clean addition

### References

- Dialog pattern: [Source: `dashboard/components/PromptEditModal.tsx`] — `max-w-3xl p-0 gap-0 [&>button]:hidden`, footer with `px-6 py-4 border-t`
- Dialog pattern confirmed from: [Source: `dashboard/components/CronJobsModal.tsx`]
- API route pattern: [Source: `dashboard/app/api/tasks/[taskId]/files/route.ts`] — `TASK_ID_RE` validation, `homedir()` path, `fs/promises`
- Memory file location: [Source: `nanobot/agent/memory.py#MemoryStore.__init__`] — `workspace / "memory" / "MEMORY.md"` and `HISTORY.md`
- Agent workspace path: [Source: `nanobot/mc/executor.py:101`] — `Path.home() / ".nanobot" / "agents" / agent_name`
- `ScrollArea` usage: already in codebase (used in TaskDetailSheet, MissionControl panels)
- `Eye` icon: `lucide-react` — already installed
- Test mock pattern: [Source: `dashboard/components/AgentConfigSheet.test.tsx`] — `vi.mock("@/components/PromptEditModal", () => ({ PromptEditModal: () => null }))`

---

## Dev Agent Record

### Agent Model Used

claude-opus-4-6

### Debug Log References

No issues encountered during implementation.

### Completion Notes List

- Task 1: Created Next.js API route at `app/api/agents/[agentName]/memory/[filename]/route.ts` — validates agent name with regex, whitelists MEMORY.md/HISTORY.md filenames, serves file content as text/plain or returns 404 JSON. Follows existing tasks files route pattern.
- Task 2: Created `AgentTextViewerModal` component — read-only Dialog with ScrollArea, monospace pre content, Copy (clipboard API) and Close buttons. Follows PromptEditModal dialog pattern.
- Task 3: Updated `AgentConfigSheet` — added useEffect to fetch memory/history on agentName change, rendered Memory and History preview sections (monospace, 4-line clamp, loading/empty states), mounted two AgentTextViewerModal instances. Read-only sections do NOT affect isDirty or handleSave.
- Task 4: Added `vi.mock` for AgentTextViewerModal and `vi.stubGlobal("fetch")` in test file. All 22 existing tests pass with no regressions.

### File List

- `dashboard/app/api/agents/[agentName]/memory/[filename]/route.ts` (new)
- `dashboard/components/AgentTextViewerModal.tsx` (new)
- `dashboard/components/AgentConfigSheet.tsx` (modified)
- `dashboard/components/AgentConfigSheet.test.tsx` (modified)

## Change Log

- 2026-02-23: Story created — agent memory & history viewer in AgentConfigSheet
- 2026-02-23: Implementation complete — API route, AgentTextViewerModal, AgentConfigSheet integration, test mock stub. All 22 AgentConfigSheet tests pass, 210/213 full suite pass (3 pre-existing TaskInput timeout failures unrelated).
- 2026-02-23: Code review (AI) — 7 issues found (1 HIGH, 3 MEDIUM, 3 LOW). All HIGH/MEDIUM fixed: race condition guard on fetch, ENOENT-specific 404 in API route, copy feedback in modal, 4 new test cases for memory/history rendering. 26/26 tests pass.
