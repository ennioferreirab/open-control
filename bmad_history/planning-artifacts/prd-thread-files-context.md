---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-02b-vision
  - step-02c-executive-summary
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
  - step-12-complete
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
  - (reference) sei-workflows/packages/shared-chat - DocumentViewerModal component
workflowType: 'prd'
documentCounts:
  briefs: 0
  research: 0
  brainstorming: 0
  projectDocs: 3
classification:
  projectType: Web App (feature extension to existing real-time SPA + Python backend)
  domain: AI Agent DevOps
  complexity: medium-high
  projectContext: brownfield
---

# Product Requirements Document - Thread Files Context

**Author:** Ennio
**Date:** 2026-02-23

## Executive Summary

Thread Files Context adds a file layer to nanobot Mission Control's task system. Today, tasks are text-only — a title, description, and threaded agent messages. But real agent work routinely involves documents: PDFs to analyze, reports to generate, code to review, spreadsheets to reference. Without a structured file mechanism, agent inputs and outputs have no home, and users have no way to provide reference material or view agent-produced artifacts directly in the dashboard.

This feature introduces a filesystem-backed directory per task, where users attach input files at creation time (or later), and agents produce output files during execution. The agent — which already has terminal, read, write, and exec tools — simply receives the task directory path as part of its context and uses its existing capabilities to interact with the files. No RAG pipeline, no embedding search, no chunking. The dashboard completes the loop with a multi-format file viewer (adapted from the proven sei-workflows DocumentViewerModal) that renders PDFs, DOCX, HTML, Markdown, code, and images directly within the task card detail view.

Target user: Ennio (primary) — nanobot Mission Control operator who needs agents to work with documents, not just text prompts.

### What Makes This Special

**Zero new AI infrastructure.** The agent already knows how to read files, execute commands, and write output. The missing piece is purely structural — a directory convention, a path in the task context, and a dashboard viewer. This follows nanobot's philosophy: maximum capability with minimum complexity.

**Files as first-class task artifacts.** Input attachments and agent outputs live alongside the task's conversation thread. One click on a task card reveals everything — messages, files in, files out. Context travels with the task.

**Battle-tested viewer.** The file viewer is adapted from sei-workflows' DocumentViewerModal — a production-proven component supporting 8 file formats with zoom, pagination, raw/rendered toggle for HTML and Markdown, and sandboxed rendering. Not built from scratch.

## Project Classification

- **Project Type:** Web App — feature extension to the existing nanobot Mission Control real-time SPA (Next.js + Convex) and Python backend
- **Domain:** AI Agent DevOps — multi-agent coordination and operations
- **Complexity:** Medium-High — touches data model (Convex schema + filesystem), dashboard UX (attachment UI + multi-format viewer), Python backend (directory management, agent context injection), and file serving infrastructure
- **Project Context:** Brownfield — extends the existing Mission Control task system, Convex schema, and dashboard components

## Success Criteria

### User Success

- User attaches a PDF to a task at creation time, and the agent explicitly references the file content in its work output — the user can see the agent *used* the document, not just acknowledged it
- User clicks the file viewer on a task card and reads an agent-produced Markdown report rendered beautifully in the dashboard — no need to open a terminal or file explorer
- User attaches additional files to an existing task, and the agent on its next interaction is aware of the new files via the updated manifest
- File attachment is as fast as task creation — drag-and-drop or file picker, file appears immediately (optimistic UI)
- Viewing a file (PDF, HTML, Markdown, code, images, text) works in one click from the task card detail view — no downloads, no external apps

### Business Success

- **1-month target:** Ennio uses file attachments on 50%+ of tasks where documents are involved — it replaces the workaround of pasting text or referencing external paths
- **3-month target:** Agent-produced outputs (reports, summaries, analyses) are the primary way Ennio consumes agent work — viewing in dashboard, not hunting in terminal
- Feature validates that nanobot agents can work with documents as naturally as they work with text prompts, opening the door for more complex agent workflows (multi-document analysis, research pipelines)

### Technical Success

