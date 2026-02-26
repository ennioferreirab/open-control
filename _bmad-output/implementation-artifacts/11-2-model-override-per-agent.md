# Story 11.2: Model Override Per Agent

Status: ready-for-dev

## Story

As an **admin**,
I want to optionally override the model tier for a specific agent with a custom model,
so that specialized agents can use different models than the tier default.

## Acceptance Criteria

### AC1: Three Model Resolution Modes

**Given** an agent's `model` field in the `agents` table (`v.optional(v.string())`)
**When** the model value is:
- `undefined` or empty: the agent uses the system default model (existing behavior, no change)
- `"tier:standard-high"`: the agent uses the tier system, resolved at runtime to the mapped model
- `"anthropic/claude-opus-4-6"`: the agent uses this exact model directly (custom override, pass-through)
**Then** all three modes work correctly without any schema changes
**And** the `TierResolver.resolve_model()` from Story 11.1 handles pass-through for non-tier strings

### AC2: Two-Level Model Dropdown in AgentConfigSheet

**Given** the `AgentConfigSheet.tsx` agent configuration panel
**When** the admin edits an agent's model
**Then** the current plain text `<Input>` for the model field is replaced with a structured selector:
- **Level 1**: A `<Select>` dropdown listing all 6 tiers (`"Standard Low"`, `"Standard Medium"`, `"Standard High"`, `"Reasoning Low"`, `"Reasoning Medium"`, `"Reasoning High"`) plus a `"Custom..."` option
- **If a tier is selected**: the model value is set to `"tier:{tier-name}"` (e.g., `"tier:standard-high"`)
- **If "Custom..." is selected**: a **Level 2** `<Select>` appears, populated with all models from the `"connected_models"` setting, allowing the admin to pick a specific model string
**And** the current model value is reflected correctly on load:
  - `undefined`/empty shows a placeholder like "System default"
  - `"tier:standard-high"` shows "Standard High" selected in Level 1
  - `"anthropic/claude-opus-4-6"` shows "Custom..." in Level 1 and the model in Level 2

### AC3: Visual Indicator for Tier vs. Custom

**Given** the model selector in AgentConfigSheet
**When** the agent uses a tier reference
**Then** a small badge or label shows "Tier" with the resolved model name (e.g., "Tier: Standard High -> claude-opus-4-6")
**When** the agent uses a custom model
**Then** a small badge or label shows "Custom" with the direct model name
**When** the agent uses the system default (empty/undefined)
**Then** a small label shows "System Default"

### AC4: Dirty State and Save Behavior

**Given** the model field participates in the existing dirty-state detection
**When** the admin changes the model from tier to custom (or vice versa)
**Then** the `isDirty` check detects the change correctly
**And** saving calls `updateConfig` with the new model value (`"tier:standard-high"`, `"anthropic/claude-opus-4-6"`, or `undefined`)
**And** the saved value persists and is correctly reflected when the sheet is reopened

### AC5: Backend Pass-Through (No Additional Backend Work)

**Given** Story 11.1 implemented `TierResolver.resolve_model()` with pass-through for non-tier strings
**When** an agent has `model: "anthropic/claude-opus-4-6"` (custom override)
**Then** `executor.py` and `step_dispatcher.py` pass it directly to `create_provider()` without tier resolution
**And** no additional backend changes are needed beyond Story 11.1

## Tasks / Subtasks

