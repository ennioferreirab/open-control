---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - _bmad-output/planning-artifacts/prd-thread-files-context.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
---

# Thread Files Context - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for the Thread Files Context feature of nanobot-ennio, decomposing the requirements from the PRD, Architecture, and UX Design Specification into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: User can attach one or more files to a task at creation time via a file picker in the task input
FR2: User can attach additional files to an existing task from the task detail view
FR3: User can see attached file names as chips/indicators on the task input before submitting
FR4: User can remove a pending attachment before task submission
FR5: System creates a dedicated task directory with `attachments/` and `output/` subdirectories when a task is created
FR6: User can view a list of all files (attachments and outputs) in a Files tab within the task detail Sheet
FR7: User can open any file from the file list in a multi-format viewer modal
FR8: User can view PDF files with page-by-page rendering, zoom controls, and pagination
FR9: User can view code files with syntax highlighting and line numbers
FR10: User can view HTML files in rendered mode and toggle to raw source view
FR11: User can view Markdown files in rendered mode and toggle to raw source view
FR12: User can view image files with zoom controls
FR13: User can view plain text and CSV files with zoom controls
FR14: User can download any file from the viewer
FR15: System serves files from the task directory to the dashboard via an API endpoint
FR16: System detects file type based on MIME type and file extension to route to the correct viewer
FR17: System includes the task directory path in the agent's task context when the agent receives a task
FR18: System includes a file manifest (name, type, size, subfolder) for all task files in the agent's task context
FR19: Agent can read files from the task's `attachments/` directory using its existing tools
FR20: Agent can write output files to the task's `output/` directory using its existing tools
FR21: System updates the file manifest when the agent creates new output files
FR22: System stores file metadata (name, type, size, subfolder, uploadedAt) on the task record
FR23: System updates the file manifest when the user uploads new attachments to an existing task
FR24: System updates the file manifest when the agent produces new output files
FR25: Dashboard reactively reflects file manifest changes (new files appear without manual refresh)
FR26: User can see a paperclip icon on task cards that have attached files on the Kanban board
FR27: User can see the file count next to the paperclip icon on the task card
FR28: Lead Agent receives the file manifest as part of the task context when routing unassigned tasks
FR29: Lead Agent can include file metadata context in its delegation message when assigning a task to a specialist agent

### NonFunctional Requirements

NFR1: File upload from dashboard to filesystem completes within 3 seconds for files up to 10MB
NFR2: File list in the task detail Sheet loads within 1 second of opening the Files tab
NFR3: File viewer opens and renders the first page/content within 2 seconds for files up to 10MB
NFR4: PDF viewer page navigation (next/previous) renders within 500ms
NFR5: File serving API endpoint returns file bytes with correct Content-Type within 1 second for files up to 10MB
NFR6: File manifest reflects a new user upload within 2 seconds of upload completion
NFR7: File manifest reflects new agent output files within 5 seconds of the agent notifying the backend
NFR8: Agent receives updated file manifest (including newly attached files) within 1 second of its next task context fetch
NFR9: Dashboard reactively displays new files without page refresh when the file manifest updates
NFR10: Task directory creation never fails silently — if directory creation fails, the task creation fails with a clear error
NFR11: File manifest is always reconcilable with the filesystem — the system can detect and resolve discrepancies
NFR12: File upload that fails mid-transfer does not leave partial files in the task directory
NFR13: Viewer gracefully handles unsupported file types with a download fallback instead of a blank screen or error

### Additional Requirements

**From Architecture:**
- Brownfield extension — no starter template needed, extends existing dashboard and Python modules
- Convex schema extension: `files` field on `tasks` table (array of `{ name, type, size, subfolder, uploadedAt }`)
- Next.js API routes for file upload and serving (not Convex functions — filesystem access required)
- Python bridge manifest sync: bridge scans `output/` directory and updates Convex when agent reports file creation
- Task directory management in Python backend (`~/.nanobot/tasks/{task-id}/attachments/` and `output/`)
- Follow existing naming conventions: camelCase in TypeScript, snake_case in Python, PascalCase for React components
- Follow existing architectural boundaries: bridge.py as the only Python-Convex integration point
- One-directional data flow for file metadata: filesystem → Python bridge → Convex → dashboard
- Every mutation that modifies task state must also write a corresponding activity event
- 500-line module limit applies to new modules

