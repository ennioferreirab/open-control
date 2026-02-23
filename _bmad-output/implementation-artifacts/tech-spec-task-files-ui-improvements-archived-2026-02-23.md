---
title: 'Task Files Tab — UI Improvements & Attachment Delete'
slug: 'task-files-ui-improvements'
created: '2026-02-23'
status: 'in-progress'
stepsCompleted: [1]
tech_stack: ['Next.js', 'Convex', 'TypeScript', 'Tailwind CSS', 'lucide-react']
files_to_modify:
  - 'dashboard/components/TaskDetailSheet.tsx'
  - 'dashboard/convex/tasks.ts'
  - 'dashboard/app/api/tasks/[taskId]/files/route.ts'
code_patterns:
  - 'useMutation (Convex) for removeTaskFile'
  - 'DELETE handler in Next.js route'
  - 'fs/promises rm for disk deletion'
test_patterns: []
---

# Tech-Spec: Task Files Tab — UI Improvements & Attachment Delete

**Created:** 2026-02-23

## Overview

### Problem Statement

The Files tab in `TaskDetailSheet` has three issues: (1) each file row renders an "attachment"/"output" `<Badge>` that is redundant (the section heading already labels the group) and causes layout breakage when the filename is long, (2) there is no way to delete an attachment once it has been uploaded, and (3) both ATTACHMENTS and OUTPUTS sections only render when files exist, producing a confusing empty state.

### Solution

Remove the redundant badge, fix the file item layout so long names truncate cleanly, add a trash-icon delete button on attachment items that calls a new DELETE API route (disk removal) followed by a new `removeTaskFile` Convex mutation (metadata removal), and always render both sections with per-section empty-state messages.

### Scope

**In Scope:**
- Remove `<Badge>` from file list items in `TaskDetailSheet.tsx`
- Fix file item layout: filename `min-w-0` + `truncate`, size label `flex-shrink-0`
- Add `DELETE` handler to `app/api/tasks/[taskId]/files/route.ts` — deletes file from disk at `~/.nanobot/tasks/{taskId}/attachments/{filename}`
- Add `removeTaskFile` Convex mutation in `convex/tasks.ts` — removes one file entry from the metadata array by name + subfolder
- Add trash icon button (attachment items only) that calls DELETE API then `removeTaskFile`; shows loading state while in-flight
- Always render ATTACHMENTS and OUTPUTS sections even when empty; per-section empty states: "No attachments yet." / "No outputs yet."
- Remove the old "No files yet. Attach files or wait for agent output." fallback

**Out of Scope:**
- Deleting output files
- Changes to file upload logic
- Test changes

---

## Context for Development

### Codebase Patterns

- **Convex mutations**: imported via `useMutation(api.tasks.X)` in the component; backend defined in `convex/tasks.ts` using `mutation` from `"./_generated/server"`.
- **File metadata array**: `task.files` is `Array<{ name, type, size, subfolder, uploadedAt }>` stored on the Convex task document. `subfolder` is `"attachments"` or `"output"`.
- **Disk path**: attachments live at `~/.nanobot/tasks/{taskId}/attachments/{filename}`. Built with `join(homedir(), ".nanobot", "tasks", taskId, "attachments", filename)`.
- **Existing DELETE pattern**: `app/api/tasks/[taskId]/files/route.ts` currently only has a `POST` handler; add `DELETE` to the same file.
- **Security**: `taskId` validated with `TASK_ID_RE = /^[a-zA-Z0-9_-]+$/`. Filename must be validated similarly — strip any path separators to prevent traversal.
- **Loading state**: existing upload uses `isUploading` boolean + `setIsUploading`. Delete follows the same pattern with a per-file loading key (use `Set<string>` keyed by `${subfolder}-${name}`).
- **Two-phase delete**: (1) call `DELETE /api/tasks/{taskId}/files` with `{ subfolder, filename }` in body → removes from disk; (2) call `removeTaskFile` Convex mutation → removes from metadata. If step 1 fails, abort and show error.
- **Imports already present**: `Trash2` is NOT yet imported from `lucide-react` — must add it.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `dashboard/components/TaskDetailSheet.tsx` | Main component — UI changes + delete handler |
| `dashboard/convex/tasks.ts` | Add `removeTaskFile` mutation |
| `dashboard/app/api/tasks/[taskId]/files/route.ts` | Add `DELETE` handler |
| `dashboard/convex/schema.ts` | Reference: tasks.files array schema |

### Technical Decisions

- **DELETE request body**: Use `request.json()` in the Next.js DELETE handler to receive `{ subfolder: string, filename: string }`. Validate `subfolder === "attachments"` (only attachments are deletable server-side).
- **Filename sanitization**: Use `path.basename(filename)` to strip any directory components before building the path — prevents traversal.
- **Convex removeTaskFile**: Filter the files array by excluding the entry where `name === filename && subfolder === subfolder`. Uses `ctx.db.patch(taskId, { files: filtered })`.
- **Per-file deleting state**: `const [deletingFiles, setDeletingFiles] = useState<Set<string>>(new Set())` — key is `${subfolder}-${name}`. Button disabled + shows spinner while key is in the set.
- **Section always visible**: Remove the `if (group.length === 0) return null` guard. Instead, render the section header + either the file list or an empty-state `<p>`.

