# Story 3.2: Build Agent Registry Sync

Status: done

## Story

As a **developer**,
I want agents defined in YAML files to be synced to the Convex agents table,
So that the dashboard and CLI can display current agent information.

## Acceptance Criteria

1. **Given** valid YAML agent configuration files exist in the agents folder, **When** the Agent Gateway starts or `nanobot mc agents list` is run, **Then** all YAML files are loaded, validated (via Story 3.1 validator), and synced to the Convex `agents` table
2. **Given** a new agent YAML file is added, **When** the registry sync runs, **Then** the agent is inserted into the Convex `agents` table with status "idle"
3. **Given** an existing agent's YAML is modified, **When** the registry sync runs, **Then** the agent's record in Convex is updated with the new values
4. **Given** a previously synced agent's YAML file is removed, **When** the registry sync runs, **Then** the agent's status is set to "idle" in Convex (soft deactivation, not deletion)
5. **Given** a successful agent sync, **Then** each new/updated agent writes an `agent_connected` activity event to Convex
6. **Given** the system-wide default LLM model is configured (FR12), **When** an agent YAML does not specify a `model` field, **Then** the agent uses the system-wide default model and the resolved model is stored in the Convex `agents` table
7. **Given** YAML files change between CLI invocations, **When** the user runs `nanobot mc agents list`, **Then** the agent registry is refreshed from YAML files before displaying results (NFR17)
8. **Given** invalid YAML files exist alongside valid ones, **Then** sync proceeds for valid agents and logs errors for invalid ones (does not block the sync)
9. **And** the Convex `agents.ts` file contains `upsertByName`, `list`, and `updateStatus` functions
10. **And** sync logic lives in `nanobot/mc/gateway.py`
11. **And** sync uses bridge methods exclusively -- no direct Convex SDK calls outside bridge

## Tasks / Subtasks