**From UX Design:**
- Files tab as new tab in TaskDetailSheet (alongside Thread, Execution Plan, Config)
- Paperclip icon follows Card-Rich design direction (alongside description preview, tags, progress bar)
- File attachment button/icon in TaskInput component
- File chips on TaskInput before submission (consistent with existing chip pattern)
- Multi-format viewer as a modal component (adapted from sei-workflows DocumentViewerModal)
- Viewer follows ShadCN design system — use design tokens, Tailwind spacing, consistent typography
- File type icons in file list (consistent with card metadata `text-xs` style)
- Drag-and-drop upload is explicitly post-MVP (Phase 2)
- DOCX viewer is post-MVP (Phase 2)

### FR Coverage Map

| FR | Epic | Description |
|----|------|-------------|
| FR1 | Epic 1 | Attach files at task creation via file picker |
| FR2 | Epic 1 | Attach files to existing task from detail view |
| FR3 | Epic 1 | File chips on task input before submission |
| FR4 | Epic 1 | Remove pending attachment before submission |
| FR5 | Epic 1 | Task directory auto-creation (attachments/ + output/) |
| FR6 | Epic 1 | Files tab in task detail Sheet |
| FR7 | Epic 2 | Open file in multi-format viewer modal |
| FR8 | Epic 2 | PDF viewer with pages, zoom, pagination |
| FR9 | Epic 2 | Code viewer with syntax highlighting |
| FR10 | Epic 2 | HTML viewer with raw/rendered toggle |
| FR11 | Epic 2 | Markdown viewer with raw/rendered toggle |
| FR12 | Epic 2 | Image viewer with zoom |
| FR13 | Epic 2 | Text/CSV viewer with zoom |
| FR14 | Epic 2 | Download file from viewer |
| FR15 | Epic 2 | File serving API endpoint |
| FR16 | Epic 2 | File type detection for viewer routing |
| FR17 | Epic 3 | Task directory path in agent context |
| FR18 | Epic 3 | File manifest in agent context |
| FR19 | Epic 3 | Agent reads from attachments/ |
| FR20 | Epic 3 | Agent writes to output/ |
| FR21 | Epic 3 | System updates manifest for agent output |
| FR22 | Epic 1 | File metadata stored on task record |
| FR23 | Epic 1 | Manifest updated on user upload |
| FR24 | Epic 3 | Manifest updated on agent output |
| FR25 | Epic 1 | Dashboard reactively reflects manifest changes |
| FR26 | Epic 1 | Paperclip icon on task cards with files |
| FR27 | Epic 1 | File count next to paperclip icon |
| FR28 | Epic 3 | Lead Agent receives file manifest for routing |
| FR29 | Epic 3 | Lead Agent includes file metadata in delegation |

### NFR Distribution

| NFR | Primary Epic | Integration |
|-----|-------------|-------------|
| NFR1 (upload < 3s) | Epic 1 | AC on upload stories |
| NFR2 (file list < 1s) | Epic 1 | AC on Files tab story |
| NFR3 (viewer < 2s) | Epic 2 | AC on viewer stories |
| NFR4 (PDF nav < 500ms) | Epic 2 | AC on PDF viewer story |
| NFR5 (serve API < 1s) | Epic 2 | AC on file serving story |
| NFR6 (manifest after upload < 2s) | Epic 1 | AC on upload stories |
| NFR7 (manifest after agent < 5s) | Epic 3 | AC on bridge sync story |
| NFR8 (agent gets fresh manifest) | Epic 3 | AC on agent context story |
| NFR9 (reactive display) | Epic 1 | AC on Files tab story |
| NFR10 (directory creation atomic) | Epic 1 | AC on directory creation story |
| NFR11 (manifest reconcilable) | Epic 3 | AC on bridge sync story |
| NFR12 (no partial files) | Epic 1 | AC on upload story |
| NFR13 (unsupported type fallback) | Epic 2 | AC on viewer story |