---

## Implementation Plan

### Tasks

- [ ] **Task 1 — Backend: add `removeTaskFile` mutation to `convex/tasks.ts`**
  - File: `convex/tasks.ts`
  - Add after `addTaskFiles`:
    ```ts
    export const removeTaskFile = mutation({
      args: {
        taskId: v.id("tasks"),
        subfolder: v.string(),
        filename: v.string(),
      },
      handler: async (ctx, { taskId, subfolder, filename }) => {
        const task = await ctx.db.get(taskId);
        if (!task) return;
        const updated = (task.files ?? []).filter(
          (f) => !(f.name === filename && f.subfolder === subfolder),
        );
        await ctx.db.patch(taskId, { files: updated });
      },
    });
    ```

- [ ] **Task 2 — API: add `DELETE` handler to `app/api/tasks/[taskId]/files/route.ts`**
  - File: `app/api/tasks/[taskId]/files/route.ts`
  - Add `import { basename } from "path"` (already have `join`).
  - Add `import { unlink } from "fs/promises"` alongside existing imports (`mkdir, rename, rm, writeFile` → add `unlink`).
  - Add after the `POST` export:
    ```ts
    export async function DELETE(
      request: NextRequest,
      { params }: { params: Promise<{ taskId: string }> },
    ) {
      const { taskId } = await params;

      if (!TASK_ID_RE.test(taskId)) {
        return NextResponse.json({ error: "Invalid taskId" }, { status: 400 });
      }

      let body: { subfolder: string; filename: string };
      try {
        body = await request.json();
      } catch {
        return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
      }

      const { subfolder, filename } = body;

      if (subfolder !== "attachments") {
        return NextResponse.json({ error: "Only attachments can be deleted" }, { status: 403 });
      }

      const safeName = basename(filename);
      if (!safeName || safeName !== filename) {
        return NextResponse.json({ error: "Invalid filename" }, { status: 400 });
      }

      const filePath = join(homedir(), ".nanobot", "tasks", taskId, "attachments", safeName);

      try {
        await unlink(filePath);
      } catch (err: unknown) {
        const code = (err as NodeJS.ErrnoException).code;
        if (code === "ENOENT") {
          // Already gone — treat as success
          return NextResponse.json({ ok: true });
        }
        return NextResponse.json({ error: "Failed to delete file" }, { status: 500 });
      }

      return NextResponse.json({ ok: true });
    }
    ```

