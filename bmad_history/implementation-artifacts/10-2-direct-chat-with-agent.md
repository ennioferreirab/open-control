# Story 10.2: Direct Chat with Agent

Status: ready-for-dev

## Story

As a **user**,
I want a Chats tab in the Activity Feed panel where I can chat directly with any agent without creating a task,
so that I can ask quick questions or brainstorm ideas outside the formal task workflow.

## Acceptance Criteria

### AC1: Chats Table Schema

**Given** the Convex schema is deployed
**When** the `chats` table is queried
**Then** it supports documents with fields: `agentName` (string), `authorName` (string), `authorType` ("user" | "agent"), `content` (string), `status` (optional: "pending" | "processing" | "done"), `timestamp` (string)
**And** it has indexes `by_agentName` on `["agentName"]` and `by_timestamp` on `["timestamp"]`

### AC2: Chats Tab in Activity Feed Panel

**Given** the Activity Feed panel is expanded
**When** the user views the panel header
**Then** two tabs are visible: "Activity" (default) and "Chats"
**And** clicking "Activity" shows the existing ActivityFeed component
**And** clicking "Chats" shows the new ChatPanel component
**And** the panel title updates to reflect the active tab

### AC3: Agent Selection in Chat Panel

**Given** the user is on the Chats tab
**When** no agent is selected
**Then** an `@` input prompt is shown: "Type @ to select an agent..."
**And** typing `@` triggers the AgentMentionAutocomplete (from Story 10.1) to select a chat target
**And** after selecting an agent, the agent name is displayed as a locked header (e.g., "Chatting with @secretary")
**And** the chat input becomes active for message composition

### AC4: Sending a Chat Message

**Given** an agent is selected in the chat panel
**When** the user types a message and presses Enter (or clicks Send)
**Then** a new document is created in the `chats` table with `authorType="user"`, `authorName="User"`, `status="pending"`, and the current ISO timestamp
**And** the message appears immediately in the chat message list
**And** the input is cleared

### AC5: Agent Processing and Response

**Given** a chat message has `status="pending"` in the `chats` table
**When** the Python backend `ChatHandler` polls for pending messages
**Then** it marks the message as `status="processing"` (triggers typing indicator in UI)
**And** it calls `agent.process_direct()` with session key `mc-chat:{agent_name}` to generate a response
**And** it creates a new chat document with `authorType="agent"`, `authorName={agent_displayName}`, `status="done"`, and the agent's response as content
**And** it marks the original user message as `status="done"`

### AC6: Typing Indicator

**Given** a chat message has `status="processing"`
**When** the ChatMessages component renders
**Then** a typing indicator (animated dots) is shown below the last message, attributed to the selected agent
**And** the indicator disappears when the agent's response message appears

### AC7: Chat Message Display

**Given** the user is chatting with an agent
**When** messages are loaded for that agent
**Then** messages are displayed in chronological order, filtered by `agentName`
**And** user messages are right-aligned with a blue/primary background
**And** agent messages are left-aligned with a muted/secondary background
**And** each message shows the author name, timestamp (relative, e.g., "2m ago"), and content
**And** messages auto-scroll to the bottom on new arrivals

### AC8: Switch Agent in Chat

**Given** the user is chatting with an agent
**When** the user types `@` in the chat input
**Then** the autocomplete appears and allows selecting a different agent
**And** the chat view switches to show the new agent's conversation history
**And** the previous agent's conversation is preserved (queryable by agentName)

### AC9: Backend Chat Handler Lifecycle

**Given** the gateway starts
**When** the `run_gateway()` function initializes all background tasks
**Then** a `ChatHandler` asyncio task is started alongside the orchestrator, executor, and timeout checker
**And** the ChatHandler polls `chats` with `status="pending"` every 2 seconds
**And** on gateway shutdown, the ChatHandler task is cancelled gracefully

## Tasks / Subtasks

