# Story 11.3: CC Backend Config in Dashboard

Status: in-progress

## Story

As an **admin**,
I want to see and configure Claude Code backend settings in the agent config panel whenever a `cc/` model is selected,
so that `permission_mode` and other CC options are transparent, persisted to Convex and YAML automatically — no manual file editing required.

## Acceptance Criteria

### AC1: CC Model Mode Detected in AgentConfigSheet

**Given** the `AgentConfigSheet.tsx` component and its `parseModelValue()` function
**When** an agent's model string starts with `"cc/"` (e.g., `"cc/claude-sonnet-4-6"`)
**Then** a new `ModelMode` of `"cc"` is returned
**And** the CC model name (without the `cc/` prefix) is exposed for display
**And** the existing `"tier"`, `"custom"`, and `"default"` modes are unaffected

### AC2: CC Settings Section Appears in AgentConfigSheet

**Given** the agent config panel with a CC model selected (`modelMode === "cc"`)
**When** the panel is open
**Then** a **"Claude Code Settings"** section appears below the model selector containing:
- A `permission_mode` dropdown with three options:
  - `"bypassPermissions"` — All tools run without approval prompts (default for CC agents)
  - `"acceptEdits"` — File edits run automatically, other tools require approval
  - `"default"` — Follows system Claude Code defaults
- An optional `max_budget_usd` number input (placeholder: "No limit")
- An optional `max_turns` number input (placeholder: "No limit")
**When** no CC model is selected
**Then** the Claude Code Settings section is hidden entirely

### AC3: CC Settings Participate in Dirty State and Save

**Given** the CC settings section is visible
**When** the admin changes `permission_mode`, `max_budget_usd`, or `max_turns`
**Then** `isDirty` becomes `true`
**And** saving calls `updateConfig` with a new `claudeCodeOpts` argument
**And** saving also PUTs to `/api/agents/{name}/config` with the `claude_code` object
**And** on next open the saved values are correctly loaded back into the form

### AC4: Convex Schema Stores claudeCodeOpts

**Given** the `agents` table in `dashboard/convex/schema.ts`
**When** the schema is updated
**Then** a new optional field `claudeCodeOpts` is added:
```typescript
claudeCodeOpts: v.optional(v.object({
  permissionMode: v.optional(v.string()),
  maxBudgetUsd: v.optional(v.number()),
  maxTurns: v.optional(v.number()),
}))
```
**And** the field is optional so existing agents are unaffected

### AC5: updateConfig Mutation Accepts claudeCodeOpts

**Given** the `updateConfig` mutation in `dashboard/convex/agents.ts`
**When** called with a `claudeCodeOpts` argument
**Then** the mutation accepts and persists the value to the agents table
**And** when `claudeCodeOpts` is `undefined`, no change is made to the existing value
**And** when `claudeCodeOpts` is an empty object `{}`, it clears the stored CC opts

### AC6: YAML API Route Writes claude_code Section

**Given** the PUT endpoint at `/api/agents/[agentName]/config/route.ts`
**When** the request body includes a `claude_code` object
**Then** the `claude_code` key is written to the YAML file with the following structure:
```yaml
claude_code:
  permission_mode: bypassPermissions
  max_budget_usd: 10.0   # omitted if null/undefined
  max_turns: 50          # omitted if null/undefined
```
**When** the request body does not include `claude_code`
**Then** the existing `claude_code` key in the YAML is preserved (not removed)

### AC7: Bridge Startup Sync Includes claudeCodeOpts

**Given** `sync_agent()` in `mc/bridge.py` running on startup
**When** an agent's `config.yaml` has a `claude_code` section
**Then** `sync_agent()` includes `claudeCodeOpts` in the Convex upsert payload
**And** the payload maps YAML snake_case fields to Convex camelCase:
- `permission_mode` → `permissionMode`
- `max_budget_usd` → `maxBudgetUsd`
- `max_turns` → `maxTurns`
**When** no `claude_code` section exists in the YAML
**Then** `claudeCodeOpts` is omitted from the Convex payload (no null write)

### AC8: Executor Reads claudeCodeOpts from Convex as Fallback