- [ ] **Task 3 — UI: update `TaskDetailSheet.tsx`**
  - File: `components/TaskDetailSheet.tsx`

  **3a. Imports:**
  - Add `Trash2` to the lucide-react import: `import { File, FileCode, FileText, Image, Paperclip, Trash2 } from "lucide-react";`
  - Remove `Badge` from `@/components/ui/badge` import (no longer used in Files tab — verify it's not used elsewhere in the file first; if used in other tabs, keep the import).

  **3b. State:**
  - Add `const removeTaskFile = useMutation(api.tasks.removeTaskFile);`
  - Add `const [deletingFiles, setDeletingFiles] = useState<Set<string>>(new Set());`

  **3c. Handler — add `handleDeleteFile`:**
  ```ts
  const handleDeleteFile = async (file: { name: string; subfolder: string }) => {
    const key = `${file.subfolder}-${file.name}`;
    setDeletingFiles((prev) => new Set(prev).add(key));
    try {
      const res = await fetch(`/api/tasks/${task!._id}/files`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subfolder: file.subfolder, filename: file.name }),
      });
      if (!res.ok) throw new Error("Delete failed");
      await removeTaskFile({ taskId: task!._id, subfolder: file.subfolder, filename: file.name });
    } catch {
      // silently ignore — file may already be gone; Convex state will reflect truth
    } finally {
      setDeletingFiles((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };
  ```

  **3d. Files tab JSX — full replacement of the `<TabsContent value="files">` block:**
  ```tsx
  <TabsContent value="files" className="flex-1 min-h-0 m-0">
    <ScrollArea className="h-full px-6 py-4">
      <div className="flex items-center justify-between mb-4">
        <input
          type="file"
          multiple
          ref={attachInputRef}
          onChange={handleAttachFiles}
          className="hidden"
        />
        <Button
          variant="outline"
          size="sm"
          onClick={() => attachInputRef.current?.click()}
          disabled={isUploading}
        >
          <Paperclip className="h-3.5 w-3.5 mr-1.5" />
          {isUploading ? "Uploading..." : "Attach File"}
        </Button>
        {uploadError && (
          <p className="text-xs text-red-500">{uploadError}</p>
        )}
      </div>

      <div className="space-y-6">
        {/* ATTACHMENTS */}
        <div>
          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
            Attachments
          </h4>
          {(task.files ?? []).filter((f) => f.subfolder === "attachments").length === 0 ? (
            <p className="text-sm text-muted-foreground py-2">No attachments yet.</p>
          ) : (
            <div className="flex flex-col gap-1">
              {(task.files ?? [])
                .filter((f) => f.subfolder === "attachments")
                .map((file) => {
                  const key = `${file.subfolder}-${file.name}`;
                  const isDeleting = deletingFiles.has(key);
                  return (
                    <div
                      key={key}
                      className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-muted/50 animate-in fade-in duration-300 group"
                    >
                      <FileIcon name={file.name} />
                      <span
                        className="flex-1 min-w-0 text-sm truncate cursor-pointer"
                        onClick={() => setViewerFile(file)}
                      >
                        {file.name}
                      </span>
                      <span className="text-xs text-muted-foreground flex-shrink-0">
                        {formatSize(file.size)}
                      </span>
                      <button
                        onClick={() => handleDeleteFile(file)}
                        disabled={isDeleting}
                        className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive disabled:opacity-50"
                        aria-label="Delete attachment"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  );
                })}
            </div>
          )}
        </div>

        {/* OUTPUTS */}
        <div>
          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
            Outputs
          </h4>
          {(task.files ?? []).filter((f) => f.subfolder === "output").length === 0 ? (
            <p className="text-sm text-muted-foreground py-2">No outputs yet.</p>
          ) : (
            <div className="flex flex-col gap-1">
              {(task.files ?? [])
                .filter((f) => f.subfolder === "output")
                .map((file) => (
                  <div
                    key={`${file.subfolder}-${file.name}`}
                    className="flex items-center gap-2 rounded-md px-2 py-1.5 cursor-pointer hover:bg-muted/50 animate-in fade-in duration-300"
                    onClick={() => setViewerFile(file)}
                  >
                    <FileIcon name={file.name} />
                    <span className="flex-1 min-w-0 text-sm truncate">{file.name}</span>
                    <span className="text-xs text-muted-foreground flex-shrink-0">
                      {formatSize(file.size)}
                    </span>
                  </div>
                ))}
            </div>
          )}
        </div>
      </div>
    </ScrollArea>
  </TabsContent>
  ```

  **Key layout fix:** `flex-1 min-w-0 text-sm truncate` on the filename span (adding `min-w-0` prevents flex children from overflowing the row).

### Acceptance Criteria

**AC1 — Badge removed:**
- Given any file in the Files tab,
- When the tab is viewed,
- Then no "attachment" or "output" badge appears on any file row.

**AC2 — Long filenames truncate cleanly:**
- Given a file with a very long name (e.g. `Destaque-Agente-de-IA-Moltbot-scale-something.png`),
- When the Files tab is viewed,
- Then the filename truncates with ellipsis and the size label remains visible on the same row.

**AC3 — Delete attachment from disk:**
- Given an attachment file exists on disk and in metadata,
- When the user clicks the trash icon and the request succeeds,
- Then the file is deleted from `~/.nanobot/tasks/{taskId}/attachments/`.

**AC4 — Delete attachment from metadata:**
- Given the disk deletion succeeds,
- When `removeTaskFile` mutation runs,
- Then the file no longer appears in `task.files` and disappears from the UI.

**AC5 — Trash icon visibility:**
- Given an attachment row is not hovered,
- Then the trash icon is invisible (`opacity-0`).
- Given the row is hovered,
- Then the trash icon appears (`opacity-100`).

**AC6 — Delete button disabled during deletion:**
- Given a delete is in flight,
- Then the trash icon button is disabled and dimmed.

**AC7 — Only outputs visible in Outputs section:**
- Given the Files tab is open,
- Then output files appear only in the Outputs section, with no delete button.

**AC8 — Always-visible sections:**
- Given a task with no files at all,
- When the Files tab is viewed,
- Then both ATTACHMENTS and OUTPUTS sections are visible with their empty-state messages.

**AC9 — Path traversal prevention:**
- Given a DELETE request with `filename: "../secret"`,
- When the handler processes it,
- Then it returns 400 (basename check fails).

---

## Additional Context

### Dependencies

- `Trash2` from `lucide-react` — already installed, just not yet imported in this file.
- `unlink` from `fs/promises` — Node built-in, no new package needed.
- `basename` from `path` — Node built-in, already imported in the route file.

### Testing Strategy

- Manual verification in browser.
- No automated test changes required for this spec.

### Notes

- The `Badge` import in `TaskDetailSheet.tsx` is also used by the status badge in the sheet header — do NOT remove the import, only remove the `<Badge>` usages inside the Files tab.
- The `viewerFile` state type is `{ name, type, size, subfolder }` — attachment rows now use `onClick` only on the filename span, not the whole row, so the trash button click doesn't also open the viewer.
- ENOENT on unlink is treated as success (idempotent delete).