- [ ] Task 1: Extend Convex schema with chats table (AC: 1)
  - [ ] 1.1: Add `chats` table definition to `dashboard/convex/schema.ts`:
    ```typescript
    chats: defineTable({
      agentName: v.string(),
      authorName: v.string(),
      authorType: v.union(v.literal("user"), v.literal("agent")),
      content: v.string(),
      status: v.optional(v.union(v.literal("pending"), v.literal("processing"), v.literal("done"))),
      timestamp: v.string(),
    }).index("by_agentName", ["agentName"]).index("by_timestamp", ["timestamp"]),
    ```
  - [ ] 1.2: Create `dashboard/convex/chats.ts` with Convex functions:
    - `listByAgent` query: args `{ agentName: v.string() }`, returns all chat messages filtered by `agentName`, ordered by insertion (chronological). Use `.withIndex("by_agentName", q => q.eq("agentName", args.agentName))`.
    - `send` mutation: args `{ agentName, authorName, authorType, content, status?, timestamp }`. Inserts a new chat document.
    - `listPending` query: args `{}`. Returns all chats with `status === "pending"`. Scan all chats and filter (no direct index on status alone; pending messages are few).
    - `updateStatus` mutation: args `{ chatId: v.id("chats"), status: v.union(v.literal("pending"), v.literal("processing"), v.literal("done")) }`. Patches the status field.

- [ ] Task 2: Add Chats tab to ActivityFeedPanel (AC: 2)
  - [ ] 2.1: In `dashboard/components/ActivityFeedPanel.tsx`, add state: `const [activeTab, setActiveTab] = useState<"activity" | "chats">("activity")`. Import `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent` from ShadCN.
  - [ ] 2.2: Replace the current header `<h2>Activity Feed</h2>` with a `Tabs` component containing two `TabsTrigger` buttons: "Activity" and "Chats". Style the tabs to fit the narrow panel (compact, `text-xs`).
  - [ ] 2.3: Wrap the existing `<ActivityFeed />` in `<TabsContent value="activity">` and add `<TabsContent value="chats"><ChatPanel /></TabsContent>`. Ensure both tabs inherit the `flex-1 min-h-0 overflow-hidden flex flex-col` layout from the parent.
  - [ ] 2.4: Import `ChatPanel` lazily to avoid loading chat components when the Activity tab is active: `const ChatPanel = dynamic(() => import('./ChatPanel').then(m => m.ChatPanel), { ssr: false })` (or use React.lazy with Suspense).

- [ ] Task 3: Build ChatPanel component (AC: 3, 4, 8)
  - [ ] 3.1: Create `dashboard/components/ChatPanel.tsx`. State: `selectedAgent: string | null` (null = no agent selected), `content: string`, `isSubmitting: boolean`. Query agents via `useQuery(api.agents.list)`.
  - [ ] 3.2: When `selectedAgent === null`, render an agent selection prompt: centered text "Type @ to select an agent" with a text input that triggers `AgentMentionAutocomplete` on `@`. Filter agents the same way as ThreadInput (all enabled, non-deleted).
  - [ ] 3.3: When `selectedAgent !== null`, render: (a) locked header bar showing `"Chatting with @{selectedAgent}"` with a small "x" button or "Switch" link to reset `selectedAgent` to null, (b) `<ChatMessages agentName={selectedAgent} />` taking `flex-1`, (c) chat input at bottom with Textarea + Send button (same pattern as ThreadInput).
  - [ ] 3.4: On message send: call `useMutation(api.chats.send)` with `{ agentName: selectedAgent, authorName: "User", authorType: "user", content, status: "pending", timestamp: new Date().toISOString() }`. Clear input, set `isSubmitting` during mutation.
  - [ ] 3.5: In the chat input, detect `@` to trigger `AgentMentionAutocomplete`. On agent selection from autocomplete, switch `selectedAgent` to the new agent (changes the conversation view). Clear the input text.

