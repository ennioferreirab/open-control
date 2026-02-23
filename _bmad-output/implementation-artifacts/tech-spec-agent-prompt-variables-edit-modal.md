---
title: 'Agent Prompt Variables — Edit Modal with {{}} Interpolation'
slug: 'agent-prompt-variables-edit-modal'
created: '2026-02-23'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Next.js', 'TypeScript', 'Convex', 'shadcn/ui', 'Tailwind CSS', 'lucide-react', 'vitest']
files_to_modify:
  - 'dashboard/convex/schema.ts'
  - 'dashboard/convex/agents.ts'
  - 'dashboard/components/AgentConfigSheet.tsx'
  - 'dashboard/components/AgentConfigSheet.test.tsx'
files_to_create:
  - 'dashboard/components/PromptEditModal.tsx'
code_patterns:
  - 'Convex v.optional(v.array(v.object(...))) for variables field'
  - 'Dialog with p-0 gap-0 [&>button]:hidden pattern'
  - 'useEffect re-init on open for modal local state'
  - 'Regex /\{\{(\w+)\}\}/g for variable detection'
test_patterns:
  - 'vi.mock stub for new component imports in AgentConfigSheet.test.tsx'
---

# Tech-Spec: Agent Prompt Variables — Edit Modal with {{}} Interpolation

**Created:** 2026-02-23

## Overview

### Problem Statement

The prompt textarea in `AgentConfigSheet` is small (6 rows) and difficult to edit for long prompts. There is no support for reusable template variables (`{{varName}}`), forcing users to manually update raw text when deploying the same agent with different configurations.

### Solution

Add a pencil Edit button next to the Prompt label in `AgentConfigSheet` that opens a larger `Dialog` modal. The modal contains a full-size resizable textarea for editing the prompt and a two-column table for `{{varName}}` variables auto-detected from the prompt text. The **template** (with `{{tokens}}`) is saved to the `prompt` field in Convex. Variable name/value pairs are saved to a new `variables` field on the agent record. When the modal is closed, variable chips appear below the inline prompt textarea. The inline textarea remains editable for quick edits.

### Scope

**In Scope:**
- Add `variables` optional field to Convex `agents` table schema
- Update `updateConfig` mutation to accept and persist `variables`
- New `PromptEditModal` component (Dialog) with large textarea + auto-detected variable table
- Variable chips rendered below prompt textarea in `AgentConfigSheet` when modal is closed
- `AgentConfigSheet` wires up: Edit button, modal open/close, variables state, dirty detection, save
- `AgentConfigSheet.test.tsx` mock stub for `PromptEditModal`

**Out of Scope:**
- Python-side variable interpolation (nanobot backend — separate concern)
- Manual add/delete of variable rows (rows driven purely by `{{}}` detection)
- Making chips editable inline (display-only)
- `upsertByName` mutation update (called by Python agent on startup, not the dashboard)

---

## Context for Development

### Codebase Patterns

