# Tech Spec: Remote Terminal Bridge

Status: ready-for-dev

## Story

As a user of Mission Control,
I want to connect remote Claude Code instances via Convex and interact with them from the dashboard,
so that I can manage remote AI agents through the same interface as local agents.

## Context

The PoC (`poc_terminal_bridge.py`) validated the full loop: Dashboard → Convex → Bridge → tmux/Claude → Bridge → Convex → Dashboard. This story promotes the PoC to production, integrating with the existing agent system.

## Acceptance Criteria

### AC1: Script rename and cleanup
- [ ] Rename `poc_terminal_bridge.py` → `terminal_bridge.py`
- [ ] Kill tmux server on startup to clean orphan sessions
- [ ] `Ctrl+C` reliably kills the bridge and tmux session (already implemented with `os._exit`)

### AC2: Agent registration on connect
- [ ] When bridge starts, register in `agents` table as a new agent with:
  - `displayName`: "Remoto" (or configurable)
  - `role`: "remote-terminal"
  - `status`: "idle"
  - `isSystem`: false
- [ ] Include the machine's IP address in agent metadata (new field or in `variables`)
- [ ] On bridge shutdown, update agent status to "crashed" or remove

### AC3: Agent sidebar display
- [ ] Remote terminal agents appear in the **Registered** section of `AgentSidebar`
- [ ] Below system agents, labeled "Remoto"
- [ ] Show the IP address (clickable — opens in new tab or copies to clipboard)
- [ ] Status dot follows existing pattern: idle=gray, active=blue, crashed=red
- [ ] Map terminal bridge statuses: `idle` → `idle`, `processing` → `active`, `error` → `crashed`
- [ ] Close/delete button works like existing agents (soft-delete via `softDeleteAgent`)

### AC4: Authentication
- [ ] Bridge script uses `admin_key` authentication (same pattern as `nanobot/mc/bridge.py`)
- [ ] Read `CONVEX_ADMIN_KEY` from environment variable
- [ ] Pass to `ConvexBridge(url, admin_key=key)`
- [ ] Dashboard already authenticates via `ConvexReactClient` (no change needed)

### AC5: Multi-session support
- [ ] Bridge script accepts `--session-id` CLI arg (default: auto-generated UUID)
- [ ] Each bridge instance registers its own agent and session
- [ ] `terminalSessions` schema: add `agentName` field linking session to agent
- [ ] `listSessions` query: filter by active (non-deleted) agents
- [ ] Multiple bridges can run simultaneously from different machines

### AC6: Auto-detection of new connections
- [ ] Dashboard uses reactive `useQuery(api.agents.list)` (already real-time)
- [ ] When a new remote agent appears (role="remote-terminal"), it shows immediately in sidebar
- [ ] When bridge disconnects (status changes), UI updates in real-time

### AC7: Terminal in board area (not right panel)
- [ ] Clicking a remote agent in the sidebar opens its terminal in the **board area** (replacing/alongside KanbanBoard)
- [ ] Terminal panel fills the board area with full height
- [ ] Each terminal has an **X button** (top-right) to close it
- [ ] Closing returns to KanbanBoard

### AC8: Multi-terminal split layout
- [ ] Opening a second terminal splits the board area horizontally (50/50)
- [ ] Each terminal has its own X button
- [ ] Opening a third splits to thirds (33/33/33)
- [ ] Closing one terminal redistributes space to remaining terminals
- [ ] If all terminals closed, KanbanBoard returns
- [ ] Max 3-4 terminals open simultaneously

### AC9: Terminal panel enhancements
- [ ] Remove TerminalPanel from ActivityFeedPanel tabs (it moves to board area)
- [ ] TerminalPanel accepts `sessionId` as prop (not hardcoded)
- [ ] Show agent name and IP in terminal header
- [ ] TUI navigation toolbar (↑↓←→ Enter Tab Space Esc) stays

## Tasks / Subtasks

### Backend (Convex)

