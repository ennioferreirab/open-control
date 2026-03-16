# Thread Journal And Rolling Compaction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a task-scoped Markdown thread journal plus mandatory rolling thread compaction that keeps agent context bounded while preserving complete history in a local file.

**Architecture:** Convex remains the canonical thread source. The runtime writes a derived `THREAD_JOURNAL.md` and `THREAD_COMPACTION_STATE.json` under each task output directory, then enriches task, step, and conversation prompts with a rolling compacted summary, a 15-message live window, and the absolute journal path. Compaction runs in background, but if the LLM compaction fails the task is crashed immediately.

**Tech Stack:** Python, Convex bridge, asyncio background tasks, Markdown/JSON file persistence, pytest

---

### Task 0: Create Or Confirm The Story Artifact

**Files:**
- Create or confirm: `_bmad-output/implementation-artifacts/<story-file>.md`
- Reference: `AGENTS.md`

**Step 1: Check whether an implementation-ready story already exists**

Run: `cd /Users/ennio/Documents/nanobot-ennio/.worktrees/thread-journal-design && rg --files _bmad-output/implementation-artifacts`
Expected: either an existing story for thread journaling/compaction or an empty/missing result.

**Step 2: Create the story artifact if it does not exist**

Use the repository's `/create-story` workflow and capture acceptance criteria for:
- task journal file creation
- rolling compaction thresholds
- prompt injection
- crash-on-compaction-failure behavior

**Step 3: Re-read the story before coding**

Expected: the story explicitly names the user-visible outcomes, failure policy, and required tests.

### Task 1: Add Canonical Task Journal Path And Local Store Coverage

**Files:**
- Modify: `mc/application/execution/file_enricher.py`
- Create: `mc/infrastructure/thread_journal_store.py`
- Test: `tests/mc/application/execution/test_file_enricher.py`
- Test: `tests/mc/infrastructure/test_thread_journal_store.py`

**Step 1: Write the failing tests**

Add tests that assert:
- the task output directory can derive `THREAD_JOURNAL.md` and `THREAD_COMPACTION_STATE.json`
- the new store writes and reloads both files atomically
- the journal store can append event sections without corrupting the header/state sections

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ennio/Documents/nanobot-ennio/.worktrees/thread-journal-design && uv run pytest tests/mc/application/execution/test_file_enricher.py tests/mc/infrastructure/test_thread_journal_store.py -q`
Expected: FAIL because the path helpers and store module do not exist yet.

**Step 3: Write the minimal implementation**

Implement:
- path helpers in `mc/application/execution/file_enricher.py`
- a local store in `mc/infrastructure/thread_journal_store.py` with read/write helpers for Markdown and JSON state

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ennio/Documents/nanobot-ennio/.worktrees/thread-journal-design && uv run pytest tests/mc/application/execution/test_file_enricher.py tests/mc/infrastructure/test_thread_journal_store.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add mc/application/execution/file_enricher.py mc/infrastructure/thread_journal_store.py tests/mc/application/execution/test_file_enricher.py tests/mc/infrastructure/test_thread_journal_store.py
git commit -m "feat: add task thread journal storage primitives"
```

### Task 2: Build Journal Sync And Rolling Compaction State

**Files:**
- Create: `mc/application/execution/thread_journal_service.py`
- Test: `tests/mc/application/execution/test_thread_journal_service.py`

**Step 1: Write the failing tests**

Add tests that lock:
- journal reconciliation from full Convex message lists
- append-only event rendering for user, plan, step-completion, and system messages
- rolling compaction reusing the previous `compacted_summary`
- structured events being preserved semantically in the summary input
- recent window preservation at 15 messages

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ennio/Documents/nanobot-ennio/.worktrees/thread-journal-design && uv run pytest tests/mc/application/execution/test_thread_journal_service.py -q`
Expected: FAIL because the service does not exist and the compaction algorithm is not implemented.

**Step 3: Write the minimal implementation**

Implement a service that:
- syncs unseen thread messages into `THREAD_JOURNAL.md`
- persists rolling state in `THREAD_COMPACTION_STATE.json`
- determines when thresholds are crossed
- recomputes `compacted_summary` from `previous summary + eligible batch`

Do not add any fallback summarizer.

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ennio/Documents/nanobot-ennio/.worktrees/thread-journal-design && uv run pytest tests/mc/application/execution/test_thread_journal_service.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add mc/application/execution/thread_journal_service.py tests/mc/application/execution/test_thread_journal_service.py
git commit -m "feat: add rolling thread journal service"
```

### Task 3: Inject Journal-Aware Context Into Task, Step, And Conversation Prompts

**Files:**
- Modify: `mc/application/execution/request.py`
- Modify: `mc/application/execution/thread_context.py`
- Modify: `mc/application/execution/context_builder.py`
- Modify: `mc/contexts/conversation/service.py`
- Modify: `mc/contexts/conversation/mentions/handler.py`
- Test: `tests/mc/test_thread_context.py`
- Test: `tests/mc/application/execution/test_context_builder.py`
- Test: `tests/mc/services/test_conversation.py`
- Test: `tests/mc/test_mention_handler_context.py`

**Step 1: Write the failing tests**

