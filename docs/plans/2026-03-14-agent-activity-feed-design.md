# Agent Activity Feed Design

## Decision Status

Approved on 2026-03-14.

Supersedes the WebSocket integration design
(`2026-03-14-provider-cli-websocket-integration-design.md`).

## Goal

Give operators structured, real-time visibility into what agents are doing
(tools, files, decisions) with the ability to intervene — without building a
new transport layer. The task thread only receives the final result.

## Problem

The supervision pipeline already flows data from Claude Code hooks through MC
to Convex. But:

1. Only the **latest** event is stored — no history.
2. The UI renders a **terminal emulator** (xterm) instead of structured activity.
3. **Intervention** requires terminal takeover instead of inline controls.

## Design Summary

Add a Convex event log table, enrich the existing supervision pipeline to write
event history, build a reactive `AgentActivityFeed` dashboard component, and
add intervention controls. Zero new transport — uses existing hooks → IPC →
Convex pipeline.

## Phasing

**Phase 1** (this spec): Event log + activity feed + interrupt/stop controls.
Approval events render as informational (no inline approve/reject buttons).
Intervention uses existing `requestHumanTakeover` + `resumeAgentControl`
mutations from `interactiveSessions`.

**Phase 2** (follow-up): Inline approve/reject buttons for `approval_requested`
events. Requires bidirectional IPC for the hook bridge to block until the
approval decision arrives. Out of scope for Phase 1.

## What Already Exists

```
Claude Code hooks → hook_bridge.py → MCSocketServer (IPC)
  → normalize_provider_event() → InteractiveSupervisionEvent
  → InteractiveExecutionSupervisor.handle_event()
  → InteractiveSessionRegistry.record_supervision()
  → bridge.mutation("interactiveSessions:upsert", metadata)
  → Convex interactiveSessions table (latest state only)
```

13 canonical event kinds already flow:
`session_started`, `session_ready`, `turn_started`, `turn_updated`,
`turn_completed`, `item_started`, `item_completed`, `approval_requested`,
`user_input_requested`, `ask_user_requested`, `paused_for_review`,
`session_failed`, `session_stopped`.

## Hook Metadata Contract

Not all hook events carry the same fields. The enrichment must handle missing
fields gracefully.

| Claude Code Hook | Canonical Kind | `tool_name` | `input` | `summary` |
|-----------------|---------------|-------------|---------|-----------|
| `PreToolUse` | `item_started` | yes | yes (dict) | no |
| `PostToolUse` | `item_completed` | yes | no | no |
| `PermissionRequest` | `approval_requested` | yes | yes (dict) | no |
| `UserPromptSubmit` | `turn_started` | no | no | no |
| `Stop` | `turn_completed` | no | no | yes (via `result`) |
| `Notification` | `turn_updated` | no | no | yes (via `message`) |
| `SubagentStart` | `item_started` | no | no | yes (via `message`) |
| `SubagentStop` | `item_completed` | no | no | yes (via `message`) |

Codex events follow a similar pattern via `CodexSupervisionRelay`. Nanobot
events come from `NanobotInteractiveSessionRunner`. Both emit canonical kinds
through the same pipeline. Where `tool_name` or `input` is absent, the UI
falls back to showing `kind` and `summary`.

The `tool_name` field appears in `event.metadata["tool_name"]` for Claude Code
hooks. The `input` field appears in `event.metadata["input"]` as a dict. Both
are placed in `metadata` by `normalize_provider_event()` since they are not
top-level fields in `InteractiveSupervisionEvent`.

## Architecture

### 1. Event Log Table (Convex)

New table `sessionActivityLog`:

```typescript
sessionActivityLog: defineTable({
  sessionId: v.string(),
  seq: v.number(),            // monotonic per session
  kind: v.string(),           // canonical event kind
  ts: v.string(),             // ISO timestamp
  // Structured fields (extracted from metadata)
  toolName: v.optional(v.string()),
  toolInput: v.optional(v.string()),  // stringified, truncated to 2000 chars
  filePath: v.optional(v.string()),
  summary: v.optional(v.string()),    // truncated to 1000 chars
  error: v.optional(v.string()),      // truncated to 2000 chars
  turnId: v.optional(v.string()),
  itemId: v.optional(v.string()),
  stepId: v.optional(v.string()),     // may be null for early lifecycle events
  agentName: v.optional(v.string()),
  provider: v.optional(v.string()),
  // Phase 1: informational only
  requiresAction: v.optional(v.boolean()),
})
  .index("by_session", ["sessionId"])
  .index("by_session_seq", ["sessionId", "seq"])
```

