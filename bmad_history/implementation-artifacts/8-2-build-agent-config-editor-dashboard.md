# Story 8.2: Build Agent Config Editor from Dashboard

Status: done

## Story

As a **user**,
I want to click on an agent in the sidebar and open a full configuration editor where I can view and edit the agent's role, skills, model, and other YAML-defined properties directly from the dashboard UI,
So that I can manage my agent roster visually without editing YAML files or using the CLI.

## Problem Statement

Currently, agents can only be configured by editing `~/.nanobot/agents/{name}/config.yaml` YAML files directly or via CLI commands (`nanobot mc agents create`). The dashboard sidebar displays agents (AgentSidebarItem) but is read-only — clicking does nothing. Users need a visual interface to:

1. View the full agent configuration (name, displayName, role, prompt, skills, model)
2. Edit any field and see real-time validation feedback
3. Select skills from the **actual nanobot project skills** (builtin + workspace), not arbitrary text
4. Save changes back to the YAML file AND sync to Convex
5. The agent registry is the same as nanobot's — this dashboard is an expansion module, not a separate system

Additionally, skills need to be **unified** between the local nanobot runtime and Convex. When Mission Control is installed, all skills from `nanobot/skills/` must be synced to Convex. New skills learned or created in nanobot must also be synced. This ensures the dashboard always has the complete, up-to-date skills catalog and the local file system remains the transparent source.

## Acceptance Criteria

### Agent Config Editor

1. **Given** agents exist in the Convex `agents` table, **When** the user clicks an AgentSidebarItem, **Then** a ShadCN Sheet slides out from the right (480px wide) displaying the agent's full configuration in an editable form
2. **Given** the AgentConfigSheet is open, **When** the user views the form, **Then** all editable fields are displayed: displayName (Input), role (Input), prompt (Textarea, monospace), skills (multi-select with available nanobot skills), model (Select dropdown or Input)
3. **Given** the user modifies any field, **When** they click "Save", **Then** the updated config is persisted to the Convex `agents` table via `agents:updateConfig` mutation AND the bridge writes the updated config back to `~/.nanobot/agents/{name}/config.yaml`
4. **Given** the user saves changes, **When** the mutation succeeds, **Then** a subtle green checkmark appears next to the Save button (auto-fades after 1.5s), the sidebar reflects the updated displayName/role immediately, and an `agent_config_updated` activity event is logged
5. **Given** the user enters invalid data (empty role, empty prompt), **When** real-time validation runs, **Then** the invalid field shows a red border with descriptive error text below (matching pydantic validation rules from `yaml_validator.py`)
6. **Given** the Convex mutation fails, **When** error is caught, **Then** the form shows an inline error banner: "Failed to save. Please try again." — no data loss, form retains user edits
7. **Given** the AgentConfigSheet is open, **When** the user presses Escape or clicks outside, **Then** if there are unsaved changes a confirmation dialog asks "Discard unsaved changes?", otherwise the sheet closes directly
8. **Given** the agent's `name` field, **When** displayed in the editor, **Then** it is shown as read-only (non-editable) since the name is the agent's identity key — cannot be renamed from UI

### Unified Skills Sync (Local <-> Convex)

9. **Given** Mission Control starts (`nanobot mc start`), **When** the gateway initializes, **Then** ALL skills from `nanobot/skills/*/SKILL.md` (builtin) and agent workspace skills are synced to the Convex `skills` table — including name, description, full SKILL.md content, metadata (emoji, requires, install instructions), and source (builtin/workspace)
10. **Given** a new skill is created in nanobot (via `skill-creator` skill or manually adding `SKILL.md`), **When** the next gateway sync runs (or `nanobot mc agents sync`), **Then** the new skill is automatically detected and synced to the Convex `skills` table
11. **Given** the skills field is being edited in AgentConfigSheet, **When** the user opens the skills selector, **Then** the available skills are read from the Convex `skills` table and displayed as a searchable multi-select checklist with: skill name (bold), description (muted text), emoji icon, availability status (green check if requirements met, amber warning if missing dependencies)
12. **Given** the Convex `skills` table has skills synced, **When** any dashboard component needs skills data, **Then** it reads from Convex — the single source of truth for the dashboard side, while `nanobot/skills/` remains the transparent local source for the nanobot runtime

