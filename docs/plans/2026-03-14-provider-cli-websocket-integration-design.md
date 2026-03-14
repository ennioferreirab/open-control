# Provider CLI WebSocket Integration Design

## Decision Status

Approved on 2026-03-14.

Extends the provider CLI parser architecture (Stories 28.1–28.7) with the
runtime wiring needed to make it usable end-to-end: gateway → WebSocket →
browser.

## Goal

Wire the provider CLI session infrastructure into the existing WebSocket server
so that a browser client can launch a provider session, watch its output in real
time, and send intervention commands (interrupt, resume, stop) — all without the
legacy PTY/xterm stack.

## Problem

Stories 28.1–28.7 built the provider CLI core: types, parsers, supervisor,
registry, live stream projector, intervention controller, and the
`ProviderLiveChatPanel` UI component. But none of it is connected to the
gateway. The WebSocket server still only knows how to relay PTY bytes. The
frontend component has no data source. There is no way to test the new
architecture end-to-end.

## Design Summary

Reuse the existing WebSocket server on `:8765`. Add a new connection mode
(`mode=live-stream`) that streams `ProjectedEvent` JSON instead of PTY binary.
The frontend connects via a new React hook and feeds data into the existing
`ProviderLiveChatPanel`.

## Architecture

### Connection Routing

The existing `InteractiveSocketServer.handle_connection()` method dispatches
based on the `mode` query parameter:

```
ws://localhost:8765?mode=live-stream&sessionId=<mc_session_id>&provider=<name>&...
  → ProviderCLI WebSocket handler (new)

ws://localhost:8765?sessionId=<id>&provider=<name>&...
  → Legacy PTY relay handler (existing, deprecated)
```

The routing branch lives inside the existing `handle_connection` instance
method. The legacy code path is extracted into a private `_handle_legacy_connection`
method. No new ports, no new servers, no new dependencies.

### Backend Components

#### 1. Session Orchestrator (`mc/contexts/provider_cli/orchestrator.py`)

Placed in `mc/contexts/provider_cli/` (not `mc/runtime/`) because it owns
lifecycle state transitions and parser selection — behavioral decisions that
belong in the contexts layer. This mirrors how `mc.contexts.interactive.coordinator`
owns session lifecycle relative to `mc.runtime.interactive`.

Coordinates the full lifecycle for one provider CLI session:

- Creates a registry entry (STARTING)
- Launches the CLI via `ProviderProcessSupervisor`
- Selects the correct `ProviderCLIParser` by provider name
- Reads output via `supervisor.stream_output()`
- Parses chunks via `parser.parse_output()`
- Projects events via `LiveStreamProjector`
- Discovers the provider session ID via `parser.discover_session()`
- Transitions registry status (STARTING → RUNNING → COMPLETED/CRASHED)
- On process exit: drains remaining events, sends final status, transitions
  to COMPLETED (exit 0) or CRASHED (non-zero)

```python
class ProviderCLISessionOrchestrator:
    def __init__(
        self,
        registry: ProviderSessionRegistry,
        supervisor: ProviderProcessSupervisor,
        parsers: dict[str, ProviderCLIParser],
    ) -> None: ...

    async def start(
        self,
        mc_session_id: str,
        provider: str,
        command: list[str],
        cwd: str,
        env: dict[str, str] | None = None,
    ) -> ProviderProcessHandle: ...

    async def run_stream_loop(self, mc_session_id: str) -> None:
        """Read output, parse, project. Runs until process exits.
        On exit: drain queue, transition to COMPLETED or CRASHED."""
        ...

    async def handle_resume(self, mc_session_id: str, message: str) -> None:
        """Provider-aware resume. See Resume Handling section."""
        ...

    def get_projector(self, mc_session_id: str) -> LiveStreamProjector: ...
    def get_handle(self, mc_session_id: str) -> ProviderProcessHandle: ...
    def get_parser(self, mc_session_id: str) -> ProviderCLIParser: ...
```

#### 2. WebSocket Handler (`mc/runtime/provider_cli/websocket_handler.py`)

Handles a single WebSocket connection in `mode=live-stream`:

- Sends a `connected` message immediately upon acceptance
- If session exists and is active: subscribes to projector, replays events
  from `lastSeq` if provided