- Task directory creation is atomic with task creation — no orphaned tasks without directories, no directories without tasks
- File manifest (names, types, sizes) is reliably passed to the agent as part of task context — agent never has to guess what files exist
- File serving from filesystem to dashboard is fast enough that the viewer feels instant for files under 10MB
- The multi-format viewer renders correctly for all MVP file types (PDF, HTML raw/rendered, Markdown raw/rendered, code with syntax highlighting, images, plain text)
- Agent output files appear in the task's file list without manual refresh — dashboard picks up new files reactively

### Measurable Outcomes

- File viewer renders PDF files correctly (pages, zoom, pagination)
- File viewer renders code with syntax highlighting for 20+ languages
- File viewer toggles HTML and Markdown between raw and rendered modes
- Agent receives file manifest with accurate metadata (name, type, size) for all attached files
- Task directory structure: `{tasks_root}/{task-id}/attachments/` for user files, `{tasks_root}/{task-id}/output/` for agent files

## User Journeys

### Journey 1: Ennio Attaches a PDF and Watches the Agent Work With It

**Opening Scene:** It's Monday morning. Ennio has received a 12-page financial report PDF from his accountant. He needs his Finance Agent to analyze the document, identify upcoming payments, and produce a summary. Today, he'd have to copy-paste excerpts into the task description or tell the agent a file path manually. With Thread Files Context, he doesn't.

**Rising Action:** Ennio opens the Mission Control dashboard. He types "Analyze the February financial report and list all payments due this week with amounts" in the task input. He clicks the attachment icon next to the input field, selects `relatorio-fev-2026.pdf` from his computer. The file name appears as a chip below the input. He hits Enter.

The task card appears in Inbox with a small paperclip icon indicating it has attachments. The Lead Agent picks it up, sees the file manifest in the task context — `attachments/relatorio-fev-2026.pdf (PDF, 847KB)` — and routes it to Finance Agent with a note: "Task includes 1 attached PDF financial report."

**Climax:** Finance Agent starts working. In the activity feed, Ennio sees: "Finance Agent reading relatorio-fev-2026.pdf." The agent reads the PDF using its existing tools, extracts the payment data, and writes a clean Markdown summary to `output/pagamentos-semana.md`. The task moves to Review.

Ennio clicks the task card. The detail Sheet opens. He clicks the **Files** tab and sees two entries:
- `attachments/relatorio-fev-2026.pdf` (input, 847KB)
- `output/pagamentos-semana.md` (output, 2KB)

He clicks the Markdown file. The viewer opens — beautifully rendered with a table of 4 payments totaling R$3,218.00, due dates, and payee names. He toggles to raw mode to verify the formatting, toggles back. He clicks the PDF to cross-check — the viewer shows the original document with page navigation and zoom. The numbers match.

**Resolution:** Ennio approves the task with one click. He downloads the Markdown summary for his records directly from the viewer. He never left the dashboard. He never opened a terminal. He never copy-pasted text from a PDF. The agent worked with the actual document, produced a structured output, and Ennio reviewed both — input and output — in the same viewer, in the same task card.

### Journey 2: Ennio Adds Files to an Existing Task

**Opening Scene:** Ennio created a research task yesterday: "Research AI agent orchestration trends for a blog post." The Research Agent is working on it, already in progress. Now Ennio finds a relevant article PDF and a competitor analysis spreadsheet he wants the agent to consider.

**Rising Action:** Ennio clicks the task card on the Kanban board. The detail Sheet opens. He clicks the **Files** tab — currently showing only `output/draft-notes.md` that the agent has started producing. He clicks the "Attach File" button, selects two files: `artigo-multi-agent.pdf` and `competitor-landscape.csv`. Both appear in the file list under `attachments/` with upload confirmation.

**Climax:** The file manifest in the task context updates. On the agent's next interaction cycle, it receives the updated manifest showing 2 new attachments. The Research Agent reads both files, incorporates the competitor data and article insights into its research, and updates `output/draft-notes.md` with a new section referencing the added materials. The activity feed shows: "Research Agent incorporated 2 new attachments into research."

**Resolution:** Ennio sees the output grow richer with each file he provides. The task becomes a living workspace — he feeds documents in, the agent produces refined output, he reviews it in the viewer. The feedback loop is visual, immediate, and entirely within the dashboard.

