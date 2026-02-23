# Story 9-11: Inject File Context into Agent Task Context

**Epic:** 9 — Thread Files Context: Agent File Integration
**Status:** done

## Story

As a **developer**,
I want agents to receive the task directory path and file manifest when they're assigned a task,
So that agents know what files are available and where to read/write them.

## Acceptance Criteria

**Given** a task has been assigned to an agent and has files in its manifest
**When** the agent receives the task context via the bridge
**Then** the context includes `filesDir`: the absolute path to `~/.nanobot/tasks/{task-id}/` (FR17)
**And** the context includes `fileManifest`: array of `{ name, type, size, subfolder }` for all files (FR18)
**And** the manifest data is fetched fresh from Convex at the time of context delivery (NFR8)

**Given** a task has no files
**When** the agent receives the task context
**Then** `filesDir` is still provided (the directory exists from Story 9-1)
**And** `fileManifest` is an empty array

**Given** new files are attached to a task while the agent is working
**When** the agent fetches updated context on its next interaction cycle
**Then** the `fileManifest` reflects the newly attached files (NFR8)

## Technical Notes

- Working directory: `nanobot/` (Python backend)
- Find where task context is assembled for agents. Look in:
  - `nanobot/mc/gateway.py` — where tasks are dispatched to agents
  - `nanobot/mc/bridge.py` — context assembly
  - `nanobot/mc/orchestrator.py` — task routing
  - `nanobot/mc/types.py` — task data model
- The task object from Convex already has a `files` field (optional array added in Story 9-1)
- Context injection: when building the task context dict passed to the agent, add:
  ```python
  safe_id = re.sub(r"[^\w\-]", "_", task_id)
  files_dir = str(Path.home() / ".nanobot" / "tasks" / safe_id)
  file_manifest = [
      {"name": f["name"], "type": f["type"], "size": f["size"], "subfolder": f["subfolder"]}
      for f in (task_data.get("files") or [])
  ]
  ```
- Add to context dict:
  ```python
  context["filesDir"] = files_dir
  context["fileManifest"] = file_manifest
  ```
- Add explicit instruction in the context/prompt:
  - If `file_manifest` is non-empty: `"Task has {n} attached file(s) at {files_dir}. Review the file manifest before starting work: {manifest_summary}"`
  - `manifest_summary`: comma-separated `"{name} ({subfolder}, {size_human})"` for each file
- Use the same filesystem-safe ID conversion as in `bridge.py` `create_task_directory`
- NFR8: context is assembled fresh from the Convex task record each time — no caching of the files field

## NFRs Covered
- NFR8: Agent receives updated file manifest within 1 second of its next task context fetch
