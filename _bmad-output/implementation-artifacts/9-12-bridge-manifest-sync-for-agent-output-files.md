# Story 9-12: Bridge Manifest Sync for Agent Output Files

**Epic:** 9 — Thread Files Context: Agent File Integration
**Status:** ready-for-dev

## Story

As a **developer**,
I want the system to automatically update the file manifest in Convex when an agent produces output files,
So that the dashboard reflects agent-produced artifacts without manual intervention.

## Acceptance Criteria

**Given** an agent writes a file to `{filesDir}/output/` during task execution
**When** the task completes (status changes to "review" or "done")
**Then** the bridge scans `~/.nanobot/tasks/{task-id}/output/` for all files
**And** for each file, constructs metadata: `{ name, type (from extension), size (bytes), subfolder: "output", uploadedAt }`
**And** calls `addTaskFiles` Convex mutation to add any new output files not already in the manifest (FR21, FR24)
**And** the manifest update is reflected in Convex within 5 seconds of task completion (NFR7)
**And** an activity event is created: `"{agent name} produced output file(s): {file names}"`

**Given** the bridge scans the output directory
**When** files exist that are not in the Convex manifest
**Then** the missing files are added (reconciliation) (NFR11)

**Given** the Convex manifest lists output files that no longer exist on the filesystem
**When** the bridge detects the discrepancy
**Then** the orphaned entries are removed and a warning is logged (NFR11)

## Technical Notes

- Working directory: `nanobot/` (Python backend)
- Implement in `nanobot/mc/bridge.py` — add a `sync_task_output_files` method to `ConvexBridge`
- Trigger: called from `executor.py` after a task execution completes (after `_run_agent_on_task` returns)
- The method should:
  1. Scan `~/.nanobot/tasks/{safe_task_id}/output/` for all files
  2. Compare against existing `task.files` entries with `subfolder == "output"` (fetch fresh from Convex)
  3. For new files not in manifest: call `addTaskFiles` Convex mutation
  4. For manifest entries not on filesystem: call a Convex mutation to remove them (or update the full output section)
  5. Create activity event if new files were found

- MIME type from extension: reuse the same extension-to-type mapping logic (keep it simple — just the key types: pdf→application/pdf, md→text/markdown, html→text/html, txt→text/plain, csv→text/csv, json→application/json, py→text/x-python, etc., fallback to `application/octet-stream`)

- Convex mutations needed:
  - `addTaskFiles` already exists (Story 9-2)
  - For removing stale entries: add a new mutation `updateTaskOutputFiles` in `convex/tasks.ts` that replaces the output section entirely (easier than individual deletes):
    ```ts
    export const updateTaskOutputFiles = mutation({
      args: { taskId: v.id("tasks"), outputFiles: v.array(v.object({ name: v.string(), type: v.string(), size: v.number(), subfolder: v.string(), uploadedAt: v.string() })) },
      handler: async (ctx, { taskId, outputFiles }) => {
        const task = await ctx.db.get(taskId);
        if (!task) return;
        const attachments = (task.files ?? []).filter(f => f.subfolder === "attachments");
        await ctx.db.patch(taskId, { files: [...attachments, ...outputFiles] });
      },
    });
    ```

- Activity event message: `f"{agent_name} produced {len(new_files)} output file(s): {', '.join(f['name'] for f in new_files)}"`
- Use existing retry logic in bridge (3x exponential backoff) for Convex mutation calls
- Run filesystem scan in a thread (`asyncio.to_thread`) to avoid blocking the event loop

## NFRs Covered
- NFR7: Manifest reflects new agent output files within 5 seconds
- NFR11: Manifest is reconcilable with filesystem
