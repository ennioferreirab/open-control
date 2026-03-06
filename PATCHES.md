# Patches Applied to Upstream nanobot

This documents all modifications made to `vendor/nanobot/nanobot/` relative to upstream HKUDS/nanobot.
Use this as a guide when running `git subtree pull` to resolve merge conflicts.

Upstream remote: `https://github.com/HKUDS/nanobot.git` (branch: `main`)
Baseline commit: `a3b13a5` (subtree import)

**Stats**: 7 new files + 23 modified files = 30 total patched files.

---

## New Files (no upstream conflict)

These files do not exist in upstream and will never conflict on `subtree pull`:

| File | Description |
|------|-------------|
| `agent/tools/ask_agent.py` | `AskAgentTool`: synchronous agent-to-agent conversation tool; requires `mc.bridge.ConvexBridge` context, silently skipped if MC unavailable. Imports `AGENTS_DIR` from `mc.infrastructure.config` (migrated from `mc.gateway` in Story 15.2). |
| `agent/tools/mc_delegate.py` | `McDelegateTool` (`delegate_task`): delegates tasks to the Mission Control Convex board; always registered in AgentLoop. Imports `_resolve_convex_url` from `mc.infrastructure.config` (migrated from `mc.gateway` in Story 15.2). |
| `channels/mission_control.py` | `MissionControlChannel`: bridges outbound messages to Convex task threads; registered via `ChannelManager.register_channel()` |
| `providers/anthropic_oauth.py` | Full Anthropic OAuth PKCE flow; stores tokens in `~/.nanobot/anthropic_oauth.json` |
| `providers/anthropic_oauth_provider.py` | `AnthropicOAuthProvider`: direct httpx+SSE provider (bypasses LiteLLM) for OAuth-authenticated Claude access |
| `agent/tools/search_memory.py` | `SearchMemoryTool`: hybrid BM25+vector search over agent memory (MEMORY.md + HISTORY.md); delegates to `HybridMemoryStore.search()` |
| `skills/create-agent/SKILL.md` | Guided 5-step wizard skill for creating nanobot agent configs |

---

## Modified Files

### `agent/loop.py` (heaviest patch)

- **New constructor params**: `reasoning_level`, `allowed_skills`, `global_skills_dir`, `memory_workspace`, `mc_consolidation_system_prompt`, `agent_name`, `memory_consolidation_max_tokens`
- **`memory_workspace`**: separate path for memory/session storage (falls back to `workspace`); propagated to `ContextBuilder`, `SessionManager`
- **`_consolidation_locks`**: changed from `weakref.WeakValueDictionary` to plain `dict`; new helpers `_get_consolidation_lock()` / `_prune_consolidation_lock()`
- **New instance vars**: `_current_task_id`, `_last_turn_content`
- **`_register_default_tools`**: registers `McDelegateTool`, `AskAgentTool`, and `SearchMemoryTool` (all with try/except for MC context)
- **`_set_tool_context()`**: type-checked dispatch; `CronTool.set_context()` receives `task_id` and `agent_name`
- **`_run_agent_loop`**: passes `reasoning_level` to `provider.chat()`
- **`_consolidate_memory()`**: uses `self.context.memory` (HybridMemoryStore if available) instead of creating new `MemoryStore`; passes `max_tokens` and `mc_system_prompt` to `consolidate()`
- **`process_direct()`**: new `task_id` param; sets `_current_task_id`; falls back to `_last_turn_content` when `MessageTool` suppresses return
- **New method `end_task_session()`**: consolidates + clears a session at end of an MC task
- **`_process_message` / `_handle_message`**: passes `skill_names=self.allowed_skills` to `context.build_messages()`

### `agent/context.py`

- **`ContextBuilder.__init__`**: new `global_skills_dir` param, passed to `SkillsLoader`; try-imports `HybridMemoryStore` from `mc.memory.store` (falls back to `MemoryStore` if unavailable)
- **`_get_identity()`**: added guideline: "Use search_memory tool to recall past decisions and events from history."
- **`build_skills_summary()` call**: passes `allowed_names=skill_names`

### `agent/memory.py`

- **`FileLock`** on all file I/O (`read_long_term`, `write_long_term`, `append_history`) for thread-safe concurrent access
- **`consolidate()`**: new params `max_tokens` and `mc_system_prompt`; passes to provider

