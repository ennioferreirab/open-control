# Epics 8-12 Wave Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement all 12 remaining stories across Epics 8-12, organized in 3 dependency-driven waves with parallel execution within each wave.

**Architecture:** Each story has a detailed spec in `_bmad-output/implementation-artifacts/`. This plan provides the execution order, TDD steps, and coordination rules. Stories within a wave run in parallel worktrees branching from the wave's base. Each wave merges to a wave branch before proceeding.

**Tech Stack:** Next.js + Convex (TypeScript, Vitest), Python (pytest, asyncio), shadcn/ui components

---

## Conventions

- **Story specs:** Each story's full spec lives at `_bmad-output/implementation-artifacts/{story-id}.md` — read it before starting the story
- **Test commands:** Python: `uv run pytest tests/mc/test_<name>.py -v` | Dashboard: `cd dashboard && npx vitest run tests/<path>`
- **Branch strategy:** Each story gets its own worktree branch `feat/{story-id}`. Waves merge to `wave-{n}` integration branch.
- **Schema coordination:** Stories 9-1, 9-3 (Wave 1) and 9-2, 10-2, 12-1 (Wave 2) all modify `schema.ts`. Merge schema changes carefully — each adds to different tables/fields.
- **Commit style:** `feat(story-id): description` for features, `test(story-id): description` for tests

---

## Wave 1 — Foundation + Quick Wins

**Base branch:** `main` (or current feature branch)
**Integration branch:** `wave-1`
**Stories:** 8-1, 8-2, 9-1, 9-3, 10-1, 11-1 (all independent, run in parallel)

---

### Task 1: Story 8-1 — Reduce TaskInput Layout Shift

**Spec:** `_bmad-output/implementation-artifacts/8-1-reduce-taskinput-layout-shift.md`

**Files:**
- Modify: `dashboard/components/TaskInput.tsx`
- Test: `dashboard/tests/components/TaskInput.layout.test.tsx` (new)

**Step 1: Read the spec and current TaskInput component**
Read: `_bmad-output/implementation-artifacts/8-1-reduce-taskinput-layout-shift.md`
Read: `dashboard/components/TaskInput.tsx`

**Step 2: Write the failing test**
Create test that checks for layout stability — supervision mode toggle should not cause reflow. Test that conditional elements use CSS visibility instead of conditional rendering.

Run: `cd dashboard && npx vitest run tests/components/TaskInput.layout.test.tsx`
Expected: FAIL

**Step 3: Implement the fix**
Replace conditional rendering (`{showField && <Field/>}`) with CSS visibility/hidden approach per spec. Ensure smooth transitions.

**Step 4: Run test to verify it passes**
Run: `cd dashboard && npx vitest run tests/components/TaskInput.layout.test.tsx`
Expected: PASS

**Step 5: Manual smoke test**
Run: `cd dashboard && npm run dev`
Toggle supervision modes — no layout shift visible.

**Step 6: Commit**
```bash
git add dashboard/components/TaskInput.tsx dashboard/tests/components/TaskInput.layout.test.tsx
git commit -m "feat(8-1): reduce TaskInput layout shift on mode toggle"
```

---

### Task 2: Story 8-2 — Cron Schedule Table

**Spec:** `_bmad-output/implementation-artifacts/8-2-cron-schedule-table.md`

**Files:**
- Create: `dashboard/lib/cron-parser.ts`
- Create: `dashboard/lib/cron-parser.test.ts`
- Modify: `dashboard/components/CronJobsModal.tsx`

**Step 1: Read the spec and current CronJobsModal**
Read: `_bmad-output/implementation-artifacts/8-2-cron-schedule-table.md`
Read: `dashboard/components/CronJobsModal.tsx`

**Step 2: Write the cron parser tests**
Create `dashboard/lib/cron-parser.test.ts` with tests for:
- Standard 5-field cron → human-readable text
- Edge cases (wildcards, ranges, lists)
- Unparseable expressions → graceful fallback

