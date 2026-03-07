# Known Issues

## Open TODOs

### Thread replies to Claude Code tasks
**File:** `mc/chat_handler.py`
**Status:** Not implemented

Plain (non-mention) user replies to done/crashed Claude Code task threads are not forwarded to the CC provider for session resumption. The MentionWatcher handles @mention messages, but direct replies need separate routing.

### Clean up cc_session keys on agent deletion
**File:** `mc/infrastructure/agent_bootstrap.py`
**Status:** Blocked

When an agent is deleted, its `cc_session:{name}:*` keys in Convex settings are not cleaned up. This requires a `settings:listByPrefix` query or equivalent bulk-delete mutation that is not yet available in the Convex schema.

## Pre-existing Test Failures

- `test_cli_tasks.py::test_create_with_title` -- CLI output assertion mismatch (expects "Status: inbox" line not present in output)
