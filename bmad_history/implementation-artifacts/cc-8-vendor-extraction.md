# CC-8: Extract CC Backend to vendor/claude-code/ Package

## Problem

The Claude Code backend modules (cc_provider, cc_workspace, mcp_bridge, mcp_ipc, mcp_ipc_server) live inside `mc/`, mixed with Mission Control orchestration code. This violates the separation of concerns established by `vendor/nanobot/` — the nanobot runtime is a self-contained package under `vendor/`, while MC is the orchestration layer that imports from it.

The CC backend should follow the same pattern: a self-contained package under `vendor/claude-code/` that MC imports.

## Acceptance Criteria

### AC1: Package Structure

Create `vendor/claude-code/` with this structure:

```
vendor/claude-code/
├── pyproject.toml                    # Package: "claude-code-backend"
├── claude_code/                      # Python package (snake_case)
│   ├── __init__.py                   # Exports __version__
│   ├── provider.py                   # ← mc/cc_provider.py
│   ├── workspace.py                  # ← mc/cc_workspace.py
│   ├── mcp_bridge.py                 # ← mc/mcp_bridge.py
│   ├── ipc_client.py                 # ← mc/mcp_ipc.py
│   ├── ipc_server.py                 # ← mc/mcp_ipc_server.py
│   └── types.py                      # CC-specific types extracted from mc/types.py
└── tests/
    └── (moved from tests/mc/test_cc_*, test_mcp_*)
```

### AC2: Type Extraction

Extract CC-specific types from `mc/types.py` to `claude_code/types.py`:

- `CC_MODEL_PREFIX`
- `is_cc_model()`
- `extract_cc_model_name()`
- `ClaudeCodeOpts`
- `WorkspaceContext`
- `CCTaskResult`

Keep `AgentData` in `mc/types.py` (shared between both backends).

Re-export from `mc/types.py` for backwards compatibility:
```python
from claude_code.types import (
    CC_MODEL_PREFIX, is_cc_model, extract_cc_model_name,
    ClaudeCodeOpts, WorkspaceContext, CCTaskResult,
)
```

### AC3: Import Updates in MC

Update all MC files that import CC modules:

| File | Old Import | New Import |
|------|-----------|------------|
| `mc/executor.py` | `from mc.cc_workspace import CCWorkspaceManager` | `from claude_code.workspace import CCWorkspaceManager` |
| `mc/executor.py` | `from mc.cc_provider import ClaudeCodeProvider` | `from claude_code.provider import ClaudeCodeProvider` |
| `mc/executor.py` | `from mc.mcp_ipc_server import MCSocketServer` | `from claude_code.ipc_server import MCSocketServer` |
| `mc/step_dispatcher.py` | Same 3 imports | Same new paths |
| `mc/chat_handler.py` | Same 3 imports | Same new paths |

### AC4: MCP Bridge Module Path

`cc_workspace.py` line 217 hardcodes `"uv run python -m mc.mcp_bridge"` in `.mcp.json`. Update to `"uv run python -m claude_code.mcp_bridge"`.

### AC5: pyproject.toml Integration

Root `pyproject.toml`:
```toml
[tool.uv.sources]
claude-code-backend = { path = "vendor/claude-code", editable = true }

[project]
dependencies = [
    "nanobot-ai",
    "claude-code-backend",
    # ... existing deps
]
```

### AC6: boot.py Vendor Path

Add `vendor/claude-code` to sys.path in `boot.py`, following the nanobot pattern:
```python
_cc_vendor = str(Path(__file__).parent / "vendor" / "claude-code")
if _cc_vendor not in sys.path:
    sys.path.insert(0, _cc_vendor)
```

### AC7: Internal Imports Fixed

Within the new package, update internal imports:
- `mcp_bridge.py` imports `from mc.mcp_ipc import MCSocketClient` → `from claude_code.ipc_client import MCSocketClient`
- `ipc_server.py` keeps its mc/ imports for bridge/gateway/validator (these are legitimate cross-package dependencies where CC calls back into MC)

### AC8: Tests Relocated

Move CC-specific tests:

| Old Path | New Path |
|----------|----------|
| `tests/mc/test_cc_provider.py` | `tests/cc/test_provider.py` |
| `tests/mc/test_cc_workspace.py` | `tests/cc/test_workspace.py` |
| `tests/mc/test_cc_workspace_context.py` | `tests/cc/test_workspace_context.py` |
| `tests/mc/test_cc_sessions.py` | `tests/cc/test_sessions.py` |
| `tests/mc/test_mcp_ipc.py` | `tests/cc/test_ipc_client.py` |
| `tests/mc/test_mcp_bridge.py` | `tests/cc/test_mcp_bridge.py` |

Update imports inside test files accordingly.

