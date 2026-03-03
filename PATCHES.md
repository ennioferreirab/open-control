# Patches Applied to Upstream nanobot

This documents all modifications made to `vendor/nanobot/nanobot/` relative to upstream HKUDS/nanobot.
Use this as a guide when running `git subtree pull` to resolve merge conflicts.

Upstream remote: `https://github.com/HKUDS/nanobot.git` (branch: `main`)

---

## New Files (no upstream conflict)

These files do not exist in upstream and will never conflict on `subtree pull`:

- `agent/tools/ask_agent.py` — `AskAgentTool`: synchronous agent-to-agent conversation tool (Story 10.3); requires `mc.bridge.ConvexBridge` context to function, silently skipped if MC is not available
- `agent/tools/mc_delegate.py` — `McDelegateTool` (`delegate_task`): tool to delegate tasks to the Mission Control Convex board; always registered in AgentLoop
- `channels/mission_control.py` — `MissionControlChannel`: channel that bridges outbound messages to Convex task threads; registered programmatically via `ChannelManager.register_channel()`
- `providers/anthropic_oauth.py` — Full Anthropic OAuth PKCE flow; stores tokens in `~/.nanobot/anthropic_oauth.json`; implements `get_anthropic_token()`, `login_interactive()`
- `providers/anthropic_oauth_provider.py` — `AnthropicOAuthProvider`: direct httpx+SSE provider (bypasses LiteLLM) for OAuth-authenticated Claude access; supports `reasoning_level` and prompt caching
- `skills/create-agent/SKILL.md` — Guided 5-step wizard skill for creating nanobot agent configs (config.yaml + SOUL.md)

---

## Modified Files

### `__init__.py`
- Version string downgraded from `0.1.4.post3` → `0.1.4`

### `agent/__init__.py`
- Import order change: `AgentLoop` moved before `ContextBuilder` (cosmetic)

### `agent/loop.py`
Major changes:

- **New constructor params**: `allowed_skills`, `global_skills_dir`, `memory_workspace`, `mc_consolidation_system_prompt`, `reasoning_level`, `agent_name`
- **Removed constructor params**: `reasoning_effort`, `web_proxy`, `channels_config`
- **Changed defaults**: `max_iterations` 40→20, `temperature` 0.1→0.7, `memory_window` 100→50; added `memory_consolidation_max_tokens`
- **`memory_workspace`**: separate path for memory/session storage (falls back to `workspace`); propagated to `ContextBuilder`, `SessionManager`, `MemoryStore`
- **New tools registered**: `McDelegateTool` always; `AskAgentTool` optionally (silently skipped if MC not available)
- **Removed `weakref.WeakValueDictionary`** for consolidation locks → plain `dict`; added `_get_consolidation_lock()` / `_prune_consolidation_lock()` helpers
- **Removed `_active_tasks` + `_processing_lock`**: task cancellation / `/stop` command removed; messages processed sequentially without global lock
- **`_run_agent_loop`**: now returns `(final_content, tools_used)` instead of `(final_content, tools_used, messages)`; removed `_TOOL_RESULT_MAX_CHARS` truncation; session persistence moved to caller; `reasoning_effort` → `reasoning_level`; removed `thinking_blocks` propagation; removed max-iterations warning message
- **`_process_message`**: session turns now saved via `session.add_message()` instead of `_save_turn()`; added `_last_turn_content` to preserve result when `MessageTool` suppresses return value; `allowed_skills` passed to `context.build_messages()`; detailed `logger.info` tracing added
- **`_save_turn()` removed**: replaced by direct `session.add_message("user", ...)` + `session.add_message("assistant", ...)`
- **`process_direct()`**: new `task_id` param; sets `_current_task_id`; falls back to `_last_turn_content` when `MessageTool` suppresses return
- **New method `end_task_session()`**: consolidates + clears a session at end of an MC task (mirrors `/new` command behavior)
- **`_set_tool_context()`**: type-checked dispatch instead of generic `hasattr`; `CronTool.set_context()` now receives `task_id` and `agent_name`
- **`_consolidate_memory()`**: passes `max_tokens` and `mc_system_prompt` through to `MemoryStore.consolidate()`
- **`_tool_hint()`**: simplified argument extraction (removed list-of-args path)
- **`run()` / `_dispatch()`**: `/stop` handling and `_handle_stop()` removed; errors caught inline instead of via separate dispatch method
- **`_build_runtime_context()` removed** from ContextBuilder callers (moved into ContextBuilder itself)
- **`SubagentManager` init**: removed `reasoning_effort`, `web_proxy` params