Add assertions that:
- execution requests carry `thread_journal_path`
- thread context rendering emits `[Compacted Thread Summary]`, `[Recent Thread Window]`, and `[Thread Journal]`
- task, step, conversation, and mention paths all use the same enriched thread context format

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ennio/Documents/nanobot-ennio/.worktrees/thread-journal-design && uv run pytest tests/mc/test_thread_context.py tests/mc/application/execution/test_context_builder.py tests/mc/services/test_conversation.py tests/mc/test_mention_handler_context.py -q`
Expected: FAIL because the request model and builders still emit the legacy 20-message-only format.

**Step 3: Write the minimal implementation**

Update the shared thread-context path so it:
- resolves the journal path from the task id
- requests the latest compacted state from `ThreadJournalService`
- renders the rolling summary and recent window
- tells the agent that full history is available at the absolute journal path

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ennio/Documents/nanobot-ennio/.worktrees/thread-journal-design && uv run pytest tests/mc/test_thread_context.py tests/mc/application/execution/test_context_builder.py tests/mc/services/test_conversation.py tests/mc/test_mention_handler_context.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add mc/application/execution/request.py mc/application/execution/thread_context.py mc/application/execution/context_builder.py mc/contexts/conversation/service.py mc/contexts/conversation/mentions/handler.py tests/mc/test_thread_context.py tests/mc/application/execution/test_context_builder.py tests/mc/services/test_conversation.py tests/mc/test_mention_handler_context.py
git commit -m "feat: inject journal-aware thread context"
```

### Task 4: Schedule Background Compaction And Crash Tasks On Failure

**Files:**
- Modify: `mc/application/execution/background_tasks.py`
- Modify: `mc/application/execution/thread_journal_service.py`
- Modify: `mc/application/execution/context_builder.py`
- Test: `tests/mc/application/execution/test_thread_journal_service.py`
- Test: `tests/mc/application/execution/test_context_builder.py`

**Step 1: Write the failing tests**

Add tests that assert:
- threshold crossings schedule at most one background compaction per task
- a compaction failure logs the error and updates the task status to `crashed`
- the service does not mutate raw thread messages during compaction

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ennio/Documents/nanobot-ennio/.worktrees/thread-journal-design && uv run pytest tests/mc/application/execution/test_thread_journal_service.py tests/mc/application/execution/test_context_builder.py -q`
Expected: FAIL because there is no deduplicated background compaction scheduler or crash-on-failure behavior.

**Step 3: Write the minimal implementation**

Implement background-task deduplication by task id and wire the service so compaction failures:
- log with task id and journal path
- optionally write a thread/system event
- call the bridge to transition the task to `crashed`

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ennio/Documents/nanobot-ennio/.worktrees/thread-journal-design && uv run pytest tests/mc/application/execution/test_thread_journal_service.py tests/mc/application/execution/test_context_builder.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add mc/application/execution/background_tasks.py mc/application/execution/thread_journal_service.py mc/application/execution/context_builder.py tests/mc/application/execution/test_thread_journal_service.py tests/mc/application/execution/test_context_builder.py
git commit -m "feat: enforce background thread compaction"
```

### Task 5: Run Verification Gates And Document Runtime Settings

**Files:**
- Modify: `docs/plans/2026-03-16-thread-journal-and-rolling-compaction-design.md`
- Modify: `docs/plans/2026-03-16-thread-journal-and-rolling-compaction-implementation-plan.md`

**Step 1: Run focused Python verification**

Run: `cd /Users/ennio/Documents/nanobot-ennio/.worktrees/thread-journal-design && uv run ruff format --check mc/application/execution/file_enricher.py mc/application/execution/request.py mc/application/execution/thread_context.py mc/application/execution/context_builder.py mc/application/execution/thread_journal_service.py mc/infrastructure/thread_journal_store.py mc/contexts/conversation/service.py mc/contexts/conversation/mentions/handler.py tests/mc/application/execution/test_file_enricher.py tests/mc/infrastructure/test_thread_journal_store.py tests/mc/application/execution/test_thread_journal_service.py tests/mc/test_thread_context.py tests/mc/application/execution/test_context_builder.py tests/mc/services/test_conversation.py tests/mc/test_mention_handler_context.py`

**Step 2: Run lint and guardrails**

Run: `cd /Users/ennio/Documents/nanobot-ennio/.worktrees/thread-journal-design && uv run ruff check mc/application/execution/file_enricher.py mc/application/execution/request.py mc/application/execution/thread_context.py mc/application/execution/context_builder.py mc/application/execution/thread_journal_service.py mc/infrastructure/thread_journal_store.py mc/contexts/conversation/service.py mc/contexts/conversation/mentions/handler.py tests/mc/application/execution/test_file_enricher.py tests/mc/infrastructure/test_thread_journal_store.py tests/mc/application/execution/test_thread_journal_service.py tests/mc/test_thread_context.py tests/mc/application/execution/test_context_builder.py tests/mc/services/test_conversation.py tests/mc/test_mention_handler_context.py && uv run pytest tests/mc/test_architecture.py tests/mc/test_module_reorganization.py tests/mc/infrastructure/test_boundary.py -q`
Expected: PASS

**Step 3: Run the focused feature test suite**

Run: `cd /Users/ennio/Documents/nanobot-ennio/.worktrees/thread-journal-design && uv run pytest tests/mc/application/execution/test_file_enricher.py tests/mc/infrastructure/test_thread_journal_store.py tests/mc/application/execution/test_thread_journal_service.py tests/mc/test_thread_context.py tests/mc/application/execution/test_context_builder.py tests/mc/services/test_conversation.py tests/mc/test_mention_handler_context.py -q`
Expected: PASS

**Step 4: Update documentation if execution revealed drift**

Record the final env vars and any path/format changes in the design and implementation docs before handoff.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-16-thread-journal-and-rolling-compaction-design.md docs/plans/2026-03-16-thread-journal-and-rolling-compaction-implementation-plan.md
git commit -m "docs: finalize thread journal implementation plan"
```
