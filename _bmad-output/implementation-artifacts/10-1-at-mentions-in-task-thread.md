# Story 10.1: @Mentions in Task Thread

Status: ready-for-dev

## Story

As a **user**,
I want to type @agentname in a task thread to activate a specific agent on that task,
so that I can direct questions to the right agent without using the dropdown selector.

## Acceptance Criteria

### AC1: @-Trigger Detection

**Given** the ThreadInput textarea is focused and the user types `@`
**When** the `@` character is entered at any position in the text
**Then** an autocomplete portal appears above or below the cursor position
**And** the autocomplete shows a filtered list of agents eligible for the task's board
**And** the list updates as the user types additional characters after `@` (e.g., `@sec` filters to agents whose name or displayName starts with "sec")

### AC2: Agent Filtering Logic

**Given** the autocomplete portal is visible
**When** the user types characters after `@`
**Then** agents are filtered case-insensitively by both `name` and `displayName`
**And** only agents enabled for the task's board are shown (same filtering as the existing agent selector: `board.enabledAgents`, empty = all; system agents always included)
**And** disabled agents (`enabled === false`) are excluded
**And** if no agents match the filter, the portal displays "No matching agents"

### AC3: Agent Selection via Click or Enter

**Given** the autocomplete portal is visible with at least one matching agent
**When** the user clicks on an agent entry or presses Enter/Tab with an agent highlighted
**Then** the `@partial` text in the textarea is replaced with `@agentname` (the agent's `name` field, not displayName)
**And** the `selectedAgent` state in ThreadInput is updated to that agent's name
**And** the autocomplete portal closes
**And** the cursor is positioned after the inserted `@agentname` with a trailing space

### AC4: Agent Selection via Keyboard Navigation

**Given** the autocomplete portal is visible
**When** the user presses ArrowDown/ArrowUp
**Then** the highlighted agent in the list cycles through available options
**And** pressing Escape closes the portal without selecting
**And** pressing Backspace past the `@` character closes the portal

### AC5: Submission with @Mention

**Given** the user has typed `@agentname` in the message (via autocomplete or manually)
**When** the user submits the message (Enter or Send button)
**Then** the message is sent via `sendThreadMessage` with `agentName` set to the mentioned agent
**And** the `@agentname` text remains in the message content (visible in the thread)
**And** the task is assigned to the mentioned agent (same behavior as selecting from the dropdown)

### AC6: Dropdown Sync

**Given** the user selects an agent via `@` autocomplete
**When** the agent is inserted
**Then** the Select dropdown value updates to show the selected agent
**And** if the user subsequently changes the dropdown, the dropdown selection takes precedence for submission
**And** if the user types a new `@agentname` after changing the dropdown, the new mention overrides the dropdown

### AC7: Plan-Chat Mode Exclusion

**Given** the task is in plan-chat mode (`in_progress` or `review` + `awaitingKickoff`)
**When** the user types `@` in the plan-chat textarea
**Then** the autocomplete does NOT appear (plan-chat is always addressed to the Lead Agent)

## Tasks / Subtasks

- [ ] Task 1: Create AgentMentionAutocomplete component (AC: 1, 2, 3, 4)
  - [ ] 1.1: Create `dashboard/components/AgentMentionAutocomplete.tsx` as a portal component. Accept props: `agents: Agent[]` (pre-filtered list), `query: string` (text after `@`), `onSelect: (agentName: string) => void`, `onClose: () => void`, `anchorRef: React.RefObject<HTMLTextAreaElement>` (for positioning). Use `createPortal` to render into `document.body` so it floats above other UI.
  - [ ] 1.2: Implement filtering logic inside the component: `agents.filter(a => a.name.toLowerCase().startsWith(query.toLowerCase()) || (a.displayName || a.name).toLowerCase().startsWith(query.toLowerCase()))`. Show "No matching agents" when the filtered list is empty.
  - [ ] 1.3: Render each agent as a list item showing `displayName || name` (primary) and `role` (secondary, muted text). Highlight the currently focused item with `bg-accent`. Style the container: `absolute`, `bg-popover`, `border`, `rounded-md`, `shadow-md`, `max-h-[200px]`, `overflow-y-auto`, `z-50`, `w-[240px]`.
  - [ ] 1.4: Implement keyboard navigation: track `focusedIndex` state (default 0). ArrowDown increments (wraps), ArrowUp decrements (wraps), Enter/Tab calls `onSelect(filteredAgents[focusedIndex].name)`, Escape calls `onClose()`. Reset `focusedIndex` to 0 when the filter query changes.
  - [ ] 1.5: Position the portal relative to the textarea caret. Use `anchorRef.current.getBoundingClientRect()` for the textarea position. Place the dropdown above the textarea (bottom aligned to textarea top) to avoid overlap with the input area. If near the top of the viewport, flip to below.

- [ ] Task 2: Integrate autocomplete into ThreadInput (AC: 1, 5, 6, 7)
  - [ ] 2.1: In `ThreadInput.tsx`, add state: `const [mentionQuery, setMentionQuery] = useState<string | null>(null)` (null = portal hidden, string = active query). Add `const textareaRef = useRef<HTMLTextAreaElement>(null)` and `const [mentionStartIndex, setMentionStartIndex] = useState<number>(0)`.
  - [ ] 2.2: In the `onChange` handler for the textarea, detect `@` trigger: when the user types `@`, check the character before it (must be start of input or whitespace). If triggered, set `mentionStartIndex` to the position of `@` and `mentionQuery` to `""`. As the user types more characters, update `mentionQuery` to the substring from `mentionStartIndex + 1` to the cursor position. If the user deletes back past `@`, set `mentionQuery` to null.
  - [ ] 2.3: Add `onSelect` callback: when an agent is selected from autocomplete, replace the text from `mentionStartIndex` to the current cursor position with `@{agentName} ` (trailing space). Update `selectedAgent` to the selected agent name. Set `mentionQuery` to null. Focus the textarea.
  - [ ] 2.4: Conditionally render `<AgentMentionAutocomplete>` only when `mentionQuery !== null` AND `!isPlanChatMode`. Pass `filteredAgents` (same filtered list used for the Select dropdown), `query={mentionQuery}`, `onSelect`, `onClose={() => setMentionQuery(null)}`, `anchorRef={textareaRef}`.
  - [ ] 2.5: In `handleKeyDown`, intercept ArrowDown, ArrowUp, Enter, Tab, and Escape when `mentionQuery !== null`. Forward these events to the autocomplete (prevent default textarea behavior). When `mentionQuery !== null` and Enter is pressed, it should select the agent rather than submit the message.
  - [ ] 2.6: In `handleSend`, parse the content for `@agentname` pattern before submission. Use regex `/@(\w[\w-]*)(?:\s|$)/` to extract the last mentioned agent name. If found AND `selectedAgent` matches (or selectedAgent was set by autocomplete), use that agent. This ensures manually typed `@agentname` also works if the agent exists.

- [ ] Task 3: Keyboard event coordination (AC: 4, 5)
  - [ ] 3.1: When autocomplete is open (`mentionQuery !== null`), the `handleKeyDown` in ThreadInput must call `e.preventDefault()` and `e.stopPropagation()` for ArrowDown, ArrowUp, Enter, Tab, and Escape to prevent the textarea from handling these keys. Pass a ref or callback to the autocomplete component so ThreadInput can invoke navigation methods.
  - [ ] 3.2: When autocomplete is closed (`mentionQuery === null`), restore normal behavior: Enter submits the message, ArrowDown/Up move the cursor in the textarea.

- [ ] Task 4: Visual styling and polish (AC: 1, 3)
  - [ ] 4.1: Ensure the autocomplete portal uses the same design tokens as the ShadCN Select/Popover components: `bg-popover`, `text-popover-foreground`, `border-border`. Add `animate-in fade-in-0 zoom-in-95` for smooth entry animation (matches ShadCN dropdown pattern).
  - [ ] 4.2: Add a subtle `@` badge or icon next to the selected agent in the dropdown after mention-based selection, to indicate the agent was chosen via mention rather than dropdown.
  - [ ] 4.3: Ensure the `ref` prop is passed through to the underlying `<textarea>` element in the ShadCN `Textarea` component. The ShadCN Textarea uses `React.forwardRef`, so pass `ref={textareaRef}` directly.

- [ ] Task 5: Edge cases and validation (AC: all)
  - [ ] 5.1: Handle multiple `@` in the same message: only the LAST `@` triggers autocomplete. Earlier `@agentname` tokens remain in text as-is. On submit, use the last mentioned agent for `selectedAgent`.
  - [ ] 5.2: Handle `@` followed by no valid characters (e.g., `@!` or `@ `): close the autocomplete immediately.
  - [ ] 5.3: If the user manually types `@agentname` without using autocomplete, and the agent name matches an existing agent, still set `selectedAgent` on submit (regex parsing in `handleSend`).
  - [ ] 5.4: If autocomplete is open and the textarea loses focus (blur), close the autocomplete after a short delay (150ms, to allow click events on the portal to fire first).

## Dev Notes

### Architecture & Design Decisions

**Portal-Based Autocomplete**: The autocomplete must use `createPortal` to render outside the ThreadInput component tree. This prevents the autocomplete from being clipped by `overflow-hidden` on parent containers (the ThreadInput sits inside a `border-t` div at the bottom of the TaskDetailSheet). The portal renders into `document.body` and positions itself using `getBoundingClientRect()` from the textarea ref.

**No Backend Changes**: This story is entirely frontend. The existing `sendThreadMessage` mutation already accepts `agentName` as a parameter (see `dashboard/convex/messages.ts`). The `ThreadInput.tsx` already has `selectedAgent` state and passes it to `sendMessage({ taskId, content, agentName: selectedAgent })`. The `@` mention simply provides an alternative way to set `selectedAgent`.

**Textarea Ref Access**: The ShadCN `Textarea` component (from `@/components/ui/textarea`) uses `React.forwardRef` and renders a native `<textarea>`. Passing `ref={textareaRef}` gives direct access to the DOM element for caret position detection and `getBoundingClientRect()`.

**Caret Position Detection**: To find where the user is typing `@`, use `textarea.selectionStart` (cursor position in the text). When `@` is detected at `selectionStart - 1`, record `mentionStartIndex = selectionStart - 1`. The query is `content.slice(mentionStartIndex + 1, selectionStart)`.

**Event Interception**: When the autocomplete is open, ThreadInput's `handleKeyDown` must intercept navigation keys BEFORE they reach the textarea. The pattern: check `mentionQuery !== null` at the top of `handleKeyDown`, and for ArrowUp/Down/Enter/Tab/Escape, call `e.preventDefault()` and handle them (forwarding to autocomplete state). This is the same pattern used by rich text editors and autocomplete libraries.

### Existing Code to Reuse

**ThreadInput.tsx** (lines 28-227):
- `selectedAgent` state (line 33) — the `@` mention updates this same state
- `filteredAgents` (lines 68-74) — reuse for autocomplete filtering
- `agents` query (line 40) — `useQuery(api.agents.list)` already loaded
- `board` query (lines 41-44) — board-based filtering already computed
- `handleSend` (lines 76-99) — submission already uses `selectedAgent`
- `handleKeyDown` (lines 102-107) — extend with autocomplete interception

**ShadCN Select/Popover Styling**:
- `bg-popover`, `text-popover-foreground`, `border` — popover background/text
- `rounded-md`, `shadow-md` — standard dropdown styling
- `data-[state=open]:animate-in`, `data-[state=open]:fade-in-0` — entry animation

### Common Mistakes to Avoid

1. **Do NOT modify the Convex backend** — no new mutations, schema changes, or backend logic needed.
2. **Do NOT replace the existing Select dropdown** — the `@` mention is an ADDITION to the existing agent selector, not a replacement. Both mechanisms coexist.
3. **Do NOT use `contentEditable` divs** — keep the native `<textarea>` element. Caret position is available via `selectionStart`.
4. **Do NOT assume displayName equals name** — agents have both `name` (unique identifier, used in `sendThreadMessage`) and `displayName` (human-readable). The autocomplete shows `displayName` but inserts `@{name}`.
5. **Do NOT trigger autocomplete in plan-chat mode** — the plan-chat textarea (lines 155-184 in ThreadInput.tsx) is always addressed to the Lead Agent.

### Project Structure Notes

- **NEW**: `dashboard/components/AgentMentionAutocomplete.tsx` — Portal-based autocomplete dropdown
- **MODIFIED**: `dashboard/components/ThreadInput.tsx` — Add mention detection, ref, autocomplete integration
- **No backend changes**
- **No new dependencies** — uses React.createPortal (built-in), existing ShadCN tokens

### References

- [Source: dashboard/components/ThreadInput.tsx — Full component, lines 1-227]
- [Source: dashboard/convex/messages.ts — sendThreadMessage mutation accepts agentName parameter]
- [Source: dashboard/convex/agents.ts — list query returns all non-deleted agents]
- [Source: dashboard/convex/schema.ts — agents table schema with name, displayName, role]
- [Source: dashboard/components/ActivityFeedPanel.tsx — Panel layout reference]

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
