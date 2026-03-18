# TypeScript / React Code Conventions

Applies to `dashboard/` excluding `dashboard/convex/` (see `convex.md`).

> **Cross-service naming**: see [`cross_service_naming.md`](cross_service_naming.md) for the shared naming contract between Python, Convex, and TypeScript.

## Tooling

| Tool | Command | Config |
|------|---------|--------|
| Formatter | `npx prettier --write .` | `.prettierrc` / `package.json` |
| Linter | `npx next lint` | `eslint.config.*` |
| Type checker | `npx tsc --noEmit` | `tsconfig.json` |
| Test runner | `npx vitest` | `vitest.config.ts` |
| Component library | shadcn/ui (New York style) | `components.json` |
| Styling | Tailwind CSS 3 | `tailwind.config.ts` |

### Pre-commit checks

```bash
cd dashboard
npx prettier --check .
npx next lint
npx tsc --noEmit
```

## Formatting (Prettier)

- **Print width**: 100
- **Quotes**: double quotes
- **Semicolons**: yes
- **Trailing commas**: yes (ES5)

## Project Structure

```
dashboard/
├── app/              # Next.js App Router (pages, layouts, API routes)
├── components/       # Shared UI components
│   └── ui/           # shadcn/ui primitives (do not edit directly)
├── features/         # Feature-first modules
│   └── tasks/
│       ├── components/   # Feature-specific UI
│       ├── hooks/        # Feature hooks (view-model pattern)
│       └── lib/          # Feature utilities
├── hooks/            # Shared hooks (prefer feature hooks)
└── lib/              # Shared utilities, constants, types
```

**Feature-first architecture**: each feature directory under `features/` owns its components, hooks, and utilities. Cross-feature dependencies should go through shared `hooks/` or `lib/`.

### Dependency rules

```
app/ → features/, components/, hooks/, lib/
features/ → components/, hooks/, lib/ (NOT other features/)
components/ → lib/, hooks/ (NOT features/, NOT convex/react)
hooks/ → lib/ (NOT components/, NOT features/)
lib/ → (nothing — leaf layer)
```

A feature can depend on shared code but **never on another feature**. If two features need shared logic, extract it to `lib/` or `hooks/`.

## Component Patterns

### Export style

**Named `function` exports** — no default exports (except Next.js pages/layouts):

```typescript
// CORRECT
export function TaskCard({ task }: TaskCardProps) {
  return <div>...</div>;
}

// WRONG — no default exports for components
export default function TaskCard() { ... }

// WRONG — no arrow function component exports
export const TaskCard = ({ task }: TaskCardProps) => { ... };
```

### Props

Use `interface` for component props:

```typescript
interface TaskCardProps {
  task: TaskData;
  onSelect: (id: string) => void;
  compact?: boolean;
}
```

- **Destructure in signature**: `({ task, onSelect }: TaskCardProps)`.
- **Children**: use `React.PropsWithChildren<Props>` or explicit `children: React.ReactNode`.
- **Event handlers**: name with `on` prefix (`onSelect`, `onDelete`). Internal handlers use `handle` prefix (`handleClick`, `handleSubmit`).

### Hooks — view-model pattern

Components consume data through hooks, never through direct Convex imports:

```typescript
// CORRECT — component uses a hook
import { useTaskDetail } from "@/features/tasks/hooks/useTaskDetail";

export function TaskDetail({ taskId }: TaskDetailProps) {
  const { task, isLoading } = useTaskDetail(taskId);
  // ...
}

// WRONG — component imports convex/react directly
import { useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
```

**`convex/react` imports are banned in `components/`** — enforced by ESLint `no-restricted-imports`. Feature hooks encapsulate all Convex access and return typed view-model objects.

### Custom hooks

```typescript
export function useTaskDetail(taskId: Id<"tasks">) {
  const task = useQuery(api.tasks.getById, { id: taskId });

  const updateStatus = useMutation(api.tasks.updateStatus);

  const handleComplete = useCallback(async () => {
    await updateStatus({ taskId, status: "completed" });
  }, [taskId, updateStatus]);

  return {
    task: task ?? null,
    isLoading: task === undefined,
    handleComplete,
  };
}
```

- Return an object, not a tuple (except for simple `[value, setter]` patterns).
- Wrap derived data in `useMemo` if computation is non-trivial.
- Wrap callbacks in `useCallback` to maintain referential stability.
- Handle the `undefined` (loading) state from `useQuery` — return `null` or an explicit `isLoading` flag.

### Styling

100% Tailwind utility classes. Use the `cn()` helper for conditional classes:

```typescript
import { cn } from "@/lib/utils";

<div className={cn("flex items-center gap-2", isActive && "bg-primary")} />
```

- No CSS modules, styled-components, or inline `style` objects.
- Use CSS variables (shadcn theme tokens) for colors: `bg-primary`, `text-muted-foreground`, etc.
- Responsive design: use Tailwind breakpoints (`sm:`, `md:`, `lg:`), mobile-first.
- Extract repeated class combinations into components, not into utility strings.

## Type Definitions

| Use case | Keyword | Example |
|----------|---------|---------|
| Component props | `interface` | `interface TaskCardProps { ... }` |
| Public API contracts (extendable) | `interface` | `interface PluginConfig { ... }` |
| Unions, intersections, mapped types | `type` | `type Status = "active" \| "done"` |
| Internal/derived types | `type` | `type TaskWithAgent = Task & { agent: Agent }` |
| Convex document shapes | `type` (from `Doc<>`) | `type TaskDoc = Doc<"tasks">` |

**Rule**: `interface` for props and extendable contracts. `type` for everything else.

## Imports