### `agent/context.py`
Major changes:

- **`ContextBuilder.__init__`**: new `global_skills_dir` param, passed to `SkillsLoader`
- **`_get_identity()`**: added current time display with IANA timezone resolution (`_get_iana_timezone()` helper added); rewritten instructions (removed `_build_runtime_context` pattern, runtime context block removed from user messages)
- **`_build_runtime_context()` removed**: runtime metadata (time, channel, chat_id) is no longer prepended to the user message; time is now in system prompt identity block; channel/chat_id appended to system prompt instead
- **`build_system_prompt()`**: accepts `skill_names` arg, passed to `skills.build_skills_summary(allowed_names=...)`; added loguru debug logging for each section
- **`build_messages()`**: system prompt + channel/chat_id now go into messages list directly; no longer merges runtime context into user message; `skill_names` passed through
- **`add_assistant_message()`**: removed `thinking_blocks` param
- **Style**: extensive docstring additions, trailing whitespace cleanup

### `agent/memory.py`
- Added `filelock.FileLock` for all file I/O in `MemoryStore` (thread-safe concurrent access)
- `consolidate()`: new params `max_tokens` and `mc_system_prompt`; passes `max_tokens` to provider; uses `mc_system_prompt` for system message; removed JSON-string-to-dict fallback for tool call arguments
- `get_memory_context()`: added loguru info logging

### `agent/skills.py`
- **`SkillsLoader.__init__`**: new `global_skills_dir` param; skills from global dir are inserted between workspace and builtin skills
- **`list_skills()`**: includes global skills dir
- **`load_skill()`**: checks global skills dir
- **`build_skills_summary()`**: new `allowed_names` param; when set, only skills whose name is in the list (or marked `always: true`) are included in summary
- **New public API methods** (used by `mc.gateway.sync_skills`): `get_skill_body()`, `is_skill_available()`, `get_missing_requirements()`, `get_nanobot_metadata()`
- Style: whitespace normalization throughout

### `agent/subagent.py`
- **Removed params**: `reasoning_effort`, `web_proxy` from `SubagentManager.__init__` and propagation
- **Removed `_session_tasks` dict** and session-scoped task tracking; `cancel_by_session()` method removed
- **`spawn()`**: removed `session_key` param; simpler cleanup callback
- **`_run_subagent()`**: removed `path_append` from `ExecTool`; removed `proxy` from web tools; removed `reasoning_effort`
- **`_build_subagent_prompt()`**: accepts `task` param; completely rewritten with inline time display; removed `ContextBuilder._build_runtime_context` dependency; removed skills summary from subagent prompt

### `agent/tools/ask_agent.py`
_New file — see New Files section._

### `agent/tools/base.py`
- Minor whitespace / style normalization; comma removed from last item in `to_schema()` return dict

### `agent/tools/cron.py`
- **Removed**: `ContextVar` (`_in_cron_context`) and associated `set_cron_context()` / `reset_cron_context()` methods; in-cron-context guard removed from `execute()`
- **`set_context()`**: new params `task_id` and `agent_name` (stored for job creation)
- **New method `set_telegram_default()`**: configures fallback Telegram chat_id for MC context
- **`description`**: dynamically includes channel/telegram hints
- **New tool parameters**: `deliver_channel`, `deliver_to` — allow overriding delivery destination at job creation time
- **`_add_job()`**: validates and uses `deliver_channel`/`deliver_to`; Telegram chat_id must be numeric; passes `task_id` and `agent` to `CronService.add_job()`
- Style: whitespace normalization

### `agent/tools/filesystem.py`
- Minor whitespace / style normalization; property dict formatting expanded to multi-line

### `agent/tools/mc_delegate.py`
_New file — see New Files section._

### `agent/tools/mcp.py`
- MCP HTTP transport: simplified `httpx.AsyncClient` handling — only creates custom client when `cfg.headers` is set; removed explicit `timeout=None` override

### `agent/tools/message.py`
- `_sent_in_turn` flag now set unconditionally when `send_callback` succeeds (previously only set when sending to the default channel)

### `agent/tools/registry.py`
- `execute()`: removed `_HINT` suffix appended to all error messages; error message for unknown tool simplified; style normalization

### `agent/tools/shell.py`
- **Removed `path_append` param** from `ExecTool.__init__`; removed PATH manipulation in `execute()`
- **Path extraction inlined** from `_extract_absolute_paths()` (static method removed; logic moved inline into `_check_safety_guard()`)
- Style: whitespace normalization

