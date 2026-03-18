# Story 12.1: Board Agent Memory Mode (Clean vs. With History)

Status: ready-for-dev

## Story

As an **admin**,
I want to choose whether agents in a board use shared memory (symlink) or clean memory (new files),
so that I can control context isolation between boards.

## Acceptance Criteria

### AC1: Schema Extension -- `agentMemoryModes` on boards table

**Given** the existing `boards` table in `dashboard/convex/schema.ts`
**When** the schema is extended
**Then** the `boards` table gains a new optional field:
```typescript
agentMemoryModes: v.optional(v.array(v.object({
  agentName: v.string(),
  mode: v.union(v.literal("clean"), v.literal("with_history")),
})))
```
**And** the Convex dev server starts without schema validation errors
**And** existing boards without `agentMemoryModes` continue to function (default behavior = clean)

### AC2: Board Update Mutation Accepts `agentMemoryModes`

**Given** the `boards.update` mutation in `dashboard/convex/boards.ts`
**When** a client sends an update with `agentMemoryModes`
**Then** the mutation accepts and persists the `agentMemoryModes` array alongside other board fields
**And** partial updates work -- sending only `agentMemoryModes` does not clear `displayName`, `description`, or `enabledAgents`
**And** an activity event is written for the update

### AC3: Frontend Memory Mode Toggle in BoardSettingsSheet

**Given** a board has `enabledAgents` configured in `BoardSettingsSheet.tsx`
**When** the admin views the board settings
**Then** for each enabled agent, a toggle appears below the agent checkbox: "Clean" | "With History"
**And** the default selection is "Clean" for agents without a saved mode
**And** toggling the mode updates local state immediately
**And** clicking Save persists the `agentMemoryModes` array to Convex via `boards.update`
**And** agents that are not in `enabledAgents` do not show a memory mode toggle
**And** system agents (lead-agent, mc-agent) do not show a memory mode toggle (they always use clean)

### AC4: Backend -- `with_history` Mode Creates Symlinks

**Given** a task is dispatched on a board where an agent has `mode: "with_history"`
**When** `_resolve_board_workspace()` runs for that agent
**Then** the board-scoped `MEMORY.md` is a symlink to the global `~/.nanobot/agents/{agent-name}/memory/MEMORY.md`
**And** the board-scoped `HISTORY.md` is a symlink to the global `~/.nanobot/agents/{agent-name}/memory/HISTORY.md`
**And** if the global files do not exist, they are created empty before symlinking
**And** if a regular file already exists at the board-scoped path (from a previous "clean" run), it is replaced with the symlink
**And** reads/writes to the symlinked files correctly propagate to the global originals

### AC5: Backend -- `clean` Mode Preserves Current Behavior

**Given** a task is dispatched on a board where an agent has `mode: "clean"` or no mode configured
**When** `_resolve_board_workspace()` runs for that agent
**Then** the behavior matches the current implementation: copies global MEMORY.md as seed (first run) or uses existing board-scoped file
**And** if a symlink exists at the board-scoped path (from a previous "with_history" run), it is removed and replaced with a regular file
**And** HISTORY.md starts empty per board (current behavior preserved)

### AC6: Refactor -- Extract `_resolve_board_workspace` to `board_utils.py`

**Given** `_resolve_board_workspace` is duplicated in both `executor.py` (as a method on TaskExecutor) and `step_dispatcher.py` (as a module-level function)
**When** the refactoring is applied
**Then** a new module `nanobot/mc/board_utils.py` is created containing the single canonical `resolve_board_workspace()` function
**And** both `executor.py` and `step_dispatcher.py` import and call `resolve_board_workspace()` from `board_utils.py`
**And** the duplicated implementations are removed from both files
**And** the function signature accepts the memory mode ("clean" | "with_history") as a parameter with default "clean"
**And** all existing tests continue to pass

### AC7: Bridge Query for Board Memory Modes

**Given** the Python backend needs to know the memory mode for an agent on a board
**When** the executor or step_dispatcher resolves board workspace
**Then** the board data (already fetched via `bridge.get_board_by_id()`) includes `agentMemoryModes`
**And** the workspace resolver extracts the mode for the specific agent from the board data
**And** if the agent is not listed in `agentMemoryModes`, default to "clean"

## Tasks / Subtasks