### Journey 3: Lead Agent Routes a Task with File Context

**Opening Scene:** Ennio creates a task: "Summarize this contract and flag any unusual clauses." He attaches `contrato-servicos-2026.pdf` (18 pages). No agent assigned — this goes to the Lead Agent for routing.

**Rising Action:** The Lead Agent picks up the task from Inbox. As part of the task context, it receives the file manifest: `attachments/contrato-servicos-2026.pdf (PDF, 2.3MB)`. The Lead Agent analyzes the task description *and* the file metadata — a PDF contract, legal analysis needed. It searches registered agents for capability match.

**Climax:** The Lead Agent finds no dedicated legal agent but identifies the Research Agent as the best fit for document analysis tasks. It delegates with enriched context: "Task involves analyzing an 18-page PDF contract (2.3MB). File is available at the task's attachments directory. Focus on identifying unusual clauses." The Research Agent picks up the task with full awareness of what files are waiting.

**Resolution:** The routing decision was informed by the file context — not just the text description. The Lead Agent didn't need to read the PDF itself; the manifest metadata (type, size, name) was enough to make an intelligent routing decision. The delegated agent received clear context about what files to expect.

### Journey Requirements Summary

| Journey | Capabilities Revealed |
|---------|----------------------|
| **Ennio + PDF** | File attachment at task creation (file picker + chip UI), task directory auto-creation, file manifest in agent context, agent output to `output/` folder, Files tab in task detail Sheet, multi-format viewer (PDF + Markdown), paperclip icon on task card |
| **Add Files Later** | Attach files to existing tasks from detail view, manifest update on agent's next cycle, agent awareness of new files, file list showing both attachments and outputs |
| **Lead Agent Routing** | File manifest included in Lead Agent context, file metadata informs routing decisions, enriched delegation context with file details passed to assigned agent |

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Feature MVP — deliver the complete file-attachment-to-viewer loop for a single user (Ennio). The MVP must cover the full cycle: attach file → agent sees it → agent produces output → user views both in dashboard. Any break in this chain means the feature doesn't work.

**Resource Requirements:** Solo developer (Ennio) extending the existing Mission Control codebase. Leverages the sei-workflows viewer component (not built from scratch). New work is: Next.js API routes (upload/serve), task directory management (Python), Convex schema extension (files field), viewer component adaptation, and dashboard UI (Files tab, attachment button).

### MVP Feature Set (Phase 1)

**Core User Journeys Supported:**
- Journey 1: Attach PDF at creation → agent works with it → view output in dashboard
- Journey 2: Add files to existing task → agent picks up new files
- Journey 3: Lead Agent routes task with file context awareness

**Must-Have Capabilities:**

| Category | Feature | Rationale |
|----------|---------|-----------|
| Filesystem | Task directory auto-creation (`attachments/` + `output/`) | Without this, files have no home |
| Upload | File picker on task creation + task detail view | Core user action — attach files |
| Convex | `files` field on task record (manifest array) | Dashboard needs to know what files exist |
| Agent context | `filesDir` path + `fileManifest` array in task context | Agent needs to know files are there |
| Agent output | Agent writes to `output/` using existing tools | Agent needs to produce artifacts |
| Bridge | Manifest sync — update Convex when agent creates output files | Dashboard must reflect agent output |
| File serving | Next.js API route to serve files from task directory | Viewer needs to fetch file content |
| Files UI | Files tab in TaskDetailSheet listing all files with type icons | User needs to see what files exist |
| Viewer - PDF | react-pdf with pages, zoom, pagination | Must-have per Ennio's requirements |
| Viewer - Code | react-syntax-highlighter with 20+ languages | Agent outputs code frequently |
| Viewer - HTML | Sandboxed iframe + raw toggle | Agents produce HTML reports |
| Viewer - Markdown | Rendered view + raw toggle | Primary agent output format |
| Viewer - Images | Native img with zoom | Reference screenshots, charts |
| Viewer - Text | Plain text with zoom | Logs, CSV, plain output |
| Task card indicator | Paperclip icon when task has files | Glanceable awareness on Kanban board |

### Post-MVP Features