## Epic List

### Epic 1: Attach Files to Tasks
User can attach files when creating a task or to existing tasks, see those files listed in a Files tab, and see at a glance which tasks have files on the Kanban board.
**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR6, FR22, FR23, FR25, FR26, FR27
**NFRs as AC:** NFR1 (upload < 3s), NFR2 (file list < 1s), NFR6 (manifest after upload < 2s), NFR9 (reactive display), NFR10 (directory creation atomic), NFR12 (no partial files)
**Implementation scope:** Task directory creation (Python backend), Next.js API route for file upload, Convex schema extension (`files` field on tasks table), file picker + chip UI on TaskInput, attach from TaskDetailSheet, Files tab with file list and type icons, paperclip icon + count on TaskCard, reactive manifest updates.

### Epic 2: View Files in Dashboard
User can open any file from the file list in a multi-format viewer — PDF, code, HTML, Markdown, images, and text — directly in the dashboard without downloading or leaving the task context.
**FRs covered:** FR7, FR8, FR9, FR10, FR11, FR12, FR13, FR14, FR15, FR16
**NFRs as AC:** NFR3 (viewer < 2s), NFR4 (PDF nav < 500ms), NFR5 (serve API < 1s), NFR13 (unsupported type fallback)
**Implementation scope:** Next.js API route for file serving (raw bytes + Content-Type), file type detection (MIME + extension), DocumentViewerModal (adapted from sei-workflows), PDF viewer (react-pdf), code viewer (react-syntax-highlighter), HTML viewer (sandboxed iframe + raw toggle), Markdown viewer (rendered + raw toggle), image viewer (zoom), text/CSV viewer (zoom), download button.

### Epic 3: Agent File Integration
Agent receives file context when assigned a task, works with attached files using existing tools, produces output files, and the dashboard reflects agent-produced files — completing the full attach-to-view loop. Lead Agent uses file metadata for intelligent routing.
**FRs covered:** FR17, FR18, FR19, FR20, FR21, FR24, FR28, FR29
**NFRs as AC:** NFR7 (manifest after agent < 5s), NFR8 (agent gets fresh manifest), NFR11 (manifest reconcilable)
**Implementation scope:** Agent context injection (filesDir path + fileManifest array), Python bridge manifest sync (scan output/ → update Convex), Lead Agent file-aware routing, Lead Agent file metadata in delegation messages, activity events for file operations.

### Epic Dependencies

```
Epic 1 (Attach Files) → Epic 2 (View Files) → Epic 3 (Agent Integration)
```

- Epic 1 is standalone — delivers file attachment and listing
- Epic 2 builds on Epic 1 (needs files to exist and file infrastructure)
- Epic 3 builds on Epic 1 (needs file infrastructure) and benefits from Epic 2 (agent outputs viewable)

## Epic 1: Attach Files to Tasks

User can attach files when creating a task or to existing tasks, see those files listed in a Files tab, and see at a glance which tasks have files on the Kanban board.

### Story 1.1: Extend Convex Schema and Create Task Directories

As a **developer**,
I want the tasks table to support file metadata and the backend to create per-task directories on the filesystem,
So that files have a structured home and the dashboard knows what files exist on each task.

**Acceptance Criteria:**

**Given** the existing Convex `tasks` table schema
**When** the schema is extended
**Then** the `tasks` table gains a `files` field: optional array of objects with `{ name: string, type: string, size: number, subfolder: string, uploadedAt: string }`
**And** the Convex dev server starts without schema validation errors
**And** existing tasks without files continue to work (field is optional)

**Given** a new task is created in Convex (by dashboard or CLI)
**When** the Python bridge detects the new task via subscription
**Then** the bridge creates the directory `~/.nanobot/tasks/{task-id}/attachments/`
**And** the bridge creates the directory `~/.nanobot/tasks/{task-id}/output/`
**And** directory creation is atomic — if it fails, the failure is logged as an activity event with a clear error message (NFR10)
**And** the task-id used in the directory path is a filesystem-safe conversion of the Convex task ID

