# Story 9-13: Lead Agent File-Aware Routing

**Epic:** 9 — Thread Files Context: Agent File Integration
**Status:** ready-for-dev

## Story

As a **user**,
I want the Lead Agent to consider attached file metadata when routing tasks to specialist agents,
So that tasks with documents are routed to agents best equipped to handle them.

## Acceptance Criteria

**Given** a task is created with file attachments and no assigned agent
**When** the Lead Agent picks up the task for routing
**Then** the Lead Agent receives the file manifest as part of the task context (FR28)
**And** the manifest includes file names, types, and sizes for all attached files

**Given** the Lead Agent selects an agent for the task
**When** the delegation message is constructed
**Then** the delegation includes file metadata: number of files, types, total size, and names (FR29)

**Given** a task has no file attachments
**When** the Lead Agent routes the task
**Then** routing proceeds normally without file metadata noise

## Technical Notes

- Working directory: `nanobot/` (Python backend)
- Find where the Lead Agent assembles context for routing — look in `nanobot/mc/orchestrator.py` and/or `nanobot/mc/planner.py`
- The task context already gets `filesDir` and `fileManifest` injected by executor.py (Story 9-11), but the Lead Agent routing path may be separate
- Find where the planning/routing prompt is built for the lead agent, and enrich it with file metadata if present
- File summary for lead agent context:
  ```python
  if file_manifest:
      types = list({f["subfolder"] + "/" + f["name"].rsplit(".", 1)[-1] for f in file_manifest})
      total_size = sum(f["size"] for f in file_manifest)
      def _human_size(b):
          return f"{b // 1024} KB" if b < 1024*1024 else f"{b/(1024*1024):.1f} MB"
      file_context = (
          f"Task has {len(file_manifest)} attached file(s) "
          f"(total {_human_size(total_size)}): "
          + ", ".join(f"{f['name']} ({_human_size(f['size'])})" for f in file_manifest)
      )
  ```
- Add `file_context` to the lead agent's routing prompt/context where capability matching happens
- The delegation message (when lead agent assigns a task to a specialist) should also include this summary
- Keep changes minimal — don't change the capability matching algorithm, only enrich the context it receives
