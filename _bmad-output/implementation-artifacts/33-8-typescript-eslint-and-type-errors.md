# Story 33.8: Fix TypeScript ESLint and Type Errors

Status: ready-for-dev

## Story

As a developer,
I want all TypeScript lint and type errors resolved,
so that the frontend codebase has verified type safety and lint compliance.

## Current State

- ESLint: 96 errors, 17 warnings
- TypeScript (`tsc --noEmit`): 65 errors (all in 1 test file)

## Acceptance Criteria

1. `npx eslint .` passes with zero errors (warnings are acceptable for now)
2. `npx tsc --noEmit` passes with zero errors
3. No `eslint-disable` without a documented reason
4. No behavioral changes

## Tasks / Subtasks

- [ ] Task 1: Fix `no-explicit-any` violations (~90 instances)
  - [ ] Audit each `any` usage and replace with proper types:
    - Use `unknown` + type guard for truly unknown shapes
    - Use `Doc<"tableName">` for Convex documents
    - Use specific callback types for event handlers
    - Use `Record<string, unknown>` for generic objects
  - [ ] For genuinely unavoidable `any`, add `// eslint-disable-next-line` with reason

- [ ] Task 2: Fix `no-restricted-imports` violations (3 instances)
  - [ ] Remaining `convex/react` imports in component files
  - [ ] Extract to hooks following the view-model pattern

- [ ] Task 3: Fix `no-require-imports` violations (3 instances)
  - [ ] Convert `require()` calls to ES module `import` statements

- [ ] Task 4: Fix TypeScript branded ID errors (65 instances)
  - [ ] All in `features/interactive/hooks/useTaskInteractiveSession.test.ts`
  - [ ] Replace string literals with `as unknown as Id<"interactiveSessions">` pattern
  - [ ] Consider creating a test helper: `testId<T>(value: string): Id<T>`

- [ ] Task 5: Fix ESLint warnings (17 instances)
  - [ ] `no-unused-vars` — remove or prefix with `_`
  - [ ] `jsx-a11y/role-has-required-aria-props` — add missing ARIA attributes
  - [ ] React compiler warnings — review and fix or suppress with reason

## Dev Notes

- Task 1 is the bulk. Many `any` types are in hook return values or API route handlers. Replace with the actual shape being returned.
- Task 4 is mechanical — all 65 errors are the same pattern in one test file.
- Consider doing Task 4 first as it clears 65 errors in one file.