Keep integration tests that test executor+CC in `tests/mc/test_executor_cc.py` (they test MC orchestration, not the CC package itself).

### AC9: Delete Old Files

After extraction, delete the original files from `mc/`:
- `mc/cc_provider.py`
- `mc/cc_workspace.py`
- `mc/mcp_bridge.py`
- `mc/mcp_ipc.py`
- `mc/mcp_ipc_server.py`

### AC10: All Tests Pass

```bash
uv run pytest tests/ -v --timeout=60
```

All existing tests must pass after the extraction. No behavioral changes.

## Technical Design

### Dependency Graph (Post-Extraction)

```
MC (orchestration layer)
├── imports claude_code.provider.ClaudeCodeProvider
├── imports claude_code.workspace.CCWorkspaceManager
├── imports claude_code.ipc_server.MCSocketServer
├── imports claude_code.types.{is_cc_model, CCTaskResult, ...}
│
└── claude_code (vendor package)
    ├── provider.py → imports claude_code.types
    ├── workspace.py → imports claude_code.types, nanobot.agent.skills
    ├── mcp_bridge.py → imports claude_code.ipc_client, mcp.server
    ├── ipc_client.py → stdlib only
    └── ipc_server.py → imports mc.bridge, mc.gateway, mc.types, nanobot.bus, nanobot.agent
```

**Note**: `ipc_server.py` has the heaviest cross-package dependencies because it implements MC operations (ask_user, delegate_task, ask_agent) that need ConvexBridge and nanobot AgentLoop. This is acceptable — it's the integration point between the CC runtime and MC.

### pyproject.toml for vendor/claude-code/

```toml
[project]
name = "claude-code-backend"
version = "0.1.0"
description = "Claude Code headless CLI backend for Mission Control"
requires-python = ">=3.11"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["claude_code"]
```

### __init__.py

```python
"""Claude Code Backend — headless CLI execution for Mission Control agents."""

__version__ = "0.1.0"
```

## Migration Strategy

1. Create `vendor/claude-code/` package structure
2. Copy files (don't move yet) to new locations with updated imports
3. Update root pyproject.toml and boot.py
4. Run `uv sync` to install the new package
5. Update MC imports to use `claude_code.*`
6. Update mc/types.py to re-export from claude_code.types
7. Run full test suite
8. Delete old mc/cc_* and mc/mcp_* files
9. Run test suite again
10. Update test file locations

## Files Changed

| Action | File |
|--------|------|
| CREATE | `vendor/claude-code/pyproject.toml` |
| CREATE | `vendor/claude-code/claude_code/__init__.py` |
| CREATE | `vendor/claude-code/claude_code/provider.py` (from mc/cc_provider.py) |
| CREATE | `vendor/claude-code/claude_code/workspace.py` (from mc/cc_workspace.py) |
| CREATE | `vendor/claude-code/claude_code/mcp_bridge.py` (from mc/mcp_bridge.py) |
| CREATE | `vendor/claude-code/claude_code/ipc_client.py` (from mc/mcp_ipc.py) |
| CREATE | `vendor/claude-code/claude_code/ipc_server.py` (from mc/mcp_ipc_server.py) |
| CREATE | `vendor/claude-code/claude_code/types.py` (extracted from mc/types.py) |
| MODIFY | `mc/types.py` — re-export CC types from claude_code.types |
| MODIFY | `mc/executor.py` — update imports |
| MODIFY | `mc/step_dispatcher.py` — update imports |
| MODIFY | `mc/chat_handler.py` — update imports |
| MODIFY | `boot.py` — add vendor/claude-code to sys.path |
| MODIFY | `pyproject.toml` — add claude-code-backend dependency |
| DELETE | `mc/cc_provider.py`, `mc/cc_workspace.py`, `mc/mcp_bridge.py`, `mc/mcp_ipc.py`, `mc/mcp_ipc_server.py` |
| MOVE   | `tests/mc/test_cc_*.py` → `tests/cc/test_*.py` |
| MOVE   | `tests/mc/test_mcp_*.py` → `tests/cc/test_*.py` |

## Dependencies

- **CC-7 (Context Parity)** must be completed first — we want to extract the enriched version of cc_workspace.py, not the current minimal one.

## Risks

- `ipc_server.py` imports heavily from `mc.*` — this creates a circular-ish dependency (MC imports CC, CC imports MC). This is acceptable because the IPC server is the integration seam. If it becomes problematic, the MC-dependent handlers can be injected via callbacks instead of direct imports.
- The `mcp_bridge.py` module path change (`mc.mcp_bridge` → `claude_code.mcp_bridge`) affects every CC agent's `.mcp.json`. Existing workspaces will have stale `.mcp.json` files — but `prepare()` rewrites `.mcp.json` on every call, so this self-heals.