- [ ] Task 4: Build ChatMessages component (AC: 6, 7)
  - [ ] 4.1: Create `dashboard/components/ChatMessages.tsx`. Props: `agentName: string`. Query: `useQuery(api.chats.listByAgent, { agentName })`.
  - [ ] 4.2: Render messages in a `ScrollArea`. User messages: right-aligned, `bg-primary/10` or `bg-blue-50`, rounded bubble. Agent messages: left-aligned, `bg-muted`, rounded bubble. Each bubble shows: author name (small, muted), content (body), relative timestamp (bottom-right, `text-xs text-muted-foreground`). Use `formatDistanceToNow` from `date-fns` for relative time.
  - [ ] 4.3: Implement auto-scroll: `useRef` for a bottom sentinel div. In a `useEffect` that depends on the messages array, scroll the sentinel into view with `behavior: "smooth"`.
  - [ ] 4.4: Implement typing indicator: if any message in the list has `status === "processing"`, render an animated typing indicator (`...` with CSS pulse animation or three bouncing dots) below the last message, left-aligned with agent styling. Attribute it to the agent: `"{agentDisplayName} is typing..."`.
  - [ ] 4.5: Handle empty state: when no messages exist for the selected agent, show centered muted text: "Start a conversation with @{agentName}".

- [ ] Task 5: Build Python ChatHandler (AC: 5, 9)
  - [ ] 5.1: Create `nanobot/mc/chat_handler.py`. Class `ChatHandler` with `__init__(self, bridge: ConvexBridge)`. Store the bridge reference.
  - [ ] 5.2: Implement `async def run(self) -> None` as the main polling loop:
    ```python
    while True:
        try:
            pending = await asyncio.to_thread(self._bridge.query, "chats:listPending")
            if pending:
                for msg in pending:
                    asyncio.create_task(self._process_chat_message(msg))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("[chat_handler] Error polling pending chats")
        await asyncio.sleep(2.0)
    ```
  - [ ] 5.3: Implement `async def _process_chat_message(self, msg: dict) -> None`:
    - Extract `chat_id = msg["id"]`, `agent_name = msg["agent_name"]`, `content = msg["content"]`.
    - Mark as processing: `await asyncio.to_thread(self._bridge.mutation, "chats:updateStatus", {"chat_id": chat_id, "status": "processing"})`.
    - Load agent config: use the same `_load_agent_config` pattern from `executor.py` (import `validate_agent_file` from `nanobot.mc.yaml_validator`, read `AGENTS_DIR / agent_name / config.yaml`).
    - Create provider: use `_make_provider` pattern from `executor.py` (import from `nanobot.mc.provider_factory`).
    - Create an `AgentLoop` instance with the agent's workspace, model, and prompt.
    - Call `await loop.process_direct(content=content, session_key=f"mc-chat:{agent_name}", channel="mc", chat_id=agent_name)`.
    - Get agent display name from config or fall back to `agent_name`.
    - Send response: `await asyncio.to_thread(self._bridge.mutation, "chats:send", {"agent_name": agent_name, "author_name": display_name, "author_type": "agent", "content": response, "status": "done", "timestamp": datetime.now(timezone.utc).isoformat()})`.
    - Mark original as done: `await asyncio.to_thread(self._bridge.mutation, "chats:updateStatus", {"chat_id": chat_id, "status": "done"})`.
  - [ ] 5.4: Add error handling in `_process_chat_message`: if agent processing fails, mark the original message as `"done"` (to prevent infinite retries) and send an error response message: `"Sorry, I encountered an error: {error_message}"` with `authorType="agent"`.