### `agent/tools/spawn.py`
- Removed `_session_key` tracking from `SpawnTool`; `execute()` no longer passes `session_key` to `manager.spawn()`
- Style: whitespace normalization

### `agent/tools/web.py`
- **`WebSearchTool`**: removed `proxy` param and `logger.debug` proxy hint; API key resolved at init (not at call time); simplified error messages
- **`WebFetchTool`**: removed `proxy` param; removed `logger.debug` / `logger.error` calls on proxy/errors
- Removed `from loguru import logger` import (no longer used in this file)

### `bus/events.py`
- `InboundMessage`: removed `session_key_override` field; `session_key` property now always returns `f"{self.channel}:{self.chat_id}"`
- Style: whitespace normalization

### `bus/queue.py`
- Queues (`inbound`, `outbound`) now lazily created on first access (properties) to avoid requiring a running event loop at instantiation time; `inbound_size` / `outbound_size` return 0 if queue not yet created

### `channels/__init__.py`
- Removed blank line before `__all__` (cosmetic)

### `channels/base.py`
- **`is_allowed()`**: empty `allow_from` now means **allow all** (upstream: empty means deny all; `"*"` means allow all)
- **`_handle_message()`**: removed `session_key` param and `InboundMessage.session_key_override` usage
- Style: whitespace normalization, expanded docstrings

### `channels/dingtalk.py`
- Removed media extension sets (`_IMAGE_EXTS`, `_AUDIO_EXTS`, `_VIDEO_EXTS`)
- Removed several imports (`mimetypes`, `os`, `Path`, `urlparse`, `unquote`)
- Import reordering (`httpx` moved after `loguru`)
- DingTalk stream imports reordered

### `channels/discord.py`
- Typing indicator loop: `CancelledError` and general exceptions now silently swallowed (was: logged + returned)
- Added blank line before `DISCORD_API_BASE`

### `channels/email.py`
- `send()`: `auto_reply_enabled` check moved earlier (before SMTP config check); removed distinction between "reply" vs "proactive" send — any outbound message respects the flag unless `force_send` metadata is set

### `channels/feishu.py`
- Import reordering (`GetFileRequest` added; `CreateMessageReaction*` reordered)
- `_extract_interactive_content()`: fixed loop — was iterating lists-of-lists, now iterates elements directly
- Minor whitespace normalization

### `channels/manager.py`
- **`register_channel()`**: new method to programmatically register a channel (used for `MissionControlChannel`)
- **Matrix channel init removed** from `_init_channels()`
- **`_validate_allow_from()`** method removed (no longer raises `SystemExit` on empty `allow_from`)
- **`_dispatch_outbound()`**: removed `send_progress` / `send_tool_hints` config filtering of progress messages; all outbound messages are dispatched to channel handlers
- Style: whitespace normalization

### `channels/mission_control.py`
_New file — see New Files section._