**Always use path aliases** — never relative imports to cross directory boundaries:

```typescript
// CORRECT
import { Button } from "@/components/ui/button";
import { useTaskDetail } from "@/features/tasks/hooks/useTaskDetail";
import { cn } from "@/lib/utils";

// WRONG — relative imports crossing boundaries
import { Button } from "../../components/ui/button";
import type { Id } from "../convex/_generated/dataModel";
```

Relative imports are acceptable only within the same feature directory (e.g., `./TaskCardActions` from `TaskCard.tsx`).

**Import order** (enforced by ESLint):
1. React / Next.js
2. Third-party libraries
3. `@/` path aliases (components, features, lib)
4. Relative imports (`./`)
5. Type-only imports (`import type`)

## File Naming

| Element | Convention | Example |
|---------|-----------|---------|
| Components | PascalCase `.tsx` | `TaskCard.tsx` |
| Hooks | camelCase `use*.ts` | `useTaskDetail.ts` |
| Utilities, constants | camelCase `.ts` | `formatDate.ts` |
| Test files | Source name + `.test.ts(x)` | `TaskCard.test.tsx` |
| Types-only files | camelCase `.ts` | `types.ts` |

No kebab-case filenames. If shadcn generates one (e.g., `use-mobile.tsx`), rename it to camelCase (`useIsMobile.ts`).

## Avoiding `any`

`any` is not allowed in production code without justification. Alternatives:

| Instead of | Use |
|-----------|-----|
| `any` for unknown shape | `unknown` + type guard |
| `any` for Convex doc | `Doc<"tableName">` |
| `any` for generic callback | `(...args: unknown[]) => unknown` |
| `any` in test mocks | `as unknown as Id<"table">` |
| `any` for event handlers | `React.MouseEvent<HTMLButtonElement>` |
| `any` for API responses | Define a response type or use `unknown` + validation |

If `any` is truly unavoidable, add a `// eslint-disable-next-line` with a comment explaining why.

## `"use client"` Directive

Required on any file that:
- Uses React hooks (`useState`, `useEffect`, `useQuery`, etc.)
- Uses browser APIs (`window`, `document`, `localStorage`)
- Renders interactive elements with event handlers

Not needed on:
- Server components (the default in App Router)
- Pure utility/type files
- Files that only export types

## Error Handling

- **Error boundaries**: wrap feature-level component trees, not individual components.
- **Loading states**: every `useQuery` hook must handle the `undefined` (loading) state. Return explicit `isLoading` from hooks.
- **Null checks**: prefer early returns over deeply nested conditionals.
- **ConvexError on the frontend**: catch structured errors from mutations:
  ```typescript
  try {
    await doMutation(args);
  } catch (error) {
    if (error instanceof ConvexError) {
      toast.error(error.data as string);
    }
  }
  ```
- **Never swallow errors silently** — always log or display to user.

## React Best Practices

### State management

- **Local state first**: `useState` for component-scoped state.
- **Convex as server state**: `useQuery` / `useMutation` — no separate client cache layer.
- **Context sparingly**: only for cross-cutting concerns (theme, auth, board context). Not for prop drilling avoidance in a single feature tree.
- **No global state libraries** (Redux, Zustand) — Convex handles server state, React handles UI state.

### Performance

- **`useMemo`** for expensive derived computations — not for every variable.
- **`useCallback`** for callbacks passed to child components or used in dependency arrays.
- **Key prop**: always use stable, unique keys in lists — never array index.
- **Avoid unnecessary re-renders**: extract components that receive changing props into separate components.

### Conditional rendering

Prefer early returns for guard clauses:

```typescript
// CORRECT
export function TaskDetail({ taskId }: TaskDetailProps) {
  const { task, isLoading } = useTaskDetail(taskId);

  if (isLoading) return <Skeleton />;
  if (!task) return <NotFound />;

  return <div>{task.title}</div>;
}

// WRONG — nested ternaries
export function TaskDetail({ taskId }: TaskDetailProps) {
  const { task, isLoading } = useTaskDetail(taskId);

  return isLoading ? <Skeleton /> : task ? <div>{task.title}</div> : <NotFound />;
}
```

## Testing

- **Framework**: Vitest + React Testing Library.
- **Co-located tests**: `TaskCard.test.tsx` next to `TaskCard.tsx`.
- **Mock hooks, not Convex**: tests mock feature hooks with `vi.mock()`, never raw Convex queries.
- **Typed test data**: use factory functions (`makeTask()`) returning properly typed objects.
- **Architecture tests**: `tests/architecture.test.ts` enforces feature boundaries — these must always pass.
- **Test behavior, not implementation**: assert what the user sees, not internal component state.

```typescript
it("renders task title and status badge", () => {
  render(<TaskCard task={makeTask({ title: "Fix bug", status: "running" })} />);

  expect(screen.getByText("Fix bug")).toBeInTheDocument();
  expect(screen.getByText("running")).toBeInTheDocument();
});
```

## ESLint Rules

Key rules enforced:

| Rule | Purpose |
|------|---------|
| `no-restricted-imports` | Blocks `convex/react` in `components/` |
| `no-explicit-any` | Prevents untyped code |
| `prefer-const` | Immutable by default |
| `react/display-name` | Components must be named (for DevTools) |
| `@next/next/core-web-vitals` | Performance rules |

## Accessibility

- Use semantic HTML elements (`button`, `nav`, `main`, not `div` with `onClick`).
- All interactive elements must be keyboard-accessible.
- Images need `alt` text. Decorative images use `alt=""`.
- shadcn/ui components handle most a11y — do not override `aria-*` props without reason.
- Focus management: modals and drawers must trap focus and return it on close.
