# Story 1.1: Initialize Dashboard Project with Starter Template

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want to initialize the Mission Control dashboard using the official Convex Next.js + ShadCN starter template,
So that I have a working foundation with the correct tech stack and monorepo structure to build on.

## Acceptance Criteria

1. **Given** the nanobot-ennio project root exists, **When** the developer runs the Convex starter template command inside a `dashboard/` directory, **Then** a Next.js + TypeScript + Convex + Tailwind CSS + ShadCN UI project is created inside `dashboard/`
2. **Given** the dashboard project is initialized, **Then** the monorepo structure has `dashboard/` as a sibling to the existing `nanobot/` package
3. **Given** the dashboard project is initialized, **Then** `dashboard/app/`, `dashboard/components/`, `dashboard/convex/`, `dashboard/lib/` directories exist
4. **Given** the dashboard project is initialized, **Then** `motion` (formerly framer-motion) is added as a dependency
5. **Given** the dashboard project is initialized, **Then** required ShadCN components are installed via CLI: Card, Badge, Sheet, Tabs, ScrollArea, Avatar, Sidebar, Tooltip, Separator, Collapsible, Switch, Select, Checkbox, Input, Textarea, Button
6. **Given** the dashboard project is initialized, **Then** `dashboard/.env.example` is created with `NEXT_PUBLIC_CONVEX_URL` and `MC_ACCESS_TOKEN` placeholders
7. **Given** the dashboard project is fully set up, **When** `npm run dev` is executed from `dashboard/`, **Then** the Next.js dev server starts at localhost:3000 successfully

## Tasks / Subtasks