**Phase 2 — Enhanced File Experience:**
- DOCX viewer (mammoth library)
- Drag-and-drop upload on task card and detail view
- File versioning (track overwrites with history)
- File size validation and limits
- Convex file storage sync (backup/portability)
- Bulk download as zip

**Phase 3 — Advanced File Intelligence:**
- Smart context loading (embeddings/summaries for selective file reading)
- File thumbnails/previews on Kanban cards
- Cross-task file references
- Collaborative editing of agent outputs
- File search across tasks

### Risk Mitigation Strategy

**Technical Risks:**

| Risk | Impact | Mitigation |
|------|--------|------------|
| Next.js API route file size limits | Large PDFs fail to upload | Use streaming upload, test with 50MB+ files early |
| react-pdf rendering issues with complex PDFs | Viewer shows blank or broken pages | Test with real-world PDFs (bank statements, contracts) during first implementation story |
| Agent doesn't reference attached files | Feature feels broken even though plumbing works | Include explicit instruction in agent context: "Task has attached files at {path}. Review them before starting work." |
| Manifest out of sync with filesystem | Dashboard shows files that don't exist or misses new ones | Bridge performs filesystem scan on manifest read, reconciles differences |
| Task ID format incompatible with filesystem paths | Directory creation fails | Use safe filename conversion for Convex IDs (already exists in nanobot helpers) |

**Resource Risks:**
- Viewer component adaptation from sei-workflows is the largest single effort — mitigated by reusing proven architecture, not innovating
- If viewer adaptation takes too long, fallback: text-only viewer (code + markdown + plain text) for first release, add PDF viewer in fast follow

## Functional Requirements

### File Attachment

- **FR1:** User can attach one or more files to a task at creation time via a file picker in the task input
- **FR2:** User can attach additional files to an existing task from the task detail view
- **FR3:** User can see attached file names as chips/indicators on the task input before submitting
- **FR4:** User can remove a pending attachment before task submission
- **FR5:** System creates a dedicated task directory with `attachments/` and `output/` subdirectories when a task is created

### File Viewing

- **FR6:** User can view a list of all files (attachments and outputs) in a Files tab within the task detail Sheet
- **FR7:** User can open any file from the file list in a multi-format viewer modal
- **FR8:** User can view PDF files with page-by-page rendering, zoom controls, and pagination
- **FR9:** User can view code files with syntax highlighting and line numbers
- **FR10:** User can view HTML files in rendered mode and toggle to raw source view
- **FR11:** User can view Markdown files in rendered mode and toggle to raw source view
- **FR12:** User can view image files with zoom controls
- **FR13:** User can view plain text and CSV files with zoom controls
- **FR14:** User can download any file from the viewer

### File Serving

- **FR15:** System serves files from the task directory to the dashboard via an API endpoint
- **FR16:** System detects file type based on MIME type and file extension to route to the correct viewer

### Agent File Context

- **FR17:** System includes the task directory path in the agent's task context when the agent receives a task
- **FR18:** System includes a file manifest (name, type, size, subfolder) for all task files in the agent's task context
- **FR19:** Agent can read files from the task's `attachments/` directory using its existing tools
- **FR20:** Agent can write output files to the task's `output/` directory using its existing tools
- **FR21:** System updates the file manifest when the agent creates new output files

### File Manifest Management

- **FR22:** System stores file metadata (name, type, size, subfolder, uploadedAt) on the task record
- **FR23:** System updates the file manifest when the user uploads new attachments to an existing task
- **FR24:** System updates the file manifest when the agent produces new output files
- **FR25:** Dashboard reactively reflects file manifest changes (new files appear without manual refresh)

### Task Card File Indicators

- **FR26:** User can see a paperclip icon on task cards that have attached files on the Kanban board
- **FR27:** User can see the file count next to the paperclip icon on the task card

### Lead Agent File Awareness

- **FR28:** Lead Agent receives the file manifest as part of the task context when routing unassigned tasks
- **FR29:** Lead Agent can include file metadata context in its delegation message when assigning a task to a specialist agent

## Non-Functional Requirements

### Performance