### `agent/skills.py`

- **`SkillsLoader.__init__`**: new `global_skills_dir` param; skills from global dir inserted between workspace and builtin
- **`list_skills()`**: includes global skills dir
- **`load_skill()`**: checks global skills dir
- **`build_skills_summary()`**: new `allowed_names` param; filters to matching skills + `always: true`
- **New public API methods**: `get_skill_body()`, `is_skill_available()`, `get_missing_requirements()`, `get_nanobot_metadata()` — used by `mc.gateway.sync_skills`
- Cosmetic: `from __future__ import annotations` added, whitespace normalization throughout

### `agent/tools/cron.py`

- **New instance vars**: `_task_id`, `_agent_name`, `_telegram_default_chat_id`
- **`set_context()`**: new params `task_id` and `agent_name`
- **New method `set_telegram_default()`**: configures fallback Telegram chat_id
- **`description`**: dynamically includes channel/telegram hints
- **New tool parameters**: `deliver_channel`, `deliver_to` — override delivery destination at job creation
- **`_add_job()`**: validates and uses `deliver_channel`/`deliver_to`; passes `task_id` and `agent` to `CronService.add_job()`

### `agent/tools/message.py`

- `_sent_in_turn` flag now set unconditionally on every successful `send_callback` call (previously only set for default channel)

### `bus/queue.py`

- Queues (`inbound`, `outbound`) lazily created on first access (properties) to avoid requiring a running event loop at instantiation time

### `channels/feishu.py`

- **Bugfix**: `_extract_interactive_content()` loop fixed — was iterating lists-of-lists, now iterates elements directly

### `channels/manager.py`

- **`register_channel()`**: new method for programmatic channel registration (used for `MissionControlChannel`)
- **Matrix channel init removed** from `_init_channels()`

### `cli/commands.py`

- **`_make_provider`**: tries `mc.provider_factory.create_provider` first; falls back to upstream logic
- **Cron CLI subcommands added**: `cron list`, `cron add`, `cron remove`, `cron enable`, `cron run`
- **`provider login anthropic_oauth`**: new login handler
- **Mission Control CLI mounted**: `from mc.cli import mc_app; app.add_typer(mc_app, name="mc")`

### `config/schema.py`

- **`MissionControlConfig` added**: replaces a duplicate `MatrixConfig` definition
- **`ChannelsConfig`**: gains `mc: MissionControlConfig` field
- **`AgentDefaults`**: added `memory_consolidation_max_tokens`
- **`AgentsConfig`**: added `models: list[str] = []`
- **`ProvidersConfig`**: added `anthropic_oauth: dict | None = None`

### `cron/service.py`

- **`_parse_raw_job()`**: parses both old flat and new nested job JSON formats
- **`_load_store()`**: uses `_parse_raw_job()` with per-job error handling
- **`_save_store()`**: atomic write via temp file + `replace()`; serializes `taskId` and `agent`
- **`add_job()`**: accepts `task_id` and `agent` params

### `cron/types.py`

- `CronPayload`: added `task_id: str | None` and `agent: str | None` fields

### `heartbeat/service.py`

- **`HeartbeatService.__init__`**: `provider` and `model` now optional; new `on_heartbeat` callback param for MC compat
- **`_decide`**: returns early `("skip", "")` if provider/model is None
- **`_tick` / `run_once`**: `FileLock` on heartbeat file; MC compat branch — if `on_heartbeat` is set, runs simple text-prompt heartbeat

### `providers/__init__.py`

- Added `AnthropicOAuthProvider` import and export

### `providers/anthropic_oauth_provider.py`

- **Reasoning API migration for Claude 4.6**: detects `4-6` models after stripping OAuth prefix and switches reasoning to `output_config={"effort": ...}` + `thinking={"type": "adaptive"}`; keeps legacy `thinking.budget_tokens` + `temperature=1.0` for older models
- **Effort clamping**: maps `max` to `high` for all non-Opus-4.6 models to avoid Anthropic API validation errors
- **Debug observability**: logs effective reasoning params (`effort` adaptive vs `budget_tokens`) before each API call

### `providers/base.py`