### `channels/qq.py`
- QQ bot init: removed `ext_handlers=False` kwarg (re-enables botpy's default file logging)
- `send()`: removed `msg_id` from `post_c2c_message()` call

### `channels/slack.py`
- Removed thread-scoped `session_key` (was `f"slack:{chat_id}:{thread_ts}"`); no longer passed to `_handle_message()`
- Removed several compiled regex constants (`_CODE_FENCE_RE`, `_INLINE_CODE_RE`, `_LEFTOVER_BOLD_RE`, `_LEFTOVER_HEADER_RE`, `_BARE_URL_RE`)
- Import reordering

### `channels/telegram.py`
- Import reordering (`BotCommand`, `Update`, `ReplyParameters` etc.)
- Whitespace normalization throughout (cosmetic)

### `channels/whatsapp.py`
- `OrderedDict` import removed (deduplication removed)
- Style: whitespace normalization

### `cli/commands.py`
- Import reordering
- **`onboard()`**: replaced `sync_workspace_templates()` call with inline `_create_workspace_templates()` function (no longer reads from `nanobot/templates/`; hardcodes AGENTS.md, SOUL.md, USER.md, memory/MEMORY.md)
- **`sync_workspace_templates` import removed**
- **Cron CLI subcommands added**: `cron add`, `cron remove`, `cron enable`, `cron run` (with `--every`, `--cron`, `--at` schedule options)
- **`provider login anthropic_oauth`**: new login handler using `nanobot.providers.anthropic_oauth.login_interactive()`
- **Mission Control CLI mounted**: `from mc.cli import mc_app; app.add_typer(mc_app, name="mc")` at bottom of file

### `config/__init__.py`
- Minor import reordering (cosmetic)

### `config/schema.py`
- **`MatrixConfig` removed** entirely (both duplicate definitions)
- **`ChannelsConfig`**: `matrix` field replaced with `mc: MissionControlConfig`; removed `send_progress` and `send_tool_hints` fields
- **`MissionControlConfig` added**: minimal config (`enabled: bool = False`)
- **`FeishuConfig`**: removed `react_emoji` field
- **`SlackConfig`**: removed `allow_from` field
- **`AgentDefaults`**: removed `provider` (auto-detection only now); `temperature` 0.1→0.7, `max_tool_iterations` 40→20, `memory_window` 100→50; added `memory_consolidation_max_tokens`; removed `reasoning_effort`; added `models` list to `AgentsConfig`
- **`GatewayConfig`**: removed `heartbeat` sub-config (`HeartbeatConfig` class removed)
- **`HeartbeatConfig` removed**
- **`WebToolsConfig`**: removed `proxy` field
- **`ExecToolConfig`**: removed `path_append` field
- **`ProvidersConfig`**: added `anthropic_oauth` field
- **`Config.find_provider()`**: removed forced-provider override via `agents.defaults.provider`

### `cron/service.py`
- **`_parse_raw_job()`**: new helper to parse both old flat and new nested job JSON formats (supports migration from old schema)
- **`_load_store()`**: removed external-modification reload (mtime tracking removed); uses `_parse_raw_job()` for loading
- `CronService`: removed `_last_mtime` field
- `CronJob.add_job()`: now accepts `task_id` and `agent` params (stored in `CronPayload`)
- Style: whitespace normalization

### `cron/types.py`
- `CronPayload`: added `task_id` and `agent` fields

### `heartbeat/service.py`
- **Major rewrite**: removed `_HEARTBEAT_TOOL` (tool-call based decision); now uses simple text prompt (`HEARTBEAT_PROMPT`) and `HEARTBEAT_OK_TOKEN` pattern
- Added `filelock.FileLock` import
- Added `_is_heartbeat_empty()` helper
- Added `DEFAULT_HEARTBEAT_INTERVAL_S` constant
- `HeartbeatService` class internal logic simplified

### `providers/__init__.py`
- Added `AnthropicOAuthProvider` import and export

### `providers/anthropic_oauth.py`
_New file — see New Files section._

### `providers/anthropic_oauth_provider.py`
_New file — see New Files section._

### `providers/base.py`
- `LLMResponse`: removed `thinking_blocks` field
- `LLMProvider.chat()`: renamed `reasoning_effort` → `reasoning_level`
- `LLMProvider.list_models()`: new method (default returns `[]`; overridden in OAuth provider)
- `_clean_messages()`: removed `dict`-type content handling branch

### `providers/custom_provider.py`
- Minor changes (whitespace / import style)

### `providers/litellm_provider.py`
- Removed `secrets` / `string` imports and `_short_tool_id()` helper
- `_ALLOWED_MSG_KEYS`: removed `reasoning_content` and `thinking_blocks` from allowed keys (stripped for strict providers)
- Added `_REASONING_BUDGET_TOKENS` map (`low/medium/max` → token counts)
- `reasoning_effort` → `reasoning_level` throughout
- Added `json` import

### `providers/openai_codex_provider.py`
- Minor changes (whitespace / import style)

### `providers/registry.py`
- `openai_codex` spec: added `"codex"` keyword
- New `anthropic_oauth` `ProviderSpec` entry with `is_oauth=True`, `is_direct=True`, `supports_prompt_caching=True`

### `providers/transcription.py`
- Added `from typing import Any` import
- Style: whitespace normalization

### `session/__init__.py`
- Minor import reordering (cosmetic)

### `session/manager.py`
- Added `filelock.FileLock` for `save()` (concurrent write safety)
- `Session.get_history()`: simplified — no longer strips leading non-user messages; returns all messages in `self.messages[-max_messages:]`; added loguru info logging
- `SessionManager.save()`: wrapped in `FileLock`
- Added loguru debug logging in `_load()` for each loaded message
- Style: whitespace normalization, import reordering

### `skills/memory/SKILL.md`
- Removed `[YYYY-MM-DD HH:MM]` entry format note from HISTORY.md description

### `utils/__init__.py`
- Minor import reordering (cosmetic)

### `utils/helpers.py`
- `sync_workspace_templates()` removed (templates now hardcoded in `cli/commands.py`)
- New utility functions added: `get_sessions_path()`, `get_skills_path()`, `truncate_string()`, `parse_session_key()`
- `safe_filename()`: reimplemented without compiled regex (character-by-character replacement)
- Import reordering (`Path` before `datetime`)