- [ ] Task 1: Initialize dashboard project with Convex starter template (AC: #1, #2, #3)
  - [ ] 1.1: Run `npm create convex@latest -- -t nextjs-shadcn` to scaffold `dashboard/` directory
  - [ ] 1.2: Verify monorepo structure — `dashboard/` is sibling to `nanobot/`
  - [ ] 1.3: Verify core directories exist: `app/`, `components/`, `convex/`, `lib/`
  - [ ] 1.4: Clean up any boilerplate/sample code from the template that won't be needed
- [ ] Task 2: Install additional dependencies (AC: #4)
  - [ ] 2.1: Install `motion` package: `npm install motion` from `dashboard/`
  - [ ] 2.2: Verify motion import works: `import { motion } from "motion/react"`
- [ ] Task 3: Install required ShadCN UI components (AC: #5)
  - [ ] 3.1: Run `npx shadcn@latest add card badge sheet tabs scroll-area avatar sidebar tooltip separator collapsible switch select checkbox input textarea button` from `dashboard/`
  - [ ] 3.2: Verify all 16 components are installed in `dashboard/components/ui/`
- [ ] Task 4: Create environment configuration (AC: #6)
  - [ ] 4.1: Create `dashboard/.env.example` with `NEXT_PUBLIC_CONVEX_URL=` and `MC_ACCESS_TOKEN=` placeholders
  - [ ] 4.2: Ensure `.env.local` is in `dashboard/.gitignore`
- [ ] Task 5: Verify development server starts (AC: #7)
  - [ ] 5.1: Run `npm run dev` from `dashboard/` and confirm localhost:3000 is accessible
  - [ ] 5.2: Verify no console errors on initial load
  - [ ] 5.3: Verify Convex dev server connects (or document Convex setup steps if deployment hasn't been created yet)

## Dev Notes

### Critical Architecture Requirements

- **Monorepo structure**: `dashboard/` is a NEW directory at the project root, sibling to the existing `nanobot/` Python package. Do NOT nest it inside `nanobot/`.
- **Starter template**: Use `get-convex/template-nextjs-shadcn` — the minimal template WITHOUT authentication. Auth (simple access token) is handled separately in Story 7.4.
- **No business logic in this story**: This story ONLY scaffolds the project. No custom components, no Convex schema, no routing — those come in Stories 1.2+.

### Library Version Intelligence (from web research, Feb 2026)

| Library | Package | Key Notes |
|---------|---------|-----------|
| **Motion** (formerly Framer Motion) | `motion` (NOT `framer-motion`) | Rebranded Nov 2024. Import: `import { motion } from "motion/react"`. Latest: v12.34.3. API compatible with framer-motion. |
| **ShadCN UI** | `shadcn` CLI | Command: `npx shadcn@latest add <components>`. CLI v3.0+ supports namespaced registries. |
| **Convex Python SDK** | `convex` (PyPI) | v0.7.0 (alpha). Wraps Rust client via PyO3. Supports async subscriptions. For later stories. |
| **Next.js 15+** | `next` | Async APIs (`cookies()`, `headers()`, `params`). `GET` handlers not cached by default. Node.js 18.18.0+ required. |

### Important: `motion` NOT `framer-motion`

The architecture document references `framer-motion`, but the library has been rebranded to `motion` as of November 2024. The new package is `motion` and imports are from `"motion/react"` instead of `"framer-motion"`. The API is compatible. All subsequent stories MUST use `motion` package and import paths.

### ShadCN Components Checklist

All 16 required components to install:

| # | Component | Purpose in Mission Control |
|---|-----------|---------------------------|
| 1 | Card | TaskCard on Kanban board |
| 2 | Badge | Status indicators, notification counts |
| 3 | Sheet | TaskDetailSheet (480px slide-out) |
| 4 | Tabs | Task detail sections (Thread, Execution Plan, Config) |
| 5 | ScrollArea | Activity feed, Kanban column overflow |
| 6 | Avatar | Agent icons on cards and sidebar |
| 7 | Sidebar | Agent sidebar (sidebar-07 pattern, collapsible) |
| 8 | Tooltip | Agent status details on hover (collapsed mode) |
| 9 | Separator | Visual dividers in sidebar and detail panel |
| 10 | Collapsible | Execution plan expand/collapse, progressive disclosure |
| 11 | Switch | Review toggle in task creation, settings |
| 12 | Select | Agent selector, reviewer selector |
| 13 | Checkbox | "Require human approval" in task creation |
| 14 | Input | Task creation text field |
| 15 | Textarea | Rejection feedback inline field |
| 16 | Button | Approve, Deny, Create task actions |

### Expected Directory Structure After Completion

```
nanobot-ennio/                    # Existing project root
├── nanobot/                      # Existing Python package (UNCHANGED)
│   ├── agent/
│   ├── bus/
│   ├── channels/
│   ├── cli/
│   ├── config/
│   ├── ...
├── dashboard/                    # NEW — created by this story
│   ├── package.json
│   ├── package-lock.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── postcss.config.mjs
│   ├── eslint.config.mjs
│   ├── components.json           # ShadCN UI config
│   ├── .env.example              # NEW — created manually
│   ├── .env.local                # NOT committed (gitignored)
│   ├── app/
│   │   ├── globals.css
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── components/
│   │   └── ui/                   # 16 ShadCN components installed
│   │       ├── button.tsx
│   │       ├── card.tsx
│   │       ├── badge.tsx
│   │       ├── input.tsx
│   │       ├── textarea.tsx
│   │       ├── sheet.tsx
│   │       ├── tabs.tsx
│   │       ├── scroll-area.tsx
│   │       ├── avatar.tsx
│   │       ├── tooltip.tsx
│   │       ├── separator.tsx
│   │       ├── collapsible.tsx
│   │       ├── switch.tsx
│   │       ├── select.tsx
│   │       ├── checkbox.tsx
│   │       └── sidebar.tsx
│   ├── convex/
│   │   ├── _generated/           # Auto-generated by Convex CLI
│   │   └── ...                   # Schema comes in Story 1.2
│   ├── lib/
│   │   └── utils.ts              # ShadCN cn() utility
│   └── public/
│       └── favicon.ico
├── workspace/                    # Existing (UNCHANGED)
├── tests/                        # Existing (UNCHANGED)
└── docs/                         # Existing (UNCHANGED)
```

### What This Story Does NOT Include

- **No Convex schema definition** — that's Story 1.2
- **No custom React components** — those start in Story 2.1 (DashboardLayout)
- **No Python code changes** — Mission Control Python package (`nanobot/mc/`) starts in Story 1.3
- **No authentication** — access token auth is Story 7.4
- **No Convex deployment setup** — the dev will need to run `npx convex dev` separately to create a Convex project; this story focuses on the dashboard scaffold

### Convex Project Initialization Note

When running the starter template, the Convex CLI may prompt to:
1. Create a new Convex project or link to an existing one
2. Set up the `CONVEX_DEPLOYMENT` and `NEXT_PUBLIC_CONVEX_URL` environment variables

The developer should create a new Convex project for nanobot Mission Control during initialization. The `.env.local` file with Convex deployment URL will be auto-generated by the Convex CLI setup.

### Project Structure Notes

- **Alignment**: Dashboard directory structure follows the architecture document exactly [Source: `_bmad-output/planning-artifacts/architecture.md#Project Structure & Boundaries`]
- **Brownfield context**: The `nanobot/` Python package already exists with agent/, bus/, channels/, cli/, config/, cron/, heartbeat/, providers/, session/, utils/ modules. This story adds `dashboard/` as a new peer directory — zero changes to existing code.
- **No conflicts detected**: The `dashboard/` directory does not exist yet. No naming collisions with existing project structure.

### References

- [Source: `_bmad-output/planning-artifacts/architecture.md#Starter Template Evaluation`] — Template selection rationale and initialization command
- [Source: `_bmad-output/planning-artifacts/architecture.md#Project Structure & Boundaries`] — Complete directory structure specification
- [Source: `_bmad-output/planning-artifacts/architecture.md#Implementation Patterns & Consistency Rules`] — Naming conventions and structure patterns
- [Source: `_bmad-output/planning-artifacts/epics.md#Story 1.1`] — Original story definition with acceptance criteria
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Design System Foundation`] — ShadCN component list and design system choice
- [Source: `_bmad-output/planning-artifacts/prd.md#Additional Requirements`] — Starter template requirement: `npm create convex@latest -t nextjs-shadcn`
- [Web: motion.dev] — Motion library (formerly Framer Motion) rebranding and migration guide
- [Web: ui.shadcn.com/docs/cli] — ShadCN CLI v3.0+ command syntax
- [Web: docs.convex.dev] — Convex Next.js 15+ integration notes

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