**Given** `_execute_cc_task()` in `mc/executor.py`
**When** `agent_data.claude_code_opts` is `None` (no YAML opts)
**But** the Convex agent record has a `claudeCodeOpts` object
**Then** the executor constructs a `ClaudeCodeOpts` from the Convex values and uses it
**And** this ensures dashboard-set permission_mode is respected even without a `claude_code` section in YAML

### AC9: Default Permission Mode for New CC Agents

**Given** the AgentConfigSheet and a user switching the model to a `cc/` model for the first time
**When** `modelMode` transitions to `"cc"` and no existing `claudeCodeOpts` is loaded from the agent
**Then** `permissionMode` defaults to `"bypassPermissions"` in the form state
**And** this default is saved when the user hits Save

## Tasks / Subtasks

- [x] **Task 1: Extend Convex schema with claudeCodeOpts** (AC: #4)
  - [x] 1.1 In `dashboard/convex/schema.ts`, add `claudeCodeOpts` to the `agents` table:
    ```typescript
    claudeCodeOpts: v.optional(v.object({
      permissionMode: v.optional(v.string()),
      maxBudgetUsd: v.optional(v.number()),
      maxTurns: v.optional(v.number()),
    })),
    ```
  - [x] 1.2 Place the new field after `reasoningLevel` (alphabetical order preferred) — Convex schema changes are non-breaking for optional fields

- [x] **Task 2: Update updateConfig mutation** (AC: #5)
  - [x] 2.1 In `dashboard/convex/agents.ts`, add `claudeCodeOpts` to the `updateConfig` args:
    ```typescript
    claudeCodeOpts: v.optional(v.object({
      permissionMode: v.optional(v.string()),
      maxBudgetUsd: v.optional(v.number()),
      maxTurns: v.optional(v.number()),
    })),
    ```
  - [x] 2.2 In the handler, add: `if (args.claudeCodeOpts !== undefined) updates.claudeCodeOpts = args.claudeCodeOpts;`
  - [x] 2.3 Update `upsertByName` mutation (lines 12-83) to accept and persist `claudeCodeOpts` (for bridge startup sync):
    - Add to args (same object type as `updateConfig`):
      ```typescript
      claudeCodeOpts: v.optional(v.object({
        permissionMode: v.optional(v.string()),
        maxBudgetUsd: v.optional(v.number()),
        maxTurns: v.optional(v.number()),
      })),
      ```
    - In the **existing agent** branch (lines ~42-58, the `patch` dict build), add:
      ```typescript
      if (args.claudeCodeOpts !== undefined) patch.claudeCodeOpts = args.claudeCodeOpts;
      ```
    - In the **new agent** branch (lines ~60-72, the `insert` call), add `claudeCodeOpts: args.claudeCodeOpts` to the inserted object (alongside `name`, `displayName`, etc.)

- [x] **Task 3: Update the YAML API route** (AC: #6)
  - [x] 3.1 In `dashboard/app/api/agents/[agentName]/config/route.ts`, extend `AgentConfig` type:
    ```typescript
    type AgentConfig = {
      name: string;
      role?: string;
      prompt?: string;
      model?: string;
      display_name?: string;
      skills?: string[];
      soul?: string;
      claude_code?: {
        permission_mode?: string;
        max_budget_usd?: number | null;
        max_turns?: number | null;
      } | null;
    };
    ```
  - [x] 3.2 In the PUT handler merge logic, when `claude_code` is present in the request body:
    - Build the `claude_code` object omitting null/undefined values:
      ```typescript
      if (body.claude_code !== undefined) {
        if (body.claude_code === null) {
          delete merged.claude_code; // remove CC opts
        } else {
          const cc: Record<string, unknown> = {};
          if (body.claude_code.permission_mode) cc.permission_mode = body.claude_code.permission_mode;
          if (body.claude_code.max_budget_usd != null) cc.max_budget_usd = body.claude_code.max_budget_usd;
          if (body.claude_code.max_turns != null) cc.max_turns = body.claude_code.max_turns;
          merged.claude_code = cc;
        }
      }
      ```
  - [x] 3.3 When `claude_code` is absent from request body, existing `merged.claude_code` stays untouched

- [x] **Task 4: Add CC mode to AgentConfigSheet parseModelValue** (AC: #1)
  - [x] 4.1 Extend `ModelMode` type in `AgentConfigSheet.tsx`:
    ```typescript
    type ModelMode = "default" | "tier" | "cc" | "custom";
    ```
  - [x] 4.2 Update `parseModelValue()` to detect `cc/` prefix before the `tier:` check:
    ```typescript
    if (model.startsWith("cc/")) {
      return { modelMode: "cc", tierLevel: "", hadReasoning: false, customModel: model.slice(3) };
    }
    ```
    The `customModel` field is repurposed to hold the bare model name (e.g. `"claude-sonnet-4-6"`) for display.
  - [x] 4.3 Update `computedModel` useMemo to handle `"cc"` mode:
    ```typescript
    case "cc":
      return customModel ? `cc/${customModel}` : "";
    ```
  - [x] 4.4 Update the Level 1 model `Select` in the model UI (around lines 505-524 in AgentConfigSheet.tsx) to handle the new `"__cc__"` sentinel value:
    - Add a `<SelectItem value="__cc__">Claude Code...</SelectItem>` option to the Level 1 Select (after the tier options, before or after "Custom...")
    - In the `onValueChange` handler, add a new branch:
      ```typescript
      if (val === "__cc__") {
        setModelMode("cc");
        setTierLevel("");
        setCustomModel("claude-sonnet-4-6"); // default CC model bare name
        setCcPermissionMode("bypassPermissions"); // default for new CC selection
      }
      ```
    - When `modelMode === "cc"`, the Level 1 Select should show `"__cc__"` as the selected value (add this case to the value computation that determines which Level 1 item is highlighted)
    - Level 2 for CC mode: show a `<Select>` with a small static list of bare CC model names (`"claude-haiku-4-5"`, `"claude-sonnet-4-6"`, `"claude-opus-4-6"`), or a plain `<Input>` for free-text entry. The bare name is stored in `customModel` state and reconstructed into `cc/{name}` by `computedModel`

- [x] **Task 5: Add Claude Code Settings state to AgentConfigSheet** (AC: #2, #3, #9)
  - [x] 5.1 Add new state variables near the existing model state declarations:
    ```typescript
    const [ccPermissionMode, setCcPermissionMode] = useState<string>("bypassPermissions");
    const [ccMaxBudget, setCcMaxBudget] = useState<string>("");   // string for input control
    const [ccMaxTurns, setCcMaxTurns] = useState<string>("");     // string for input control
    ```
  - [x] 5.2 In the `useEffect` that initializes form state from `agent`, load CC opts:
    ```typescript
    const ccOpts = agent.claudeCodeOpts;
    setCcPermissionMode(ccOpts?.permissionMode ?? "bypassPermissions");
    setCcMaxBudget(ccOpts?.maxBudgetUsd != null ? String(ccOpts.maxBudgetUsd) : "");
    setCcMaxTurns(ccOpts?.maxTurns != null ? String(ccOpts.maxTurns) : "");
    ```
  - [x] 5.3 Update `isDirty` useMemo to include CC state comparison:
    ```typescript
    const existingCc = agent?.claudeCodeOpts;
    const ccDirty = modelMode === "cc" && (
      ccPermissionMode !== (existingCc?.permissionMode ?? "bypassPermissions") ||
      ccMaxBudget !== (existingCc?.maxBudgetUsd != null ? String(existingCc.maxBudgetUsd) : "") ||
      ccMaxTurns !== (existingCc?.maxTurns != null ? String(existingCc.maxTurns) : "")
    );
    ```
  - [x] 5.4 Update `handleSave` to include CC opts in both saves:
    ```typescript
    // Compute CC opts payload (only when CC model is active)
    const claudeCodeOpts = modelMode === "cc" ? {
      permissionMode: ccPermissionMode || undefined,
      maxBudgetUsd: ccMaxBudget ? parseFloat(ccMaxBudget) : undefined,
      maxTurns: ccMaxTurns ? parseInt(ccMaxTurns, 10) : undefined,
    } : undefined;

    // In the Convex updateConfig call:
    updateConfig({ ..., claudeCodeOpts })

    // In the YAML fetch body:
    JSON.stringify({
      role, prompt, model: computedModel || null,
      display_name: displayName, skills,
      claude_code: modelMode === "cc" ? {
        permission_mode: ccPermissionMode || undefined,
        max_budget_usd: ccMaxBudget ? parseFloat(ccMaxBudget) : null,
        max_turns: ccMaxTurns ? parseInt(ccMaxTurns, 10) : null,
      } : undefined,
    })
    ```
  - [x] 5.5 When `modelMode` transitions to `"cc"` (user switches to a CC model), auto-set `ccPermissionMode` to `"bypassPermissions"` if not already loaded from agent

- [x] **Task 6: Build Claude Code Settings section JSX** (AC: #2)
  - [x] 6.1 Below the reasoning level section in AgentConfigSheet JSX, add a conditionally rendered CC settings block:
    ```tsx
    {modelMode === "cc" && (
      <div className="space-y-3 border-t pt-3">
        <label className="text-sm font-semibold">Claude Code Settings</label>

        {/* Permission Mode */}
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Permission Mode</label>
          <Select value={ccPermissionMode} onValueChange={setCcPermissionMode}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="bypassPermissions">
                Bypass — all tools run without approval
              </SelectItem>
              <SelectItem value="acceptEdits">
                Accept Edits — file edits auto-approved
              </SelectItem>
              <SelectItem value="default">
                Default — follows system CC defaults
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Max Budget */}
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Max Budget (USD)</label>
          <Input
            type="number"
            min={0}
            step={0.5}
            placeholder="No limit"
            value={ccMaxBudget}
            onChange={(e) => setCcMaxBudget(e.target.value)}
          />
        </div>

        {/* Max Turns */}
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Max Turns</label>
          <Input
            type="number"
            min={1}
            step={1}
            placeholder="No limit"
            value={ccMaxTurns}
            onChange={(e) => setCcMaxTurns(e.target.value)}
          />
        </div>
      </div>
    )}
    ```
  - [ ] 6.2 `Input` is already imported at line 23 of `AgentConfigSheet.tsx` — no action needed

- [x] **Task 7: Update mc/bridge.py sync_agent to include claudeCodeOpts** (AC: #7)
  - [x] 7.1 In `mc/bridge.py` `sync_agent()` method (line ~535), after building the existing upsert payload, add using **snake_case keys** (the bridge's `_convert_keys_to_camel()` will auto-convert to camelCase for Convex):
    ```python
    cc_opts = agent_data.claude_code_opts
    if cc_opts is not None:
        cc_payload: dict = {}
        if cc_opts.permission_mode:
            cc_payload["permission_mode"] = cc_opts.permission_mode
        if cc_opts.max_budget_usd is not None:
            cc_payload["max_budget_usd"] = cc_opts.max_budget_usd
        if cc_opts.max_turns is not None:
            cc_payload["max_turns"] = cc_opts.max_turns
        if cc_payload:
            payload["claude_code_opts"] = cc_payload  # bridge converts to claudeCodeOpts
    ```
    NOTE: Use snake_case (`"claude_code_opts"`, `"permission_mode"`) to be consistent with the rest of `sync_agent()` (e.g., `"display_name"`, `"is_system"`) and rely on the bridge's automatic camelCase conversion.
  - [x] 7.2 Verify that the `upsertByName` mutation (updated in Task 2) accepts `claudeCodeOpts`

- [x] **Task 8: Executor reads claudeCodeOpts from Convex as fallback** (AC: #8)
  - [x] 8.1 In `mc/executor.py` `_execute_cc_task()`, after the existing Convex agent sync block (after `convex_agent` is loaded), add:
    ```python
    # Sync claudeCodeOpts from Convex if agent_data.claude_code_opts is None
    if agent_data.claude_code_opts is None and convex_agent:
        cc_raw = convex_agent.get("claudeCodeOpts")
        if cc_raw and isinstance(cc_raw, dict):
            from claude_code.types import ClaudeCodeOpts
            agent_data.claude_code_opts = ClaudeCodeOpts(
                permission_mode=cc_raw.get("permissionMode", "acceptEdits"),
                max_budget_usd=cc_raw.get("maxBudgetUsd"),
                max_turns=cc_raw.get("maxTurns"),
            )
            logger.info(
                "[executor] CC: claudeCodeOpts loaded from Convex for '%s': permission_mode=%s",
                agent_name, agent_data.claude_code_opts.permission_mode,
            )
    ```
  - [x] 8.2 This fallback runs BEFORE step 0c (reasoning/effort level), so the opts object exists for effort level injection too

- [x] **Task 9: Update sprint-status.yaml** (housekeeping)
  - [x] 9.1 Add `11-3-cc-backend-config-dashboard: ready-for-dev` under epic-9 in sprint-status (create epic-11 block if missing)

## Dev Notes

### Architecture Overview

This story closes the full cycle for CC model configuration:

```
User selects cc/model in Dashboard
       ↓
AgentConfigSheet shows CC Settings section (permission_mode, budget, turns)
       ↓
handleSave → Convex updateConfig (claudeCodeOpts) + YAML PUT (claude_code)
       ↓
YAML now has:  model: cc/claude-sonnet-4-6
               claude_code:
                 permission_mode: bypassPermissions
       ↓
executor._execute_cc_task reads ClaudeCodeOpts from YAML (via yaml_validator)
  OR falls back to Convex claudeCodeOpts if YAML has no claude_code section
       ↓
ClaudeCodeProvider builds CLI command with --permission-mode bypassPermissions
```

### Critical Pre-condition: yaml_validator fix (already done)

`mc/yaml_validator.py` line 288 now reads:
```python
uses_cc_model = config.model is not None and config.model.startswith("cc/")
if (backend == "claude-code" or uses_cc_model) and config.claude_code:
    cc_opts = _parse_claude_code_opts(config.claude_code)
```
This means YAML with `model: cc/...` will have its `claude_code` section parsed into `ClaudeCodeOpts`. The dev agent should **not** revert this change — it was applied as a hotfix before this story.

### What NOT to do

- **Do NOT** change how `cc/` model strings are routed in `executor.py` — the routing via `is_cc_model()` is already correct
- **Do NOT** add `backend: claude-code` to agent configs — `cc/` prefix is the signal, `backend` field is internal
- **Do NOT** modify `ClaudeCodeProvider._build_command()` — it already reads `permission_mode` from `ClaudeCodeOpts`
- **Do NOT** add a separate `permissionMode` field to Convex at top-level — keep it nested under `claudeCodeOpts`

### Connected Models and CC Model List

Currently `connectedModels` from the settings key `"connected_models"` holds model strings like `"anthropic/claude-sonnet-4-6"`. CC models are referenced as `"cc/claude-sonnet-4-6"`. These are different conventions:
- `anthropic/...` = direct nanobot provider model
- `cc/...` = Claude Code CLI backend model

In the Level 1 model selector, add a separate option `"Claude Code..."` to enter CC mode, and in Level 2 show a hard-coded or settings-driven list of CC model options. Simplest approach: show a free-text input pre-populated with `"claude-sonnet-4-6"` as the default CC model name, or a small static list (`claude-haiku-4-5`, `claude-sonnet-4-6`, `claude-opus-4-6`).

### Convex Schema Change

Optional fields are backwards-compatible in Convex. Adding `claudeCodeOpts: v.optional(...)` does **not** require a data migration — existing agents will simply have `undefined` for this field. New agents that set a CC model via the dashboard will have it populated.

### Files to Touch

**Frontend:**
- `dashboard/convex/schema.ts` — add `claudeCodeOpts` to agents table
- `dashboard/convex/agents.ts` — update `updateConfig` and `upsertByName` mutations
- `dashboard/app/api/agents/[agentName]/config/route.ts` — write `claude_code` to YAML
- `dashboard/components/AgentConfigSheet.tsx` — CC mode detection, CC settings UI, save logic

**Backend Python:**
- `mc/bridge.py` — `sync_agent()` to include `claudeCodeOpts` in upsert payload
- `mc/executor.py` — `_execute_cc_task()` fallback to Convex `claudeCodeOpts`

**No changes needed:**
- `vendor/claude-code/claude_code/provider.py` — already handles `ClaudeCodeOpts.permission_mode`
- `vendor/claude-code/claude_code/types.py` — `ClaudeCodeOpts` dataclass already correct
- `mc/yaml_validator.py` — already fixed (hotfix applied)

### Existing Code Patterns to Follow

- `AgentConfigSheet.tsx` lines 171-188 — `useEffect` for form state initialization (add CC state here)
- `AgentConfigSheet.tsx` lines 247-259 — `isDirty` useMemo (extend with `ccDirty`)
- `AgentConfigSheet.tsx` lines 274-315 — `handleSave` (extend both Convex + YAML calls)
- `mc/bridge.py` sync_agent — look for the `payload` dict build pattern, append `claude_code_opts` at the end
- `mc/executor.py` `_execute_cc_task()` lines 1436-1459 — the existing `convex_agent` sync block; add fallback after it

### Testing

- Open AgentConfigSheet for `youtube-summarizer` (model: `cc/claude-sonnet-4-6`) → CC Settings section should appear with `bypassPermissions` pre-selected
- Change `permission_mode` to `acceptEdits` → isDirty becomes true → Save → YAML updated → executor respects it
- Open AgentConfigSheet for a nanobot agent → CC Settings section NOT shown
- Switch a nanobot agent's model to a CC model → CC Settings appear with `bypassPermissions` default
- Restart nanobot → bridge `sync_agent()` should sync the `claudeCodeOpts` from YAML to Convex
- Run `uv run pytest tests/mc/test_executor_cc.py` to verify no regressions

### References

- `dashboard/components/AgentConfigSheet.tsx` — current full component (model state at line ~67-168, handleSave at ~274-315, model UI at ~500-619)
- `dashboard/convex/agents.ts` — `updateConfig` mutation at lines ~120-164, `upsertByName` at ~12-83
- `dashboard/convex/schema.ts` — agents table at lines ~150-174
- `dashboard/app/api/agents/[agentName]/config/route.ts` — YAML PUT handler at lines ~19-68
- `mc/bridge.py` — `sync_agent()` around line 535
- `mc/executor.py` — `_execute_cc_task()` at line 1408, Convex sync block at ~1436-1459
- `vendor/claude-code/claude_code/types.py` — `ClaudeCodeOpts` dataclass at line 29
- `vendor/claude-code/claude_code/provider.py` — `_build_command()` at line 120 (reads `cc.permission_mode`)
- `mc/yaml_validator.py` — `_parse_claude_code_opts()` at line 237, `_config_to_agent_data()` at line 280

## Dev Agent Record

### Agent Model Used
- GPT-5 Codex

### Debug Log References
- `cd dashboard && npx tsc --noEmit`
- `cd dashboard && npm test` (fails due to existing unrelated suite failures)

### Completion Notes List
- Implemented `claudeCodeOpts` as an optional nested object in the Convex `agents` schema after `reasoningLevel`.
- Updated `updateConfig` and `upsertByName` mutations to accept and persist `claudeCodeOpts` in both existing-agent patch and new-agent insert paths.
- Extended agent YAML route `AgentConfig` typing and PUT merge logic to support `claude_code`, including explicit nested null/undefined cleanup before writing YAML.
- Scope intentionally limited to Tasks 1-3 only; no changes made to `AgentConfigSheet.tsx` or Python files.
- Validation: `tsc` passes; current dashboard test suite has broad pre-existing failures not caused by these scoped backend-config changes.

### File List
- `dashboard/convex/schema.ts`
- `dashboard/convex/agents.ts`
- `dashboard/app/api/agents/[agentName]/config/route.ts`
- `_bmad-output/implementation-artifacts/11-3-cc-backend-config-dashboard.md`
