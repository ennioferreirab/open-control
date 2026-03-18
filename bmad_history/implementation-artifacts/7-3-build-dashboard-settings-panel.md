# Story 7.3: Build Dashboard Settings Panel

Status: done

## Story

As a **user**,
I want to configure global system defaults from the dashboard,
So that I can adjust timeouts and model settings without editing files.

## Acceptance Criteria

1. **Given** the dashboard is loaded, **When** the user accesses the settings panel (via a settings icon/button in the layout), **Then** a settings view displays with configurable options
2. **Given** the settings panel is open, **Then** it shows: Global task timeout (number input, in minutes) (FR41), Global inter-agent review timeout (number input, in minutes) (FR41), System-wide default LLM model (select dropdown with available models) (FR43)
3. **Given** the user changes a setting value, **When** the setting auto-saves on change, **Then** the setting is persisted to the Convex `settings` table as a key-value pair
4. **Given** a setting is saved, **Then** a subtle green checkmark appears next to the field (auto-fades after 1.5s)
5. **Given** no settings have been configured, **When** the settings panel renders, **Then** sensible defaults are displayed (e.g., task timeout: 30 minutes, inter-agent timeout: 10 minutes)
6. **Given** settings are saved, **Then** the new values take effect immediately for subsequent operations (timeout checker reads from settings)
7. **And** settings UI is accessible via a settings icon in the `DashboardLayout.tsx` header
8. **And** Convex `settings.ts` contains `get`, `set`, and `list` queries/mutations (from Story 7.2 or created here)
9. **And** Vitest tests exist for the settings panel

## Tasks / Subtasks

