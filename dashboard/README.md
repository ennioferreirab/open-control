# Dashboard

The dashboard is the web UI for Open Control.

It is built with:

- Next.js App Router
- React
- TypeScript
- Convex for realtime data and mutations
- Vitest for frontend architecture and behavior tests

## Development

```bash
npm install
npm run dev
```

## Baseline Checks

```bash
npm run format:check
npm run lint
npm run typecheck
npm run test
npm run test:architecture
```

For quick local iteration on touched files:

```bash
npm run format:file:check -- path/to/file.tsx
npm run lint:file -- path/to/file.tsx
```

## Ownership Model

The dashboard is being migrated to a feature-first structure under `dashboard/features/`.

Current shared layers:

- `app/` for routing and page composition
- `components/ui/` for reusable UI primitives
- `components/viewers/` for shared document and media viewers
- `convex/` for data contract boundaries
- `lib/` for truly cross-feature utilities

Feature ownership should move into:

- `features/<feature>/components/` for feature UI
- `features/<feature>/hooks/` for orchestration and view-model hooks
- `features/<feature>/lib/` for pure feature helpers

## Architecture Rules

- Feature UI should not import `convex/react` directly.
- Feature hooks may depend on Convex/read-model layers but must not depend on feature UI components.
- `app/` should compose feature entry points instead of becoming the home for feature logic.
- New logic should land in the owning feature, not in broad root-level buckets by default.

See `dashboard/tests/architecture.test.ts` for the currently enforced guardrails.