- **`LLMProvider.chat()`**: added `reasoning_level: str | None = None` param (alongside existing `reasoning_effort`)
- **`list_models()`**: new method (default returns `[]`)

### `providers/custom_provider.py`

- `chat()`: `reasoning_effort` param renamed to `reasoning_level`

### `providers/litellm_provider.py`

- **`_REASONING_BUDGET_TOKENS`** dict constant added (`low/medium/max` → token budgets)
- **`chat()`**: added `reasoning_level` param with model-aware injection (Anthropic → `thinking` dict + `temperature=1.0`; OpenAI → `reasoning_effort` string)
- **Reasoning API migration for Claude 4.6**: detects `4-6` models (after stripping Anthropic prefixes) and passes `reasoning_effort=<effort>` (LiteLLM native kwarg, auto-mapped to `output_config.effort`) instead of deprecated `thinking.budget_tokens`; clamps `max` effort to `high` for non-Opus-4.6; logs effective reasoning params at DEBUG level before `acompletion()`
- **`list_models()`**: queries `/v1/models` endpoint if api_key/api_base available

### `providers/openai_codex_provider.py`

- `chat()`: `reasoning_effort` param renamed to `reasoning_level`

### `providers/registry.py`

- `openai_codex` spec: added `"codex"` keyword
- New `anthropic_oauth` `ProviderSpec` entry

### `session/manager.py`

- **`FileLock`** on `_load()` and `save()` for concurrent write safety

### `utils/helpers.py`

- **New utility functions**: `get_sessions_path()`, `get_skills_path()`, `parse_session_key()`

---

## Upstream Sync Procedure

```bash
git fetch upstream
git subtree pull --prefix=vendor/nanobot upstream main --squash
# Resolve conflicts using this file as guide
# Run: uv run pytest tests/mc/ -q
```

Files most likely to conflict on upstream sync (sorted by patch size):
1. `agent/loop.py` — heaviest patch
2. `cli/commands.py` — CLI additions
3. `config/schema.py` — schema additions
4. `agent/skills.py` — global skills + allowed_names
5. `providers/litellm_provider.py` — reasoning_level injection

---

## vendor/claude-code/ (CC Backend)

### New Files

| File | Description |
|------|-------------|
| `claude_code/memory_consolidator.py` | `CCMemoryConsolidator`: post-task LLM consolidation into MEMORY.md + HISTORY.md + SQLite index; mirrors nanobot `end_task_session()` |

### Modified Files

#### `claude_code/types.py`
- **`CCTaskResult`**: added `error_type: str = ""` and `error_message: str = ""` fields

#### `claude_code/provider.py`
- **`_handle_message()`**: captures `stream_event` API errors (invalid model, rate limit, auth, overloaded); extracts error details from `result.error` dict when `is_error=True`
- **`_build_command()`**: warns on unrecognized model names (does not block)

#### `claude_code/ipc_server.py`
- **Import migration (Story 15.2)**: `AGENTS_DIR` now imported from `mc.infrastructure.config` instead of `mc.gateway`

#### `claude_code/workspace.py`

- **`CCWorkspaceManager.prepare()`**: new `board_name: str | None = None` and `memory_mode: str = "clean"` params; when `board_name` is provided, workspace root is set via `mc.board_utils.resolve_board_workspace()` instead of the global `~/.nanobot/agents/{agent}/` path.

---

## mc/ (Mission Control Backend)

### Modified Files

#### `mc/chat_handler.py`

- **Fire-and-forget CC memory consolidation** added to the CC chat path (in the `finally` block after IPC server stop): when `execute_task()` returns a result object (even on error), a background `asyncio.Task` runs `CCMemoryConsolidator.consolidate()` to persist facts into MEMORY.md/HISTORY.md. Uses `tier:standard-low` model resolved via `TierResolver`. Strong references held in `_chat_background_tasks` set to prevent premature GC.

#### `mc/executor.py`

- **`_execute_cc_task()`**: board-scoped workspace block (step 0d) now runs _before_ the output-dir snapshot (step 0e), matching the ordering in the nanobot execution path.
- **`handle_cc_thread_reply()`**: fetches task data via `tasks:getById` to extract `board_id`; resolves `board_name` / `memory_mode` the same way as `_execute_cc_task()` before preparing the workspace. Falls back to global workspace on any bridge failure.
