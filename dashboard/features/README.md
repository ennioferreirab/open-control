# Dashboard Features

This directory is the target ownership layer for dashboard feature code.

## Placement Rules

- `features/<feature>/components/`: feature-specific UI
- `features/<feature>/hooks/`: feature orchestration, view-model, and mutation hooks
- `features/<feature>/lib/`: pure helpers, selectors, and mappers

## Allowed Dependencies

- feature components may import:
  - feature hooks
  - feature lib helpers
  - shared UI primitives from `components/ui/`
  - shared viewers when needed
- feature hooks may import:
  - `convex/`
  - feature `lib/`
  - shared helpers from `lib/`
- feature hooks must not import feature UI components
- feature components must not import `convex/react` directly

## Shared vs Feature-Owned

Keep code outside `features/` only when it is clearly shared:

- `components/ui/` for primitives
- `components/viewers/` for reusable viewer/rendering modules
- `lib/` for cross-feature helpers
- `app/` for routing and composition

If the code primarily serves one workflow such as tasks, agents, boards, or thread interactions, it belongs under that feature.