- [ ] **Task 1: Replace model input with two-level selector in AgentConfigSheet.tsx** (AC: #2, #4)
  - [ ] 1.1 Add new state variables at the top of the component (near line ~71 where `model` state is declared):
    ```tsx
    const [modelMode, setModelMode] = useState<"default" | "tier" | "custom">("default");
    const [selectedTier, setSelectedTier] = useState<string>("");
    const [customModel, setCustomModel] = useState<string>("");
    ```
  - [ ] 1.2 Fetch connected models from settings — add query near the top of the component:
    ```tsx
    const connectedModelsRaw = useQuery(api.settings.get, { key: "connected_models" });
    const connectedModels: string[] = useMemo(() => {
      try { return connectedModelsRaw ? JSON.parse(connectedModelsRaw) : []; }
      catch { return []; }
    }, [connectedModelsRaw]);
    ```
  - [ ] 1.3 Fetch current tier mappings for display (showing resolved model in badge):
    ```tsx
    const modelTiersRaw = useQuery(api.settings.get, { key: "model_tiers" });
    const modelTiers: Record<string, string | null> = useMemo(() => {
      try { return modelTiersRaw ? JSON.parse(modelTiersRaw) : {}; }
      catch { return {}; }
    }, [modelTiersRaw]);
    ```
  - [ ] 1.4 Define tier options constant (outside component or as useMemo):
    ```tsx
    const TIER_OPTIONS = [
      { value: "standard-low", label: "Standard Low" },
      { value: "standard-medium", label: "Standard Medium" },
      { value: "standard-high", label: "Standard High" },
      { value: "reasoning-low", label: "Reasoning Low" },
      { value: "reasoning-medium", label: "Reasoning Medium" },
      { value: "reasoning-high", label: "Reasoning High" },
    ];
    ```
  - [ ] 1.5 Update the `useEffect` that initializes form state from agent data (line ~91) to parse the model value into `modelMode`, `selectedTier`, and `customModel`:
    ```tsx
    // Inside the existing useEffect that runs when `agent` changes:
    const agentModel = agent.model || "";
    if (!agentModel) {
      setModelMode("default");
      setSelectedTier("");
      setCustomModel("");
    } else if (agentModel.startsWith("tier:")) {
      setModelMode("tier");
      setSelectedTier(agentModel.slice(5)); // strip "tier:" prefix
      setCustomModel("");
    } else {
      setModelMode("custom");
      setSelectedTier("");
      setCustomModel(agentModel);
    }
    ```
  - [ ] 1.6 Add a `computedModel` derived value that reconstitutes the model string from the state:
    ```tsx
    const computedModel = useMemo(() => {
      if (modelMode === "tier" && selectedTier) return `tier:${selectedTier}`;
      if (modelMode === "custom" && customModel) return customModel;
      return ""; // system default
    }, [modelMode, selectedTier, customModel]);
    ```
  - [ ] 1.7 Update the `isDirty` useMemo (line ~163) — replace `model !== (agent.model || "")` with `computedModel !== (agent.model || "")`
  - [ ] 1.8 Update `handleSave` (line ~189) — replace `model: model || undefined` with `model: computedModel || undefined`
  - [ ] 1.9 Remove the old `setModel` state setter calls since model is now derived from `modelMode + selectedTier + customModel`

- [ ] **Task 2: Build the model selector JSX** (AC: #2, #3)
  - [ ] 2.1 Replace the current model `<Input>` block (lines ~399-407 in AgentConfigSheet.tsx) with the new two-level selector:
    ```tsx
    {/* Model */}
    <div className="space-y-2">
      <label className="text-sm font-medium">Model</label>
      {/* Level 1: Mode selector */}
      <Select
        value={modelMode === "tier" ? `tier:${selectedTier}` : modelMode}
        onValueChange={(val) => {
          if (val === "default") {
            setModelMode("default");
            setSelectedTier("");
            setCustomModel("");
          } else if (val === "custom") {
            setModelMode("custom");
            setSelectedTier("");
          } else if (val.startsWith("tier:")) {
            setModelMode("tier");
            setSelectedTier(val.slice(5));
            setCustomModel("");
          }
        }}
      >
        <SelectTrigger>
          <SelectValue placeholder="System default" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="default">System Default</SelectItem>
          {TIER_OPTIONS.map((t) => (
            <SelectItem key={t.value} value={`tier:${t.value}`}>
              {t.label}
            </SelectItem>
          ))}
          <SelectItem value="custom">Custom...</SelectItem>
        </SelectContent>
      </Select>

      {/* Level 2: Custom model picker (only when Custom is selected) */}
      {modelMode === "custom" && (
        <Select value={customModel} onValueChange={setCustomModel}>
          <SelectTrigger>
            <SelectValue placeholder="Select a model..." />
          </SelectTrigger>
          <SelectContent>
            {connectedModels.map((m) => (
              <SelectItem key={m} value={m}>{m}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      {/* Visual indicator badge */}
      {/* ... (see Task 3) */}
    </div>
    ```
  - [ ] 2.2 Import `Select`, `SelectContent`, `SelectItem`, `SelectTrigger`, `SelectValue` from `@/components/ui/select` at the top of the file
  - [ ] 2.3 Ensure the `Select` components match existing shadcn/ui patterns used elsewhere in the dashboard

- [ ] **Task 3: Add visual indicator badge** (AC: #3)
  - [ ] 3.1 Below the Select components, add the visual indicator:
    ```tsx
    <div className="text-xs text-muted-foreground">
      {modelMode === "default" && (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-muted">
          System Default
        </span>
      )}
      {modelMode === "tier" && selectedTier && (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">
          Tier: {TIER_OPTIONS.find(t => t.value === selectedTier)?.label}
          {modelTiers[selectedTier] && (
            <span className="opacity-70">
              {" -> "}{modelTiers[selectedTier]}
            </span>
          )}
          {modelTiers[selectedTier] === null && (
            <span className="opacity-70 text-amber-600 dark:text-amber-400">
              {" (not configured)"}
            </span>
          )}
        </span>
      )}
      {modelMode === "custom" && customModel && (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300">
          Custom: {customModel}
        </span>
      )}
    </div>
    ```
  - [ ] 3.2 When a reasoning tier is selected and its mapping is null, show a warning that the tier is not available
  - [ ] 3.3 Ensure badge styling is consistent with the existing `variables` badge styling in the same file (line ~381)

- [ ] **Task 4: Clean up old model state** (AC: #4)
  - [ ] 4.1 Keep the `model` state variable for backward compatibility during form init, but the actual saved value comes from `computedModel`
  - [ ] 4.2 Alternatively, remove the `model` state entirely and use `computedModel` everywhere — verify no other code references `model` state setter
  - [ ] 4.3 Verify dirty detection works by testing: change from default to tier, tier to custom, custom back to default, and ensure isDirty reflects correctly
  - [ ] 4.4 Verify that `handleSave` passes the correct `model` value: `undefined` for default, `"tier:standard-high"` for tier, `"anthropic/claude-opus-4-6"` for custom

- [ ] **Task 5: Verify backend pass-through** (AC: #1, #5)
  - [ ] 5.1 Confirm that `TierResolver.resolve_model()` from Story 11.1 correctly passes through non-tier model strings without modification
  - [ ] 5.2 Confirm that `executor.py` and `step_dispatcher.py` from Story 11.1 only invoke tier resolution when `is_tier_reference(agent_model)` is true
  - [ ] 5.3 Test end-to-end: create an agent with `model: "anthropic/claude-opus-4-6"` (custom), verify it uses that model directly without tier lookup
  - [ ] 5.4 Test end-to-end: create an agent with `model: "tier:standard-high"`, verify it resolves to the configured tier mapping

## Dev Notes

### Architecture Patterns

- **No schema changes required**: The `agents.model` field is already `v.optional(v.string())` and accepts any string value. The three modes (undefined/tier-ref/direct-model) are a convention enforced by the frontend UI and interpreted by the backend tier resolver.

- **Frontend-only complexity**: This story is primarily a frontend change to `AgentConfigSheet.tsx`. The backend work was already done in Story 11.1 — `TierResolver.resolve_model()` has built-in pass-through for non-tier strings, so custom model overrides work automatically.

- **Two-level dropdown pattern**: The Level 1 Select determines the mode (system default, one of 6 tiers, or custom). Only when "Custom..." is selected does the Level 2 Select appear with the full connected models list. This keeps the UI clean for the common case (tier selection) while allowing power users to specify exact models.

- **State decomposition**: Instead of a single `model` string, the form state is split into `modelMode`, `selectedTier`, and `customModel`. The `computedModel` derived value reconstitutes the string for saving. This mirrors the pattern of decomposing a complex field into UI-friendly sub-states.

### Code to Reuse

- `AgentConfigSheet.tsx` line ~91-104 — existing `useEffect` for form state initialization (extend, don't replace)
- `AgentConfigSheet.tsx` line ~163-174 — existing `isDirty` useMemo (modify model comparison)
- `AgentConfigSheet.tsx` line ~189-214 — existing `handleSave` callback (modify model argument)
- `dashboard/convex/settings.ts` — `get` query for fetching connected_models and model_tiers
- Existing shadcn/ui `<Select>` component — check `dashboard/components/ui/select.tsx` for import paths

### Common Mistakes to Avoid

- Do NOT add a separate `modelMode` field to the Convex schema — the mode is derived from the model string format at load time
- Do NOT forget to handle the case where `connected_models` setting does not exist yet (empty array fallback)
- When comparing `computedModel` in `isDirty`, compare against `agent.model || ""` (not `agent.model`) to handle undefined correctly
- The `Select` `value` must exactly match one of the `SelectItem` `value` props or the component will show nothing — ensure the tier ref format `"tier:{name}"` is consistent between the value and the option values
- Ensure the old `setModel` state is not referenced in the dirty check or save handler after refactoring to `computedModel`
- Use `uv run python` not `python3`. Use `uv run pytest` for tests.

### Project Structure Notes

- Frontend: `dashboard/components/AgentConfigSheet.tsx` (primary file to modify)
- Backend: No changes needed beyond Story 11.1 (`nanobot/mc/executor.py`, `nanobot/mc/step_dispatcher.py` already handle tier resolution)
- Convex: No schema or mutation changes needed

### References

- `dashboard/components/AgentConfigSheet.tsx` — full component source, model input at lines ~399-407
- `dashboard/convex/settings.ts` — settings queries for connected_models and model_tiers
- `nanobot/mc/types.py` — `is_tier_reference()` and `extract_tier_name()` helpers (from Story 11.1)
- `nanobot/mc/tier_resolver.py` — `TierResolver.resolve_model()` pass-through behavior (from Story 11.1)
- `nanobot/mc/executor.py` — tier resolution integration point (from Story 11.1)
- `nanobot/mc/step_dispatcher.py` — tier resolution integration point (from Story 11.1)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
