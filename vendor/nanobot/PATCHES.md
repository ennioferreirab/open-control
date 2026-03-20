# Patches to vendor/nanobot

This file documents modifications made to the upstream `HKUDS/nanobot` subtree for Open Control compatibility. These patches must be re-applied after any upstream sync.

## 2026-03-20: Runtime home env var support

**Reason:** The upstream nanobot hardcodes `~/.nanobot` as the data directory across 10 files. Open Control needs all runtime paths to respect `OPEN_CONTROL_HOME` and `NANOBOT_HOME` environment variables for isolation (Docker containers, multi-instance testing).

**Approach:** Patched `nanobot/utils/helpers.py::get_data_path()` — the single root function — to check `OPEN_CONTROL_HOME` → `NANOBOT_HOME` → `~/.nanobot` (same fallback chain as `mc/infrastructure/runtime_home.py`). All other files now call `get_data_path()` instead of constructing paths directly.

**Files modified:**

| File | Change |
|------|--------|
| `nanobot/utils/helpers.py` | `get_data_path()` checks env vars; `get_workspace_path()` uses `get_data_path()` |
| `nanobot/config/loader.py` | `get_config_path()` uses `get_data_path()` |
| `nanobot/config/schema.py` | `AgentDefaults.workspace` default changed from `~/.nanobot/workspace` to `""` (resolved at runtime) |
| `nanobot/session/manager.py` | `legacy_sessions_dir` uses `get_data_path()` |
| `nanobot/providers/anthropic_oauth.py` | `_TOKEN_FILE` constant → `_get_token_file()` function using `get_data_path()` |
| `nanobot/cli/commands.py` | History file and bridge dir use `get_data_path()` |
| `nanobot/channels/telegram.py` | Media dir uses `get_data_path()` |
| `nanobot/channels/feishu.py` | Media dir uses `get_data_path()` |
| `nanobot/channels/discord.py` | Media dir uses `get_data_path()` |