- [ ] **T1** Update `terminalSessions` schema: add `agentName: v.string()` field (AC: #5)
- [ ] **T2** Update `upsert` mutation to accept and store `agentName` (AC: #5)
- [ ] **T3** Update `listSessions` to join with agents table or filter by agentName (AC: #5)
- [ ] **T4** Add `registerTerminal` mutation: creates agent + session atomically (AC: #2)
- [ ] **T5** Add `disconnectTerminal` mutation: updates agent status to crashed (AC: #2)

### Bridge Script (Python)

- [ ] **T6** Rename `poc_terminal_bridge.py` → `terminal_bridge.py` (AC: #1)
- [ ] **T7** Add CLI args: `--session-id`, `--display-name`, `--convex-url`, `--admin-key` (AC: #4, #5)
  - [ ] Fallback to env vars: `CONVEX_URL`, `CONVEX_ADMIN_KEY`
- [ ] **T8** On startup: detect machine IP, call `registerTerminal` mutation (AC: #2)
- [ ] **T9** On shutdown: call `disconnectTerminal` mutation (AC: #2)
- [ ] **T10** Use `admin_key` in `ConvexBridge` constructor (AC: #4)

### Dashboard Frontend

- [ ] **T11** Add `openTerminals` state to `BoardContext` (or new context): `Array<{ sessionId, agentName }>` (AC: #7)
- [ ] **T12** Create `TerminalBoard` component: manages split layout of open terminals (AC: #8)
  - [ ] Single terminal: full width/height
  - [ ] Two terminals: flex row or column, 50/50
  - [ ] Three: 33/33/33
  - [ ] Each with X button overlay (top-right, absolute positioned)
- [ ] **T13** Update `DashboardLayout`: when `openTerminals.length > 0`, render `TerminalBoard` instead of `KanbanBoard` (AC: #7)
- [ ] **T14** Update `AgentSidebarItem`: clicking a remote-terminal agent opens its terminal in board (AC: #7)
  - [ ] Show IP as subtitle (clickable)
  - [ ] Map status: idle→idle, processing→active, error→crashed
- [ ] **T15** Update `TerminalPanel`: accept `sessionId` prop, remove hardcoded "poc-bridge-001" (AC: #9)
- [ ] **T16** Remove "Terminal" tab from `ActivityFeedPanel` (AC: #9)
- [ ] **T17** Add terminal header bar: agent name, IP badge, status dot, X close button (AC: #9)

## Dev Notes

### Architecture Patterns to Follow

- **Agent registration**: Follow `gateway.sync_agent_registry()` → `agents:upsertByName` pattern
- **Status dots**: Use `STATUS_DOT_STYLES` from `lib/constants.ts` (idle/active/crashed)
- **Lazy loading**: Use `React.lazy()` + `Suspense` for TerminalBoard (follows ChatPanel pattern)
- **Board switching**: BoardContext already has `activeBoardId` — extend for terminal overlay state
- **Real-time**: All Convex queries are reactive by default — no polling needed

### Key Files

| Component | File |
|-----------|------|
| Agent Sidebar | `dashboard/components/AgentSidebar.tsx` |
| Agent Item | `dashboard/components/AgentSidebarItem.tsx` |
| Dashboard Layout | `dashboard/components/DashboardLayout.tsx` |
| Board Context | `dashboard/components/BoardContext.tsx` |
| Kanban Board | `dashboard/components/KanbanBoard.tsx` |
| Terminal Panel | `dashboard/components/TerminalPanel.tsx` |
| Activity Feed Panel | `dashboard/components/ActivityFeedPanel.tsx` |
| Agents API | `dashboard/convex/agents.ts` |
| Terminal Sessions | `dashboard/convex/terminalSessions.ts` |
| Schema | `dashboard/convex/schema.ts` |
| Constants | `dashboard/lib/constants.ts` |
| Bridge (Python) | `poc_terminal_bridge.py` → `terminal_bridge.py` |
| ConvexBridge | `nanobot/mc/bridge.py` |

### Project Structure Notes

- Bridge script stays at project root (not in `nanobot/mc/`) — it's a standalone entry point
- Agent registration goes through Convex mutations (same as MC gateway)
- No changes needed to `nanobot/agent/` package (heavy deps, keep isolated)

### References

- [Source: dashboard/components/AgentSidebarItem.tsx] — STATUS_DOT_STYLES pattern
- [Source: dashboard/convex/agents.ts#upsertByName] — Agent registration mutation
- [Source: nanobot/mc/bridge.py#ConvexBridge] — Admin key auth pattern
- [Source: dashboard/components/DashboardLayout.tsx] — Board area layout structure
- [Source: poc_terminal_bridge.py] — Current PoC implementation

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