**Given** the task directory already exists (idempotent)
**When** directory creation is triggered again
**Then** no error occurs — the operation is safely idempotent

### Story 1.2: Upload Files at Task Creation

As a **user**,
I want to attach files when creating a task by selecting them from a file picker,
So that agents receive relevant documents alongside my task description.

**Acceptance Criteria:**

**Given** the TaskInput component exists on the dashboard
**When** the user clicks the attachment button (paperclip icon) next to the task input
**Then** a native file picker dialog opens allowing selection of one or more files

**Given** the user selects files from the file picker
**When** the files are selected
**Then** each selected file appears as a chip below the task input showing: file name and size
**And** the user can remove any pending attachment by clicking the X on the chip (FR4)

**Given** the user submits a task with pending file attachments
**When** the form is submitted
**Then** the task is created in Convex first (optimistic UI — card appears in Inbox)
**And** files are uploaded to `~/.nanobot/tasks/{task-id}/attachments/` via a Next.js API route (`POST /api/tasks/[taskId]/files`) accepting multipart form data
**And** the API route writes each file to the `attachments/` subdirectory
**And** on successful upload, the Convex task record's `files` array is updated with metadata for each file: `{ name, type, size, subfolder: "attachments", uploadedAt }` (FR23)
**And** file upload completes within 3 seconds for files up to 10MB (NFR1)
**And** the file manifest reflects the upload within 2 seconds of completion (NFR6)

**Given** a file upload fails mid-transfer
**When** the error is detected
**Then** no partial file is left in the task directory (NFR12)
**And** an error message is shown to the user
**And** successfully uploaded files from the same batch are not affected

**Given** the user submits a task with no attachments
**When** the form is submitted
**Then** the task is created normally without files — the `files` field remains empty or undefined

### Story 1.3: Build Files Tab in Task Detail Sheet

As a **user**,
I want to see a list of all files on a task in a dedicated Files tab,
So that I can browse attachments and outputs in one place.

**Acceptance Criteria:**

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

### Story 1.4: Attach Files to Existing Tasks

As a **user**,
I want to add files to a task that already exists,
So that I can provide additional context to agents working on in-progress tasks.

**Acceptance Criteria:**

**Given** the TaskDetailSheet is open on the Files tab (Story 1.3)
**When** the user clicks the "Attach File" button at the top of the Files tab
**Then** a native file picker dialog opens allowing selection of one or more files

**Given** the user selects files
**When** the upload is initiated
**Then** files are uploaded to `~/.nanobot/tasks/{task-id}/attachments/` via the same API route as Story 1.2
**And** the Convex task record's `files` array is updated with the new file metadata (FR2, FR23)
**And** the Files tab updates reactively to show the newly attached files (FR25)
**And** an activity event is created: "User attached {count} file(s) to task"

**Given** the upload completes
**When** the user views the Files tab
**Then** both previously existing files and newly uploaded files are visible
**And** upload completes within 3 seconds for files up to 10MB (NFR1)

### Story 1.5: File Indicators on Task Cards

As a **user**,
I want to see at a glance which tasks have files on the Kanban board,
So that I can identify document-related tasks without clicking into each one.

**Acceptance Criteria:**

**Given** a task has one or more files in its `files` manifest
**When** the TaskCard renders on the Kanban board
**Then** a paperclip icon is displayed on the card (consistent with Card-Rich metadata row, `text-xs`) (FR26)
**And** the file count is shown next to the paperclip icon (e.g., "3") (FR27)

**Given** a task has no files
**When** the TaskCard renders
**Then** no paperclip icon or file count is shown

**Given** a file is added to a task (by user upload or agent output)
**When** the Convex reactive query updates
**Then** the paperclip icon and count appear (or count updates) on the card in real-time

## Epic 2: View Files in Dashboard

User can open any file from the file list in a multi-format viewer — PDF, code, HTML, Markdown, images, and text — directly in the dashboard without downloading or leaving the task context.