Run: `cd dashboard && npx vitest run lib/cron-parser.test.ts`
Expected: FAIL

**Step 3: Implement cron parser**
Create `dashboard/lib/cron-parser.ts` — parse 5-field cron to 3-column breakdown (Days/Hours/Minutes).

**Step 4: Run parser tests**
Run: `cd dashboard && npx vitest run lib/cron-parser.test.ts`
Expected: PASS

**Step 5: Update CronJobsModal to show parsed schedule**
Modify `dashboard/components/CronJobsModal.tsx` to display human-readable breakdown below raw cron expression.

**Step 6: Commit**
```bash
git add dashboard/lib/cron-parser.ts dashboard/lib/cron-parser.test.ts dashboard/components/CronJobsModal.tsx
git commit -m "feat(8-2): add human-readable cron schedule table"
```

---

### Task 3: Story 9-1 — Favorite Tasks

**Spec:** `_bmad-output/implementation-artifacts/9-1-favorite-tasks.md`

**Files:**
- Modify: `dashboard/convex/schema.ts` (add `isFavorite` to tasks)
- Modify: `dashboard/convex/tasks.ts` (add toggle mutation)
- Create: `dashboard/components/CompactFavoriteCard.tsx`
- Modify: `dashboard/components/TaskCard.tsx` (add star icon)
- Modify: `dashboard/components/KanbanBoard.tsx` (add Favorites section)
- Test: `dashboard/tests/components/CompactFavoriteCard.test.tsx` (new)

**Step 1: Read the spec**
Read: `_bmad-output/implementation-artifacts/9-1-favorite-tasks.md`

**Step 2: Add schema field**
Add `isFavorite: v.optional(v.boolean())` to tasks table in `schema.ts`.

**Step 3: Add Convex mutation**
Add `toggleFavorite` mutation in `dashboard/convex/tasks.ts`.

**Step 4: Write test for CompactFavoriteCard**
Create `dashboard/tests/components/CompactFavoriteCard.test.tsx`.

Run: `cd dashboard && npx vitest run tests/components/CompactFavoriteCard.test.tsx`
Expected: FAIL

**Step 5: Implement CompactFavoriteCard and star toggle on TaskCard**
Create `dashboard/components/CompactFavoriteCard.tsx`.
Modify `dashboard/components/TaskCard.tsx` — add star icon.

**Step 6: Add Favorites section to KanbanBoard**
Modify `dashboard/components/KanbanBoard.tsx` — fixed section above columns with horizontally scrollable favorite cards.

**Step 7: Run tests**
Run: `cd dashboard && npx vitest run tests/components/CompactFavoriteCard.test.tsx`
Expected: PASS

**Step 8: Commit**
```bash
git add dashboard/convex/schema.ts dashboard/convex/tasks.ts dashboard/components/CompactFavoriteCard.tsx dashboard/components/TaskCard.tsx dashboard/components/KanbanBoard.tsx dashboard/tests/components/CompactFavoriteCard.test.tsx
git commit -m "feat(9-1): add favorite tasks with star toggle and Kanban favorites section"
```

---

### Task 4: Story 9-3 — Edit Tags After Task Creation

**Spec:** `_bmad-output/implementation-artifacts/9-3-edit-tags-after-task-creation.md`

**Files:**
- Modify: `dashboard/convex/tasks.ts` (add updateTags mutation)
- Modify: `dashboard/components/TaskDetailSheet.tsx` (editable tag chips)
- Test: inline or `dashboard/tests/components/TaskDetailSheet.tags.test.tsx`

**Step 1: Read the spec**
Read: `_bmad-output/implementation-artifacts/9-3-edit-tags-after-task-creation.md`
Read: `dashboard/components/TaskDetailSheet.tsx`

**Step 2: Add Convex mutation for tag updates**
Add `updateTags` mutation to `dashboard/convex/tasks.ts`.

