# Open Control Rebrand Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebrand the project from nanobot/Mission Control to Open Control at the public product layer, while preserving runtime compatibility until filesystem and backend contracts are explicitly migrated.

**Architecture:** Treat the rename as a layered migration, not a global search-and-replace. Phase 1 rewrites the public front door and OSS posture; Phase 2 aligns visible UI and contributor surfaces; Phase 3 adds public package and CLI aliases; Phase 4 introduces compatibility abstractions for runtime naming; Phase 5 is an optional breaking migration only after dual-support ships and stabilizes.

**Tech Stack:** Python 3.11+, Typer CLI, Next.js 16, React 19, Convex, Vitest, Pytest, GitHub Actions.

---

## Naming Policy And Defaults

Use these assumptions unless a human overrides them before implementation:

- Public product name: `Open Control`
- Public app/UI name: `Open Control`
- Internal term `Mission Control`: retire from public UI and top-level docs; allow only where it is describing historical architecture
- `nanobot`: describe only as the current upstream runtime dependency / compatibility layer
- Public CLI target: `open-control`
- Compatibility CLI alias: keep `nanobot` working for at least one release cycle
- Runtime home migration: do not rename `~/.nanobot` in the first public rebrand release

### Task 1: Freeze Public Naming And OSS Launch Policy

**Files:**
- Create: `docs/ARCHITECTURE.md`
- Modify: `README.md`
- Modify: `CONTRIBUTING.md`
- Modify: `LICENSE`
- Test: no new automated tests

**Step 1: Create a short naming-policy section in `README.md`**

Include:
- `Open Control` as the primary public name
- one sentence that `vendor/nanobot` remains an implementation dependency
- one sentence that `nanobot` commands and `~/.nanobot` are currently compatibility surfaces

**Step 2: Create `docs/ARCHITECTURE.md`**

Add:
- system overview
- owned layers (`mc/`, `dashboard/`, `shared/`)
- vendor boundary for `vendor/nanobot/`
- note that runtime compatibility names still exist internally

**Step 3: Update `CONTRIBUTING.md`**

Replace:
- `nanobot-mcontrol` clone paths
- public references to `nanobot` as the product name

Keep:
- actual developer commands that still work today
- an explicit note when a command still uses the compatibility CLI alias

**Step 4: Update `LICENSE` copyright line**

Change `nanobot contributors` to the intended Open Control holder string chosen by maintainers.

**Step 5: Verify docs are coherent**

Run:
```bash
rg -n '(?i)nanobot-mcontrol|nanobot mission control|open mission control' README.md CONTRIBUTING.md docs/ARCHITECTURE.md LICENSE
```

Expected:
- No stale public-brand strings remain except deliberate compatibility notes

**Step 6: Commit**

```bash
git add README.md CONTRIBUTING.md LICENSE docs/ARCHITECTURE.md
git commit -m "docs: define open control public naming policy"
```

### Task 2: Rewrite The Public Front Door For Open Source

**Files:**
- Modify: `README.md`
- Create: `SECURITY.md`
- Create: `CODE_OF_CONDUCT.md`
- Create: `.github/ISSUE_TEMPLATE/bug_report.md`
- Create: `.github/ISSUE_TEMPLATE/feature_request.md`
- Create: `.github/pull_request_template.md`
- Test: no new automated tests

**Step 1: Rewrite `README.md` hero and positioning**

Replace the current upstream-first structure with:
- Open Control headline
- what the product does today
- who it is for
- owned architecture summary
- install/run story for this repo

**Step 2: Remove or replace upstream-only links and assets**

Replace:
- HKUDS release links
- HKUDS roadmap / PR links
- upstream badges
- upstream contributors widgets
- upstream star history widgets
- missing `COMMUNICATION.md` link

**Step 3: Add OSS governance files**

Create:
- `SECURITY.md` with disclosure path and scope
- `CODE_OF_CONDUCT.md`
- issue templates
- PR template with validation checklist

**Step 4: Add a short "Start Here" section to `README.md`**

Include:
- `uv sync`
- `make start`
- `make validate`
- where the dashboard lives
- Convex singleton warning

**Step 5: Add an explicit vendor boundary note**

In `README.md`, state:
- do not edit `vendor/nanobot/` without explicit approval
- Open Control owns orchestration, dashboard, and local platform glue

**Step 6: Verify repo front door**

Run:
```bash
rg -n 'HKUDS/nanobot|nanobot-ai|COMMUNICATION.md|Open Mission Control' README.md .github SECURITY.md CODE_OF_CONDUCT.md
```

Expected:
- No upstream public links remain unless deliberately labeled as upstream dependency references

**Step 7: Commit**

```bash
git add README.md SECURITY.md CODE_OF_CONDUCT.md .github/ISSUE_TEMPLATE .github/pull_request_template.md
git commit -m "docs: prepare open control open source front door"
```

### Task 3: Align Visible App Copy And Contributor Surfaces