- **UI components**: shadcn/ui — `Dialog`, `Button`, `Textarea`, `Input` from `@/components/ui/`
- **State management**: local React state + Convex reactive queries (`useQuery`, `useMutation`)
- **Chip styling**: task tag chips in `TaskCard.tsx` use `text-xs px-1.5 py-0.5 rounded-full`; use `bg-muted text-muted-foreground font-mono` for variable chips
- **Convex mutations**: `v.optional(...)` args with `ctx.db.patch` pattern in `agents.ts`
- **Icons**: lucide-react — `Pencil` for the edit button (already installed)
- **Dirty detection**: `AgentConfigSheet` has `isDirty` useMemo comparing all form fields vs. `agent` data from Convex
- **Variable regex**: `/\{\{(\w+)\}\}/g` — extracts `varName` from `{{varName}}` in prompt text
- **Dialog modal pattern** (confirmed from `CronJobsModal.tsx`): `DialogContent` uses `className="max-w-4xl w-full flex flex-col p-0 gap-0 [&>button]:hidden"`. The `[&>button]:hidden` hides the built-in Radix X close button. `DialogFooter` has no built-in padding — add `className="px-6 py-4 border-t gap-2"` explicitly.
- **Test framework**: vitest + @testing-library/react. All shadcn UI components are mocked via `vi.mock`. `mockAgent` has no `variables` field — fine since schema is optional. The `updateConfig` assertion uses `expect.objectContaining(...)` so adding `variables` to the call is non-breaking.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `dashboard/components/AgentConfigSheet.tsx` | Main file to modify — agent config panel sheet |
| `dashboard/convex/schema.ts` | Convex schema — add `variables` field to `agents` table |
| `dashboard/convex/agents.ts` | Convex mutations — update `updateConfig` |
| `dashboard/components/ui/dialog.tsx` | Dialog component — exports `Dialog`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogFooter` |
| `dashboard/components/TaskCard.tsx` | Chip styling reference: `text-xs px-1.5 py-0.5 rounded-full` |
| `dashboard/components/CronJobsModal.tsx` | Dialog usage pattern — `p-0 gap-0 [&>button]:hidden`, manual close handling |
| `dashboard/components/AgentConfigSheet.test.tsx` | Test patterns — vitest mock strategy, must add `PromptEditModal` stub |

### Technical Decisions

- **`variables` type in Convex**: `v.optional(v.array(v.object({ name: v.string(), value: v.string() })))` on the agents table
- **Sync logic in modal**: On prompt textarea change, re-run regex detection. New vars → `value: ""`. Existing vars → keep value. Removed vars → dropped. Order follows detection order.
- **Modal saves to local state only**: Modal Save calls `onSave(prompt, variables)` on the parent. Does NOT call Convex directly. Sheet Save button persists everything to Convex.
- **DialogContent className**: `"max-w-3xl w-full flex flex-col p-0 gap-0 [&>button]:hidden"` — 3xl is wide enough for prompt editing without being full-screen
- **`agent.variables` undefined handling**: Existing agents have no `variables` field → treat as `[]` everywhere with `agent.variables || []`

---

## Implementation Plan

### Tasks

- [x] **Task 1 — Convex schema: add `variables` field to agents table**
  - File: `dashboard/convex/schema.ts`
  - Action: In the `agents` defineTable call, add after the `model: v.optional(v.string()),` line:
    ```ts
    variables: v.optional(v.array(v.object({ name: v.string(), value: v.string() }))),
    ```

- [x] **Task 2 — Convex mutation: update `updateConfig` to accept variables**
  - File: `dashboard/convex/agents.ts`
  - Action: In the `updateConfig` mutation args object, add after `model: v.optional(v.string()),`:
    ```ts
    variables: v.optional(v.array(v.object({ name: v.string(), value: v.string() }))),
    ```
  - Action: In the handler, after `if (args.model !== undefined) updates.model = args.model;`, add:
    ```ts
    if (args.variables !== undefined) updates.variables = args.variables;
    ```

- [x] **Task 3 — Create `PromptEditModal` component**
  - File: `dashboard/components/PromptEditModal.tsx` (new file)
  - Action: Create with the following full implementation:

```tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export type PromptVariable = { name: string; value: string };

interface PromptEditModalProps {
  open: boolean;
  onClose: () => void;
  onSave: (prompt: string, variables: PromptVariable[]) => void;
  initialPrompt: string;
  initialVariables: PromptVariable[];
}

function detectVariables(prompt: string, existing: PromptVariable[]): PromptVariable[] {
  const matches = new Set<string>();
  const regex = /\{\{(\w+)\}\}/g;
  let m: RegExpExecArray | null;
  while ((m = regex.exec(prompt)) !== null) {
    matches.add(m[1]);
  }
  const existingMap = new Map(existing.map((v) => [v.name, v.value]));
  return Array.from(matches).map((name) => ({
    name,
    value: existingMap.get(name) ?? "",
  }));
}