**Step 3: Write test for tag editing behavior**
Test: removable chips (X button), popover-based tag picker, already-assigned tags shown as disabled.

Run: `cd dashboard && npx vitest run tests/components/TaskDetailSheet.tags.test.tsx`
Expected: FAIL

**Step 4: Implement tag editing UI in TaskDetailSheet**
Modify `dashboard/components/TaskDetailSheet.tsx` — make tag chips removable, add popover for adding tags.

**Step 5: Run tests**
Run: `cd dashboard && npx vitest run tests/components/TaskDetailSheet.tags.test.tsx`
Expected: PASS

**Step 6: Commit**
```bash
git add dashboard/convex/tasks.ts dashboard/components/TaskDetailSheet.tsx dashboard/tests/components/TaskDetailSheet.tags.test.tsx
git commit -m "feat(9-3): enable tag editing after task creation"
```

---

### Task 5: Story 10-1 — @Mentions in Task Thread

**Spec:** `_bmad-output/implementation-artifacts/10-1-at-mentions-in-task-thread.md`

**Files:**
- Create: `dashboard/components/AgentMentionAutocomplete.tsx`
- Modify: `dashboard/components/ThreadInput.tsx`
- Test: `dashboard/tests/components/AgentMentionAutocomplete.test.tsx` (new)

**Step 1: Read the spec and current ThreadInput**
Read: `_bmad-output/implementation-artifacts/10-1-at-mentions-in-task-thread.md`
Read: `dashboard/components/ThreadInput.tsx`

**Step 2: Write tests for AgentMentionAutocomplete**
Test: portal-based dropdown on @trigger, case-insensitive filtering, keyboard navigation (up/down/enter/escape), drops to dropdown for submission.

Run: `cd dashboard && npx vitest run tests/components/AgentMentionAutocomplete.test.tsx`
Expected: FAIL

**Step 3: Implement AgentMentionAutocomplete**
Create `dashboard/components/AgentMentionAutocomplete.tsx` — portal-positioned dropdown, keyboard nav, agent list filtering.

**Step 4: Integrate into ThreadInput**
Modify `dashboard/components/ThreadInput.tsx` — detect @ character, show autocomplete, inject selected agent name. Not in plan-chat mode.

**Step 5: Run tests**
Run: `cd dashboard && npx vitest run tests/components/AgentMentionAutocomplete.test.tsx`
Expected: PASS

**Step 6: Commit**
```bash
git add dashboard/components/AgentMentionAutocomplete.tsx dashboard/components/ThreadInput.tsx dashboard/tests/components/AgentMentionAutocomplete.test.tsx
git commit -m "feat(10-1): add @mention autocomplete for agents in task thread"
```

---

### Task 6: Story 11-1 — Implement Model Tier System

**Spec:** `_bmad-output/implementation-artifacts/11-1-implement-model-tiers.md`

**Files:**
- Modify: `nanobot/mc/types.py` (add tier types)
- Create: `nanobot/mc/tier_resolver.py`
- Modify: `nanobot/mc/executor.py` (resolve tier at dispatch)
- Modify: `nanobot/mc/step_dispatcher.py` (pass resolved model)
- Modify: `nanobot/mc/gateway.py` (sync connected models on startup)
- Create: `dashboard/components/ModelTierSettings.tsx`
- Test: `tests/mc/test_tier_resolver.py` (new)

**Step 1: Read the spec**
Read: `_bmad-output/implementation-artifacts/11-1-implement-model-tiers.md`
Read: `nanobot/mc/types.py`

**Step 2: Write tier resolver tests**
Create `tests/mc/test_tier_resolver.py`:
- Test `tier:standard-high` resolution to actual model string
- Test fallback when tier not found
- Test 60s cache behavior
- Test null reasoning tier

Run: `uv run pytest tests/mc/test_tier_resolver.py -v`
Expected: FAIL