### Story 2.1: File Serving API Route

As a **developer**,
I want an API endpoint that serves files from task directories with correct content types,
So that the dashboard viewer can fetch and render any file stored on the filesystem.

**Acceptance Criteria:**

**Given** a file exists at `~/.nanobot/tasks/{task-id}/{subfolder}/{filename}`
**When** the dashboard requests `GET /api/tasks/[taskId]/files/[subfolder]/[filename]`
**Then** the API route returns the raw file bytes with the correct `Content-Type` header based on file extension and MIME type detection (FR15, FR16)
**And** the response includes `Content-Disposition` header with the filename
**And** the response returns within 1 second for files up to 10MB (NFR5)

**Given** the requested file does not exist
**When** the API route is called
**Then** a 404 response is returned with a clear error message

**Given** a request includes path traversal characters (e.g., `../`)
**When** the API route validates the path
**Then** the request is rejected with a 400 response — no directory traversal outside the task directory

**Given** a file has an ambiguous or missing extension
**When** MIME type detection runs
**Then** the system falls back to `application/octet-stream` and the viewer uses the download fallback

**And** the API route is created at `dashboard/app/api/tasks/[taskId]/files/[...path]/route.ts`
**And** MIME type detection uses a standard library (e.g., `mime-types` package)

### Story 2.2: Viewer Modal Shell with Text and Code Viewers

As a **user**,
I want to click a file in the Files tab and see it rendered in a viewer modal with support for text and code files,
So that I can read plain text, CSV data, and syntax-highlighted code without leaving the dashboard.

**Acceptance Criteria:**

**Given** the Files tab is open on a task (Story 1.3)
**When** the user clicks a file entry in the file list
**Then** a `DocumentViewerModal` opens as a centered modal overlay (FR7)
**And** the modal header shows: file name, file size, file type badge
**And** the modal includes a "Download" button that triggers a browser download of the file (FR14)
**And** the modal can be closed with Escape key or clicking outside

**Given** the user opens a plain text file (`.txt`, `.csv`, `.log`, `.json`, `.xml`, `.yaml`, `.yml`)
**When** the viewer renders
**Then** the content is displayed as plain text in a monospace font with zoom controls (increase/decrease font size) (FR13)
**And** the viewer opens and renders within 2 seconds for files up to 10MB (NFR3)

**Given** the user opens a code file (`.py`, `.ts`, `.tsx`, `.js`, `.jsx`, `.java`, `.go`, `.rs`, `.rb`, `.php`, `.c`, `.cpp`, `.h`, `.css`, `.scss`, `.sql`, `.sh`, `.bash`, `.zsh`, `.swift`, `.kt`)
**When** the viewer renders
**Then** the content is displayed with syntax highlighting using `react-syntax-highlighter` and line numbers (FR9)
**And** the language is auto-detected from the file extension
**And** zoom controls adjust font size

**Given** the user opens an unsupported or unrecognized file type
**When** the viewer cannot render it
**Then** the modal shows a message: "Preview not available for this file type" with a prominent Download button as fallback (NFR13)

**And** `DocumentViewerModal.tsx` is created as a reusable modal component
**And** `useDocumentFetch.ts` hook fetches file content from the serving API (Story 2.1)
**And** the viewer uses a type-detection switch to route to the appropriate sub-viewer
**And** the component follows ShadCN design tokens and Tailwind spacing

### Story 2.3: PDF Viewer

As a **user**,
I want to view PDF files in the dashboard with page navigation and zoom,
So that I can read documents like financial reports and contracts without opening an external app.

**Acceptance Criteria:**

**Given** the user opens a PDF file from the Files tab
**When** the DocumentViewerModal renders
**Then** the PDF is displayed using `react-pdf` (or `pdfjs-dist`) with the first page visible (FR8)
**And** page navigation controls are visible: previous page, next page, current page / total pages indicator
**And** zoom controls are visible: zoom in, zoom out, fit-to-width
**And** the first page renders within 2 seconds for files up to 10MB (NFR3)

**Given** the user clicks next/previous page
**When** navigation is triggered
**Then** the target page renders within 500ms (NFR4)

