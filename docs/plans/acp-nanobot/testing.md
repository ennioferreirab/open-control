# Testing strategy

Back to [overview.md](overview.md).

Every phase needs both a static gate and a runtime gate (the **prove-it-works** principle). Unit tests show a branch behaves a certain way; they do not prove a task runs. Both are required.

## Static (every phase)

- `make check` — the pre-commit aggregate. Must pass before any PR.
- `make lint && make typecheck` — ruff + pyright, 100-col, double quotes.
- `uv run pytest` — Python suite.
- `cd dashboard && npm run test` — only when a phase touches `dashboard/`.

Read [agent_docs/running_tests.md](../../../agent_docs/running_tests.md) before writing or changing any test. It is mandatory and defines what to test, what to skip, and the banned anti-patterns.

## Test style to follow

Pytest with `pytest-asyncio` (`asyncio_mode = "auto"`). External I/O mocked via `unittest.mock` (`patch`, `MagicMock`, `AsyncMock`); no live LLM calls in unit tests. Strategy tests use local fake classes that structurally satisfy `RunnerStrategy`, not mocks. Follow these existing files as templates:

- ACP parser → mirror `tests/mc/provider_cli/test_claude_code_parser.py`.
- Engine dispatch → `tests/mc/application/execution/test_engine.py` (the `strategies={...}` injection fixture).
- Selection → `tests/mc/application/execution/test_interactive_mode.py`.
- Process launch → `tests/mc/provider_cli/test_process_supervisor.py` (launches real shell-builtin subprocesses; the closest existing integration test).

## Runtime (per phase, on the real stack)

No bundled control-cli or control-ui skill exists for this project's surfaces. Drive them directly:

- **mc backend / CLI.** Drive the actual CLI and inspect Convex state. Use the `/run` skill or direct commands.
- **Dashboard.** Drive the running UI with Playwright or Chrome DevTools MCP (both available as MCP servers in this session).
- **ACP harness.** Phase 1 proves the adapter with a standalone spike before anything depends on it.

The per-phase runtime checks are listed in each phase file. The two hard gates:

- **Phase 5** — a real task completes through ACP for Claude Code. Track A is not done until this passes.
- **Phase 11** — full smoke from a clean build with zero nanobot references. The plan is not done until this passes.

## Migration test rule

The **migrate-callers-then-delete-legacy-apis** principle applies to tests too. When a phase deletes an old path (Phase 6 NDJSON parser, Phase 8 Factory), delete the tests that only protected that path's internals and rewrite execution tests to assert the new ACP contract. Do not keep dead tests alive as append-only ballast.

## Known surface gaps to flag during implementation

- No automated test spawns a real `claude` binary today; ACP end-to-end proof is manual on the stack (Phases 5, 11). Consider adding one scripted smoke test (the **build-the-lever** principle: a re-runnable check beats a one-time eyeball).
- The @mention routing bug (Phase 7) must be reproduced on the real surface first, then proven fixed on the same surface. A passing unit test alone does not close it.