- [ ] Task 6: Add bridge helper methods for chats (AC: 5)
  - [ ] 6.1: In `nanobot/mc/bridge.py`, add `get_pending_chat_messages(self) -> list[dict]`:
    ```python
    def get_pending_chat_messages(self) -> list[dict[str, Any]]:
        result = self.query("chats:listPending")
        return result if isinstance(result, list) else []
    ```
  - [ ] 6.2: Add `send_chat_response(self, agent_name, author_name, content) -> Any`:
    ```python
    def send_chat_response(self, agent_name: str, author_name: str, content: str) -> Any:
        return self.mutation("chats:send", {
            "agent_name": agent_name,
            "author_name": author_name,
            "author_type": "agent",
            "content": content,
            "status": "done",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    ```
  - [ ] 6.3: Add `mark_chat_processing(self, chat_id: str) -> Any`:
    ```python
    def mark_chat_processing(self, chat_id: str) -> Any:
        return self.mutation("chats:updateStatus", {"chat_id": chat_id, "status": "processing"})
    ```
  - [ ] 6.4: Add `mark_chat_done(self, chat_id: str) -> Any`:
    ```python
    def mark_chat_done(self, chat_id: str) -> Any:
        return self.mutation("chats:updateStatus", {"chat_id": chat_id, "status": "done"})
    ```

- [ ] Task 7: Register ChatHandler in gateway (AC: 9)
  - [ ] 7.1: In `nanobot/mc/gateway.py`, import `ChatHandler` at the top of `run_gateway()` (lazy import pattern, like `TaskExecutor`): `from nanobot.mc.chat_handler import ChatHandler`.
  - [ ] 7.2: After the executor and timeout checker are created (around line 887), instantiate and start the ChatHandler:
    ```python
    chat_handler = ChatHandler(bridge)
    chat_task = asyncio.create_task(chat_handler.run())
    ```
  - [ ] 7.3: Add `chat_task` to the shutdown cancellation list (around line 904):
    ```python
    chat_task.cancel()
    ```
    And add it to the await-cancellation loop (around line 911).

- [ ] Task 8: Tests (AC: all)
  - [ ] 8.1: Write Python unit tests in `tests/mc/test_chat_handler.py`:
    - Test `_process_chat_message` marks message as processing, calls agent, sends response, marks as done.
    - Test error handling: agent crash sends error response and marks original as done.
    - Test polling loop skips when no pending messages.
    Use `unittest.mock.AsyncMock` for bridge methods and `AgentLoop.process_direct`.
  - [ ] 8.2: Write Convex function tests or manual verification:
    - `chats:send` creates a document with correct fields.
    - `chats:listByAgent` returns only messages for the specified agent.
    - `chats:listPending` returns only pending messages.
    - `chats:updateStatus` updates the status field.

## Dev Notes

### Architecture & Design Decisions

**Polling vs Subscription**: The `ChatHandler` uses a polling approach (query every 2s) rather than a Convex subscription. This matches the existing pattern used by `async_subscribe()` in the bridge (which is itself a polling wrapper). The Convex Python SDK's blocking subscription iterator has thread-safety issues with asyncio (see `bridge.py` lines 649-705 comments). Polling at 2s intervals provides acceptable latency for chat interactions.

**Session Persistence**: Each agent's chat session uses the key `mc-chat:{agent_name}`. This means conversation history persists across multiple chat interactions with the same agent (the AgentLoop's SessionManager stores history). The user does NOT need to re-explain context across separate messages. This is intentional and different from task sessions (which are cleared after each task via `end_task_session`).

**No Task Creation**: Chat messages do NOT create tasks. They are a lightweight interaction channel that bypasses the task/step/plan workflow entirely. The `chats` table is independent of the `tasks` and `messages` tables.

**Agent Loading Pattern**: The ChatHandler loads agent configs using the same pattern as `executor.py:_load_agent_config()`. To avoid code duplication, consider extracting a shared utility. However, for this story, it is acceptable to duplicate the pattern (3 lines of code) to avoid coupling the chat handler to the executor module.

**Convex Index Strategy**: The `by_agentName` index on the `chats` table allows efficient queries for `listByAgent`. The `listPending` query scans all chats and filters by `status === "pending"` -- this is acceptable because pending messages are transient (they exist for 2-4 seconds before being processed). An index on `status` is not needed.

### Existing Code to Reuse

**bridge.py** (lines 80-95, 96-108):
- `query()` and `mutation()` methods with automatic snake_case/camelCase conversion
- The ChatHandler calls these through `asyncio.to_thread` for async compatibility