- If session does not exist: launches via orchestrator
- If session is in terminal state: sends `ended` message and closes
- Streams `ProjectedEvent` JSON to the client
- Sends status updates on state changes
- Receives and dispatches intervention commands
- Cleans up on disconnect (process keeps running for reconnection)

```python
async def handle_live_stream_connection(
    websocket: WebSocketServerProtocol,
    orchestrator: ProviderCLISessionOrchestrator,
    intervention: HumanInterventionController,
    mc_session_id: str,
    last_seq: int | None = None,
) -> None: ...
```

#### 3. Gateway Integration (`mc/runtime/interactive.py`)

Modify `InteractiveSocketServer.handle_connection()` to check `mode`:

```python
async def handle_connection(self, connection):
    params = parse_qs(connection.request.path)
    mode = params.get("mode", [None])[0]

    if mode == "live-stream":
        mc_session_id = params["sessionId"][0]
        last_seq = int(params.get("lastSeq", [0])[0]) or None
        await handle_live_stream_connection(
            connection, self._orchestrator, self._intervention,
            mc_session_id, last_seq,
        )
    else:
        await self._handle_legacy_connection(connection)
```

### WebSocket Protocol

#### Server → Client

Connected (sent immediately on acceptance):
```json
{"type": "connected", "mc_session_id": "mc-123", "protocol_version": 1}
```

Event message:
```json
{
  "type": "event",
  "seq": 42,
  "kind": "output",
  "text": "Running tests...",
  "ts": "2026-03-14T10:00:00.123Z",
  "provider_session_id": "sess-abc",
  "metadata": {}
}
```

Status message (sent after connected and on every state change):
```json
{
  "type": "status",
  "mc_session_id": "mc-123",
  "provider": "claude-code",
  "status": "running",
  "provider_session_id": "sess-abc",
  "supports_resume": true,
  "supports_interrupt": true,
  "supports_stop": true
}
```

Error message:
```json
{"type": "error", "code": "session_not_found", "message": "No session mc-999"}
```

Session ended:
```json
{
  "type": "ended",
  "mc_session_id": "mc-123",
  "exit_code": 0,
  "final_status": "completed"
}
```

#### Client → Server

```json
{"type": "interrupt"}
{"type": "resume", "message": "Use a different approach"}
{"type": "stop"}
```

### Reconnection Protocol

The `LiveStreamProjector` stores events in a bounded buffer (last 2000 events).
On reconnect, the client passes `lastSeq` as a query parameter:

```
ws://localhost:8765?mode=live-stream&sessionId=mc-123&lastSeq=42
```

The handler replays all buffered events with `seq > lastSeq` before subscribing
to the live queue. If `lastSeq` is older than the buffer window, the handler
replays from the oldest available event and sends a warning.

### Resume Handling

Resume semantics differ by provider. The orchestrator owns this decision:

**Claude Code** (`provider-native`, `supports_resume=True`):
1. `ClaudeCodeCLIParser.resume()` returns a command list with `--resume <session_id>`
2. Orchestrator launches a **new process** with the resume command
3. Orchestrator replaces the handle and restarts the stream loop
4. The old process has already exited (was interrupted)

**Codex** (`provider-native`, `supports_resume=True`):
1. Resume via stdin write to the running process (placeholder in current impl)
2. Orchestrator continues the existing stream loop

**Nanobot** (`runtime-owned`, `supports_resume=False`):
1. `NanobotCLIParser.resume()` raises `NotImplementedError`
2. The UI does not show the resume button when `supports_resume=False`
3. The WebSocket handler sends an error if the client sends resume anyway

The orchestrator's `handle_resume()` method checks `snapshot.supports_resume`
and the provider's resume mechanism before acting.

### Connection States

When a client connects with `mode=live-stream&sessionId=mc-123`:

| Scenario | Behavior |
|----------|----------|
| Session does not exist | Launch process, start streaming |
| Session active (RUNNING, etc.) | Subscribe to projector, replay from lastSeq |
| Session in terminal state (COMPLETED/STOPPED/CRASHED) | Send `ended` + close |
| Duplicate session ID on create | Second client subscribes to existing session |

### Frontend Components

#### 1. Hook: `useProviderLiveStream`