**`listForSession` query** uses the `by_session_seq` index to guarantee
ordering by `seq`. Returns at most the last 500 events. Client-side filtering
by kind in Phase 1; server-side `by_session_kind` index deferred to Phase 2.

**`seq` generation**: the `append` mutation reads the current max `seq` for the
session within the same Convex transaction (via `by_session_seq` index, ordered
descending, take 1). Convex OCC serializes concurrent mutations that read and
write overlapping data, so this is safe.

**Cleanup**: a scheduled Convex action runs daily and deletes events older than
7 days for ended sessions. Active session events are not pruned.

### 2. Supervisor Enrichment (Python)

Modify `InteractiveExecutionSupervisor.handle_event()` to also write to the
event log after the existing `record_supervision` call:

```python
def _stringify_input(raw: Any, max_len: int = 2000) -> str | None:
    """Stringify and truncate tool input for display."""
    if raw is None:
        return None
    text = json.dumps(raw) if isinstance(raw, dict) else str(raw)
    return text[:max_len] if len(text) > max_len else text

def _extract_file_path(metadata: dict[str, Any]) -> str | None:
    """Extract file path from tool input when available."""
    inp = metadata.get("input", {})
    if isinstance(inp, dict):
        return inp.get("file_path") or inp.get("path")
    return None

_ACTION_KINDS = {"approval_requested", "user_input_requested",
                 "ask_user_requested"}

# In handle_event(), after record_supervision:
self._bridge.mutation("sessionActivityLog:append", {
    "session_id": event.session_id,
    "kind": event.kind,
    "ts": timestamp,
    "tool_name": event.metadata.get("tool_name"),
    "tool_input": _stringify_input(event.metadata.get("input")),
    "file_path": _extract_file_path(event.metadata),
    "summary": (event.summary or "")[:1000] or None,
    "error": (event.error or "")[:2000] or None,
    "turn_id": event.turn_id,
    "item_id": event.item_id,
    "step_id": event.step_id,  # may be null for early events
    "agent_name": event.agent_name,
    "provider": event.provider,
    "requires_action": event.kind in _ACTION_KINDS,
})
```

~25 lines added to the existing supervisor. No new Python modules.

### 3. Intervention Controls (Phase 1)

Phase 1 reuses the existing `interactiveSessions` mutations for intervention:

- **Interrupt/Stop**: uses existing `requestHumanTakeover()` mutation (already
  wired in `useInteractiveTakeoverControls` hook)
- **Resume**: uses existing `resumeAgentControl()` mutation
- **Send message**: uses existing free-form message flow through the IPC channel

The `AgentActivityFeed` footer renders Interrupt and Stop buttons that call
these existing mutations. No new Convex mutations needed for Phase 1.

`approval_requested` events render as informational status items (icon + text)
without inline buttons. The operator uses Interrupt to take over if they need
to reject a pending approval.

### 4. Agent Activity Feed Component (Dashboard)

```typescript
// dashboard/features/interactive/components/AgentActivityFeed.tsx

interface AgentActivityFeedProps {
  sessionId: string;
}
```

Renders a reactive list of session events:

```
┌─────────────────────────────────────────────┐
│ 🟢 claude-pair • running • step 3           │
├─────────────────────────────────────────────┤
│ ⚡ Bash: uv run pytest tests/ -v            │
│ 📝 Edit: mc/runtime/gateway.py:45           │
│ ⚡ Bash: uv run ruff check mc/              │
│ ⚠️  Approval requested: rm -rf /tmp/test    │
│ ✅ Completed: "Tests passing, PR ready"      │
├─────────────────────────────────────────────┤
│ [Interrupt] [Stop]                           │
└─────────────────────────────────────────────┘
```

Event rendering rules:

| kind | Display | Fallback |
|------|---------|----------|
| `item_started` | `{toolName}: {toolInput}` (truncated) | `Activity started` |
| `item_completed` | `{toolName} done` (collapsed) | `Activity completed` |
| `approval_requested` | `Approval: {summary or toolName}` (info only in Phase 1) | `Approval requested` |
| `turn_started` | `Turn started` (subtle) | — |
| `turn_completed` | `{summary}` (highlighted) | `Turn completed` |
| `session_failed` | `{error}` (red) | `Session failed` |
| `user_input_requested` | `{summary}` (info only) | `Input requested` |
| other | `{kind}: {summary}` | `{kind}` |

Features:
- Auto-scroll to bottom (with scroll-away detection)
- Collapsible detail for tool inputs (click to expand)
- Session header with status, provider, agent name from `interactiveSessions`
- Interrupt/Stop buttons in footer (via existing takeover hook)