**Given** the user changes zoom level
**When** zoom is applied
**Then** the current page re-renders at the new zoom level without losing page position

**Given** a PDF file is corrupted or cannot be parsed
**When** the viewer attempts to render it
**Then** an error message is shown: "Unable to render this PDF" with the Download button as fallback (NFR13)

**And** `react-pdf` (or equivalent) is added as a dependency
**And** PDF worker is configured correctly for Next.js (web worker or CDN worker)
**And** the PDF viewer sub-component is integrated into the DocumentViewerModal type switch

### Story 2.4: HTML and Markdown Viewers with Raw Toggle

As a **user**,
I want to view HTML and Markdown files in rendered mode and toggle to raw source,
So that I can read agent-produced reports beautifully and inspect the source when needed.

**Acceptance Criteria:**

**Given** the user opens an HTML file (`.html`, `.htm`)
**When** the DocumentViewerModal renders
**Then** the HTML content is displayed in a sandboxed iframe (`sandbox="allow-same-origin"`) showing the rendered page (FR10)
**And** a toggle button "Raw / Rendered" is visible in the viewer toolbar
**And** clicking "Raw" shows the HTML source code with syntax highlighting (reusing the code viewer from Story 2.2)
**And** clicking "Rendered" returns to the sandboxed iframe view
**And** the viewer opens within 2 seconds (NFR3)

**Given** the user opens a Markdown file (`.md`, `.markdown`)
**When** the DocumentViewerModal renders
**Then** the Markdown content is rendered as formatted HTML using a Markdown rendering library (e.g., `react-markdown` or `marked`) (FR11)
**And** the rendered view supports: headings, paragraphs, lists, tables, code blocks (with syntax highlighting), bold/italic, links, images (relative paths resolved)
**And** a toggle button "Raw / Rendered" is visible
**And** clicking "Raw" shows the raw Markdown source in monospace font
**And** clicking "Rendered" returns to the formatted view

**Given** the HTML file contains potentially dangerous content (scripts, external resources)
**When** the sandboxed iframe renders it
**Then** scripts do not execute and external resources are blocked by the sandbox attribute

**And** the HTML and Markdown viewer sub-components are integrated into the DocumentViewerModal type switch
**And** `react-markdown` (or equivalent) is added as a dependency for Markdown rendering

### Story 2.5: Image Viewer

As a **user**,
I want to view image files in the dashboard with zoom controls,
So that I can inspect screenshots, charts, and reference images without downloading them.

**Acceptance Criteria:**

**Given** the user opens an image file (`.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.webp`, `.bmp`, `.ico`)
**When** the DocumentViewerModal renders
**Then** the image is displayed using a native `<img>` element centered in the viewer area (FR12)
**And** zoom controls are available: zoom in, zoom out, fit-to-container, actual size (1:1)
**And** the image loads within 2 seconds for files up to 10MB (NFR3)

**Given** the user zooms in on an image
**When** the image exceeds the viewer area
**Then** scroll/pan is available to navigate the zoomed image

**Given** the image file is corrupted or in an unrecognized format
**When** the viewer attempts to render it
**Then** a broken image placeholder is shown with the Download button as fallback (NFR13)

**And** the image viewer sub-component is integrated into the DocumentViewerModal type switch

## Epic 3: Agent File Integration

Agent receives file context when assigned a task, works with attached files using existing tools, produces output files, and the dashboard reflects agent-produced files — completing the full attach-to-view loop. Lead Agent uses file metadata for intelligent routing.

### Story 3.1: Inject File Context into Agent Task Context

As a **developer**,
I want agents to receive the task directory path and file manifest when they're assigned a task,
So that agents know what files are available and where to read/write them.

**Acceptance Criteria:**

**Given** a task has been assigned to an agent and has files in its manifest
**When** the agent receives the task context via the bridge
**Then** the context includes `filesDir`: the absolute path to `~/.nanobot/tasks/{task-id}/` (FR17)
**And** the context includes `fileManifest`: an array of `{ name, type, size, subfolder }` for all files currently on the task (FR18)
**And** the manifest data is fetched fresh from Convex at the time of context delivery — no stale data (NFR8)

