# Story 9-3: Build Files Tab in Task Detail Sheet

**Epic:** 9 — Thread Files Context: Attach Files to Tasks
**Status:** ready-for-dev

## Story

As a **user**,
I want to see a list of all files on a task in a dedicated Files tab,
So that I can browse attachments and outputs in one place.

## Acceptance Criteria

**Given** the TaskDetailSheet exists with a Thread tab
**When** the user clicks a task card to open the detail Sheet
**Then** a "Files" tab is available alongside the existing tabs
**And** the Files tab is visually consistent with the existing tab design (ShadCN `Tabs`)

**Given** the user opens the Files tab
**When** the task has files in its `files` manifest
**Then** files are listed with: file type icon, file name, size (human-readable, e.g., "847 KB"), subfolder label ("attachment" or "output")
**And** attachments are grouped separately from outputs with clear section headers
**And** the file list loads within 1 second of opening the tab (NFR2)

**Given** the task's file manifest is updated (new file uploaded or agent produces output)
**When** the Convex reactive query updates
**Then** the Files tab updates in real-time without manual refresh (NFR9, FR25)
**And** new files appear with a subtle fade-in

**Given** a task has no files
**When** the Files tab is opened
**Then** a muted placeholder displays: "No files yet. Attach files or wait for agent output."

## Technical Notes

- Read `components/TaskCard.tsx` and the TaskDetailSheet to understand the current sheet/tab structure
- The TaskDetailSheet already has tabs (Thread, Execution Plan, Config) — add "Files" as a new tab
- The `task` object passed to the sheet already comes from a Convex reactive query — the `files` field is now on it (from story 9-1 schema change)
- File type icon: use lucide-react icons based on MIME type / extension:
  - PDF → `FileText`
  - Image → `Image`
  - Code → `FileCode`
  - Other → `File`
- Group files by `subfolder`: "attachments" section first, then "output" section
- Only render a section if it has files (don't show empty "Output" section if no outputs yet)
- Human-readable size: same `formatSize` helper from Story 9-2 (can extract to a shared lib or inline)
- Each file row should be clickable (onClick stub for now — Story 9-6 will wire the viewer)
- Subtle fade-in for new items: `animate-in fade-in duration-300` (Tailwind/ShadCN animation)
- Follow the exact tab style used by existing tabs in the sheet

## NFRs Covered

- NFR2: File list loads within 1 second of opening the Files tab
- NFR9: Dashboard reactively displays new files without page refresh