## Tasks / Subtasks

- [x] Task 1: Add `skills` table to Convex schema and create skills sync (AC: #9, #10, #12)
  - [x] 1.1: Add `skills` table to `convex/schema.ts` with fields: name (string), description (string), content (string — full SKILL.md body without frontmatter), metadata (optional string — JSON with nanobot emoji/requires/install), source (string — "builtin" or "workspace"), always (optional boolean — whether skill is always-loaded), available (boolean — whether requirements are met on host), requires (optional string — human-readable missing deps description)
  - [x] 1.2: Add index `by_name` on the `skills` table
  - [x] 1.3: Create `convex/skills.ts` with mutations and queries:
    - `list` query: returns all skills
    - `upsertByName` mutation: insert or update a skill by name
    - `deactivateExcept` mutation: mark removed skills (same pattern as `agents:deactivateExcept`)
  - [x] 1.4: Add `sync_skills()` method to `ConvexBridge` in `bridge.py` that:
    - Uses `SkillsLoader` to discover all skills (builtin + workspace)
    - For each skill: reads SKILL.md, parses frontmatter (name, description, metadata), strips frontmatter to get content body
    - Calls `skills:upsertByName` mutation for each skill
    - Calls `skills:deactivateExcept` with active skill names to handle removed skills
    - Checks `_check_requirements()` for each skill and sets `available` field
  - [x] 1.5: Call `bridge.sync_skills()` from `sync_agent_registry()` in `gateway.py` — skills sync happens alongside agent sync on every gateway start
  - [x] 1.6: Also trigger skills sync from `nanobot mc agents sync` CLI command

- [x] Task 2: Add `prompt` field to Convex agents schema and update mutations (AC: #2, #3)
  - [x] 2.1: Add `prompt: v.optional(v.string())` to `agents` table in `convex/schema.ts`
  - [x] 2.2: Update `agents:upsertByName` mutation to accept and store `prompt`
  - [x] 2.3: Create `agents:updateConfig` mutation accepting: name (identifier), displayName, role, prompt, skills, model — updates all fields except name, writes `agent_config_updated` activity event
  - [x] 2.4: Add `agents:getByName` query to fetch a single agent by name
  - [x] 2.5: Update `AgentData` dataclass in `nanobot/mc/types.py` if needed to ensure prompt is always synced
  - [x] 2.6: Update `sync_agent_registry()` in `gateway.py` to include prompt when syncing agents to Convex

- [x] Task 3: Build AgentConfigSheet component (AC: #1, #2, #8)
  - [x] 3.1: Create `components/AgentConfigSheet.tsx` using ShadCN Sheet (480px right slide-out)
  - [x] 3.2: Sheet header: agent avatar (reuse `getAvatarColor`/`getInitials` from AgentSidebarItem) + displayName + status badge
  - [x] 3.3: Form fields layout:
    - name (Input, read-only, muted background, with lock icon)
    - displayName (Input)
    - role (Input)
    - prompt (Textarea with monospace font `font-mono`, min 6 rows, resizable)
    - model (Input with placeholder showing system default model)
    - skills (SkillsSelector component — see Task 4)
  - [x] 3.4: Form state management with `useState` for each field, initialized from agent data via `agents:getByName` query
  - [x] 3.5: Footer with "Save" (primary) and "Cancel" (outline) buttons, disabled when no changes or validation errors

- [x] Task 4: Build SkillsSelector component (AC: #11, #12)
  - [x] 4.1: Create `components/SkillsSelector.tsx` — searchable multi-select checklist
  - [x] 4.2: Read skills from Convex `skills.list` query (reactive — updates if skills sync runs)
  - [x] 4.3: Display each skill as a row with: Checkbox, emoji icon (from metadata), skill name (`font-medium`), description (`text-xs text-muted-foreground`), availability indicator (green dot if available, amber dot + tooltip "Missing: gh CLI" if not)
  - [x] 4.4: Search Input at top: filters skills by name or description
  - [x] 4.5: Selected skills pinned to top of list with visual separation
  - [x] 4.6: Selected count badge: "3 of 8 skills selected"
  - [x] 4.7: Skills marked `always: true` shown with "(always loaded)" label and cannot be unchecked

- [x] Task 5: Wire AgentSidebarItem click to open sheet (AC: #1)
  - [x] 5.1: Add `onClick` handler to AgentSidebarItem that sets selected agent state
  - [x] 5.2: Lift state up: AgentSidebar manages `selectedAgent` state and renders AgentConfigSheet
  - [x] 5.3: Change `cursor-default` to `cursor-pointer` on SidebarMenuButton
  - [x] 5.4: Add hover highlight effect (`hover:bg-sidebar-accent`) to AgentSidebarItem

- [x] Task 6: Implement validation and save flow (AC: #3, #4, #5, #6, #7)
  - [x] 6.1: Client-side validation matching `yaml_validator.py` rules: non-empty role, non-empty prompt, skills must be from available list
  - [x] 6.2: Show red border + error message below invalid fields on blur and on submit attempt
  - [x] 6.3: On save: call `agents:updateConfig` mutation
  - [x] 6.4: Show green checkmark on success (auto-fade 1.5s via CSS animation)
  - [x] 6.5: Show inline error banner on mutation failure, form retains all edits
  - [x] 6.6: Track dirty state (compare current values vs initial); show ShadCN AlertDialog on close with unsaved changes: "Discard unsaved changes?"
  - [x] 6.7: The `agents:updateConfig` mutation writes an `agent_config_updated` activity event

- [x] Task 7: Bridge write-back to local YAML (AC: #3)
  - [x] 7.1: Add `write_agent_config()` method to `ConvexBridge` that writes agent config to `~/.nanobot/agents/{name}/config.yaml` using `yaml.dump(default_flow_style=False)`
  - [x] 7.2: In `sync_agent_registry()`, before syncing local → Convex, check reverse: if Convex agent has newer `lastActiveAt` than local YAML mtime, write Convex data back to YAML (bidirectional sync)
  - [x] 7.3: Ensure YAML output matches expected format: name, role, prompt, skills (as YAML list), model, display_name — using snake_case field names

- [x] Task 8: Add `agent_config_updated` event type (AC: #4)
  - [x] 8.1: Add `"agent_config_updated"` to the `eventType` union in `convex/schema.ts` activities table
  - [x] 8.2: Update `nanobot/mc/types.py` `ActivityEventType` if it exists as an enum/literal

- [x] Task 9: Write tests (AC: all)
  - [x] 9.1: Vitest test for AgentConfigSheet — renders all form fields, displays agent data correctly, name field is read-only
  - [x] 9.2: Vitest test for SkillsSelector — renders skills from Convex, search filter works, selection toggles, always-skills cannot be unchecked
  - [x] 9.3: Vitest test for validation — empty role shows error, empty prompt shows error, valid data enables save
  - [x] 9.4: Vitest test for dirty state — unsaved changes trigger confirmation dialog, clean state closes directly
  - [x] 9.5: Python test for `sync_skills()` — discovers skills, extracts frontmatter, calls upsert mutation

## Dev Notes

### Critical Architecture: Unified Skills System

**The core principle**: Skills exist in TWO places, always in sync:
1. **Local filesystem** (`nanobot/skills/*/SKILL.md`) — transparent, the nanobot runtime reads skills from here
2. **Convex `skills` table** — the dashboard reads skills from here for UI display and agent configuration

**Sync direction**: Local → Convex (local is the primary source, Convex is the mirror)

**When skills sync happens**:
- On `nanobot mc start` (gateway startup via `sync_agent_registry()`)
- On `nanobot mc agents sync` (manual CLI command)
- Future: could add file watcher for real-time sync (out of scope for this story)

**What gets synced per skill**:
```
From SKILL.md frontmatter:
  - name: "github"
  - description: "Interact with GitHub using the `gh` CLI..."
  - metadata: '{"nanobot":{"emoji":"🐙","requires":{"bins":["gh"]},...}}'
  - always: true/false (from frontmatter `always` field)

From SKILL.md body:
  - content: full markdown body (frontmatter stripped)

Computed at sync time:
  - source: "builtin" or "workspace"
  - available: true/false (based on _check_requirements — are bins/env vars present?)
  - requires: "CLI: gh" (human-readable missing deps, empty if available)
```

**Why store full content in Convex?**: Future stories may display skill content in the dashboard (skill detail view, skill browser). For now, content is stored but not rendered in UI — only name/description/metadata are displayed in the SkillsSelector.

### Schema Changes Required

**1. New `skills` table in `convex/schema.ts`:**

```typescript
skills: defineTable({
  name: v.string(),
  description: v.string(),
  content: v.string(),                    // Full SKILL.md body (frontmatter stripped)
  metadata: v.optional(v.string()),       // JSON: {emoji, requires, install}
  source: v.union(v.literal("builtin"), v.literal("workspace")),
  always: v.optional(v.boolean()),        // Always-loaded skill
  available: v.boolean(),                 // Requirements met on host
  requires: v.optional(v.string()),       // Missing deps description
}).index("by_name", ["name"]),
```

**2. Add `prompt` field to `agents` table:**

```typescript
// In convex/schema.ts - agents table, add:
prompt: v.optional(v.string()),
```

**3. Add `agent_config_updated` to activities eventType union:**

```typescript
// In convex/schema.ts - activities table eventType, add:
v.literal("agent_config_updated"),
```

### Skills Sync Data Flow

```
Gateway startup
  │
  ├─ sync_agent_registry(bridge, agents_dir)
  │   ├─ Validate & sync agent YAML → Convex agents table (existing)
  │   └─ sync_skills(bridge)  ← NEW
  │       ├─ SkillsLoader(workspace).list_skills(filter_unavailable=False)
  │       ├─ For each skill:
  │       │   ├─ Read SKILL.md
  │       │   ├─ Parse frontmatter → name, description, metadata, always
  │       │   ├─ Strip frontmatter → content body
  │       │   ├─ Check requirements → available, requires
  │       │   └─ Bridge.mutate("skills:upsertByName", {...})
  │       └─ Bridge.mutate("skills:deactivateExcept", {activeNames: [...]})
  │
  └─ Dashboard reads from Convex skills table (reactive queries)
```

### Agent Config Edit Data Flow

```
User clicks agent in sidebar
  → AgentConfigSheet opens
  → Fetches agent data from Convex (agents:getByName)
  → Fetches skills catalog from Convex (skills:list)
  → User edits fields (role, skills, prompt, model)
  → User clicks Save
  → Client validation (mirrors yaml_validator.py)
  → Convex mutation: agents:updateConfig
    → Updates agent document
    → Writes agent_config_updated activity event
  → Dashboard reflects changes immediately (reactive query)
  → Next gateway sync: bridge detects Convex is newer
    → Writes updated config.yaml to local filesystem
    → nanobot runtime picks up changes on next agent load
```

### Agent YAML Write-Back Strategy

**Bidirectional sync in `sync_agent_registry()`:**

1. **Local → Convex** (existing): Read YAML files, validate, upsert to Convex
2. **Convex → Local** (new): After step 1, query all agents from Convex. For any agent where Convex `lastActiveAt` > local YAML file mtime, write Convex data back to YAML

This ensures dashboard edits propagate to local YAML on the next gateway start. The YAML format:

```yaml
name: my-agent
display_name: My Agent
role: Senior Developer
prompt: "You are a coding expert..."
skills:
  - github
  - summarize
model: claude-sonnet-4-6
```

### Available Nanobot Skills (Current Builtin)

| Skill | Description | Emoji | Requires |
|-------|------------|-------|----------|
| `clawhub` | ClawHub skill registry search | | — |
| `cron` | Scheduled tasks | | — |
| `github` | GitHub interaction via `gh` CLI | 🐙 | `gh` binary |
| `memory` | Memory persistence (always-loaded) | | — |
| `skill-creator` | Create new skills | | — |
| `summarize` | URL/file/video summarization | 🧾 | `summarize` binary |
| `tmux` | Remote tmux session control | | `tmux` binary |
| `weather` | Weather data via wttr.in | | — |

### Existing Code Reference

| Component | File | Relevance |
|-----------|------|-----------|
| AgentSidebarItem | `dashboard/components/AgentSidebarItem.tsx` | Add onClick, change cursor |
| AgentSidebar | `dashboard/components/AgentSidebar.tsx` | Lift selectedAgent state, render sheet |
| Convex agents | `dashboard/convex/agents.ts` | Add `updateConfig`, `getByName` |
| Convex schema | `dashboard/convex/schema.ts` | Add `skills` table, `prompt` on agents, event type |
| YAML validator | `nanobot/mc/yaml_validator.py` | Mirror validation rules client-side |
| SkillsLoader | `nanobot/agent/skills.py` | Use `list_skills()`, `get_skill_metadata()`, `_check_requirements()` |
| ConvexBridge | `nanobot/mc/bridge.py` | Add `sync_skills()`, `write_agent_config()` |
| Gateway | `nanobot/mc/gateway.py` | Call `sync_skills()` from `sync_agent_registry()` |
| AgentData | `nanobot/mc/types.py` | Dataclass reference |
| TaskDetailSheet | `dashboard/components/TaskDetailSheet.tsx` | Sheet UI pattern reference |
| SettingsPanel | `dashboard/components/SettingsPanel.tsx` | Save feedback pattern reference |

### Previous Story Intelligence

From Story 8-1:
- `filter_agent_fields()` utility exists in `gateway.py` for safely constructing AgentData from Convex results — use same pattern for skills
- Bridge retry logic is solid — reuse for skills sync mutations
- The executor loads agent config from YAML via `_load_agent_config()` — after this story, it should also check Convex for newer config
- `_resolve_convex_url()` helper exists for gateway — no need to re-implement

### UI Component Patterns

Follow existing patterns from the codebase:
- Sheet: Copy pattern from `TaskDetailSheet.tsx` (ShadCN Sheet, 480px, right slide-out)
- Form inputs: Use ShadCN `Input`, `Textarea`, `Select`, `Checkbox`, `Button`
- Validation: Red border + error text below field (same pattern as TaskInput empty validation)
- Success feedback: Green checkmark that fades (same pattern as SettingsPanel save)
- Status colors: Reuse `STATUS_DOT_STYLES` from AgentSidebarItem
- Confirmation dialog: ShadCN `AlertDialog` for unsaved changes warning

### Project Structure Notes

- New dashboard components go in `dashboard/components/`
- New Convex functions go in `dashboard/convex/`
- Bridge extensions go in `nanobot/mc/bridge.py`
- Tests co-located: `dashboard/components/AgentConfigSheet.test.tsx`, `dashboard/components/SkillsSelector.test.tsx`
- Python tests: `tests/mc/test_skills_sync.py`
- Follows monorepo structure: `dashboard/` is the frontend, `nanobot/mc/` is the backend

### References

- [Source: dashboard/components/AgentSidebarItem.tsx] — Current agent display, needs onClick + cursor-pointer
- [Source: dashboard/components/TaskDetailSheet.tsx] — Sheet pattern reference
- [Source: dashboard/convex/agents.ts] — Existing mutations (upsertByName, updateStatus, deactivateExcept)
- [Source: dashboard/convex/schema.ts] — Current schema, needs skills table + prompt field + event type
- [Source: nanobot/mc/yaml_validator.py] — Validation rules to mirror on frontend
- [Source: nanobot/mc/bridge.py] — Bridge integration point, needs sync_skills() + write_agent_config()
- [Source: nanobot/mc/gateway.py] — Agent registry sync, needs skills sync call
- [Source: nanobot/agent/skills.py] — SkillsLoader with list_skills(), get_skill_metadata(), _check_requirements()
- [Source: nanobot/skills/*/SKILL.md] — 8 builtin skill definitions with frontmatter metadata
- [Source: nanobot/skills/github/SKILL.md] — Example skill with full metadata: name, description, emoji, requires, install
- [Source: nanobot/skills/memory/SKILL.md] — Example always-loaded skill (always: true)

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
