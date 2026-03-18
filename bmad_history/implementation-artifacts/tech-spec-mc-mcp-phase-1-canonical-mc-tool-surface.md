# Story: MC MCP Phase 1 Canonical MC Tool Surface

Status: ready-for-dev

## Story

As a Mission Control platform maintainer,
I want a repo-owned canonical MCP surface for the Phase 1 MC tools,
so that nanobot MC execution can consume one explicit, namespaced tool contract
without relying on duplicated inline tool definitions or overlapping native
tools.

## Acceptance Criteria

### AC1: Canonical Phase 1 Tool Surface Exists

**Given** Phase 1 includes MC-owned coordination tools
**When** the repo-owned MC MCP surface is defined
**Then** it exposes `ask_user`, `ask_agent`, `delegate_task`, `send_message`, `cron`, `report_progress`, and `record_final_result`
**And** `send_message` is the canonical message tool for this surface.

### AC2: Repo-Owned MCP Bridge Exists

**Given** upstream nanobot already knows how to consume MCP servers
**When** MC nanobot execution is configured for Phase 1
**Then** it can connect to a repo-owned MC MCP bridge through the existing `mcpServers` mechanism
**And** the bridge forwards tool calls to the existing MC IPC/runtime handlers.

### AC3: Public Naming is Semantic, Not Transport-Coupled

**Given** tool names are part of the prompt contract
**When** the bridge is exposed to the model
**Then** the public names stay semantic and short
**And** the system does not expose names like `send_message_mc`
**And** namespace identity is carried by the MCP server identity rather than the tool name suffix.

### AC4: Low Vendor Impact is Preserved

**Given** `vendor/nanobot` and `vendor/claude-code` are upstream-oriented dependencies
**When** this story completes
**Then** the canonical tool surface lives under `mc/`
**And** vendor edits are limited to a thin import seam only if that seam materially reduces duplication.

### AC5: Focused Tool-Surface Regression Passes

**Given** the tool list is part of runtime behavior
**When** this story completes
**Then** focused tests prove the repo-owned MCP bridge lists the expected tools
**And** tool calls are forwarded correctly through the existing MC IPC path.

## Tasks / Subtasks

- [ ] **Task 1: Define canonical tool specs** (AC: #1, #3, #4)
  - [ ] 1.1 Create repo-owned tool-spec definitions for the Phase 1 surface
  - [ ] 1.2 Make `send_message` the single canonical message tool on that surface
  - [ ] 1.3 Keep names semantic and stable

- [ ] **Task 2: Add the repo-owned MCP bridge** (AC: #2, #4)
  - [ ] 2.1 Create a repo-owned stdio MCP bridge entrypoint
  - [ ] 2.2 Forward calls through the existing MC IPC contract
  - [ ] 2.3 Ensure the bridge can be launched by nanobot through `mcpServers`

- [ ] **Task 3: Decide whether to reuse specs in the Claude Code bridge** (AC: #4)
  - [ ] 3.1 If low-risk, make the vendor Claude Code bridge import canonical specs from `mc`
  - [ ] 3.2 If not low-risk, leave the vendor bridge stable and document the follow-up explicitly

- [ ] **Task 4: Add focused regression tests** (AC: #1, #2, #5)
  - [ ] 4.1 Add list-tools coverage for the repo-owned bridge
  - [ ] 4.2 Add call-through coverage for at least `send_message` and `ask_user`
  - [ ] 4.3 Add a regression assertion that `message` is not part of the MCP Phase 1 surface

## Dev Notes

### Architecture Notes

- This story is about ownership and surface definition, not yet about removing every legacy path.
- The canonical MC surface should live in `mc`, because the tool semantics belong to Mission Control.
- Upstream nanobot remains the generic MCP consumer.

### Likely Touch Points

- `mc/runtime/mcp/tool_specs.py`
- `mc/runtime/mcp/bridge.py`
- `tests/mc/runtime/test_mc_mcp_bridge.py`
- optionally a thin seam in `vendor/claude-code/claude_code/mcp_bridge.py`

### References

- [Source: /Users/ennio/Documents/nanobot-ennio/vendor/nanobot/nanobot/agent/tools/mcp.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/vendor/claude-code/claude_code/mcp_bridge.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/vendor/claude-code/claude_code/ipc_server.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/vendor/claude-code/claude_code/workspace.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/docs/plans/2026-03-14-mc-mcp-phase-1-tools-implementation-plan.md]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