**Step 3: Add tier types to types.py**
Add `ModelTier`, `TierConfig` types to `nanobot/mc/types.py`.

**Step 4: Implement tier_resolver.py**
Create `nanobot/mc/tier_resolver.py` — settings-based tier storage, runtime resolution with 60s cache.

**Step 5: Run tier resolver tests**
Run: `uv run pytest tests/mc/test_tier_resolver.py -v`
Expected: PASS

**Step 6: Integrate tier resolution into executor and step_dispatcher**
Modify `nanobot/mc/executor.py` and `nanobot/mc/step_dispatcher.py` — resolve `tier:` prefixed model strings before dispatch.

**Step 7: Update gateway to sync connected models**
Modify `nanobot/mc/gateway.py` — on startup, populate tier config with connected provider models.

**Step 8: Build ModelTierSettings UI**
Create `dashboard/components/ModelTierSettings.tsx` — UI for configuring tier mappings.

**Step 9: Run all related tests**
Run: `uv run pytest tests/mc/test_tier_resolver.py tests/mc/test_step_dispatcher.py -v`
Expected: PASS

**Step 10: Commit**
```bash
git add nanobot/mc/types.py nanobot/mc/tier_resolver.py nanobot/mc/executor.py nanobot/mc/step_dispatcher.py nanobot/mc/gateway.py dashboard/components/ModelTierSettings.tsx tests/mc/test_tier_resolver.py
git commit -m "feat(11-1): implement model tier system with runtime resolution"
```

---

### Wave 1 Integration Checkpoint

**After all 6 stories are complete:**

1. Create `wave-1` integration branch from main
2. Merge each story branch in order: 8-1, 8-2, 9-1, 9-3, 10-1, 11-1
3. Resolve any schema.ts conflicts (9-1 and 9-3 both add to tasks table)
4. Run full test suite:
   ```bash
   uv run pytest tests/ -v
   cd dashboard && npx vitest run
   ```
5. Manual smoke test: create task, toggle modes (no shift), check cron display, favorite a task, edit tags, type @agent in thread, check model tier settings
6. Commit integration and tag: `wave-1-complete`

---

## Wave 2 — Unlocked Features

**Base branch:** `wave-1` integration branch
**Integration branch:** `wave-2`
**Stories:** 9-2, 10-2, 10-3, 11-2, 12-1 (all run in parallel — prerequisites from Wave 1 done)

---

### Task 7: Story 9-2 — Thread Comments Without Agent Trigger

**Spec:** `_bmad-output/implementation-artifacts/9-2-thread-comments-without-agent-trigger.md`

**Files:**
- Modify: `dashboard/convex/schema.ts` (add comment messageType)
- Modify: `dashboard/convex/messages.ts` (add sendComment mutation)
- Modify: `dashboard/lib/constants.ts` (add COMMENT type)
- Modify: `dashboard/components/ThreadInput.tsx` (toggle pill: Message Agent / Comment)
- Modify: `dashboard/components/ThreadMessage.tsx` (visual differentiation for comments)
- Modify: `nanobot/mc/thread_context.py` (format comments in context)
- Test: `dashboard/tests/components/ThreadInput.comment.test.tsx` (new)

**Step 1: Read the spec**
Read: `_bmad-output/implementation-artifacts/9-2-thread-comments-without-agent-trigger.md`

**Step 2: Write test for comment toggle behavior**
Test: toggle pill renders, comment mode doesn't trigger agent assignment, comment messages render with distinct styling.

Run: `cd dashboard && npx vitest run tests/components/ThreadInput.comment.test.tsx`
Expected: FAIL

**Step 3: Add comment type to schema and constants**
Modify `schema.ts` — add `"comment"` to messageType union.
Modify `constants.ts` — add COMMENT type.

**Step 4: Add sendComment mutation**
Modify `dashboard/convex/messages.ts`.