**Given** the agent receives the file context
**When** the agent uses its existing `read` tool on a file in `{filesDir}/attachments/`
**Then** the agent can read the file content successfully (FR19)

**Given** the agent uses its existing `write` tool to create a file in `{filesDir}/output/`
**When** the write completes
**Then** the file is persisted in the task's output directory (FR20)

**Given** a task has no files
**When** the agent receives the task context
**Then** `filesDir` is still provided (the directory exists from Story 1.1)
**And** `fileManifest` is an empty array

**Given** new files are attached to a task by the user while the agent is working
**When** the agent fetches updated context on its next interaction cycle
**Then** the `fileManifest` reflects the newly attached files (NFR8)

**And** context injection is implemented in the bridge/gateway layer where task context is assembled for agents
**And** the `filesDir` path uses the same filesystem-safe task ID conversion as Story 1.1
**And** an explicit instruction is included in the agent context: "Task has attached files at {filesDir}. Review the file manifest before starting work."

### Story 3.2: Bridge Manifest Sync for Agent Output Files

As a **developer**,
I want the system to automatically update the file manifest in Convex when an agent produces output files,
So that the dashboard reflects agent-produced artifacts without manual intervention.

**Acceptance Criteria:**

**Given** an agent writes a file to `{filesDir}/output/` during task execution
**When** the agent notifies the bridge that output files have been created (or the bridge performs a periodic scan of the output directory)
**Then** the bridge scans `~/.nanobot/tasks/{task-id}/output/` for all files
**And** for each file found, the bridge constructs metadata: `{ name, type (from extension), size (bytes), subfolder: "output", uploadedAt (ISO 8601) }` (FR21)
**And** the bridge updates the Convex task record's `files` array with the new output file entries (FR24)
**And** the manifest update is reflected in Convex within 5 seconds of the agent notification (NFR7)
**And** an activity event is created: "{agent name} produced output file(s): {file names}"

**Given** the bridge scans the output directory
**When** files exist on the filesystem that are not in the Convex manifest
**Then** the missing files are added to the manifest (reconciliation) (NFR11)

**Given** the Convex manifest lists output files that no longer exist on the filesystem
**When** the bridge detects the discrepancy during reconciliation
**Then** the orphaned entries are removed from the manifest (NFR11)
**And** a warning is logged to stdout: "Manifest reconciliation: removed {count} orphaned entries"

**Given** the manifest is updated in Convex
**When** the dashboard's reactive query fires
**Then** the new output files appear in the Files tab and the TaskCard file count updates automatically (builds on Story 1.3 and 1.5)

**And** manifest sync logic is implemented in `nanobot/mc/bridge.py`
**And** the bridge uses the existing retry logic (3x exponential backoff) for the Convex manifest update mutation

### Story 3.3: Lead Agent File-Aware Routing

As a **user**,
I want the Lead Agent to consider attached file metadata when routing tasks to specialist agents,
So that tasks with documents are routed to agents best equipped to handle them.

**Acceptance Criteria:**

**Given** a task is created with file attachments and no assigned agent (status "inbox")
**When** the Lead Agent picks up the task for routing
**Then** the Lead Agent receives the file manifest as part of the task context (FR28)
**And** the manifest includes file names, types, and sizes for all attached files

**Given** the Lead Agent selects an agent for the task
**When** the delegation message is constructed
**Then** the delegation includes file metadata context: number of files, file types, total size, and file names (FR29)
**And** the delegation message example: "Task includes 1 attached PDF (847KB): relatorio-fev-2026.pdf. File is available at the task's attachments directory."

**Given** a task has no file attachments
**When** the Lead Agent routes the task
**Then** routing proceeds normally without file metadata — no error or empty file context noise

**And** file-aware routing is implemented in `nanobot/mc/orchestrator.py` where Lead Agent context is assembled
**And** the file metadata enriches the delegation context but does not change the capability-matching algorithm itself (file awareness informs, not overrides)
