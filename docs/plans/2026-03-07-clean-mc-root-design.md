# Clean `mc/` Root Design

## Summary

The `mc/` root still mixes compatibility facades, shared foundational modules,
and concrete feature modules. That breaks the authority model introduced by
`mc/runtime/`, `mc/contexts/`, `mc/infrastructure/`, `mc/domain/`, and
`mc/cli/`.

This cleanup moves concrete modules out of the root and leaves only:

- `mc/__init__.py`
- temporary public compatibility facades
- `mc/types.py` only if it still needs a transition period

## Goals

- make `mc/` root visually small and predictable
- assign every concrete module to a clear owner layer
- remove "extracted but homeless" modules from the root
- migrate internal imports to canonical locations
- tighten guardrails so new concrete root modules do not reappear

## Ownership Model

### `mc/cli`

Owns user-facing command and setup flows.

- `agent_assist`
- `init_wizard`
- `process_manager`

### `mc/infrastructure`

Owns providers, filesystem helpers, environment adapters, and agent bootstrap helpers.

- `board_utils`
- `agent_orientation`
- `provider_factory`
- `tier_resolver`
- `yaml_validator`

### `mc/contexts/planning`

Owns planning-specific parsing and shaping.

- `plan_parser`

### `mc/contexts/execution`

Owns execution-time post-processing and crash recovery.

- `output_enricher`
- `crash_handler`

### `mc/application/execution`

Owns reusable execution kernel helpers.

- `thread_context`

### `mc/domain`

Owns workflow/state validation and any truly shared pure rule helpers.

- `state_machine`
- root `utils.py` should be absorbed or reduced to a domain helper module if still needed

### `mc/runtime`

Owns lifecycle loops and runtime supervision.

- `timeout_checker`

## Compatibility Strategy

Move modules to their new canonical packages, then keep thin root facades only
where compatibility is still useful. Internal imports should be rewritten to
canonical paths immediately.

For the new cleanup, compatibility facades are acceptable for:

- currently public runtime/context entrypoints already documented
- moved shared modules that are still imported by vendor or tests during the transition

The target is for facades to remain small and dumb, not as long-term ownership.

## Guardrails

Add architecture rules so that:

- new concrete modules cannot be added to `mc/` root outside an allowlist
- root facade files must stay thin
- `contexts/*`, `runtime/*`, `infrastructure/*`, and `domain/*` must not import old root module paths
- canonical imports point to the new package locations

## Migration Order

1. Move infrastructure and CLI support modules.
2. Move planning and execution leftovers.
3. Move `thread_context`, `state_machine`, and `timeout_checker`.
4. Rewrite imports and tests.
5. Update architecture docs and guardrails.

## Verification

- focused tests for each moved module
- full `uv run pytest tests/mc -q`
- architecture tests proving the root stays thin