**Files:**
- Modify: `dashboard/app/layout.tsx`
- Modify: `dashboard/app/login/page.tsx`
- Modify: `dashboard/README.md`
- Modify: `CHANGELOG.md`
- Modify: `CLAUDE.md`
- Modify: `docs/design-book/index.md`
- Modify: `docs/design-book/mood-board.md`
- Modify: `docs/design-book/tokens.md`
- Modify: `docs/design-audit/current-inventory.md`
- Test: `dashboard/app/login/LoginPage.test.tsx`
- Test: `dashboard/components/DashboardLayout.test.tsx`
- Test: `dashboard/e2e/dashboard-smoke.spec.ts`

**Step 1: Rename visible dashboard product copy**

Update:
- browser title
- metadata description
- login card title
- desktop header title

Public strings should say `Open Control`.

**Step 2: Update dashboard and contributor docs**

Align:
- `dashboard/README.md`
- `CHANGELOG.md`
- `CLAUDE.md`

Keep compatibility commands when they still shell out to `nanobot`, but mark them as current runtime commands rather than brand identity.

**Step 3: Update design docs that would appear in public repo review**

Change the visible project naming in the design-book and design-audit docs to `Open Control`.

**Step 4: Update UI tests for the new product name**

Adjust assertions in:
- `dashboard/app/login/LoginPage.test.tsx`
- `dashboard/components/DashboardLayout.test.tsx`
- `dashboard/e2e/dashboard-smoke.spec.ts`

**Step 5: Run targeted frontend verification**

Run:
```bash
cd dashboard && npx vitest run app/login/LoginPage.test.tsx components/DashboardLayout.test.tsx
```

Run:
```bash
cd dashboard && npx playwright test e2e/dashboard-smoke.spec.ts
```

Expected:
- UI tests assert `Open Control`
- smoke flow still loads the app shell successfully

**Step 6: Commit**

```bash
git add dashboard/app/layout.tsx dashboard/app/login/page.tsx dashboard/README.md CHANGELOG.md CLAUDE.md docs/design-book docs/design-audit dashboard/app/login/LoginPage.test.tsx dashboard/components/DashboardLayout.test.tsx dashboard/e2e/dashboard-smoke.spec.ts
git commit -m "docs: align app and contributor surfaces with open control"
```

### Task 4: Add Public Package And CLI Naming Without Breaking Existing Users

**Files:**
- Modify: `pyproject.toml`
- Modify: `boot.py`
- Modify: `Makefile`
- Modify: `README.md`
- Modify: `CONTRIBUTING.md`
- Modify: `mc/cli/__init__.py`
- Modify: `mc/cli/lifecycle.py`
- Test: `tests/mc/test_cli_lifecycle.py`
- Test: `tests/mc/test_cli_status.py`
- Test: add focused CLI alias coverage if needed

**Step 1: Add a second public CLI entrypoint in `pyproject.toml`**

Keep:
- `nanobot = "boot:cli"`

Add:
- `open-control = "boot:cli"`

Also update project metadata away from `nanobot-mcontrol`.

**Step 2: Update public docs to prefer `open-control`**

Replace public examples in:
- `README.md`
- `CONTRIBUTING.md`
- `Makefile` comments

Do not remove `nanobot` examples that are needed for compatibility notes.

**Step 3: Update CLI help copy**

In `mc/cli/__init__.py` and `mc/cli/lifecycle.py`:
- describe the product as `Open Control`
- avoid telling users only `nanobot mc start`
- if examples are shown, prefer `open-control mc start`

**Step 4: Preserve runtime compatibility**

Do not change:
- vendor import namespace `nanobot.*`
- runner/provider keys
- parser prefixes like `[nanobot-live]`

**Step 5: Run targeted CLI verification**

Run:
```bash
uv run pytest tests/mc/test_cli_lifecycle.py tests/mc/test_cli_status.py
```

Expected:
- help and status output reflects `Open Control`
- no compatibility regression in lifecycle commands

**Step 6: Commit**

```bash
git add pyproject.toml boot.py Makefile README.md CONTRIBUTING.md mc/cli/__init__.py mc/cli/lifecycle.py tests/mc/test_cli_lifecycle.py tests/mc/test_cli_status.py
git commit -m "feat: add open control public cli alias"
```

### Task 5: Decouple Public Branding From Runtime Contracts

**Files:**
- Create: `mc/infrastructure/runtime_home.py`
- Modify: `mc/infrastructure/config.py`
- Modify: `mc/infrastructure/runtime_context.py`
- Modify: `dashboard/app/api/channels/route.ts`
- Modify: `dashboard/app/api/agents/[agentName]/config/route.ts`
- Modify: `dashboard/app/api/agents/[agentName]/memory/[filename]/route.ts`
- Modify: `dashboard/app/api/boards/[boardName]/artifacts/route.ts`
- Modify: `dashboard/app/api/tasks/[taskId]/files/route.ts`
- Modify: `dashboard/app/api/settings/global-orientation-default/route.ts`
- Modify: `dashboard/lib/constants.ts`
- Modify: `dashboard/features/agents/hooks/useNanobotProvider.ts`
- Modify: `dashboard/app/api/agents/create/route.ts`
- Test: dashboard route tests covering filesystem paths
- Test: `tests/mc/infrastructure/test_config.py`
- Test: `tests/mc/infrastructure/test_runtime_context.py`

