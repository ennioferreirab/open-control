# Patches Applied to Upstream nanobot

This documents all modifications made to `vendor/nanobot/nanobot/` relative to upstream HKUDS/nanobot.
Use this as a guide when running `git subtree pull` to resolve merge conflicts.

Upstream remote: `https://github.com/HKUDS/nanobot.git` (branch: `main`)
Baseline commit: `a3b13a5` (subtree import)

**Stats**: 6 new files + 22 modified files = 28 total patched files.

---

## New Files (no upstream conflict)

These files do not exist in upstream and will never conflict on `subtree pull`:

| File | Description |
|------|-------------|
| `agent/tools/ask_agent.py` | `AskAgentTool`: synchronous agent-to-agent conversation tool; requires `mc.bridge.ConvexBridge` context, silently skipped if MC unavailable |
| `agent/tools/mc_delegate.py` | `McDelegateTool` (`delegate_task`): delegates tasks to the Mission Control Convex board; always registered in AgentLoop |
| `channels/mission_control.py` | `MissionControlChannel`: bridges outbound messages to Convex task threads; registered via `ChannelManager.register_channel()` |
| `providers/anthropic_oauth.py` | Full Anthropic OAuth PKCE flow; stores tokens in `~/.nanobot/anthropic_oauth.json` |
| `providers/anthropic_oauth_provider.py` | `AnthropicOAuthProvider`: direct httpx+SSE provider (bypasses LiteLLM) for OAuth-authenticated Claude access |
| `skills/create-agent/SKILL.md` | Guided 5-step wizard skill for creating nanobot agent configs |

---

## Modified Files

### `agent/loop.py` (heaviest patch)

- **New constructor params**: `reasoning_level`, `allowed_skills`, `global_skills_dir`, `memory_workspace`, `mc_consolidation_system_prompt`, `agent_name`, `memory_consolidation_max_tokens`
- **`memory_workspace`**: separate path for memory/session storage (falls back to `workspace`); propagated to `ContextBuilder`, `SessionManager`
- **`_consolidation_locks`**: changed from `weakref.WeakValueDictionary` to plain `dict`; new helpers `_get_consolidation_lock()` / `_prune_consolidation_lock()`
- **New instance vars**: `_current_task_id`, `_last_turn_content`
- **`_register_default_tools`**: registers `McDelegateTool` and `AskAgentTool` (with try/except for MC context)
- **`_set_tool_context()`**: type-checked dispatch; `CronTool.set_context()` receives `task_id` and `agent_name`
- **`_run_agent_loop`**: passes `reasoning_level` to `provider.chat()`
- **`_consolidate_memory()`**: passes `max_tokens` and `mc_system_prompt` to `MemoryStore.consolidate()`
- **`process_direct()`**: new `task_id` param; sets `_current_task_id`; falls back to `_last_turn_content` when `MessageTool` suppresses return
- **New method `end_task_session()`**: consolidates + clears a session at end of an MC task
- **`_process_message` / `_handle_message`**: passes `skill_names=self.allowed_skills` to `context.build_messages()`

### `agent/context.py`

- **`ContextBuilder.__init__`**: new `global_skills_dir` param, passed to `SkillsLoader`
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

### `providers/base.py`

- **`LLMProvider.chat()`**: added `reasoning_level: str | None = None` param (alongside existing `reasoning_effort`)
- **`list_models()`**: new method (default returns `[]`)

### `providers/custom_provider.py`

- `chat()`: `reasoning_effort` param renamed to `reasoning_level`

### `providers/litellm_provider.py`

- **`_REASONING_BUDGET_TOKENS`** dict constant added (`low/medium/max` → token budgets)
- **`chat()`**: added `reasoning_level` param with model-aware injection (Anthropic → `thinking` dict + `temperature=1.0`; OpenAI → `reasoning_effort` string)
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