### 5. Hook: `useAgentActivity`

```typescript
// dashboard/features/interactive/hooks/useAgentActivity.ts

function useAgentActivity(sessionId: string | undefined) {
  const events = useQuery(
    api.sessionActivityLog.listForSession,
    sessionId ? { sessionId } : "skip"
  );
  const session = useQuery(
    api.interactiveSessions.getBySessionId,
    sessionId ? { sessionId } : "skip"
  );

  return {
    events: events ?? [],
    session,
  };
}
```

Convex handles reactivity. Intervention actions come from the existing
`useInteractiveTakeoverControls` hook.

### 6. Wiring

The `AgentActivityFeed` is rendered by `ChatPanel` when an active interactive
session exists, as a companion panel alongside the chat. The existing
`InteractiveChatTabs` component is unchanged (it already just passes through
`chatView`).

For step live share in `TaskDetailSheet`, the same `AgentActivityFeed`
component is used with the step's `sessionId`, replacing the current
`InteractiveTerminalPanel` usage.

## Data Flow

```
1. Claude Code calls a tool (e.g., Bash)
2. PreToolUse hook fires → hook_bridge.py
3. Bridge sends IPC → MCSocketServer
4. Server normalizes → InteractiveSupervisionEvent(kind="item_started",
     metadata={"tool_name": "Bash", "input": {"command": "uv run pytest"}})
5. Supervisor calls record_supervision (existing — updates latest state)
6. Supervisor calls sessionActivityLog:append (NEW — persists event with seq)
7. Convex subscription pushes new event to browser
8. AgentActivityFeed renders: ⚡ Bash: uv run pytest
9. If kind=approval_requested, shows ⚠️ informational status
10. Operator uses Interrupt button → existing takeover mutation
```

## What Gets Reused From Stories 28.x

| Component | Reuse |
|-----------|-------|
| `SessionStatus` enum | Maps to supervision states |
| `ParsedCliEvent` kinds | Align with canonical event kinds |
| `InterventionController` state machine | Interrupt/stop logic |
| `ProviderCLIParser` contract | Not needed — hooks provide richer data |
| `ProviderProcessSupervisor` | Not needed — existing adapters launch |
| `LiveStreamProjector` | Not needed — Convex is the projector |
| `ProviderLiveChatPanel` | Deprecated — replaced by `AgentActivityFeed` |

## What This Does NOT Do

- Does not build a new WebSocket transport
- Does not replace the existing supervision pipeline
- Does not change how providers are launched
- Does not affect the task thread (only final result goes there)
- Does not add inline approve/reject (Phase 2)
- Does not add stdout parsing for live output

## Risks and Mitigations

### Event volume
Long sessions could produce thousands of events. Mitigation: query returns max
500 events, daily cleanup job prunes events for ended sessions older than 7 days.

### Missing metadata fields
Not all hook events carry `tool_name` or `input`. Mitigation: UI has fallback
text for every event kind. See Hook Metadata Contract section.

### Approval response delivery (Phase 2)
Getting approval responses back to Claude Code requires bidirectional IPC.
Deferred to Phase 2. Phase 1 uses interrupt as the intervention mechanism.

### Codex and Nanobot
Both already emit canonical events through the same pipeline. The activity feed
works for all providers automatically.

## Testing Strategy

- Convex schema tests: validate table, indexes, mutation args
- `append` mutation test: verify seq auto-increment with concurrent writes
- Supervisor enrichment tests: verify `sessionActivityLog:append` is called
  with correct fields, verify truncation, verify fallback for missing metadata
- AgentActivityFeed component tests: render with different event kinds, verify
  fallback text, verify footer controls
- useAgentActivity hook tests: verify reactive query wiring
- Integration: fire a supervision event through the pipeline, verify it
  appears in the Convex table

## Files Affected

New:
- `dashboard/convex/sessionActivityLog.ts` — table, queries, append mutation
- `dashboard/features/interactive/components/AgentActivityFeed.tsx`
- `dashboard/features/interactive/components/AgentActivityFeed.test.tsx`
- `dashboard/features/interactive/hooks/useAgentActivity.ts`

Modified:
- `dashboard/convex/schema.ts` — add `sessionActivityLog` table
- `mc/contexts/interactive/supervisor.py` — add `sessionActivityLog:append`
- `tests/mc/test_interactive_supervisor.py` — verify new mutation call
- `docs/ARCHITECTURE.md` — document `dashboard/features/interactive`

Deprecated:
- `dashboard/features/interactive/components/ProviderLiveChatPanel.tsx`
- `dashboard/features/interactive/components/ProviderLiveChatPanel.test.tsx`