**Step 1: Introduce a single runtime-home resolver**

Create `mc/infrastructure/runtime_home.py` with functions that:
- resolve the preferred Open Control home name
- fall back to `~/.nanobot`
- expose helper paths for agents, boards, tasks, workspace, config, secrets

**Step 2: Switch Python runtime code to use the resolver**

Replace direct `Path.home() / ".nanobot"` call sites in the files listed above with resolver calls.

**Step 3: Switch dashboard server routes to use one shared home-root helper**

Create a small server-side helper in `dashboard/` if needed so API routes stop hardcoding `join(homedir(), ".nanobot", ...)`.

**Step 4: Keep the public label separate from the internal agent key**

Do not rename the stored `nanobot` system agent key yet.
Instead:
- update copy and descriptions
- preserve underlying routing key
- introduce a display label such as `Open Control Core` if desired

**Step 5: Add compatibility env-var reads**

Where branded env vars are read, prefer:
- `OPEN_CONTROL_*`
- fall back to `NANOBOT_*`

Do not remove legacy env vars in this phase.

**Step 6: Run targeted path and route tests**

Run:
```bash
uv run pytest tests/mc/infrastructure/test_config.py tests/mc/infrastructure/test_runtime_context.py tests/mc/bridge/test_repositories.py tests/mc/test_bridge.py
```

Run:
```bash
cd dashboard && npx vitest run app/api/cron/route.test.ts app/api/agents/[agentName]/config/route.test.ts app/api/settings/global-orientation-default/route.test.ts app/api/tasks/[taskId]/files/[subfolder]/[filename]/route.test.ts
```

Expected:
- legacy path still works
- path resolution is centralized
- no direct hardcoded `.nanobot` references remain in the updated files

**Step 7: Commit**

```bash
git add mc/infrastructure/runtime_home.py mc/infrastructure/config.py mc/infrastructure/runtime_context.py dashboard/app/api dashboard/lib/constants.ts dashboard/features/agents/hooks/useNanobotProvider.ts tests/mc/infrastructure/test_config.py tests/mc/infrastructure/test_runtime_context.py tests/mc/bridge/test_repositories.py tests/mc/test_bridge.py
git commit -m "refactor: centralize open control runtime naming compatibility"
```

### Task 6: Optional Full Runtime Migration After One Stable Release

**Files:**
- Modify: `mc/types.py`
- Modify: `mc/infrastructure/agent_bootstrap.py`
- Modify: `mc/contexts/execution/executor_routing.py`
- Modify: `mc/contexts/execution/step_dispatcher.py`
- Modify: `agent_docs/harness_engineering.md`
- Modify: `agent_docs/service_architecture.md`
- Modify: `agent_docs/service_communication_patterns.md`
- Modify: `agent_docs/scaling_decisions.md`
- Test: `tests/mc/test_nanobot_agent.py`
- Test: `tests/mc/test_sync_nanobot_model.py`
- Test: any route and integration suites affected by agent-key changes

**Step 1: Decide whether the internal system agent key must change**

If not required, stop here and keep `nanobot` as an internal compatibility identifier.

**Step 2: If changing it, add alias support before migration**

Support both:
- old key: `nanobot`
- new key: chosen Open Control system-agent key

Add data migration or read-time normalization before removing the old key.

**Step 3: Update structural contracts and tests**

Revise all contract docs and tests that assert the old key or old home layout.

**Step 4: Ship migration tooling**

Provide:
- one migration command or script
- rollback instructions
- release notes describing the break

**Step 5: Run full validation**

Run:
```bash
make validate
```

Expected:
- all Python, dashboard, and architecture checks pass

**Step 6: Commit**

```bash
git add mc/types.py mc/infrastructure/agent_bootstrap.py mc/contexts/execution/executor_routing.py mc/contexts/execution/step_dispatcher.py agent_docs tests/mc
git commit -m "feat: migrate open control runtime identifiers"
```

## Final Verification Gate

After Tasks 1-5 are complete, run:

```bash
make validate
```

Then run a final audit:

```bash
rg -n --hidden --glob '!vendor/nanobot/**' --glob '!.git/**' '(?i)nanobot|mission control|open mission control' README.md CONTRIBUTING.md pyproject.toml dashboard mc agent_docs .github
```

Expected:
- `Open Control` is the only public-facing brand
- remaining `nanobot` matches compatibility surfaces, runtime contracts, vendor references, or clearly labeled migration notes

## Release Notes Checklist

- Explain that Open Control is the new public name
- Call out that `nanobot` CLI and `~/.nanobot` remain supported for compatibility
- Document the preferred new command
- Document any new env-var aliases
- Link to migration notes if runtime-home abstraction shipped