**executor.py** (lines 80-88, 91-165):
- `_make_provider()` — creates LLM provider from config
- `_run_agent_on_task()` — reference for AgentLoop instantiation (but ChatHandler uses `process_direct()` directly, not this function, because chat does not need task context, session clearing, or orientation injection)

**AgentLoop.process_direct()** (loop.py lines 482-496):
- The direct processing method used for CLI and cron
- ChatHandler calls this with `session_key=f"mc-chat:{agent_name}"`

**ActivityFeedPanel.tsx** (lines 1-48):
- Current panel structure with collapsed/expanded states
- The tabs will be added inside the expanded view

**ThreadInput.tsx** (lines 76-99):
- `handleSend` pattern with `isSubmitting` state, try/finally, and `setContent("")`
- Reuse for ChatPanel's send handler

### Common Mistakes to Avoid

1. **Do NOT use `end_task_session` for chat sessions** -- chat sessions persist across messages. The user expects continuity. Only task sessions are cleared after each execution.
2. **Do NOT create activity events for chat messages** -- chats are informal and should not pollute the Activity Feed. They live in their own tab.
3. **Do NOT import `nanobot.agent` package at module level in chat_handler.py** -- use lazy imports inside `_process_chat_message` to avoid heavy dependency loading at gateway startup. Follow the pattern in `gateway.py:sync_skills()` (lines 471-484) which uses `importlib.util`.
4. **Do NOT block the gateway's event loop** -- all bridge calls in ChatHandler MUST use `await asyncio.to_thread(...)`. The Convex Python SDK is synchronous.
5. **Do NOT forget to handle the camelCase/snake_case conversion** -- the bridge handles this automatically. When calling `self._bridge.mutation("chats:send", {...})`, use snake_case keys and the bridge converts them.

### Project Structure Notes

- **NEW**: `dashboard/convex/chats.ts` — Convex queries and mutations for the chats table
- **NEW**: `dashboard/components/ChatPanel.tsx` — Chat panel with agent selection and message input
- **NEW**: `dashboard/components/ChatMessages.tsx` — Message list with typing indicator
- **NEW**: `nanobot/mc/chat_handler.py` — Async chat message processing handler
- **NEW**: `tests/mc/test_chat_handler.py` — Unit tests for ChatHandler
- **MODIFIED**: `dashboard/convex/schema.ts` — Add `chats` table definition
- **MODIFIED**: `dashboard/components/ActivityFeedPanel.tsx` — Add tabs (Activity | Chats)
- **MODIFIED**: `nanobot/mc/bridge.py` — Add chat helper methods
- **MODIFIED**: `nanobot/mc/gateway.py` — Register ChatHandler as asyncio task

### Testing Standards

- **Python tests**: `uv run pytest tests/mc/test_chat_handler.py` — mock bridge and AgentLoop
- **TypeScript**: `npx tsc --noEmit` — no type errors in new/modified files
- **Manual E2E**: Send a chat message in the Chats tab -> see typing indicator -> receive agent response
- **Edge cases**: Switch agents mid-conversation, send multiple messages rapidly, agent crash recovery

### References

- [Source: dashboard/components/ActivityFeedPanel.tsx — Panel layout, lines 1-48]
- [Source: dashboard/components/ActivityFeed.tsx — Feed rendering pattern, lines 1-132]
- [Source: dashboard/convex/schema.ts — Existing table definitions, lines 1-229]
- [Source: nanobot/mc/bridge.py — query/mutation with conversion, lines 80-108]
- [Source: nanobot/mc/gateway.py — run_gateway() background task registration, lines 774-923]
- [Source: nanobot/mc/executor.py — _make_provider, _load_agent_config patterns, lines 80-88, 470-496]
- [Source: nanobot/agent/loop.py — process_direct() method, lines 482-496]
- [Source: nanobot/agent/loop.py — AgentLoop constructor parameters, lines 46-107]

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
