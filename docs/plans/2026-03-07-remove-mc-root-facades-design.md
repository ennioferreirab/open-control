# Remove MC Root Facades Design

## Goal

Finish the `mc/` reorganization by removing the remaining root-level facade
modules and making package entrypoints the canonical import surface.

## Decisions

- Keep only `mc/__init__.py` and `mc/types.py` in the package root.
- Use package `__init__.py` files for short canonical imports:
  - `mc.runtime`
  - `mc.contexts.planning`
  - `mc.contexts.execution`
  - `mc.contexts.conversation`
  - `mc.contexts.review`
- Rewrite internal imports, tests, and CLI entrypoints to use canonical module
  paths or package entrypoints.
- Keep `mc/services/*` facades for now; the cleanup target in this step is the
  `mc/` root only.

## Migration Rules

- No new concrete modules may be added to the `mc/` root.
- Contexts and runtime modules must not import removed root aliases.
- Tests should patch the concrete module that owns behavior, not a deleted shim.