```typescript
// dashboard/features/interactive/hooks/useProviderLiveStream.ts

interface UseProviderLiveStreamOptions {
  sessionId: string;
  provider: string;
  enabled?: boolean;
}

interface UseProviderLiveStreamResult {
  messages: ProviderLiveChatMessage[];
  sessionStatus: ProviderLiveChatSessionStatus;
  isStreaming: boolean;    // true when connected AND status is running/interrupting
  isConnected: boolean;    // true when WebSocket is open
  sendInterrupt: () => void;
  sendResume: (message: string) => void;
  sendStop: () => void;
}
```

- Reads WebSocket URL from the same config the existing interactive system uses
  (not hardcoded `localhost:8765`)
- Tracks `lastSeq` from received events; passes it on reconnect
- Auto-reconnects with exponential backoff (1s, 2s, 4s, max 30s)
- Max reconnect attempts: 20
- `isStreaming` = `isConnected && status in (running, interrupting, resuming)`

#### 2. Wiring into `InteractiveChatTabs`

```tsx
const stream = useProviderLiveStream({
  sessionId: session?.sessionId,
  provider: session?.provider,
  enabled: !!session,
});

return (
  <ProviderLiveChatPanel
    messages={stream.messages}
    sessionStatus={stream.sessionStatus}
    isStreaming={stream.isStreaming}
    onSendMessage={stream.sessionStatus.status === "human_intervening"
      ? stream.sendResume
      : undefined}
  />
);
```

### Data Flow

```
1. Client connects: ws://localhost:8765?mode=live-stream&sessionId=mc-123&provider=claude-code
2. Handler sends {"type": "connected"}
3. Gateway routes to ProviderCLI handler
4. Orchestrator launches CLI (or subscribes to existing session)
5. Handler replays buffered events from lastSeq (if reconnecting)
6. Supervisor streams stdout chunks
7. Parser normalizes chunks → ParsedCliEvent[]
8. LiveStreamProjector assigns seq/timestamp → ProjectedEvent (bounded buffer)
9. WebSocket handler reads from projector queue → sends JSON to client
10. Browser hook receives JSON → feeds ProviderLiveChatPanel
11. User clicks "Interrupt" → client sends {"type": "interrupt"}
12. Handler calls InterventionController.interrupt() → parser signals process
13. Status updates flow back through the same WebSocket
```

## What This Does NOT Do

- Does not replace the legacy PTY relay (stays for TaskDetailSheet)
- Does not add HTTP endpoints or SSE
- Does not modify Convex schema
- Does not add new dependencies
- Does not change the gateway boot sequence
- Does not add authentication to the WebSocket endpoint (acceptable for
  local-only deployment; must be revisited if exposed over network)

## Files Affected

New:
- `mc/contexts/provider_cli/orchestrator.py`
- `mc/runtime/provider_cli/websocket_handler.py`
- `dashboard/features/interactive/hooks/useProviderLiveStream.ts`
- `tests/mc/provider_cli/test_orchestrator.py`
- `tests/mc/provider_cli/test_websocket_handler.py`
- `tests/mc/provider_cli/test_mode_routing.py`
- `dashboard/features/interactive/hooks/useProviderLiveStream.test.ts`

Modified:
- `mc/runtime/interactive.py` — add mode routing in handle_connection
- `mc/runtime/provider_cli/live_stream.py` — add bounded buffer (max 2000 events)
- `dashboard/features/interactive/components/InteractiveChatTabs.tsx` — wire hook
- `mc/runtime/provider_cli/__init__.py` — export new modules
- `mc/contexts/provider_cli/__init__.py` — export orchestrator
- `docs/ARCHITECTURE.md` — document provider_cli packages

## Risks

- **Reconnection edge cases**: if the buffer overflows between disconnects,
  the client loses events. Mitigated by bounded buffer of 2000 events.
- **Resume protocol mismatch**: Claude Code resume means launching a new process.
  The orchestrator must swap the handle and restart the stream loop cleanly.
- **Concurrent connections**: multiple tabs connecting to the same session
  should see the same stream. The projector supports multiple subscribers.
- **No authentication**: WebSocket endpoint is unauthenticated. Acceptable for
  local dev but must be addressed before network exposure.

## Testing Strategy

- Unit tests for orchestrator (mock supervisor, parser, projector)
- Unit tests for WebSocket handler (mock WebSocket, mock orchestrator)
- Unit test for mode routing in handle_connection (legacy vs live-stream)
- Frontend hook tests (mock WebSocket)
- Integration test: launch a real `echo` process through the full pipeline
- Reconnection test: connect, disconnect, reconnect with lastSeq, verify replay
