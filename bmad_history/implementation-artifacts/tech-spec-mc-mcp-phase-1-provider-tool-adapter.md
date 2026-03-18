# Story: MC MCP Phase 1 Provider Tool Adapter

Status: ready-for-dev

## Story

As a Mission Control backend maintainer,
I want MC-owned tools to pass through a provider-specific adaptation layer in
repo-owned code,
so that Codex, Anthropic, and other providers can each receive a compliant tool
payload without forcing schema hacks into vendor nanobot or tool authors.

## Acceptance Criteria

### AC1: Provider Adapter Contract Exists

**Given** MC runtime can create different provider implementations
**When** a provider is created for MC task execution
**Then** an explicit provider tool-adapter contract exists in `mc`
**And** the adapter can transform the tool list before submission to the provider
**And** vendor provider implementations do not need to understand MC-specific tool semantics.

### AC2: Codex-Safe Adaptation Exists

**Given** Codex rejects top-level schema combinators like `oneOf`
**When** the MC runtime sends the canonical `ask_user` tool to Codex
**Then** the provider-facing schema is transformed into a Codex-safe payload
**And** the semantic requirement previously expressed by top-level `oneOf` is preserved outside the raw top-level schema.

### AC3: Public Tool Names Stay Stable

**Given** the public MC tool names are part of the agent contract
**When** the tool-adapter layer transforms tools for provider submission
**Then** the public names remain `ask_user`, `ask_agent`, `delegate_task`, `send_message`, `cron`, `report_progress`, and `record_final_result`
**And** no transport-coupled public names like `send_message_mc` are introduced.

### AC4: Factory-Owned Wrapping

**Given** upstream nanobot is an external vendor dependency
**When** the MC runtime creates providers
**Then** wrapping and adaptation happen in `mc/infrastructure/providers/*`
**And** the implementation avoids invasive edits to `vendor/nanobot/*`.

### AC5: Focused Regression Passes

**Given** provider creation and Codex serialization already have test coverage
**When** this story completes
**Then** focused provider-factory and adapter tests pass
**And** there is a regression test proving the `ask_user` top-level `oneOf` does not reach Codex unchanged.

## Tasks / Subtasks

- [ ] **Task 1: Add adapter module and contract** (AC: #1, #3, #4)
  - [ ] 1.1 Create an MC-owned provider tool-adapter contract
  - [ ] 1.2 Add a generic pass-through adapter for providers that accept the canonical schema
  - [ ] 1.3 Add a Codex adapter that rewrites unsupported top-level schema constructs

- [ ] **Task 2: Wrap provider creation in the MC factory** (AC: #1, #4)
  - [ ] 2.1 Update `create_provider()` call flow to return an adapted provider in MC runtime
  - [ ] 2.2 Keep resolved model behavior unchanged
  - [ ] 2.3 Avoid edits inside vendor provider implementations unless a tiny compatibility seam is unavoidable

- [ ] **Task 3: Preserve semantic validation outside raw schema** (AC: #2, #3)
  - [ ] 3.1 Represent the `ask_user` question-versus-questions requirement without top-level `oneOf`
  - [ ] 3.2 Document where semantic validation now lives
  - [ ] 3.3 Keep public tool names and descriptions stable

- [ ] **Task 4: Add focused regression coverage** (AC: #2, #5)
  - [ ] 4.1 Add tests for Codex-safe schema adaptation
  - [ ] 4.2 Add tests for public-name stability
  - [ ] 4.3 Add tests for MC factory wrapping behavior

## Dev Notes

### Architecture Notes

- This story is deliberately low-vendor-impact. The adaptation layer belongs to `mc`, not `vendor/nanobot`.
- Treat MCP schema as a canonical source format, not automatically the exact provider payload.
- Preserve semantic intent while changing provider wire format.

### Likely Touch Points

- `mc/infrastructure/providers/factory.py`
- `mc/infrastructure/providers/tool_adapters.py`
- `tests/mc/test_provider_factory.py`
- new focused tests under `tests/mc/infrastructure/providers/`

### References

- [Source: /Users/ennio/Documents/nanobot-ennio/mc/infrastructure/providers/factory.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/vendor/nanobot/nanobot/providers/openai_codex_provider.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/vendor/nanobot/nanobot/agent/tools/ask_user.py]
- [Source: /Users/ennio/Documents/nanobot-ennio/docs/plans/2026-03-14-mc-mcp-phase-1-tools-implementation-plan.md]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