- [ ] **Task 1: Extend Convex Schema** (AC: #1)
  - [ ] 1.1 In `dashboard/convex/schema.ts`, add `agentMemoryModes` field to the `boards` table definition:
    ```typescript
    agentMemoryModes: v.optional(v.array(v.object({
      agentName: v.string(),
      mode: v.union(v.literal("clean"), v.literal("with_history")),
    }))),
    ```
    Add it after `enabledAgents` (line ~9, between `enabledAgents` and `isDefault`).
  - [ ] 1.2 Verify `npx convex dev` starts without errors and existing board documents remain valid.

- [ ] **Task 2: Update Board Mutations** (AC: #2)
  - [ ] 2.1 In `dashboard/convex/boards.ts`, update the `update` mutation args to accept `agentMemoryModes`:
    ```typescript
    agentMemoryModes: v.optional(v.array(v.object({
      agentName: v.string(),
      mode: v.union(v.literal("clean"), v.literal("with_history")),
    }))),
    ```
    Add it to the `args` object (around line ~91).
  - [ ] 2.2 In the `update` handler, add `agentMemoryModes` to the patch object (follow the same pattern as `enabledAgents` on line ~104):
    ```typescript
    if (args.agentMemoryModes !== undefined) patch.agentMemoryModes = args.agentMemoryModes;
    ```
  - [ ] 2.3 Verify existing board updates (displayName, description, enabledAgents) continue to work without regression.

- [ ] **Task 3: Frontend Memory Mode Toggle** (AC: #3)
  - [ ] 3.1 In `dashboard/components/BoardSettingsSheet.tsx`, add state for memory modes:
    ```typescript
    const [agentMemoryModes, setAgentMemoryModes] = useState<Array<{ agentName: string; mode: "clean" | "with_history" }>>([]);
    ```
  - [ ] 3.2 In the `useEffect` that syncs board data (line ~47), also initialize `agentMemoryModes` from `board.agentMemoryModes ?? []`.
  - [ ] 3.3 Create a helper function to get/set the mode for a given agent:
    ```typescript
    const getAgentMode = (agentName: string): "clean" | "with_history" => {
      return agentMemoryModes.find((m) => m.agentName === agentName)?.mode ?? "clean";
    };
    const toggleAgentMode = (agentName: string) => {
      setAgentMemoryModes((prev) => {
        const current = prev.find((m) => m.agentName === agentName);
        const newMode = current?.mode === "with_history" ? "clean" : "with_history";
        return [
          ...prev.filter((m) => m.agentName !== agentName),
          { agentName, mode: newMode },
        ];
      });
    };
    ```
  - [ ] 3.4 In the "Registered agents" section (line ~160), below each agent checkbox that is checked (enabled), render a small toggle:
    ```tsx
    {enabledAgents.includes(agent.name) && (
      <div className="ml-7 flex items-center gap-2 text-xs text-muted-foreground">
        <span>Memory:</span>
        <button
          onClick={() => toggleAgentMode(agent.name)}
          className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
            getAgentMode(agent.name) === "clean"
              ? "bg-muted text-foreground"
              : "bg-transparent text-muted-foreground"
          }`}
        >
          Clean
        </button>
        <button
          onClick={() => toggleAgentMode(agent.name)}
          className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
            getAgentMode(agent.name) === "with_history"
              ? "bg-muted text-foreground"
              : "bg-transparent text-muted-foreground"
          }`}
        >
          With History
        </button>
      </div>
    )}
    ```
  - [ ] 3.5 In `handleSave` (line ~85), pass `agentMemoryModes` to the `updateBoard` mutation:
    ```typescript
    await updateBoard({
      boardId: activeBoardId as Id<"boards">,
      displayName: displayName.trim() || board.displayName,
      description: description.trim() || undefined,
      enabledAgents,
      agentMemoryModes,
    });
    ```
  - [ ] 3.6 Verify system agents (from `SYSTEM_AGENT_NAMES`) do NOT show the memory mode toggle. They are rendered in the system agents section (line ~144) with `disabled` checkboxes, which already excludes them from the toggle.

- [ ] **Task 4: Refactor -- Extract `board_utils.py`** (AC: #6)
  - [ ] 4.1 Create `nanobot/mc/board_utils.py` with the canonical `resolve_board_workspace()` function. Base it on the existing implementation in `step_dispatcher.py` (lines 43-67) since that is the standalone version:
    ```python
    def resolve_board_workspace(
        board_name: str,
        agent_name: str,
        mode: str = "clean",
    ) -> Path:
    ```
  - [ ] 4.2 Add the memory mode logic inside the function:
    - If `mode == "with_history"`: create symlinks from `board_workspace/memory/MEMORY.md` and `board_workspace/memory/HISTORY.md` to their global counterparts at `~/.nanobot/agents/{agent_name}/memory/`. If the global files do not exist, create them empty first. If a regular file (not symlink) already exists at the board path, remove it before creating the symlink.
    - If `mode == "clean"` (default): preserve current behavior (copy global MEMORY.md as seed on first run, empty HISTORY.md). If a symlink exists at the board path, unlink it and create a regular file.
  - [ ] 4.3 Add a helper function to extract agent memory mode from board data:
    ```python
    def get_agent_memory_mode(
        board_data: dict[str, Any] | None,
        agent_name: str,
    ) -> str:
        """Return 'clean' or 'with_history' for the given agent on a board."""
        if not board_data:
            return "clean"
        modes = board_data.get("agent_memory_modes") or []
        for entry in modes:
            if entry.get("agent_name") == agent_name:
                return entry.get("mode", "clean")
        return "clean"
    ```
  - [ ] 4.4 In `nanobot/mc/executor.py`, remove the `_resolve_board_workspace` method from `TaskExecutor` (lines 426-468). Replace all calls with:
    ```python
    from nanobot.mc.board_utils import resolve_board_workspace, get_agent_memory_mode
    ```
    Update the call site in `_execute_task` (around line 744) to pass the memory mode:
    ```python
    mode = get_agent_memory_mode(board, agent_name)
    memory_workspace = resolve_board_workspace(board_name, agent_name, mode=mode)
    ```
  - [ ] 4.5 In `nanobot/mc/step_dispatcher.py`, remove the module-level `_resolve_board_workspace` function (lines 43-67). Replace the import/call at line 386 with:
    ```python
    from nanobot.mc.board_utils import resolve_board_workspace, get_agent_memory_mode
    ```
    Update the call site (around line 386) to pass the memory mode:
    ```python
    mode = get_agent_memory_mode(board, agent_name) if isinstance(board, dict) else "clean"
    memory_workspace = resolve_board_workspace(board_name, agent_name, mode=mode)
    ```
  - [ ] 4.6 Run `uv run pytest` to confirm all existing tests pass with no regressions.

- [ ] **Task 5: Implement Symlink Logic in `resolve_board_workspace`** (AC: #4, #5)
  - [ ] 5.1 In `board_utils.py`, implement the `with_history` branch:
    ```python
    if mode == "with_history":
        global_memory_dir = Path.home() / ".nanobot" / "agents" / agent_name / "memory"
        global_memory_dir.mkdir(parents=True, exist_ok=True)
        for fname in ("MEMORY.md", "HISTORY.md"):
            global_file = global_memory_dir / fname
            board_file = memory_dir / fname
            # Ensure global file exists
            if not global_file.exists():
                global_file.write_text("", encoding="utf-8")
            # Replace regular file or stale symlink with correct symlink
            if board_file.is_symlink():
                if board_file.resolve() == global_file.resolve():
                    continue  # Already correct
                board_file.unlink()
            elif board_file.exists():
                board_file.unlink()
            os.symlink(global_file, board_file)
    ```
  - [ ] 5.2 In `board_utils.py`, implement the `clean` branch (guard against leftover symlinks):
    ```python
    else:  # mode == "clean"
        memory_md = memory_dir / "MEMORY.md"
        if memory_md.is_symlink():
            memory_md.unlink()
        if not memory_md.exists():
            # Bootstrap from global
            global_memory = Path.home() / ".nanobot" / "agents" / agent_name / "memory" / "MEMORY.md"
            if global_memory.exists():
                shutil.copy2(global_memory, memory_md)
            else:
                memory_md.write_text("", encoding="utf-8")
        history_md = memory_dir / "HISTORY.md"
        if history_md.is_symlink():
            history_md.unlink()
        if not history_md.exists():
            history_md.write_text("", encoding="utf-8")
    ```
  - [ ] 5.3 Add `import os` to board_utils.py (needed for `os.symlink`).

- [ ] **Task 6: Write Tests** (AC: #4, #5, #6)
  - [ ] 6.1 Create `tests/mc/test_board_utils.py` with unit tests:
    - `test_resolve_board_workspace_clean_creates_dirs` -- verify directory creation and empty files
    - `test_resolve_board_workspace_clean_bootstraps_from_global` -- verify global MEMORY.md is copied
    - `test_resolve_board_workspace_with_history_creates_symlinks` -- verify symlinks point to global files
    - `test_resolve_board_workspace_with_history_creates_global_if_missing` -- verify global files created
    - `test_resolve_board_workspace_clean_replaces_symlinks` -- switching from with_history to clean replaces symlinks with regular files
    - `test_resolve_board_workspace_with_history_replaces_regular_files` -- switching from clean to with_history replaces regular files with symlinks
    - `test_get_agent_memory_mode_defaults_to_clean` -- no modes configured returns "clean"
    - `test_get_agent_memory_mode_returns_configured_mode` -- returns "with_history" when configured
  - [ ] 6.2 Use `tmp_path` fixture and monkeypatch `Path.home()` to isolate filesystem operations.
  - [ ] 6.3 Run `uv run pytest tests/mc/test_board_utils.py -v` to verify all new tests pass.
  - [ ] 6.4 Run `uv run pytest` to verify no regressions in existing tests.

## Dev Notes

### Architecture Patterns

**Symlink Strategy for `with_history` mode:**
The key insight is that `with_history` means the board should share the agent's global memory. Using `os.symlink()` is the cleanest approach because:
1. The AgentLoop's MemoryStore reads/writes `MEMORY.md` via the workspace path -- if that path is a symlink, all reads/writes transparently go to the global file.
2. Multiple boards with `with_history` for the same agent will all point to the same global file -- memory stays synchronized.
3. Switching modes is safe: just remove the symlink and create a regular file (or vice versa).

**Bridge key conversion:** Convex stores `agentMemoryModes` (camelCase), but the bridge auto-converts to `agent_memory_modes` (snake_case) in Python. The `get_agent_memory_mode()` helper must use snake_case keys: `board_data.get("agent_memory_modes")` and `entry.get("agent_name")`.

**Race condition mitigation:** If two tasks on the same board start simultaneously and the mode has changed, both will attempt to swap the file/symlink. Use `try/except FileExistsError` around symlink creation and re-check state after unlinking.

**Common mistake to avoid:** Do NOT use `shutil.copy2` to copy a symlink -- it copies the target file, not the symlink. Use `os.symlink()` explicitly. Also, `Path.exists()` returns False for broken symlinks, so check `Path.is_symlink()` first.

### Project Structure Notes

**Files to CREATE:**
- `nanobot/mc/board_utils.py` -- canonical board workspace resolution
- `tests/mc/test_board_utils.py` -- unit tests

**Files to MODIFY:**
- `dashboard/convex/schema.ts` -- add `agentMemoryModes` to boards table
- `dashboard/convex/boards.ts` -- accept `agentMemoryModes` in update mutation
- `dashboard/components/BoardSettingsSheet.tsx` -- memory mode toggle per agent
- `nanobot/mc/executor.py` -- remove `_resolve_board_workspace`, import from board_utils
- `nanobot/mc/step_dispatcher.py` -- remove `_resolve_board_workspace`, import from board_utils

### References

- [Source: `dashboard/convex/schema.ts`] -- Existing boards table definition (lines 5-16)
- [Source: `dashboard/convex/boards.ts`] -- Board CRUD mutations, especially `update` (lines 87-114)
- [Source: `dashboard/components/BoardSettingsSheet.tsx`] -- Board settings UI with agent checklist (lines 57-172)
- [Source: `nanobot/mc/executor.py`] -- `TaskExecutor._resolve_board_workspace()` method (lines 426-468) and its call site in `_execute_task` (lines 732-756)
- [Source: `nanobot/mc/step_dispatcher.py`] -- Module-level `_resolve_board_workspace()` (lines 43-67) and its call site in `_execute_step` (lines 378-386)
- [Source: `nanobot/mc/bridge.py`] -- `get_board_by_id()` method (board data already includes all fields)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