**Step 5: Implement comment toggle in ThreadInput**
Modify `ThreadInput.tsx` — add toggle pill between "Message Agent" and "Comment".

**Step 6: Style comments in ThreadMessage**
Modify `ThreadMessage.tsx` — visual differentiation for comment messages.

**Step 7: Update Python thread context**
Modify `nanobot/mc/thread_context.py` — format comments as `"{author} [Comment]: {content}"`.

**Step 8: Run tests**
Run: `cd dashboard && npx vitest run tests/components/ThreadInput.comment.test.tsx`
Run: `uv run pytest tests/mc/test_thread_context.py -v`
Expected: PASS

**Step 9: Commit**
```bash
git add dashboard/convex/schema.ts dashboard/convex/messages.ts dashboard/lib/constants.ts dashboard/components/ThreadInput.tsx dashboard/components/ThreadMessage.tsx nanobot/mc/thread_context.py dashboard/tests/components/ThreadInput.comment.test.tsx
git commit -m "feat(9-2): add thread comments without agent trigger"
```

---

### Task 8: Story 10-2 — Direct Chat with Agent

**Spec:** `_bmad-output/implementation-artifacts/10-2-direct-chat-with-agent.md`

**Files:**
- Modify: `dashboard/convex/schema.ts` (add chats table)
- Create: `dashboard/convex/chats.ts`
- Modify: `dashboard/components/ActivityFeedPanel.tsx` (add Chats tab)
- Create: `dashboard/components/ChatPanel.tsx`
- Create: `dashboard/components/ChatMessages.tsx`
- Create: `nanobot/mc/chat_handler.py`
- Modify: `nanobot/mc/gateway.py` (register chat handler)
- Modify: `nanobot/mc/bridge.py` (add chat mutations/queries)
- Test: `tests/mc/test_chat_handler.py` (new)
- Test: `dashboard/tests/components/ChatPanel.test.tsx` (new)

**Step 1: Read the spec**
Read: `_bmad-output/implementation-artifacts/10-2-direct-chat-with-agent.md`

**Step 2: Write Python chat handler tests**
Create `tests/mc/test_chat_handler.py`:
- Test polling for pending messages
- Test agent response via process_direct()
- Test typing indicator state transitions

Run: `uv run pytest tests/mc/test_chat_handler.py -v`
Expected: FAIL

**Step 3: Add chats table to schema**
Modify `schema.ts` — add `chats` table with status tracking, agentName, messages.

**Step 4: Create Convex chats module**
Create `dashboard/convex/chats.ts` — mutations for send/receive, queries for list/get.

**Step 5: Implement Python ChatHandler**
Create `nanobot/mc/chat_handler.py` — polls for pending messages, processes via agent, posts response.

**Step 6: Register chat handler in gateway and bridge**
Modify `gateway.py` — start chat handler alongside existing handlers.
Modify `bridge.py` — add chat-related mutations/queries.

**Step 7: Run Python tests**
Run: `uv run pytest tests/mc/test_chat_handler.py -v`
Expected: PASS

**Step 8: Write frontend tests**
Create `dashboard/tests/components/ChatPanel.test.tsx`.

Run: `cd dashboard && npx vitest run tests/components/ChatPanel.test.tsx`
Expected: FAIL

**Step 9: Build ChatPanel and ChatMessages components**
Create `dashboard/components/ChatPanel.tsx` and `ChatMessages.tsx`.
Reuse `AgentMentionAutocomplete` from Story 10-1.

**Step 10: Add Chats tab to ActivityFeedPanel**
Modify `dashboard/components/ActivityFeedPanel.tsx`.

**Step 11: Run frontend tests**
Run: `cd dashboard && npx vitest run tests/components/ChatPanel.test.tsx`
Expected: PASS