export function PromptEditModal({
  open,
  onClose,
  onSave,
  initialPrompt,
  initialVariables,
}: PromptEditModalProps) {
  const [localPrompt, setLocalPrompt] = useState(initialPrompt);
  const [localVariables, setLocalVariables] = useState<PromptVariable[]>(initialVariables);

  useEffect(() => {
    if (open) {
      setLocalPrompt(initialPrompt);
      setLocalVariables(initialVariables);
    }
  }, [open, initialPrompt, initialVariables]);

  const handlePromptChange = useCallback((value: string) => {
    setLocalPrompt(value);
    setLocalVariables((prev) => detectVariables(value, prev));
  }, []);

  const handleValueChange = useCallback((name: string, value: string) => {
    setLocalVariables((prev) =>
      prev.map((v) => (v.name === name ? { ...v, value } : v)),
    );
  }, []);

  const handleSave = useCallback(() => {
    onSave(localPrompt, localVariables);
    onClose();
  }, [localPrompt, localVariables, onSave, onClose]);

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-3xl w-full flex flex-col p-0 gap-0 [&>button]:hidden">
        <DialogHeader className="px-6 pt-6 pb-4">
          <DialogTitle>Edit Prompt</DialogTitle>
        </DialogHeader>

        <div className="flex-1 px-6 pb-4 space-y-4 overflow-y-auto">
          <Textarea
            value={localPrompt}
            onChange={(e) => handlePromptChange(e.target.value)}
            className="font-mono min-h-[300px] resize-y"
          />

          {localVariables.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-medium">Variables</p>
              <div className="border rounded-md overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-muted/50 border-b">
                      <th className="text-left px-3 py-2 text-xs font-medium text-muted-foreground w-1/2">
                        Variable
                      </th>
                      <th className="text-left px-3 py-2 text-xs font-medium text-muted-foreground w-1/2">
                        Value
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {localVariables.map((v, i) => (
                      <tr key={v.name} className={i > 0 ? "border-t" : ""}>
                        <td className="px-3 py-2">
                          <span className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">
                            {`{{${v.name}}}`}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <Input
                            value={v.value}
                            onChange={(e) => handleValueChange(v.name, e.target.value)}
                            placeholder={`Value for ${v.name}`}
                            className="h-7 text-sm"
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        <DialogFooter className="px-6 py-4 border-t gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave}>Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [x] **Task 4 — Update `AgentConfigSheet`**
  - File: `dashboard/components/AgentConfigSheet.tsx`

  **4a. Imports** — change `import { Check, Lock } from "lucide-react";` to:
  ```ts
  import { Check, Lock, Pencil } from "lucide-react";
  ```
  Add below the lucide import:
  ```ts
  import { PromptEditModal, type PromptVariable } from "@/components/PromptEditModal";
  ```

  **4b. State** — Add after the `[showDiscardDialog, setShowDiscardDialog]` state line:
  ```ts
  const [variables, setVariables] = useState<PromptVariable[]>([]);
  const [showPromptModal, setShowPromptModal] = useState(false);
  ```

  **4c. Initialize variables from agent** — In the `useEffect` (after `setShowSuccess(false);`), add:
  ```ts
  setVariables((agent.variables as PromptVariable[]) || []);
  ```

  **4d. Dirty detection** — In `isDirty` useMemo, extend the `return` boolean expression by appending:
  ```ts
  || JSON.stringify(variables) !== JSON.stringify(agent.variables || [])
  ```
  Add `variables` to the useMemo dependency array.

  **4e. handleSave** — In the `updateConfig({ ... })` call, add `variables` as an argument:
  ```ts
  variables,
  ```
  Add `variables` to the `useCallback` dependency array.

  **4f. Prompt label — add Edit button** — Replace:
  ```tsx
  <label className="text-sm font-medium">Prompt</label>
  ```
  With:
  ```tsx
  <div className="flex items-center justify-between">
    <label className="text-sm font-medium">Prompt</label>
    <Button
      variant="ghost"
      size="sm"
      className="h-6 px-2 text-xs gap-1"
      onClick={() => setShowPromptModal(true)}
    >
      <Pencil className="h-3 w-3" />
      Edit
    </Button>
  </div>
  ```

  **4g. Variable chips** — After the `{errors.prompt && <p ...>}` block, add:
  ```tsx
  {variables.length > 0 && (
    <div className="flex flex-wrap gap-1 mt-1">
      {variables.map((v) => (
        <span
          key={v.name}
          className="text-xs px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground font-mono"
        >
          {`{{${v.name}}}`}
        </span>
      ))}
    </div>
  )}
  ```

  **4h. Mount PromptEditModal** — Add inside the `{isLoaded ? (<> ... </>) }` block, just before the closing `</>` (after the `AlertDialog`):
  ```tsx
  <PromptEditModal
    open={showPromptModal}
    onClose={() => setShowPromptModal(false)}
    onSave={(newPrompt, newVariables) => {
      setPrompt(newPrompt);
      setVariables(newVariables);
      if (errors.prompt && newPrompt.trim()) {
        setErrors((prev) => ({ ...prev, prompt: undefined }));
      }
    }}
    initialPrompt={prompt}
    initialVariables={variables}
  />
  ```

- [x] **Task 5 — Add `PromptEditModal` mock stub to `AgentConfigSheet.test.tsx`**
  - File: `dashboard/components/AgentConfigSheet.test.tsx`
  - Action: Add after the existing `vi.mock("@/components/AgentSidebarItem", ...)` block:
    ```ts
    vi.mock("@/components/PromptEditModal", () => ({
      PromptEditModal: () => null,
    }));
    ```
  - Notes: This prevents the Dialog import from failing in the test environment. No new test cases required — existing tests remain valid.

---

### Acceptance Criteria

- [ ] **AC1 — Edit button opens modal**: Given the agent config sheet is open with a loaded agent, when I click the "Edit" button next to the Prompt label, then a Dialog modal opens with title "Edit Prompt" and a large textarea pre-filled with the current prompt.

- [ ] **AC2 — Variables auto-detected on typing**: Given the prompt modal is open, when I type `Hello {{name}}, your role is {{role}}` in the textarea, then two rows appear in the Variables table — `{{name}}` and `{{role}}` — each with an editable value input and empty placeholder.

- [ ] **AC3 — Variable values preserved on prompt edit**: Given `{{name}}` has value "Alice" in the table, when I add `{{greeting}}` to the prompt text, then the `name` row still shows "Alice" and a new `greeting` row appears with empty value.

- [ ] **AC4 — Variable removed when token deleted from prompt**: Given `{{name}}` and `{{role}}` are in the table, when I delete `{{role}}` from the prompt text, then the `role` row disappears and `name` row remains with its value intact.

- [ ] **AC5 — Modal Save updates parent state and shows chips**: Given I edited the prompt and filled in a variable value in the modal, when I click Save, then the modal closes, the inline textarea shows the updated prompt, and a chip for each variable appears below the textarea.

- [ ] **AC6 — Chips display on sheet open with saved variables**: Given an agent has `variables: [{name: "env", value: "prod"}]` persisted in Convex, when the agent config sheet is opened (modal not open), then a chip `{{env}}` appears below the prompt textarea in muted, monospace, rounded-full style.

- [ ] **AC7 — Variables persisted to Convex on sheet Save**: Given I have set variable values via the modal and clicked modal Save, when I click the sheet Save button, then `updateConfig` is called including the `variables` array and the record is updated in Convex.

- [ ] **AC8 — Dirty state includes variable changes**: Given the agent config sheet is open with no prior changes, when I change a variable value via the modal and click modal Save, then the sheet Save button becomes enabled.

- [ ] **AC9 — Modal Cancel discards changes**: Given I have edited the prompt in the modal, when I click Cancel, then the modal closes and the parent sheet's prompt and variables are unchanged.

- [ ] **AC10 — No chips rendered when no variables**: Given the agent prompt contains no `{{varName}}` tokens and variables array is empty, when the sheet is open, then no chip section appears below the prompt textarea.

---

## Additional Context

### Dependencies

- `Dialog`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogFooter` from `@/components/ui/dialog` — already in codebase
- `Pencil` from `lucide-react` — already installed
- Task ordering: Tasks 1 & 2 (Convex layer) can run in parallel with Tasks 3 & 4a–4g. Task 4e requires Tasks 1 & 2 to be deployed first. Task 4h requires Task 3. Task 5 requires Task 4 (because the import must exist to be mocked).

### Testing Strategy

- Manual verification: open agent sheet → click Edit button → type `{{foo}}` in modal textarea → fill in value → click modal Save → verify `{{foo}}` chip appears below textarea → click sheet Save → verify Convex record has `variables: [{name: "foo", value: "..."}]`
- `AgentConfigSheet.test.tsx`: add `vi.mock("@/components/PromptEditModal", () => ({ PromptEditModal: () => null }))` stub. No new test cases required — existing `updateConfig` assertion uses `expect.objectContaining` so adding `variables` to the call is non-breaking.

### Notes

- `upsertByName` (Python agent startup registration) does NOT need updating — variables are a dashboard-only concern
- Python-side interpolation (replacing `{{name}}` with stored values before sending prompt to LLM) is out of scope here — separate nanobot backend task
- Inline textarea stays editable; typing there does NOT re-detect variables — only the modal does. This is intentional per decision 4b.
- `agent.variables` will be `undefined` for all existing agents — handled everywhere with `|| []`
- If the same `{{varName}}` token appears multiple times in the prompt, `detectVariables` uses a `Set` so only one row is created per unique name

## Review Notes
- Adversarial review completed
- Findings: 10 total, 7 fixed, 3 accepted/skipped
- Resolution approach: auto-fix
- Fixed: F1 (useEffect open-transition guard), F3 (remove type cast), F4 (useCallback for onSave), F5 (preserve variable row order), F6 (label htmlFor + textarea id), F7 (guard modal mount with isLoaded), F8 (aria-label on Edit button)
- Accepted: F2 ([] ≡ undefined semantically, complexity not warranted), F9 (consistent with codebase, no error boundaries), F10 (React JSX escaping prevents XSS)
