# Story 33.5: Run Formatters and Linters Across All Layers

Status: ready-for-dev

## Story

As a developer,
I want all code formatted and linted according to the new conventions,
so that the codebase has a clean, uniform baseline going forward.

## Acceptance Criteria

1. `uv run ruff format mc/ tests/mc/` reformats all files with zero remaining drift
2. `uv run ruff check mc/ tests/mc/` passes with zero errors (new rules: UP, B, RUF)
3. `cd dashboard && npx prettier --write .` reformats all 104+ files
4. `cd dashboard && npx next lint` passes with zero errors (or known exceptions documented)
5. `pyproject.toml` has the updated ruff rules and pyright config
6. All changes committed as a single formatting baseline commit

## Tasks / Subtasks

- [ ] Task 1: Apply Python formatter (AC: #1)
  - [ ] Run `uv run ruff format mc/ tests/mc/`
  - [ ] This will reformat ~99 files
  - [ ] Review diff — purely whitespace/formatting changes

- [ ] Task 2: Apply Python linter auto-fixes (AC: #2)
  - [ ] Run `uv run ruff check mc/ tests/mc/ --fix`
  - [ ] This auto-fixes ~119 violations (I001 import sorting, W293 whitespace, some F401)
  - [ ] Manually fix remaining non-auto-fixable violations
  - [ ] The new UP rule will flag `Optional[]` (should be fixed by Story 33.1)
  - [ ] The new B rule will flag mutable defaults (fix case by case)
  - [ ] The new RUF rule will flag unused `noqa` directives (remove them)

- [ ] Task 3: Apply TypeScript formatter (AC: #3)
  - [ ] Run `cd dashboard && npx prettier --write .`
  - [ ] This will reformat ~104 files
  - [ ] Review diff — purely formatting changes

- [ ] Task 4: Fix remaining ESLint errors (AC: #4)
  - [ ] Run `cd dashboard && npx next lint`
  - [ ] Address `no-explicit-any` violations (81+ instances) — fix what's simple, add eslint-disable with comment for complex cases
  - [ ] Fix `prefer-const` violations
  - [ ] Fix `no-require-imports` violations (3 instances)
  - [ ] Document any exceptions that remain with rationale

- [ ] Task 5: Verify pyproject.toml config (AC: #5)
  - [ ] Confirm ruff rules: `["E", "F", "I", "N", "W", "UP", "B", "RUF"]`
  - [ ] Confirm per-file-ignores for tests: `"tests/**" = ["N803", "N806"]`
  - [ ] Confirm `extend-exclude = ["vendor/nanobot"]` (not all vendor/)
  - [ ] Confirm pyright config in `[tool.pyright]`
  - [ ] Confirm pyright in dev dependencies

- [ ] Task 6: Commit formatting baseline (AC: #6)
  - [ ] Stage all formatting changes
  - [ ] Commit with message: "style: apply formatting baseline across Python, Convex, and TypeScript"
  - [ ] This commit should be formatting-only — no logic changes

## Dev Notes

- **This story must run LAST** (after stories 33.1-33.4) because code changes from those stories would be reformatted again.
- The formatting commit should be a single commit to keep git blame useful. Consider adding the commit hash to `.git-blame-ignore-revs` afterward.
- The 81+ `any` violations in TypeScript may not all be fixable in this pass. For those that remain, add `// eslint-disable-next-line @typescript-eslint/no-explicit-any -- <reason>`.
- Python formatting is purely cosmetic (ruff format). The linter fixes include import reordering which is also safe.

### Execution Order

```
Story 33.1 (Python types)     — can run in parallel with 33.2, 33.4
Story 33.2 (Convex validators) — must run before 33.3
Story 33.3 (Convex boundary)   — depends on 33.2
Story 33.4 (TypeScript)        — can run in parallel with 33.1, 33.2
Story 33.5 (Formatters)        — must run LAST after all others
```

### References

- [Source: agent_docs/code_conventions/python.md#Tooling] — ruff commands
- [Source: agent_docs/code_conventions/typescript.md#Tooling] — prettier/eslint commands
- [Source: pyproject.toml] — ruff and pyright configuration