- [ ] Task 1: Ensure Convex settings queries/mutations exist (AC: #3, #8)
  - [ ] 1.1: Verify `dashboard/convex/settings.ts` exists with `get`, `set`, `list` (may already exist from Story 7.2)
  - [ ] 1.2: If not, create the file with queries and mutations as specified in Story 7.2

- [ ] Task 2: Create the SettingsPanel component (AC: #1, #2, #4, #5)
  - [ ] 2.1: Create `dashboard/components/SettingsPanel.tsx` with `"use client"` directive
  - [ ] 2.2: Use `useQuery(api.settings.list)` to fetch all current settings
  - [ ] 2.3: Use `useMutation(api.settings.set)` for saving changes
  - [ ] 2.4: Render settings form with:
    - "Task Timeout (minutes)" — number input, default 30
    - "Inter-Agent Review Timeout (minutes)" — number input, default 10
    - "Default LLM Model" — Select dropdown with model options
  - [ ] 2.5: Use `Input` (type="number") for timeout fields
  - [ ] 2.6: Use `Select` for model dropdown with options: "claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-6", or read from a constants file
  - [ ] 2.7: Auto-save on blur or after debounced input (300ms debounce)
  - [ ] 2.8: Show green checkmark icon (`Check` from Lucide) next to saved fields, auto-fade after 1.5s

- [ ] Task 3: Implement auto-save with debounce (AC: #3, #4, #6)
  - [ ] 3.1: Use a custom `useDebounce` hook or `setTimeout` for debounced saving
  - [ ] 3.2: On each input change, start a 300ms timer; if the user keeps typing, reset the timer
  - [ ] 3.3: When the timer fires (or on blur), call `setMutation({ key: "task_timeout_minutes", value: String(value) })`
  - [ ] 3.4: Show the green checkmark after mutation succeeds
  - [ ] 3.5: Hide the checkmark after 1.5s using `setTimeout`

- [ ] Task 4: Integrate settings into DashboardLayout (AC: #1, #7)
  - [ ] 4.1: Add a settings icon button (e.g., `Settings` Lucide icon) to the dashboard header/toolbar
  - [ ] 4.2: Option A: Clicking opens a ShadCN `Sheet` (slide-out from right) containing `SettingsPanel`
  - [ ] 4.3: Option B: Clicking navigates to a settings section within the layout
  - [ ] 4.4: Preferred: Sheet (slide-out) — consistent with TaskDetailSheet pattern
  - [ ] 4.5: The settings Sheet uses the same 480px width as TaskDetailSheet

- [ ] Task 5: Write Vitest tests (AC: #9)
  - [ ] 5.1: Create `dashboard/components/SettingsPanel.test.tsx`
  - [ ] 5.2: Test settings panel renders with default values when no settings exist
  - [ ] 5.3: Test settings panel renders with saved values from Convex
  - [ ] 5.4: Test changing a value calls the set mutation
  - [ ] 5.5: Test green checkmark appears after save and disappears after 1.5s

## Dev Notes

### Critical Architecture Requirements

- **Settings are key-value pairs in Convex**: The `settings` table stores simple key-value pairs. This is intentionally simple — no complex configuration objects.
- **Settings take effect immediately**: The gateway's timeout checker reads settings from Convex on each check cycle. When the user changes a timeout, the new value is used on the next check.
- **No page navigation**: Settings open in a slide-out Sheet, consistent with the single-screen dashboard pattern. The user never leaves the Kanban board.

### Settings Keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `task_timeout_minutes` | string (number) | "30" | Global task timeout in minutes |
| `inter_agent_timeout_minutes` | string (number) | "10" | Global inter-agent review timeout |
| `default_llm_model` | string | "claude-sonnet-4-6" | System-wide default LLM model |

### SettingsPanel Component Pattern

```tsx
"use client";

import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Check } from "lucide-react";

const DEFAULTS: Record<string, string> = {
  task_timeout_minutes: "30",
  inter_agent_timeout_minutes: "10",
  default_llm_model: "claude-sonnet-4-6",
};

const MODEL_OPTIONS = [
  { value: "claude-opus-4-6", label: "Claude Opus 4.6" },
  { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
  { value: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5" },
];

export function SettingsPanel() {
  const allSettings = useQuery(api.settings.list);
  const setSetting = useMutation(api.settings.set);
  const [savedFields, setSavedFields] = useState<Record<string, boolean>>({});

  // Convert settings array to map
  const settingsMap: Record<string, string> = {};
  allSettings?.forEach((s) => {
    settingsMap[s.key] = s.value;
  });

  const getValue = (key: string) => settingsMap[key] ?? DEFAULTS[key];

  const handleSave = async (key: string, value: string) => {
    await setSetting({ key, value });
    setSavedFields((prev) => ({ ...prev, [key]: true }));
    setTimeout(() => {
      setSavedFields((prev) => ({ ...prev, [key]: false }));
    }, 1500);
  };

  return (
    <div className="space-y-6 p-6">
      <h2 className="text-lg font-semibold">Settings</h2>

      <SettingField
        label="Task Timeout (minutes)"
        value={getValue("task_timeout_minutes")}
        onSave={(val) => handleSave("task_timeout_minutes", val)}
        saved={savedFields["task_timeout_minutes"]}
        type="number"
      />

      <SettingField
        label="Inter-Agent Review Timeout (minutes)"
        value={getValue("inter_agent_timeout_minutes")}
        onSave={(val) => handleSave("inter_agent_timeout_minutes", val)}
        saved={savedFields["inter_agent_timeout_minutes"]}
        type="number"
      />

      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium">Default LLM Model</label>
          {savedFields["default_llm_model"] && (
            <Check className="h-4 w-4 text-green-500" />
          )}
        </div>
        <Select
          value={getValue("default_llm_model")}
          onValueChange={(val) => handleSave("default_llm_model", val)}
        >
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {MODEL_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
```

### Save Feedback Animation

```tsx
// Green checkmark that fades after 1.5s:
{saved && (
  <Check className="h-4 w-4 text-green-500 transition-opacity" />
)}
```

The `saved` state is set to `true` on save, then `false` after 1.5s via `setTimeout`.

### Common LLM Developer Mistakes to Avoid

1. **DO NOT store settings as a single JSON object** — The settings table uses individual key-value rows. Each setting is its own document.

2. **DO NOT require a "Save" button** — Settings auto-save on change (debounced for text inputs, immediate for Select). This matches the UX spec.

3. **DO NOT store numbers as numbers in the settings table** — The settings table uses `v.string()` for the value field. Convert to/from numbers in the UI.

4. **DO NOT add validation for model names** — The Select dropdown constrains the choices. No free-text model input for MVP.

5. **DO NOT create a separate route for settings** — Settings open in a Sheet overlay, not a separate page. The user stays on the dashboard.

6. **DO NOT forget defaults** — When no settings exist in the database, the UI must show sensible defaults.

### What This Story Does NOT Include

- **Per-task timeout input at creation** — This could be added to the TaskInput progressive disclosure panel as a future enhancement
- **Agent-specific model overrides from dashboard** — Agent models are configured in YAML (Story 3.1)
- **Advanced configuration** — This is a simple settings panel for the 3 most important global defaults

### Files Created in This Story

| File | Purpose |
|------|---------|
| `dashboard/components/SettingsPanel.tsx` | Settings UI with auto-save |
| `dashboard/components/SettingsPanel.test.tsx` | Vitest tests |

### Files Modified in This Story

| File | Changes |
|------|---------|
| `dashboard/components/DashboardLayout.tsx` | Add settings icon button and Sheet for settings |
| `dashboard/convex/settings.ts` | Ensure get/set/list queries exist (may already exist from Story 7.2) |

### Verification Steps

1. Click settings icon in dashboard header — verify settings Sheet opens
2. Verify default values display (30 min, 10 min, claude-sonnet-4-6)
3. Change task timeout to 60 — verify it saves (green checkmark appears)
4. Refresh the page — verify the saved value persists
5. Change LLM model — verify it saves immediately
6. Verify checkmark disappears after 1.5 seconds
7. Run `cd dashboard && npx vitest run` — tests pass

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 7.3`] — Original story definition
- [Source: `_bmad-output/planning-artifacts/prd.md#FR41`] — Global timeout config
- [Source: `_bmad-output/planning-artifacts/prd.md#FR43`] — System-wide default LLM model
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#UX Consistency Patterns`] — Settings save feedback (green checkmark, 1.5s fade)
- [Source: `dashboard/convex/schema.ts`] — Settings table schema
- [Source: `dashboard/components/DashboardLayout.tsx`] — Layout to add settings button

## Dev Agent Record

### Agent Model Used
claude-opus-4-6

### Debug Log References
- TypeScript check: `npx tsc --noEmit` passes (only pre-existing error in LoginPage.test.tsx)

### Completion Notes List
- Created `dashboard/convex/settings.ts` with `get`, `set`, `list` queries/mutations
- Created `dashboard/components/SettingsPanel.tsx` with auto-save debounce, green checkmark feedback
- Modified `dashboard/components/DashboardLayout.tsx` to add settings icon in header and Sheet slide-out
- Created `dashboard/components/SettingsPanel.test.tsx` with Vitest tests
- Settings panel: number inputs for task timeout (default 30) and inter-agent timeout (default 10), Select for LLM model (default claude-sonnet-4-6)
- Auto-save on 300ms debounce for number inputs, immediate save for Select
- Green checkmark appears after save and fades after 1.5s
- Sheet matches TaskDetailSheet pattern (480px, slide from right)

### File List
- `dashboard/convex/settings.ts` (created)
- `dashboard/components/SettingsPanel.tsx` (created)
- `dashboard/components/SettingsPanel.test.tsx` (created)
- `dashboard/components/DashboardLayout.tsx` (modified)
