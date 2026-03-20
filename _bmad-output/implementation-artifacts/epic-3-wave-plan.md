# Epic 3 — Runtime Home Migration — Wave Plan

## Wave 1: Foundation (parallel)

| Story | Agent | Worktree branch |
|-------|-------|-----------------|
| 3-1 runtime_home logging | Sonnet A | `feat/3-1-runtime-home-logging` |
| 3-2 secrets/PID/config/orientation | Sonnet B | `feat/3-2-secrets-pid-config` |

**Gate:** `make validate` → Opus code review → merge both to main

## Wave 2: Bulk Python migration (parallel)

| Story | Agent | Worktree branch |
|-------|-------|-----------------|
| 3-3 agents domain | Sonnet C | `feat/3-3-agents-domain` |
| 3-4 tasks domain | Sonnet D | `feat/3-4-tasks-domain` |
| 3-5 boards + workspace | Sonnet E | `feat/3-5-boards-workspace` |
| 3-6 cron + memory settings | Sonnet F | `feat/3-6-cron-memory` |

**Dependency:** Wave 1 merged (stories import from runtime_home.py which gets logging in 3-1)
**Note:** Stories 3-5 and 3-6 both touch `agent_bootstrap.py` but at non-overlapping lines (3-5: lines 147, 264, 349; 3-6: line 622). Merge 3-5 first, then 3-6.
**Gate:** `make validate` → Opus code review → merge to main

## Wave 3: Dashboard + tests (parallel)

| Story | Agent | Worktree branch |
|-------|-------|-----------------|
| 3-7 dashboard routes | Sonnet G | `feat/3-7-dashboard-routes` |
| 3-8 test path assertions | Sonnet H | `feat/3-8-test-paths` |

**Dependency:** Wave 2 merged (tests must reflect migrated code)
**Gate:** `make validate` → Opus code review → `make docker-test` → merge to main

## Final validation

After Wave 3 merge:
1. `make validate` — lint + typecheck + all tests
2. `grep -r '\.nanobot' mc/ dashboard/lib/ dashboard/app/ --include='*.py' --include='*.ts' --include='*.tsx' | grep -v vendor/ | grep -v node_modules/ | grep -v _bmad | grep -v tests/ | grep -v '\.md'` — verify no remaining hardcoded paths in source (docstrings/comments OK)
3. `make docker-test` — full stack starts correctly