- **NFR1:** File upload from dashboard to filesystem completes within 3 seconds for files up to 10MB
- **NFR2:** File list in the task detail Sheet loads within 1 second of opening the Files tab
- **NFR3:** File viewer opens and renders the first page/content within 2 seconds for files up to 10MB
- **NFR4:** PDF viewer page navigation (next/previous) renders within 500ms
- **NFR5:** File serving API endpoint returns file bytes with correct Content-Type within 1 second for files up to 10MB

### Integration

- **NFR6:** File manifest reflects a new user upload within 2 seconds of upload completion
- **NFR7:** File manifest reflects new agent output files within 5 seconds of the agent notifying the backend
- **NFR8:** Agent receives updated file manifest (including newly attached files) within 1 second of its next task context fetch — no stale manifests
- **NFR9:** Dashboard reactively displays new files without page refresh when the file manifest updates

### Reliability

- **NFR10:** Task directory creation never fails silently — if directory creation fails, the task creation fails with a clear error
- **NFR11:** File manifest is always reconcilable with the filesystem — the system can detect and resolve discrepancies (missing files, extra files)
- **NFR12:** File upload that fails mid-transfer does not leave partial files in the task directory
- **NFR13:** Viewer gracefully handles unsupported file types with a download fallback instead of a blank screen or error

## Technical Architecture — Web App Feature

### Overview

Thread Files Context is a feature extension to the existing nanobot Mission Control web app. It adds a filesystem-backed file layer to the task system. The architectural approach follows the existing stack conventions: Next.js API routes for file I/O (upload/serve), filesystem storage following the `~/.nanobot/` convention, and Convex for metadata tracking.

### File Upload Path (Browser → Filesystem)

- Next.js API route accepts multipart file upload from the dashboard
- Writes file to `~/.nanobot/tasks/{task-id}/attachments/`
- Returns file metadata (name, type, size) to the dashboard
- Dashboard updates Convex task record with file manifest entry
- Post-MVP: sync files to Convex storage for backup/portability

### File Serving Path (Filesystem → Browser)

- Next.js API route serves files from `~/.nanobot/tasks/{task-id}/`
- Route pattern: `/api/tasks/{task-id}/files/{subfolder}/{filename}`
- Serves raw bytes with correct `Content-Type` header
- Dashboard viewer fetches from this endpoint (same pattern as sei-workflows' `getDocumentBlob()`)

### Task Directory Structure

```
~/.nanobot/tasks/{task-id}/
├── attachments/          # User-uploaded input files
│   ├── relatorio-fev.pdf
│   └── dados.csv
└── output/               # Agent-produced output files
    ├── summary.md
    └── analysis.html
```

### File Manifest in Convex

- Task record gains a `files` field: array of `{ name, type, size, subfolder, uploadedAt }`
- `subfolder` is either `"attachments"` or `"output"`
- Manifest is the source of truth for the dashboard file list
- Agent output files: Python bridge scans `output/` directory and updates manifest in Convex when agent reports file creation
- User uploads: Next.js API route updates manifest on upload

### Agent Context Injection

- When an agent receives a task, the context includes:
  - `filesDir`: absolute path to `~/.nanobot/tasks/{task-id}/`
  - `fileManifest`: array of `{ name, type, size, subfolder }` for all files
- Agent uses its existing tools (`read`, `exec`, `write`) to interact with files
- Agent writes output to `{filesDir}/output/`
- After writing, agent notifies the bridge which updates the Convex manifest

### Viewer Component

- Adapted from sei-workflows `DocumentViewerModal`
- Fetches files via `/api/tasks/{task-id}/files/{subfolder}/{filename}`
- Same viewer architecture: `DocumentViewerModal` → `useDocumentFetch` → type detection → viewer switch
- MVP viewers: PDF, Code, HTML (raw/rendered), Markdown (raw/rendered), Images, Text/CSV

### Implementation Considerations

- Task directory is created by the Python backend (via bridge) when a task is created in Convex — the bridge listens for new tasks and ensures the directory exists
- Directory cleanup: when a task is deleted, the directory is removed (post-MVP — for now, directories persist)
- File size: no hard limit for MVP (single-user, localhost). Post-MVP: configurable max file size
- Concurrent access: not a concern for MVP (single agent per task, single user)