- [ ] Task 1: Create Convex agents functions (AC: #9)
  - [ ] 1.1: Create `dashboard/convex/agents.ts` with `list` query returning all agents
  - [ ] 1.2: Add `upsertByName` mutation that inserts or updates an agent by matching on `name` field, using the `by_name` index
  - [ ] 1.3: Add `updateStatus` mutation that updates an agent's `status` and `lastActiveAt` fields
  - [ ] 1.4: Ensure `upsertByName` mutation also writes an `agent_connected` activity event when inserting or updating
  - [ ] 1.5: Add `deactivateExcept` mutation that sets status to "idle" for all agents NOT in a provided list of names (for soft deactivation of removed YAML files)

- [ ] Task 2: Add bridge methods for agent operations (AC: #11)
  - [ ] 2.1: Add `sync_agent(agent_data: AgentData) -> Any` method to `ConvexBridge` that calls `agents:upsertByName`
  - [ ] 2.2: Add `list_agents() -> list[dict]` method to `ConvexBridge` that calls `agents:list`
  - [ ] 2.3: Add `deactivate_agents_except(active_names: list[str]) -> Any` method to `ConvexBridge`

- [ ] Task 3: Implement agent registry sync in gateway (AC: #1, #2, #3, #4, #5, #6, #8, #10)
  - [ ] 3.1: Create `sync_agent_registry(bridge: ConvexBridge, agents_dir: Path, default_model: str | None = None) -> tuple[list[AgentData], dict[str, list[str]]]` function in `gateway.py`
  - [ ] 3.2: Call `validate_agents_dir()` from yaml_validator to get valid agents and errors
  - [ ] 3.3: For each valid agent, resolve the model (use agent's `model` if set, else `default_model`)
  - [ ] 3.4: Call `bridge.sync_agent()` for each valid agent
  - [ ] 3.5: Call `bridge.deactivate_agents_except()` with the list of valid agent names (soft deactivate removed agents)
  - [ ] 3.6: Log errors for invalid files to stdout
  - [ ] 3.7: Return the list of synced agents and any errors

- [ ] Task 4: Implement default model resolution (AC: #6)
  - [ ] 4.1: Read the system-wide default model from Convex `settings` table (key: `default_model`) via bridge query
  - [ ] 4.2: Fall back to a hardcoded default (e.g., `"claude-sonnet-4-6"`) if no setting exists
  - [ ] 4.3: Apply the resolved default model to any agent that does not specify its own `model`

- [ ] Task 5: Write unit tests
  - [ ] 5.1: Test `sync_agent_registry` with valid agents -> all synced to bridge
  - [ ] 5.2: Test sync with mix of valid/invalid agents -> valid ones synced, errors logged
  - [ ] 5.3: Test model resolution: agent with model set keeps it, agent without model gets default
  - [ ] 5.4: Test deactivation: agent removed from disk -> deactivate called with remaining names

## Dev Notes

### Critical Architecture Requirements

- **Bridge-only Convex access**: The sync logic in `gateway.py` MUST use `ConvexBridge` methods to interact with Convex. No direct `ConvexClient` imports or usage. This is Architectural Boundary 1.
- **Validator dependency**: This story depends on Story 3.1. The `validate_agents_dir()` function from `yaml_validator.py` is the entry point for loading and validating YAML files.
- **Upsert pattern**: The Convex `upsertByName` mutation should query by the `by_name` index. If an agent with that name exists, patch it. If not, insert. This avoids duplicates across syncs.
- **Activity event on sync**: Every `upsertByName` must also insert an `agent_connected` activity event in the same mutation. This follows the architecture rule: "Every Convex mutation that modifies agent state MUST also write a corresponding activity event."
- **Soft deactivation**: When a YAML file is removed, the agent is NOT deleted from Convex. Its status is set to "idle". This preserves historical data and prevents orphaned references in tasks/messages.

### Convex agents.ts Pattern

```typescript
import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const list = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db.query("agents").collect();
  },
});

export const upsertByName = mutation({
  args: {
    name: v.string(),
    displayName: v.string(),
    role: v.string(),
    skills: v.array(v.string()),
    model: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.name))
      .first();

    const timestamp = new Date().toISOString();

    if (existing) {
      await ctx.db.patch(existing._id, {
        displayName: args.displayName,
        role: args.role,
        skills: args.skills,
        model: args.model,
        lastActiveAt: timestamp,
      });
    } else {
      await ctx.db.insert("agents", {
        name: args.name,
        displayName: args.displayName,
        role: args.role,
        skills: args.skills,
        status: "idle",
        model: args.model,
        lastActiveAt: timestamp,
      });
    }

    // Write activity event
    await ctx.db.insert("activities", {
      agentName: args.name,
      eventType: "agent_connected",
      description: `Agent '${args.displayName}' (${args.role}) registered`,
      timestamp,
    });
  },
});
```

### Agent Directory Path

The default agents directory is `~/.nanobot/agents/`. Each agent has its own subdirectory with a `config.yaml` file:

```
~/.nanobot/agents/
  dev-agent/
    config.yaml
    memory/
    skills/
  financeiro/
    config.yaml
    memory/
    skills/
```

The `validate_agents_dir()` function (Story 3.1) should scan for `*/config.yaml` patterns.

### Default Model Resolution Chain

1. Agent YAML `model` field (highest priority)
2. Convex `settings` table key `default_model`
3. Hardcoded fallback: `"claude-sonnet-4-6"` (lowest priority)

### Common LLM Developer Mistakes to Avoid

1. **DO NOT import ConvexClient directly in gateway.py** -- Use `ConvexBridge` methods exclusively. The bridge is the single integration point.
2. **DO NOT delete agents from Convex when YAML files are removed** -- Set status to "idle" (soft deactivation). Deleting would orphan references in tasks and messages.
3. **DO NOT skip the activity event** -- Every agent sync MUST write an `agent_connected` activity event. This is an architecture invariant.
4. **DO NOT block sync on validation errors** -- Valid agents must sync even if some YAML files are invalid. Log errors, continue processing.
5. **DO NOT hardcode the agents directory** -- Accept it as a parameter. The CLI and gateway may use different paths.
6. **DO NOT create a new bridge instance in gateway** -- The bridge is created once (by the process manager or CLI) and passed to the sync function.
7. **DO NOT forget the `by_name` index** -- The upsert query must use the index for efficient lookup. The index is already defined in `schema.ts`.

### What This Story Does NOT Include

- **No file watcher** -- NFR17 says detection on CLI command/refresh, not real-time file watching
- **No agent status management beyond sync** -- Active/crashed status updates are handled by the gateway during agent execution (Epic 4)
- **No CLI commands** -- Story 3.4 adds `nanobot mc agents list/create`
- **No dashboard components** -- Story 3.3 builds the agent sidebar

### Files Created in This Story

| File | Purpose |
|------|---------|
| `dashboard/convex/agents.ts` | Convex queries and mutations for agents table |

### Files Modified in This Story

| File | Changes |
|------|---------|
| `nanobot/mc/bridge.py` | Add `sync_agent()`, `list_agents()`, `deactivate_agents_except()` methods |
| `nanobot/mc/gateway.py` | Add `sync_agent_registry()` function |

### Verification Steps

1. Create 2 valid agent YAML files in `~/.nanobot/agents/`
2. Run sync -> both agents appear in Convex `agents` table with status "idle"
3. Check Convex `activities` table -> 2 `agent_connected` events exist
4. Remove one YAML file, run sync -> removed agent status set to "idle", remaining agent still active
5. Modify a YAML file (change role), run sync -> agent record updated in Convex
6. Create an invalid YAML file alongside valid ones -> valid ones sync, error logged for invalid
7. Verify no direct `convex` SDK imports in `gateway.py`: `grep -r "from convex" nanobot/mc/gateway.py` should return nothing
8. Run tests: `cd /Users/ennio/Documents/nanobot-ennio && python -m pytest nanobot/mc/test_gateway.py -v`

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 3.2`] -- Original story definition
- [Source: `_bmad-output/planning-artifacts/architecture.md#Architectural Boundaries`] -- Bridge as single Convex access point
- [Source: `_bmad-output/planning-artifacts/architecture.md#Communication Patterns`] -- Every mutation writes activity event
- [Source: `dashboard/convex/schema.ts`] -- Convex `agents` table schema with `by_name` and `by_status` indexes
- [Source: `nanobot/mc/bridge.py`] -- Existing ConvexBridge class
- [Source: `nanobot/mc/types.py`] -- `AgentData` dataclass
- [Source: `nanobot/mc/gateway.py`] -- Existing gateway placeholder

## Dev Agent Record

### Agent Model Used
claude-opus-4-6

### Debug Log References
- All 12 unit tests pass: `python -m pytest nanobot/mc/test_gateway.py -v`
- Full mc test suite: 194 passed (11 pre-existing failures in test_process_manager.py unrelated to this story)

### Completion Notes List
- Created `dashboard/convex/agents.ts` with `list`, `upsertByName`, `updateStatus`, `deactivateExcept` functions
- Added bridge methods: `sync_agent()`, `list_agents()`, `deactivate_agents_except()` to `ConvexBridge`
- Implemented `sync_agent_registry()` in `gateway.py` with model resolution chain (agent > default_model > hardcoded fallback)
- `upsertByName` writes `agent_connected` activity event on every insert/update (architectural invariant)
- `deactivateExcept` sets status to "idle" for removed agents (soft deactivation, no deletion)
- Invalid YAML files log errors but do not block sync of valid agents
- No direct Convex SDK imports in gateway.py — bridge-only access enforced

### File List
| File | Action |
|------|--------|
| `dashboard/convex/agents.ts` | Modified — added `upsertByName`, `updateStatus`, `deactivateExcept` mutations |
| `nanobot/mc/bridge.py` | Modified — added `sync_agent()`, `list_agents()`, `deactivate_agents_except()` methods |
| `nanobot/mc/gateway.py` | Modified — added `sync_agent_registry()` function with model resolution |
| `nanobot/mc/test_gateway.py` | Created — 12 unit tests covering sync, validation, model resolution, deactivation |