**Step 12: Commit**
```bash
git add dashboard/convex/schema.ts dashboard/convex/chats.ts dashboard/components/ActivityFeedPanel.tsx dashboard/components/ChatPanel.tsx dashboard/components/ChatMessages.tsx nanobot/mc/chat_handler.py nanobot/mc/gateway.py nanobot/mc/bridge.py tests/mc/test_chat_handler.py dashboard/tests/components/ChatPanel.test.tsx
git commit -m "feat(10-2): add direct chat with agent via Chats tab"
```

---

### Task 9: Story 10-3 — Agent-to-Agent Synchronous Conversation

**Spec:** `_bmad-output/implementation-artifacts/10-3-agent-to-agent-sync-conversation.md`

**Files:**
- Create: `nanobot/agent/tools/ask_agent.py`
- Modify: `nanobot/agent/loop.py` (register tool)
- Modify: `nanobot/mc/executor.py` (handle ask_agent calls)
- Test: `tests/mc/test_ask_agent.py` (new)

**Step 1: Read the spec**
Read: `_bmad-output/implementation-artifacts/10-3-agent-to-agent-sync-conversation.md`

**Step 2: Write ask_agent tests**
Create `tests/mc/test_ask_agent.py`:
- Test synchronous execution with timeout (120s)
- Test depth limit of 2 (prevent infinite recursion)
- Test lead-agent protection (can't be asked)
- Test thread logging via system_event

Run: `uv run pytest tests/mc/test_ask_agent.py -v`
Expected: FAIL

**Step 3: Implement ask_agent tool**
Create `nanobot/agent/tools/ask_agent.py` — sync call to another agent with timeout and depth limiting.

**Step 4: Register tool in agent loop**
Modify `nanobot/agent/loop.py` — add ask_agent to available tools.

**Step 5: Handle ask_agent in executor**
Modify `nanobot/mc/executor.py` — process ask_agent tool calls, manage subprocess lifecycle.

**Step 6: Run tests**
Run: `uv run pytest tests/mc/test_ask_agent.py -v`
Expected: PASS

**Step 7: Commit**
```bash
git add nanobot/agent/tools/ask_agent.py nanobot/agent/loop.py nanobot/mc/executor.py tests/mc/test_ask_agent.py
git commit -m "feat(10-3): add agent-to-agent synchronous conversation tool"
```

---

### Task 10: Story 11-2 — Model Override Per Agent

**Spec:** `_bmad-output/implementation-artifacts/11-2-model-override-per-agent.md`

**Files:**
- Modify: `dashboard/components/AgentConfigSheet.tsx`
- Test: `dashboard/tests/components/AgentConfigSheet.model.test.tsx` (new or extend existing)

**Step 1: Read the spec and current AgentConfigSheet**
Read: `_bmad-output/implementation-artifacts/11-2-model-override-per-agent.md`
Read: `dashboard/components/AgentConfigSheet.tsx`

**Step 2: Write test for model override UI**
Test: two-level dropdown (tier selector + custom model picker), visual badge showing tier vs custom vs default.

Run: `cd dashboard && npx vitest run tests/components/AgentConfigSheet.model.test.tsx`
Expected: FAIL

**Step 3: Implement model override dropdown**
Modify `AgentConfigSheet.tsx` — add tier/custom model selection with visual badge.

**Step 4: Run tests**
Run: `cd dashboard && npx vitest run tests/components/AgentConfigSheet.model.test.tsx`
Expected: PASS

**Step 5: Commit**
```bash
git add dashboard/components/AgentConfigSheet.tsx dashboard/tests/components/AgentConfigSheet.model.test.tsx
git commit -m "feat(11-2): add per-agent model override with tier/custom selection"
```

---

### Task 11: Story 12-1 — Board Agent Memory Mode

**Spec:** `_bmad-output/implementation-artifacts/12-1-board-agent-memory-mode.md`

**Files:**
- Modify: `dashboard/convex/schema.ts` (add agentMemoryModes to boards)
- Modify: `dashboard/convex/boards.ts` (add updateMemoryMode mutation)
- Modify: `dashboard/components/BoardSettingsSheet.tsx` (toggle per agent)
- Create: `nanobot/mc/board_utils.py` (workspace resolution, symlink management)
- Modify: `nanobot/mc/executor.py` (use board_utils for workspace)
- Modify: `nanobot/mc/step_dispatcher.py` (pass memory mode)
- Test: `tests/mc/test_board_utils.py` (new)

**Step 1: Read the spec**
Read: `_bmad-output/implementation-artifacts/12-1-board-agent-memory-mode.md`

**Step 2: Write board_utils tests**
Create `tests/mc/test_board_utils.py`:
- Test symlink creation for with_history mode
- Test isolated workspace for clean mode
- Test symlink-to-file transition handling

Run: `uv run pytest tests/mc/test_board_utils.py -v`
Expected: FAIL

**Step 3: Implement board_utils.py**
Create `nanobot/mc/board_utils.py` — workspace resolution logic, symlink management.

**Step 4: Run tests**
Run: `uv run pytest tests/mc/test_board_utils.py -v`
Expected: PASS

**Step 5: Add schema and mutation**
Modify `schema.ts` — add `agentMemoryModes` array to boards.
Modify `boards.ts` — add `updateMemoryMode` mutation.

**Step 6: Build toggle UI**
Modify `BoardSettingsSheet.tsx` — per-agent memory mode toggle.

**Step 7: Integrate into executor and step_dispatcher**
Modify `executor.py` and `step_dispatcher.py` — resolve workspace using board_utils.

**Step 8: Run all tests**
Run: `uv run pytest tests/mc/test_board_utils.py tests/mc/test_step_dispatcher.py -v`
Expected: PASS

**Step 9: Commit**
```bash
git add dashboard/convex/schema.ts dashboard/convex/boards.ts dashboard/components/BoardSettingsSheet.tsx nanobot/mc/board_utils.py nanobot/mc/executor.py nanobot/mc/step_dispatcher.py tests/mc/test_board_utils.py
git commit -m "feat(12-1): add board agent memory mode with symlink management"
```

---

### Wave 2 Integration Checkpoint

**After all 5 stories are complete:**

1. Create `wave-2` integration branch from `wave-1`
2. Merge story branches. **Merge order matters for conflict resolution:**
   - First: 11-2 (small, FE only)
   - Second: 9-2 (touches schema + ThreadInput)
   - Third: 10-3 (backend only, no FE conflicts)
   - Fourth: 12-1 (touches schema + executor)
   - Last: 10-2 (largest, touches schema + gateway + bridge — most likely to conflict)
3. Resolve schema.ts conflicts: 9-2 adds to messages, 10-2 adds chats table, 12-1 adds to boards
4. Resolve executor.py conflicts: 10-3 adds ask_agent handling, 12-1 adds board_utils integration
5. Run full test suite:
   ```bash
   uv run pytest tests/ -v
   cd dashboard && npx vitest run
   ```
6. Manual smoke test: post comment (no agent trigger), open Chats tab and talk to agent, check agent-to-agent in logs, change model on agent config, toggle memory mode in board settings
7. Tag: `wave-2-complete`

---

## Wave 3 — Tags CRM

**Base branch:** `wave-2` integration branch
**Integration branch:** `wave-3` (final)
**Stories:** 12-2 (single story, dedicated wave)

---

### Task 12: Story 12-2 — Tags with Custom Attributes (Lightweight CRM)

**Spec:** `_bmad-output/implementation-artifacts/12-2-tags-with-custom-attributes.md`

**Files:**
- Modify: `dashboard/convex/schema.ts` (add tagAttributes, tagAttributeValues tables)
- Create: `dashboard/convex/tagAttributes.ts`
- Create: `dashboard/convex/tagAttributeValues.ts`
- Modify: `dashboard/components/TagsPanel.tsx` (attribute management)
- Modify: `dashboard/components/TaskDetailSheet.tsx` (inline attribute editors)
- Create: `dashboard/components/TagAttributeEditor.tsx`
- Modify: `nanobot/mc/executor.py` (inject tag attributes into thread context)
- Test: `dashboard/tests/components/TagAttributeEditor.test.tsx` (new)
- Test: `tests/mc/test_tag_attributes.py` (new, for context injection)

**Step 1: Read the spec**
Read: `_bmad-output/implementation-artifacts/12-2-tags-with-custom-attributes.md`
Read: `dashboard/components/TagsPanel.tsx`

**Step 2: Write Python tests for tag attribute context injection**
Create `tests/mc/test_tag_attributes.py`:
- Test tag attributes formatted in thread context
- Test multiple attributes per tag

Run: `uv run pytest tests/mc/test_tag_attributes.py -v`
Expected: FAIL

**Step 3: Add schema tables**
Modify `schema.ts` — add `tagAttributes` (shared catalog: name, type, options) and `tagAttributeValues` (per-tag values).

**Step 4: Create Convex modules**
Create `dashboard/convex/tagAttributes.ts` — CRUD for attribute definitions.
Create `dashboard/convex/tagAttributeValues.ts` — upsert/cascade for values.

**Step 5: Write frontend tests for TagAttributeEditor**
Create `dashboard/tests/components/TagAttributeEditor.test.tsx`:
- Test type-aware inline editors (text input, number input, date picker, select dropdown)
- Test upsert behavior

Run: `cd dashboard && npx vitest run tests/components/TagAttributeEditor.test.tsx`
Expected: FAIL

**Step 6: Implement TagAttributeEditor**
Create `dashboard/components/TagAttributeEditor.tsx` — type-aware inline editors.

**Step 7: Integrate into TagsPanel**
Modify `TagsPanel.tsx` — add attribute management to tag catalog.

**Step 8: Integrate into TaskDetailSheet**
Modify `TaskDetailSheet.tsx` — show tag attributes inline, editable.

**Step 9: Run frontend tests**
Run: `cd dashboard && npx vitest run tests/components/TagAttributeEditor.test.tsx`
Expected: PASS

**Step 10: Implement Python context injection**
Modify `nanobot/mc/executor.py` — inject tag attributes into thread context when building agent prompt.

**Step 11: Run Python tests**
Run: `uv run pytest tests/mc/test_tag_attributes.py -v`
Expected: PASS

**Step 12: Run full test suite**
Run: `uv run pytest tests/ -v && cd dashboard && npx vitest run`
Expected: ALL PASS

**Step 13: Commit**
```bash
git add dashboard/convex/schema.ts dashboard/convex/tagAttributes.ts dashboard/convex/tagAttributeValues.ts dashboard/components/TagsPanel.tsx dashboard/components/TaskDetailSheet.tsx dashboard/components/TagAttributeEditor.tsx nanobot/mc/executor.py tests/mc/test_tag_attributes.py dashboard/tests/components/TagAttributeEditor.test.tsx
git commit -m "feat(12-2): add tags with custom attributes as lightweight CRM"
```

---

### Wave 3 Integration Checkpoint

1. Merge 12-2 branch to `wave-3`
2. Run full test suite:
   ```bash
   uv run pytest tests/ -v
   cd dashboard && npx vitest run
   ```
3. Manual smoke test: create tag attribute (text, number, date, select), assign values per tag, check attributes visible in task detail, verify agents see tag context
4. Tag: `wave-3-complete`

---

## Final Checklist

- [ ] All 12 stories implemented and tested
- [ ] Epics 8-12 marked as `done` in sprint-status.yaml
- [ ] Full test suite passes (Python + Dashboard)
- [ ] No schema.ts conflicts remaining
- [ ] Manual walkthrough of all 4 user journeys from PRD still works
- [ ] Update sprint-status.yaml with final statuses
